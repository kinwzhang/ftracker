import csv
import io
import json
from calendar import monthrange
from datetime import date, time, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, F, Max, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from .holidays import calculate_scheduled_date, hk_public_holidays, hk_public_holidays_named
from .models import AuditLog, Group, Task, TaskTemplate


def _get_current_month(request):
    month_str = request.session.get("current_month")
    if month_str:
        try:
            parts = month_str.split("-")
            return date(int(parts[0]), int(parts[1]), 1)
        except (ValueError, IndexError):
            pass
    today = timezone.localdate()
    return date(today.year, today.month, 1)


def _gantt_bar_for_task(task, month, pixel_per_day, total_days):
    """Compute percentage left/width for an individual task bar in the Gantt chart."""
    start = task.month
    end = task.scheduled_date if task.scheduled_date >= start else start
    duration_days = (end - start).days + 1
    offset_days = (start - month).days
    if offset_days < 0:
        offset_days = 0
    left_pct = (offset_days + 0.15) / total_days * 100
    width_pct = max((duration_days - 0.3) / total_days * 100, 1.0)
    return {
        "task": task,
        "start_offset": left_pct,
        "duration": width_pct,
    }


def _build_group_block(group, tasks_in_group, today, month, pixel_per_day, total_days):
    """Build the render context for a single group's collapsible block.

    `group` is a `Group` instance, or None for the synthetic ungrouped bucket.
    Returns a dict with: id, group, tasks, gantt_tasks, summary, group_bar.

    The single ``group_bar`` is rendered on the group summary row. Per E5 +
    B7 (Round 5):
      * Color follows the dominant status with the priority
        ``overdue > pending > completed`` (matches task-list row tints).
      * Counts overlay ("x overdue [Heavy Red], y pending/in progress [Heavy
        Blue], z completed [Heavy Green]") live in ``summary`` so the
        template can render the text inside the bar.
      * Span: month start → latest ``scheduled_date`` across **all** tasks
        in the group (finished or not). B7 made this the rule so the
        group's bar length always reflects the longest task, regardless
        of whether that task was completed early. Clamped to the month
        end so the bar never paints past the visible canvas.
      * Empty group → no bar (status still ``pending`` for layout).
    """
    unfinished = sorted(
        [t for t in tasks_in_group if not t.finished],
        key=lambda t: t.scheduled_date,
    )
    finished = sorted(
        [t for t in tasks_in_group if t.finished],
        key=lambda t: t.completion_date or t.scheduled_date,
    )
    ordered_tasks = unfinished + finished

    gantt_tasks = [
        _gantt_bar_for_task(t, month, pixel_per_day, total_days) for t in ordered_tasks
    ]

    total_count = len(tasks_in_group)
    overdue_count = sum(
        1 for t in tasks_in_group if not t.finished and t.scheduled_date < today
    )
    pending_count = sum(
        1 for t in tasks_in_group if not t.finished and t.scheduled_date >= today
    )
    completed_count = sum(1 for t in tasks_in_group if t.finished)

    # Dominant status priority: overdue > pending > completed. Mirrors the
    # status priority used elsewhere (E2.1) and the task-list row tints.
    if total_count == 0:
        status = "pending"
    elif overdue_count > 0:
        status = "overdue"
    elif pending_count > 0:
        status = "pending"
    else:
        status = "completed"

    if total_count == 0:
        group_bar = None
    else:
        # B7: bar length always tracks the longest task in the group, no
        # matter its completion status. scheduled_date is what defines a
        # task's footprint on the Gantt canvas (its bar always starts at
        # day 1 of the month), so we use it instead of completion_date.
        bar_end = max(t.scheduled_date for t in tasks_in_group)
        # Clamp bar_end so we never paint past the end of the displayed month.
        last_day = month.replace(day=monthrange(month.year, month.month)[1])
        if bar_end > last_day:
            bar_end = last_day

        offset_days = (month - month).days  # 0; bar always starts at day 1.
        duration_days = (bar_end - month).days + 1
        left_pct = (offset_days + 0.15) / total_days * 100
        width_pct = max((duration_days - 0.3) / total_days * 100, 1.0)
        group_bar = {
            "start_offset": left_pct,
            "width": width_pct,
            "status": status,
        }

    # Use the group's real id, or 0 for the ungrouped bucket. The id is used
    # by the template to wire up expand/collapse sync between Gantt and table.
    block_id = group.id if group is not None else 0
    return {
        "id": block_id,
        "group": group,
        "tasks": ordered_tasks,
        "gantt_tasks": gantt_tasks,
        "summary": {
            "total": total_count,
            "completed": completed_count,
            "pending": pending_count,
            "overdue": overdue_count,
            "status": status,
        },
        "group_bar": group_bar,
    }


@login_required
def task_list(request):
    month = _get_current_month(request)
    tasks_raw = list(
        Task.objects.filter(month=month).select_related("group")
    )
    templates = TaskTemplate.objects.all()
    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    today = timezone.localdate()
    holidays_set = hk_public_holidays(month.year)

    days_in_month = []
    if month.month == 12:
        next_month = date(month.year + 1, 1, 1)
    else:
        next_month = date(month.year, month.month + 1, 1)
    total_days = (next_month - month).days
    for day in range(1, total_days + 1):
        d = date(month.year, month.month, day)
        days_in_month.append({
            "date": d,
            "weekday": weekdays[d.weekday()],
            "is_holiday": d in holidays_set,
        })

    pixel_per_day = 28
    canvas_width = total_days * pixel_per_day
    canvas_total_width = 200 + canvas_width
    today_pct = None
    if month <= today <= date(month.year, month.month, total_days):
        today_pct = ((today - month).days + 0.5) / total_days * 100

    # Group tasks. Tasks with group_id=None share a synthetic "Ungrouped" block
    # which is rendered last so real groups lead.
    grouped: dict[int, list] = {}
    for t in tasks_raw:
        grouped.setdefault(t.group_id, []).append(t)
    groups_by_id = {g.id: g for g in Group.objects.all()}

    group_blocks = []
    # Real groups first, ordered by (completed→bottom, Group.sort_order, name).
    # A group is "completed" when every task in it is finished.
    for gid, gtasks in sorted(
        grouped.items(),
        key=lambda kv: (
            1 if kv[0] is None else 0,
            0 if any(not t.finished for t in kv[1]) else 1,
            groups_by_id[kv[0]].sort_order if kv[0] is not None else 0,
            groups_by_id[kv[0]].name if kv[0] is not None else "",
        ),
    ):
        if gid is None:
            continue
        group_blocks.append(
            _build_group_block(
                groups_by_id[gid], gtasks, today, month, pixel_per_day, total_days
            )
        )

    # Synthetic ungrouped block (only if there are ungrouped tasks).
    if None in grouped:
        group_blocks.append(
            _build_group_block(None, grouped[None], today, month, pixel_per_day, total_days)
        )

    total = len(tasks_raw)
    completed = sum(1 for t in tasks_raw if t.finished)
    pending = sum(1 for t in tasks_raw if not t.finished)
    overdue = sum(
        1 for t in tasks_raw if not t.finished and t.scheduled_date < today
    )

    # Flat list of every task, in the same order they appear across blocks.
    # Useful for templates that want to iterate all rows regardless of group.
    all_tasks = []
    for block in group_blocks:
        all_tasks.extend(block["tasks"])

    return render(
        request,
        "tracker/task_list.html",
        {
            "tasks": all_tasks,
            "templates": templates,
            "groups": Group.objects.all(),
            "month": month,
            "months": list(range(1, 13)),
            "days_in_month": days_in_month,
            "group_blocks": group_blocks,
            "canvas_width": canvas_width,
            "canvas_total_width": canvas_total_width,
            "total_days": total_days,
            "today": today,
            "today_pct": today_pct,
            "total_count": total,
            "completed_count": completed,
            "pending_count": pending,
            "overdue_count": overdue,
        },
    )


# --- Inline toggle finished (E3, E4) ---

@require_POST
@login_required
def task_toggle_finished(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    old_finished = task.finished
    task.finished = not task.finished
    if task.finished and not task.completion_date:
        now_local = timezone.localtime()
        task.completion_date = now_local.date()
        task.completion_time = now_local.time()
    elif not task.finished:
        task.completion_date = None
        task.completion_time = None
    task.save()
    AuditLog.objects.create(
        task=task,
        task_name=task.task_name,
        action="updated",
        changes={
            "old": {"finished": old_finished, "completion_date": str(task.completion_date) if task.finished else None},
            "new": {"finished": task.finished, "completion_date": str(task.completion_date) if task.finished else None},
        },
    )
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        # B9: client-side update path; return the formatted completion string
        # so the row's "Completed At" cell can be updated without reloading.
        return JsonResponse({
            "ok": True,
            "finished": task.finished,
            "completion_display": _format_completion(task),
        })
    return redirect("/")


def _format_completion(task):
    """Format 'YYYY-MM-DD HH:MM' for tasks with a time, else 'YYYY-MM-DD'.
    Returns '' for tasks that aren't finished (or have no completion date)."""
    if not task.completion_date:
        return ""
    if task.completion_time:
        return f"{task.completion_date.isoformat()} {task.completion_time.strftime('%H:%M')}"
    return task.completion_date.isoformat()


def _parse_completion(value):
    """Parse the value from a <input type=date> or <input type=datetime-local>
    form field. Accepts:
      * '' / None → (None, None)
      * 'YYYY-MM-DD' → (date, None)
      * 'YYYY-MM-DDTHH:MM' or 'YYYY-MM-DDTHH:MM:SS' → (date, time)
    """
    value = (value or "").strip()
    if not value:
        return None, None
    if "T" in value:
        date_part, time_part = value.split("T", 1)
        return date.fromisoformat(date_part), time.fromisoformat(time_part)
    return date.fromisoformat(value), None


# --- Inline save comment (E4) ---

@require_POST
@login_required
def task_save_comment(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    old_comments = task.comments
    task.comments = request.POST.get("comments", "")
    task.save()
    AuditLog.objects.create(
        task=task,
        task_name=task.task_name,
        action="updated",
        changes={"old": {"comments": old_comments}, "new": {"comments": task.comments}},
    )
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "comments": task.comments})
    return redirect("/")


# --- Regular task add/edit/delete ---

@login_required
def task_add(request):
    if request.method == "POST":
        task_name = request.POST.get("task_name")
        assigned_to = request.POST.get("assigned_to")
        sla_days = int(request.POST.get("sla_days", 0))
        sla_type = request.POST.get("sla_type", "Working Day")
        comments = request.POST.get("comments", "")
        month = _get_current_month(request)
        scheduled_date = calculate_scheduled_date(month, sla_days, sla_type)
        group_id = _parse_group_id(request.POST.get("group"))

        task = Task.objects.create(
            task_name=task_name,
            assigned_to=assigned_to,
            sla_days=sla_days,
            sla_type=sla_type,
            scheduled_date=scheduled_date,
            month=month,
            comments=comments,
            group_id=group_id,
        )
        AuditLog.objects.create(
            task=task,
            task_name=task.task_name,
            action="created",
            changes={"task_name": task_name, "assigned_to": assigned_to, "sla_days": sla_days, "sla_type": sla_type},
        )
        messages.success(request, f"Task '{task_name}' created.")
        return redirect("/")

    templates = TaskTemplate.objects.all()
    return render(request, "tracker/task_form.html", {
        "templates": templates,
        "templates_json": [{"id": t.id, "task_name": t.task_name, "assigned_to": t.assigned_to, "sla_days": t.sla_days, "sla_type": t.sla_type} for t in templates],
        "month": _get_current_month(request),
        "groups": Group.objects.all(),
    })


@login_required
def task_edit(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    if request.method == "POST":
        old_values = {
            "task_name": task.task_name,
            "assigned_to": task.assigned_to,
            "sla_days": task.sla_days,
            "sla_type": task.sla_type,
            "finished": task.finished,
            "completion_date": str(task.completion_date) if task.completion_date else None,
            "completion_time": str(task.completion_time) if task.completion_time else None,
            "comments": task.comments,
        }
        task.task_name = request.POST.get("task_name", task.task_name)
        task.assigned_to = request.POST.get("assigned_to", task.assigned_to)
        task.sla_days = int(request.POST.get("sla_days", task.sla_days))
        task.sla_type = request.POST.get("sla_type", task.sla_type)
        finished = request.POST.get("finished") == "on"
        task.finished = finished
        task.completion_date, task.completion_time = _parse_completion(
            request.POST.get("completion_date", "")
        )
        task.comments = request.POST.get("comments", "")
        task.group_id = _parse_group_id(request.POST.get("group"))
        task.scheduled_date = calculate_scheduled_date(task.month, task.sla_days, task.sla_type)
        task.save()

        new_values = {
            "task_name": task.task_name,
            "assigned_to": task.assigned_to,
            "sla_days": task.sla_days,
            "sla_type": task.sla_type,
            "finished": task.finished,
            "completion_date": str(task.completion_date) if task.completion_date else None,
            "completion_time": str(task.completion_time) if task.completion_time else None,
            "comments": task.comments,
            "group_id": task.group_id,
        }
        AuditLog.objects.create(
            task=task,
            task_name=task.task_name,
            action="updated",
            changes={"old": old_values, "new": new_values},
        )
        messages.success(request, f"Task '{task.task_name}' updated.")
        return redirect("/")

    return render(request, "tracker/task_form.html", {
        "task": task,
        "month": _get_current_month(request),
        "groups": Group.objects.all(),
    })


def _apply_task_updates(task, payload):
    """Apply an update payload to ``task`` and return the (old, new) value dicts.

    Used by both ``task_inline_save`` (per-row AJAX) and ``task_bulk_save``
    (multi-row Edit-All + Save All) so validation stays in one place.
    ``payload`` is a dict-like that supports ``.get(key, default)``. ``group``
    is optional — when absent, the existing group_id is preserved.
    """
    old_values = {
        "task_name": task.task_name,
        "assigned_to": task.assigned_to,
        "sla_days": task.sla_days,
        "sla_type": task.sla_type,
        "completion_date": str(task.completion_date) if task.completion_date else None,
        "completion_time": str(task.completion_time) if task.completion_time else None,
        "comments": task.comments,
        "group_id": task.group_id,
    }
    task.task_name = payload.get("task_name", task.task_name)
    task.assigned_to = payload.get("assigned_to", task.assigned_to)
    task.sla_days = int(payload.get("sla_days", task.sla_days))
    task.sla_type = payload.get("sla_type", task.sla_type)
    task.completion_date, task.completion_time = _parse_completion(
        payload.get("completion_date", "") or ""
    )
    task.comments = payload.get("comments", task.comments)
    if "group" in payload:
        task.group_id = _parse_group_id(payload.get("group"))
    task.scheduled_date = calculate_scheduled_date(
        task.month, task.sla_days, task.sla_type
    )
    task.save()
    new_values = {
        "task_name": task.task_name,
        "assigned_to": task.assigned_to,
        "sla_days": task.sla_days,
        "sla_type": task.sla_type,
        "completion_date": str(task.completion_date) if task.completion_date else None,
        "completion_time": str(task.completion_time) if task.completion_time else None,
        "comments": task.comments,
        "group_id": task.group_id,
    }
    return old_values, new_values


@require_POST
@login_required
def task_inline_save(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    old_values, new_values = _apply_task_updates(task, request.POST)
    AuditLog.objects.create(
        task=task,
        task_name=task.task_name,
        action="updated",
        changes={"old": old_values, "new": new_values},
    )
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "ok": True,
            "scheduled_date": task.scheduled_date.isoformat(),
            "sla_type_short": "WD" if task.sla_type == "Working Day" else "CD",
        })
    return redirect("/")


def _bulk_payload_from_request(request):
    """Parse a bulk-save POST body into a list of {id, fields} dicts.

    Accepts either ``Content-Type: application/json`` (``{"updates": [...]}``)
    or normal form-encoded ``updates[<idx>][id]=…``-style data mirroring what
    the JS will send. Skips entries without an ``id``.
    """
    updates = []
    if request.content_type and request.content_type.startswith("application/json"):
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return []
        raw_list = payload.get("updates") if isinstance(payload, dict) else payload
        if not isinstance(raw_list, list):
            return []
        for entry in raw_list:
            if not isinstance(entry, dict):
                continue
            if "id" not in entry:
                continue
            try:
                entry_id = int(entry["id"])
            except (TypeError, ValueError):
                continue
            updates.append((entry_id, entry))
        return updates
    # Form-encoded: parse updates[<idx>][field]=…
    raw = request.POST
    by_index: dict[int, dict] = {}
    for key in raw.keys():
        if not key.startswith("updates[") or "][" not in key:
            continue
        try:
            head, field = key.split("][", 1)
            index = int(head[len("updates["):])
        except ValueError:
            continue
        field = field.rstrip("]")
        by_index.setdefault(index, {})[field] = raw.get(key)
    for index in sorted(by_index):
        entry = by_index[index]
        if "id" not in entry:
            continue
        try:
            entry_id = int(entry["id"])
        except (TypeError, ValueError):
            continue
        updates.append((entry_id, entry))
    return updates


@require_POST
@login_required
def task_bulk_save(request):
    """Apply a batch of task updates atomically.

    Body (JSON): ``{"updates": [{"id": 1, "task_name": "…", ...}, ...]}``.
    All rows commit in one transaction; if any single update raises ValueError
    (bad ``sla_days``, bad date), nothing is written and the error is returned.
    """
    updates = _bulk_payload_from_request(request)
    if not updates:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "no_updates"}, status=400)
        messages.error(request, "No task updates were received.")
        return redirect("/")

    saved_ids: list[int] = []
    try:
        with transaction.atomic():
            for entry_id, payload in updates:
                task = Task.objects.filter(id=entry_id).first()
                if task is None:
                    raise ValueError(f"Task {entry_id} not found")
                old_values, new_values = _apply_task_updates(task, payload)
                AuditLog.objects.create(
                    task=task,
                    task_name=task.task_name,
                    action="updated",
                    changes={"old": old_values, "new": new_values},
                )
                saved_ids.append(task.id)
    except (ValueError, TypeError) as exc:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": str(exc)}, status=400)
        messages.error(request, f"Bulk save failed: {exc}")
        return redirect("/")

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "saved": saved_ids})
    messages.success(request, f"Updated {len(saved_ids)} task(s).")
    return redirect("/")


@require_POST
@login_required
def task_delete(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    AuditLog.objects.create(
        task=None,
        task_name=task.task_name,
        action="deleted",
        changes={"task_name": task.task_name, "month": str(task.month)},
    )
    task.delete()
    messages.success(request, "Task deleted.")
    return redirect("/")


# --- Dashboard (E1 stats are also on main page now) ---

@login_required
def dashboard(request):
    month = _get_current_month(request)
    tasks = Task.objects.filter(month=month)
    today = timezone.localdate()

    total = tasks.count()
    completed = tasks.filter(finished=True).count()
    pending = tasks.filter(finished=False).count()
    overdue = tasks.filter(finished=False, scheduled_date__lt=today).count()
    completion_rate = round(completed / total * 100, 1) if total > 0 else 0

    audit_logs = AuditLog.objects.all()[:50]

    months_data = []
    for i in range(5, -1, -1):
        m = date(month.year, month.month, 1) - timedelta(days=1)
        m = date(m.year, m.month, 1)
        for _ in range(i):
            m = date(m.year, m.month, 1) - timedelta(days=1)
            m = date(m.year, m.month, 1)
        mtasks = Task.objects.filter(month=m)
        mtotal = mtasks.count()
        mcompleted = mtasks.filter(finished=True).count()
        months_data.append({
            "label": m.strftime("%b %Y"),
            "total": mtotal,
            "completed": mcompleted,
            "rate": round(mcompleted / mtotal * 100, 1) if mtotal > 0 else 0,
        })

    return render(request, "tracker/dashboard.html", {
        "total": total,
        "completed": completed,
        "pending": pending,
        "overdue": overdue,
        "completion_rate": completion_rate,
        "month": month,
        "months": list(range(1, 13)),
        "audit_logs": audit_logs,
        "months_data": months_data,
    })


# --- Generate next month ---

@require_POST
@login_required
def generate_next_month(request):
    current_month = _get_current_month(request)
    if current_month.month == 12:
        next_month = date(current_month.year + 1, 1, 1)
    else:
        next_month = date(current_month.year, current_month.month + 1, 1)

    existing = Task.objects.filter(month=next_month).count()
    if existing > 0:
        messages.warning(request, f"Tasks already exist for {next_month.strftime('%B %Y')}.")
        return redirect("/")

    templates = TaskTemplate.objects.all()
    if templates.exists():
        for tmpl in templates:
            scheduled = calculate_scheduled_date(next_month, tmpl.sla_days, tmpl.sla_type)
            Task.objects.create(
                task_name=tmpl.task_name,
                assigned_to=tmpl.assigned_to,
                sla_days=tmpl.sla_days,
                sla_type=tmpl.sla_type,
                scheduled_date=scheduled,
                month=next_month,
                group_id=tmpl.group_id,
            )
    else:
        last_month_tasks = Task.objects.filter(month=current_month)
        for t in last_month_tasks:
            scheduled = calculate_scheduled_date(next_month, t.sla_days, t.sla_type)
            Task.objects.create(
                task_name=t.task_name,
                assigned_to=t.assigned_to,
                sla_days=t.sla_days,
                sla_type=t.sla_type,
                scheduled_date=scheduled,
                month=next_month,
                group_id=t.group_id,
            )

    request.session["current_month"] = next_month.isoformat()
    messages.success(request, f"Tasks generated for {next_month.strftime('%B %Y')}.")
    return redirect("/")


@require_POST
@login_required
def set_month(request):
    year = int(request.POST.get("year"))
    month_num = int(request.POST.get("month"))
    request.session["current_month"] = date(year, month_num, 1).isoformat()
    # Honor a `next` form field if it's a safe same-origin path; default to task list.
    next_url = request.POST.get("next", "").strip()
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect("/")


# --- Export ---

@login_required
def export_csv(request):
    month = _get_current_month(request)
    tasks = Task.objects.filter(month=month)
    import csv

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="tasks_{month.year}_{month.month:02d}.csv"'
    writer = csv.writer(response)
    writer.writerow(["Task Name", "Assigned To", "SLA Days", "SLA Type", "Scheduled Date", "Finished", "Completion Date", "Comments"])
    for t in tasks:
        writer.writerow([t.task_name, t.assigned_to, t.sla_days, t.sla_type, t.scheduled_date, t.finished, t.completion_date or "", t.comments])
    return response


@login_required
def export_html(request):
    month = _get_current_month(request)
    tasks = Task.objects.filter(month=month)
    audit_logs = AuditLog.objects.all()

    html = render_to_string("tracker/export_report.html", {
        "tasks": tasks,
        "month": month,
        "audit_logs": audit_logs,
        "generated_at": timezone.now(),
    })
    response = HttpResponse(html, content_type="text/html")
    response["Content-Disposition"] = f'attachment; filename="report_{month.year}_{month.month:02d}.html"'
    return response


# --- E2: Task Template management ---

@login_required
def template_list(request):
    templates = TaskTemplate.objects.select_related("group").all()
    groups = Group.objects.all()
    return render(
        request,
        "tracker/template_list.html",
        {"templates": templates, "groups": groups},
    )


def _parse_int_field(value, default=None):
    """Return int(value) or default if value is missing/blank/non-numeric."""
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _assign_template_sort_order(requested_order, exclude_id=None):
    """Pick a sort_order for a new/edited template, shifting existing rows if needed.

    Rules:
      * None / blank / <= 0  -> append at the end (max(existing)+1, or 1).
      * Otherwise, if some other template already has that order, every template
        with sort_order >= requested_order is shifted up by 1, then the new row
        lands at requested_order.
      * If `exclude_id` is given, that row is excluded from the collision check
        (so editing a row to its own current order is a no-op).

    Returns ``(actual_order, shifted_count)`` and runs inside an atomic block.
    """
    with transaction.atomic():
        if requested_order is None or requested_order <= 0:
            current_max = (
                TaskTemplate.objects.aggregate(m=Max("sort_order"))["m"] or 0
            )
            requested_order = current_max + 1 if current_max >= 1 else 1

        collision = TaskTemplate.objects.filter(sort_order=requested_order)
        if exclude_id is not None:
            collision = collision.exclude(id=exclude_id)
        if collision.exists():
            shift_qs = TaskTemplate.objects.filter(sort_order__gte=requested_order)
            if exclude_id is not None:
                shift_qs = shift_qs.exclude(id=exclude_id)
            shifted = shift_qs.update(sort_order=F("sort_order") + 1)
            return requested_order, shifted
        return requested_order, 0


@login_required
def template_add(request):
    if request.method == "POST":
        requested = _parse_int_field(request.POST.get("sort_order"))
        actual, shifted = _assign_template_sort_order(requested)
        TaskTemplate.objects.create(
            task_name=request.POST["task_name"],
            assigned_to=request.POST["assigned_to"],
            sla_days=int(request.POST["sla_days"]),
            sla_type=request.POST["sla_type"],
            sort_order=actual,
            group_id=_parse_group_id(request.POST.get("group")),
        )
        if shifted:
            messages.info(
                request,
                f"Reordered {shifted} template(s) to make room for order {actual}.",
            )
        messages.success(request, "Template added.")
        return redirect("/templates")
    return render(
        request,
        "tracker/template_form.html",
        {"groups": Group.objects.all()},
    )


@login_required
def template_edit(request, template_id):
    tmpl = get_object_or_404(TaskTemplate, id=template_id)
    if request.method == "POST":
        tmpl.task_name = request.POST["task_name"]
        tmpl.assigned_to = request.POST["assigned_to"]
        tmpl.sla_days = int(request.POST["sla_days"])
        tmpl.sla_type = request.POST["sla_type"]
        requested = _parse_int_field(request.POST.get("sort_order"))
        actual, shifted = _assign_template_sort_order(requested, exclude_id=tmpl.id)
        tmpl.sort_order = actual
        tmpl.group_id = _parse_group_id(request.POST.get("group"))
        tmpl.save()
        if shifted:
            messages.info(
                request,
                f"Reordered {shifted} template(s) to make room for order {actual}.",
            )
        messages.success(request, "Template updated.")
        return redirect("/templates")
    return render(
        request,
        "tracker/template_form.html",
        {"tmpl": tmpl, "groups": Group.objects.all()},
    )


def _apply_template_updates(tmpl, payload):
    """Apply an update payload to ``tmpl``. Returns ``(shifted, old, new)``.

    ``payload`` is a dict-like that supports ``.get(key, default)``. ``group``
    is optional — when absent, the existing group_id is preserved.
    ``sort_order`` defaults to the current value so un-touched rows stay put.
    """
    old_values = {
        "task_name": tmpl.task_name,
        "assigned_to": tmpl.assigned_to,
        "sla_days": tmpl.sla_days,
        "sla_type": tmpl.sla_type,
        "sort_order": tmpl.sort_order,
        "group_id": tmpl.group_id,
    }
    tmpl.task_name = payload.get("task_name", tmpl.task_name)
    tmpl.assigned_to = payload.get("assigned_to", tmpl.assigned_to)
    tmpl.sla_days = int(payload.get("sla_days", tmpl.sla_days))
    tmpl.sla_type = payload.get("sla_type", tmpl.sla_type)
    requested = _parse_int_field(
        payload.get("sort_order"), default=tmpl.sort_order
    )
    actual, shifted = _assign_template_sort_order(requested, exclude_id=tmpl.id)
    tmpl.sort_order = actual
    if "group" in payload:
        tmpl.group_id = _parse_group_id(payload.get("group"))
    tmpl.save()
    new_values = {
        "task_name": tmpl.task_name,
        "assigned_to": tmpl.assigned_to,
        "sla_days": tmpl.sla_days,
        "sla_type": tmpl.sla_type,
        "sort_order": tmpl.sort_order,
        "group_id": tmpl.group_id,
    }
    return shifted, old_values, new_values


@require_POST
@login_required
def template_inline_save(request, template_id):
    tmpl = get_object_or_404(TaskTemplate, id=template_id)
    shifted, old_values, new_values = _apply_template_updates(tmpl, request.POST)
    if shifted and request.headers.get("X-Requested-With") != "XMLHttpRequest":
        messages.info(
            request,
            f"Reordered {shifted} template(s) to make room for order {new_values['sort_order']}.",
        )
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse(
            {"ok": True, "sort_order": tmpl.sort_order, "group_id": tmpl.group_id}
        )
    return redirect("/templates")


@require_POST
@login_required
def template_bulk_save(request):
    """Apply a batch of template updates atomically.

    Same shape as ``task_bulk_save``. Sort-order collisions against OTHER
    templates shift them via the existing ``_assign_template_sort_order``
    helper. ``group`` is optional in each row.

    Note: templates don't write to ``AuditLog`` — its ``task`` FK points at
    ``Task``, not ``TaskTemplate`` (matches the existing
    ``template_inline_save`` behaviour).
    """
    updates = _bulk_payload_from_request(request)
    if not updates:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "no_updates"}, status=400)
        messages.error(request, "No template updates were received.")
        return redirect("/templates")

    saved_ids: list[int] = []
    total_shifted = 0
    try:
        with transaction.atomic():
            for entry_id, payload in updates:
                tmpl = TaskTemplate.objects.filter(id=entry_id).first()
                if tmpl is None:
                    raise ValueError(f"Template {entry_id} not found")
                shifted, _, _ = _apply_template_updates(tmpl, payload)
                saved_ids.append(tmpl.id)
                total_shifted += shifted
    except (ValueError, TypeError) as exc:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": str(exc)}, status=400)
        messages.error(request, f"Bulk save failed: {exc}")
        return redirect("/templates")

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "saved": saved_ids, "shifted": total_shifted})
    messages.success(request, f"Updated {len(saved_ids)} template(s).")
    if total_shifted:
        messages.info(
            request,
            f"Reordered {total_shifted} template(s) to accommodate unique sort orders.",
        )
    return redirect("/templates")


@require_POST
@login_required
def template_delete(request, template_id):
    tmpl = get_object_or_404(TaskTemplate, id=template_id)
    tmpl.delete()
    messages.success(request, "Template deleted.")
    return redirect("/templates")


# --- Group management ---

def _parse_group_id(value):
    """Return int(value), or None if blank/missing/non-numeric."""
    if value in (None, "", "null", "None"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@require_POST
@login_required
def group_add(request):
    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "Group name is required.")
        return redirect("/templates")
    if Group.objects.filter(name__iexact=name).exists():
        messages.error(request, f"A group named '{name}' already exists.")
        return redirect("/templates")
    requested = _parse_int_field(request.POST.get("sort_order"))
    actual, shifted = _assign_group_sort_order(requested)
    group = Group.objects.create(name=name, sort_order=actual)
    if shifted:
        messages.info(
            request,
            f"Reordered {shifted} group(s) to make room for order {actual}.",
        )
    messages.success(request, f"Group '{group.name}' added.")
    return redirect("/templates")


@require_POST
@login_required
def group_edit(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "Group name is required.")
        return redirect("/templates")
    if Group.objects.filter(name__iexact=name).exclude(id=group.id).exists():
        messages.error(request, f"A group named '{name}' already exists.")
        return redirect("/templates")
    requested = _parse_int_field(request.POST.get("sort_order"), default=group.sort_order)
    actual, shifted = _assign_group_sort_order(requested, exclude_id=group.id)
    group.name = name
    group.sort_order = actual
    group.save()
    if shifted:
        messages.info(
            request,
            f"Reordered {shifted} group(s) to make room for order {actual}.",
        )
    messages.success(request, f"Group '{group.name}' updated.")
    return redirect("/templates")


@require_POST
@login_required
def group_inline_save(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    name = (request.POST.get("name") or "").strip()
    if name:
        if Group.objects.filter(name__iexact=name).exclude(id=group.id).exists():
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"ok": False, "error": "name_taken"}, status=400)
            messages.error(request, f"A group named '{name}' already exists.")
            return redirect("/templates")
        group.name = name
    requested = _parse_int_field(request.POST.get("sort_order"), default=group.sort_order)
    actual, shifted = _assign_group_sort_order(requested, exclude_id=group.id)
    group.sort_order = actual
    group.save()
    if shifted and request.headers.get("X-Requested-With") != "XMLHttpRequest":
        messages.info(
            request,
            f"Reordered {shifted} group(s) to make room for order {actual}.",
        )
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "name": group.name, "sort_order": actual})
    return redirect("/templates")


@require_POST
@login_required
def group_delete(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    template_count = group.templates.count()
    task_count = group.tasks.count()
    # on_delete=SET_NULL handles the FK unlink on delete, but we report counts
    # up-front so the user understands the impact.
    name = group.name
    group.delete()
    summary = f"Group '{name}' deleted."
    if template_count or task_count:
        summary += (
            f" Unlinked {template_count} template(s) and {task_count} task(s)."
        )
    messages.success(request, summary)
    return redirect("/templates")


def _assign_group_sort_order(requested_order, exclude_id=None):
    """Same shifting logic as templates, scoped to the Group model."""
    with transaction.atomic():
        if requested_order is None or requested_order <= 0:
            current_max = Group.objects.aggregate(m=Max("sort_order"))["m"] or 0
            requested_order = current_max + 1 if current_max >= 1 else 1
        collision = Group.objects.filter(sort_order=requested_order)
        if exclude_id is not None:
            collision = collision.exclude(id=exclude_id)
        if collision.exists():
            shift_qs = Group.objects.filter(sort_order__gte=requested_order)
            if exclude_id is not None:
                shift_qs = shift_qs.exclude(id=exclude_id)
            shifted = shift_qs.update(sort_order=F("sort_order") + 1)
            return requested_order, shifted
        return requested_order, 0


# --- Bulk upload (CSV file or pasted text) ---

# Column-name aliases. Keys are normalised (lower, no whitespace/underscores).
_BULK_HEADER_ALIASES = {
    "taskname": "task_name",
    "name": "task_name",
    "assignedto": "assigned_to",
    "assignee": "assigned_to",
    "sladays": "sla_days",
    "sla": "sla_days",
    "slatype": "sla_type",
    "type": "sla_type",
    "sortorder": "sort_order",
    "order": "sort_order",
    "group": "group",
    "groupname": "group",
    "group_name": "group",
}
_BULK_REQUIRED = {"task_name", "assigned_to", "sla_days", "sla_type"}
_BULK_SLA_TYPES = {choice for choice, _ in TaskTemplate.SLAType.choices}


def _normalise_header(value: str) -> str:
    return value.strip().lower().replace(" ", "").replace("_", "")


def _resolve_csv_source(request) -> tuple[str | None, str]:
    """Return (csv_text, source_label) or (None, '') if nothing was provided."""
    upload = request.FILES.get("csv_file")
    if upload:
        # Decode bytes as utf-8, replacing errors so a stray BOM never breaks parsing.
        raw = upload.read().decode("utf-8-sig", errors="replace")
        return raw, upload.name
    pasted = (request.POST.get("csv_text") or "").strip()
    if pasted:
        return pasted, "pasted text"
    return None, ""


def _parse_bulk_csv(csv_text: str) -> tuple[list[str], list[dict], list[str]]:
    """Parse CSV text into (header_fields, rows, warnings).

    The first non-empty line is treated as a header. Header names are matched
    against aliases (case/space/underscore-insensitive). Missing required
    columns, blank required cells, and invalid SLA types generate warnings
    rather than aborting — callers decide how strict to be.
    """
    reader = csv.reader(io.StringIO(csv_text))
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        return [], [], ["CSV is empty."]

    raw_header = [_normalise_header(c) for c in rows[0]]
    mapping: dict[int, str] = {}
    for idx, key in enumerate(raw_header):
        if key in _BULK_HEADER_ALIASES:
            mapping[idx] = _BULK_HEADER_ALIASES[key]
    # If the first row doesn't look like a header at all, assume a positional
    # layout: task_name, assigned_to, sla_days, sla_type [, sort_order].
    if not mapping:
        positional = ["task_name", "assigned_to", "sla_days", "sla_type", "sort_order", "group"]
        for idx, field in enumerate(positional):
            if idx < len(rows[0]):
                mapping[idx] = field
        data_rows = rows
    else:
        data_rows = rows[1:]

    if not _BULK_REQUIRED.issubset(set(mapping.values())):
        missing = _BULK_REQUIRED - set(mapping.values())
        return list(mapping.values()), [], [
            f"CSV header missing required columns: {', '.join(sorted(missing))}."
        ]

    parsed: list[dict] = []
    warnings: list[str] = []
    for line_no, row in enumerate(data_rows, start=2):
        record: dict = {}
        for idx, field in mapping.items():
            if idx < len(row):
                record[field] = row[idx].strip()
        missing_fields = _BULK_REQUIRED - {k for k, v in record.items() if v}
        if missing_fields:
            warnings.append(f"Row {line_no}: skipped (missing {', '.join(sorted(missing_fields))}).")
            continue
        if record["sla_type"] not in _BULK_SLA_TYPES:
            warnings.append(
                f"Row {line_no}: invalid SLA Type '{record['sla_type']}', "
                f"expected one of {sorted(_BULK_SLA_TYPES)} — skipped."
            )
            continue
        try:
            record["sla_days"] = int(record["sla_days"])
        except ValueError:
            warnings.append(f"Row {line_no}: SLA Days must be an integer, got '{record['sla_days']}' — skipped.")
            continue
        sort_order_raw = record.get("sort_order", "")
        if sort_order_raw == "":
            record["sort_order"] = 0
        else:
            try:
                record["sort_order"] = int(sort_order_raw)
            except ValueError:
                warnings.append(
                    f"Row {line_no}: Order must be an integer, got '{sort_order_raw}' — defaulted to 0."
                )
                record["sort_order"] = 0
        parsed.append(record)
    return list(mapping.values()), parsed, warnings


@require_POST
@login_required
def template_bulk_upload(request):
    csv_text, source = _resolve_csv_source(request)
    if not csv_text:
        messages.error(request, "Provide a CSV file or paste CSV text before uploading.")
        return redirect("/templates")

    _, records, warnings = _parse_bulk_csv(csv_text)

    created = 0
    total_shifted = 0
    auto_created_groups: list[str] = []
    with transaction.atomic():
        # Auto-create any groups referenced by the CSV that don't already
        # exist. Names are matched case-insensitively (matching the lookup
        # behaviour below); create_missing skips names already present.
        existing_group_names = {g.name.lower() for g in Group.objects.all()}
        csv_group_names: list[str] = []
        seen_in_csv: set[str] = set()
        for record in records:
            raw = (record.get("group") or "").strip()
            if not raw:
                continue
            key = raw.lower()
            if key in seen_in_csv:
                continue
            seen_in_csv.add(key)
            if key not in existing_group_names:
                csv_group_names.append(raw)
        for name in csv_group_names:
            actual_sort, _ = _assign_group_sort_order(None)
            Group.objects.create(name=name, sort_order=actual_sort)
            auto_created_groups.append(name)
            existing_group_names.add(name.lower())

        # Refresh the lookup now that any missing groups exist so the row
        # loop below resolves all group references correctly.
        groups_by_name = {g.name.lower(): g.id for g in Group.objects.all()}

        for record in records:
            actual, shifted = _assign_template_sort_order(record.get("sort_order"))
            total_shifted += shifted
            group_name = (record.get("group") or "").strip().lower()
            group_id = groups_by_name.get(group_name) if group_name else None
            TaskTemplate.objects.create(
                task_name=record["task_name"],
                assigned_to=record["assigned_to"],
                sla_days=record["sla_days"],
                sla_type=record["sla_type"],
                sort_order=actual,
                group_id=group_id,
            )
            created += 1

    if created:
        messages.success(
            request,
            f"Bulk upload from {source}: created {created} template(s)."
            + (f" {len(warnings)} warning(s)." if warnings else ""),
        )
        if auto_created_groups:
            messages.info(
                request,
                "Auto-created group(s): "
                + ", ".join(auto_created_groups)
                + ".",
            )
        if total_shifted:
            messages.info(
                request,
                f"Reordered {total_shifted} template(s) to accommodate unique sort orders.",
            )
    else:
        messages.error(
            request,
            f"Bulk upload from {source}: no templates created."
            + (f" {len(warnings)} warning(s)." if warnings else ""),
        )
    for warning in warnings[:10]:
        messages.warning(request, warning)
    if len(warnings) > 10:
        messages.warning(request, f"... and {len(warnings) - 10} more warning(s).")
    return redirect("/templates")


# --- E6: Public holiday list ---

@login_required
def holiday_list(request):
    year = int(request.GET.get("year", timezone.localdate().year))
    month_num = int(request.GET.get("month", timezone.localdate().month))
    all_named = hk_public_holidays_named(year)
    all_named.sort(key=lambda h: h.date)
    month_holidays = [h for h in all_named if h.date.month == month_num] if month_num != 0 else []
    return render(request, "tracker/holiday_list.html", {
        "year": year,
        "month": month_num,
        "months": list(range(1, 13)),
        "years": list(range(2025, 2031)),
        "month_holidays": month_holidays,
        "all_year": all_named,
    })


# --- React SPA catch-all view ---

import os
from django.conf import settings


def react_index(request, path=""):
    """Serve the React SPA index.html for all non-API, non-admin routes."""
    index_path = os.path.join(settings.BASE_DIR, "frontend", "dist", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            return HttpResponse(f.read(), content_type="text/html")
    return HttpResponse(
        "<h1>React app not built</h1><p>Run <code>npm run build</code> in the frontend/ directory.</p>",
        content_type="text/html",
        status=500,
    )
