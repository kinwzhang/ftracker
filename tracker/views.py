import csv
import io
import json
from calendar import monthrange
from datetime import date, datetime, time, timedelta

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, F, Max, Q
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from .holidays import calculate_scheduled_date, hk_public_holidays, hk_public_holidays_named
from .models import AuditLog, Group, System, SystemRerun, Task, TaskTemplate, task_status


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


def _gantt_bar_for_task(task, month, pixel_per_day, total_days, today=None):
    """Compute percentage left/width for an individual task bar in the Gantt chart.
    Returns None for tasks without a scheduled_date (no SLA).
    """
    if task.scheduled_date is None:
        return None
    start = task.month
    end = task.scheduled_date if task.scheduled_date >= start else start
    duration_days = (end - start).days + 1
    offset_days = (start - month).days
    if offset_days < 0:
        offset_days = 0
    left_pct = (offset_days + 0.15) / total_days * 100
    width_pct = max((duration_days - 0.3) / total_days * 100, 1.0)
    today = today or date.today()
    status = task_status(task, today)
    return {
        "task": task,
        "start_offset": left_pct,
        "duration": width_pct,
        "status": status,
    }


def _gantt_rerun_bar(rerun, month, total_days, pixel_per_day):
    """Compute percentage left/width for a system-rerun interval bar.

    Returns dict with left_pct, width_pct, and a label-friendly status.
    Same-day reruns produce a visible 1-day marker. Active reruns
    (no completed_at) end at today, clamped to the visible month.
    """
    from datetime import timezone as dt_timezone
    trigger_local = timezone.localtime(rerun.triggered_at)
    trigger_date = trigger_local.date()

    if rerun.completed_at:
        completed_local = timezone.localtime(rerun.completed_at)
        end_date = completed_local.date()
    else:
        end_date = timezone.localdate()

    month_start = month
    if month.month == 12:
        month_end = date(month.year + 1, 1, 1)
    else:
        month_end = date(month.year, month.month + 1, 1)

    clip_start = trigger_date if trigger_date >= month_start else month_start
    clip_end = end_date if end_date < month_end else month_end - timedelta(days=1)

    if clip_start > clip_end or clip_start >= month_end:
        return None

    offset_days = (clip_start - month).days
    duration_days = (clip_end - clip_start).days + 1

    left_pct = (offset_days + 0.15) / total_days * 100
    width_pct = max((duration_days - 0.3) / total_days * 100, 1.0)

    is_active = rerun.completed_at is None
    end = rerun.completed_at or timezone.now()
    dur_seconds = (end - rerun.triggered_at).total_seconds()
    return {
        "rerun": rerun,
        "left_pct": left_pct,
        "width_pct": width_pct,
        "is_active": is_active,
        "trigger_date": trigger_date,
        "end_date": end_date,
        "system_name": rerun.system.name,
        "task_name": rerun.task.task_name,
        "duration_str": _format_duration(dur_seconds),
    }


def _format_duration(seconds):
    """Format a duration in seconds as compact 'Xd Yh Zm'."""
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


def _allocate_lanes(bars):
    """Assign a non-overlapping lane to each bar using a simple greedy algorithm.
    Each bar has left_pct/width_pct; returns a list with 'lane' added.
    """
    if not bars:
        return bars
    intervals = []
    for i, bar in enumerate(bars):
        left = bar["left_pct"]
        right = bar["left_pct"] + bar["width_pct"]
        intervals.append((left, right, i))
    intervals.sort()
    lanes = []
    result = list(bars)
    for left, right, idx in intervals:
        placed = False
        for lane_idx, lane_end in enumerate(lanes):
            if left >= lane_end:
                lanes[lane_idx] = right
                result[idx] = dict(bars[idx], lane=lane_idx, top_px=lane_idx * 24 + 1)
                placed = True
                break
        if not placed:
            lanes.append(right)
            lane_idx = len(lanes) - 1
            result[idx] = dict(bars[idx], lane=lane_idx, top_px=lane_idx * 24 + 1)
    return result


def _build_rerun_gantt(reruns, month, total_days, pixel_per_day):
    """Build the rerun Gantt section.

    Returns a dict:
      collapsed_bars: list of all rerun bars with lane assignment (one track)
      expanded_systems: list of {system_name, bars} per system with lanes
      total: count of reruns
    """
    bars_by_system: dict[str, list] = {}
    all_bars = []
    for rerun in reruns:
        bar = _gantt_rerun_bar(rerun, month, total_days, pixel_per_day)
        if bar is None:
            continue
        all_bars.append(bar)
        bars_by_system.setdefault(rerun.system.name, []).append(bar)

    collapsed = _allocate_lanes(all_bars)
    expanded = [
        {
            "system_name": name,
            "bars": _allocate_lanes(bars),
        }
        for name, bars in sorted(bars_by_system.items())
    ]
    for item in expanded:
        item["track_height"] = max(24, 24 * (max((b["lane"] for b in item["bars"]), default=0) + 1))

    return {
        "collapsed_bars": collapsed,
        "collapsed_track_height": max(24, 24 * (max((b["lane"] for b in collapsed), default=0) + 1)),
        "expanded_systems": expanded,
        "total": len(reruns),
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
        key=lambda t: (t.scheduled_date is None, t.scheduled_date or date.max),
    )
    finished = sorted(
        [t for t in tasks_in_group if t.finished],
        key=lambda t: (
            (t.completion_date or t.scheduled_date) is None,
            t.completion_date or t.scheduled_date or date.max,
        ),
    )
    ordered_tasks = unfinished + finished

    gantt_tasks_raw = [
        _gantt_bar_for_task(t, month, pixel_per_day, total_days, today) for t in ordered_tasks
    ]
    gantt_tasks = [g for g in gantt_tasks_raw if g is not None]

    total_count = len(tasks_in_group)
    overdue_count = sum(
        1 for t in tasks_in_group
        if not t.finished and t.scheduled_date is not None and t.scheduled_date < today
    )
    pending_count = sum(
        1 for t in tasks_in_group
        if not t.finished and (t.scheduled_date is None or t.scheduled_date >= today)
    )
    finished_count = sum(1 for t in tasks_in_group if t.finished)
    finished_late_count = sum(
        1 for t in tasks_in_group
        if t.finished and t.completion_date and t.scheduled_date
        and t.completion_date > t.scheduled_date
    )
    on_time_count = finished_count - finished_late_count

    # Dominant status priority: overdue > pending > finished_late/completed.
    if total_count == 0:
        status = "pending"
    elif overdue_count > 0:
        status = "overdue"
    elif pending_count > 0:
        status = "pending"
    else:
        # All finished — finished_late wins if any member is late.
        status = "finished_late" if finished_late_count > 0 else "completed"

    if total_count == 0:
        group_bar = None
    else:
        dates_with_sla = [t.scheduled_date for t in tasks_in_group if t.scheduled_date is not None]
        if dates_with_sla:
            bar_end = max(dates_with_sla)
            last_day = month.replace(day=monthrange(month.year, month.month)[1])
            if bar_end > last_day:
                bar_end = last_day
            offset_days = (month - month).days
            duration_days = (bar_end - month).days + 1
            left_pct = (offset_days + 0.15) / total_days * 100
            width_pct = max((duration_days - 0.3) / total_days * 100, 1.0)
            group_bar = {
                "start_offset": left_pct,
                "width": width_pct,
                "status": status,
            }
        else:
            group_bar = None

    block_id = group.id if group is not None else 0
    return {
        "id": block_id,
        "group": group,
        "tasks": ordered_tasks,
        "gantt_tasks": gantt_tasks,
        "summary": {
            "total": total_count,
            "completed": finished_count,
            "pending": pending_count,
            "overdue": overdue_count,
            "finished_late": finished_late_count,
            "on_time": on_time_count,
            "status": status,
        },
        "group_bar": group_bar,
    }


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
        1 for t in tasks_raw
        if not t.finished and t.scheduled_date is not None and t.scheduled_date < today
    )
    finished_late_count = sum(
        1 for t in tasks_raw
        if t.finished and t.completion_date and t.scheduled_date
        and t.completion_date > t.scheduled_date
    )

    # System reruns whose interval overlaps the selected calendar month.
    # Include reruns where any part of [triggered_at, completed_at or today]
    # falls within the month. Active reruns use today as the provisional end.
    month_start_dt = timezone.make_aware(datetime.combine(month, time.min))
    next_month_date = date(month.year + 1, 1, 1) if month.month == 12 else date(month.year, month.month + 1, 1)
    month_end_dt = timezone.make_aware(datetime.combine(next_month_date, time.min))
    today_local = timezone.localdate()
    today_dt = timezone.make_aware(datetime.combine(today_local, time.min))

    active_overlap = Q(completed_at__isnull=True, triggered_at__lt=today_dt + timedelta(days=1))
    if today_dt + timedelta(days=1) <= month_start_dt:
        active_overlap = Q(pk__in=[])
    reruns = SystemRerun.objects.filter(
        triggered_at__lt=month_end_dt,
    ).filter(
        active_overlap | Q(completed_at__gte=month_start_dt)
    ).select_related("system", "task")

    # Task editing shows complete history; Gantt/dashboard use the month-overlap query above.
    task_history = SystemRerun.objects.filter(task_id__in=[t.id for t in tasks_raw]).select_related("system")
    reruns_by_task: dict[int, list] = {}
    for r in task_history:
        reruns_by_task.setdefault(r.task_id, []).append(r)
    for r in reruns:
        end = r.completed_at or timezone.now()
        r.duration_seconds = (end - r.triggered_at).total_seconds()
        r.duration_str = _format_duration(r.duration_seconds)

    # Build rerun Gantt data.
    rerun_gantt_entries = _build_rerun_gantt(reruns, month, total_days, pixel_per_day)

    for t in tasks_raw:
        t.computed_status = task_status(t, today)
        t.computed_reruns = reruns_by_task.get(t.id, [])

    # Collect tasks with substantive comments for the comments table.
    comment_tasks = [t for t in tasks_raw if t.comments.strip()]

    # Flat list of every task, in the same order they appear across blocks.
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
            "systems": System.objects.all(),
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
            "finished_late_count": finished_late_count,
            "reruns_by_task": reruns_by_task,
            "rerun_gantt_total": len(reruns),
            "rerun_gantt_entries": rerun_gantt_entries,
            "comment_tasks": comment_tasks,
        },
    )


# --- Inline toggle finished (E3, E4) ---

@require_POST
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
        status = task_status(task, timezone.localdate())
        return JsonResponse({
            "ok": True,
            "finished": task.finished,
            "completion_display": _format_completion(task),
            "status": status,
            "is_late": status == "finished_late",
        })
    return redirect("task_list")


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
    return redirect("task_list")


# --- Regular task add/edit/delete ---

def task_add(request):
    if request.method == "POST":
        task_name = request.POST.get("task_name")
        assigned_to = request.POST.get("assigned_to")
        sla_days_raw = request.POST.get("sla_days", "").strip()
        sla_days = int(sla_days_raw) if sla_days_raw else None
        sla_type = request.POST.get("sla_type", "Working Day")
        comments = request.POST.get("comments", "")
        month = _get_current_month(request)
        if sla_days is not None:
            scheduled_date = calculate_scheduled_date(month, sla_days, sla_type)
        else:
            scheduled_date = None
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
        return redirect("task_list")

    templates = TaskTemplate.objects.all()
    return render(request, "tracker/task_form.html", {
        "templates": templates,
        "templates_json": json.dumps([{"id": t.id, "task_name": t.task_name, "assigned_to": t.assigned_to, "sla_days": t.sla_days, "sla_type": t.sla_type} for t in templates]),
        "month": _get_current_month(request),
        "groups": Group.objects.all(),
    })


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
        sla_raw = request.POST.get("sla_days", "").strip()
        task.sla_days = int(sla_raw) if sla_raw else None
        task.sla_type = request.POST.get("sla_type", task.sla_type)
        finished = request.POST.get("finished") == "on"
        task.finished = finished
        task.completion_date, task.completion_time = _parse_completion(
            request.POST.get("completion_date", "")
        )
        task.comments = request.POST.get("comments", "")
        task.group_id = _parse_group_id(request.POST.get("group"))
        if task.sla_days is not None:
            task.scheduled_date = calculate_scheduled_date(task.month, task.sla_days, task.sla_type)
        else:
            task.scheduled_date = None
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
        return redirect("task_list")

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
    if "sla_days" in payload:
        sla_raw = payload.get("sla_days", "")
        task.sla_days = int(sla_raw) if str(sla_raw).strip() else None
    task.sla_type = payload.get("sla_type", task.sla_type)
    task.completion_date, task.completion_time = _parse_completion(
        payload.get("completion_date", "") or ""
    )
    task.comments = payload.get("comments", task.comments)
    if "group" in payload:
        task.group_id = _parse_group_id(payload.get("group"))
    if task.sla_days is not None:
        task.scheduled_date = calculate_scheduled_date(
            task.month, task.sla_days, task.sla_type
        )
    else:
        task.scheduled_date = None
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
            "scheduled_date": task.scheduled_date.isoformat() if task.scheduled_date else "",
            "sla_type_short": "WD" if task.sla_type == "Working Day" else "CD",
        })
    return redirect("task_list")


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
        return redirect("task_list")

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
        return redirect("task_list")

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "saved": saved_ids})
    messages.success(request, f"Updated {len(saved_ids)} task(s).")
    return redirect("task_list")


@require_POST
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
    return redirect("task_list")


# --- System rerun CRUD ---

@require_POST
def task_rerun_create(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    try:
        system_id = int(request.POST.get("system", ""))
        triggered_at_str = request.POST.get("triggered_at", "").strip()
        completed_at_str = request.POST.get("completed_at", "").strip() or None
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "Invalid parameters"}, status=400)

    system = get_object_or_404(System, id=system_id)
    if not triggered_at_str:
        return JsonResponse({"ok": False, "error": "triggered_at is required"}, status=400)

    try:
        from django.utils.dateparse import parse_datetime
        triggered_at = parse_datetime(triggered_at_str)
        if triggered_at is None:
            raise ValueError
        if not timezone.is_aware(triggered_at):
            triggered_at = timezone.make_aware(triggered_at)
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "Invalid triggered_at datetime"}, status=400)

    completed_at = None
    if completed_at_str:
        try:
            completed_at = parse_datetime(completed_at_str)
            if completed_at is None:
                raise ValueError
            if not timezone.is_aware(completed_at):
                completed_at = timezone.make_aware(completed_at)
            if completed_at < triggered_at:
                return JsonResponse(
                    {"ok": False, "error": "completed_at must not be earlier than triggered_at"},
                    status=400,
                )
        except (ValueError, TypeError):
            return JsonResponse({"ok": False, "error": "Invalid completed_at datetime"}, status=400)

    rerun = SystemRerun.objects.create(
        task=task,
        system=system,
        triggered_at=triggered_at,
        completed_at=completed_at,
    )
    AuditLog.objects.create(
        task=task,
        task_name=task.task_name,
        action="rerun_created",
        changes={
            "system": system.name,
            "triggered_at": triggered_at.isoformat(),
        },
    )
    return JsonResponse({
        "ok": True,
        "id": rerun.id,
        "system_id": system.id,
        "system_name": system.name,
        "triggered_at": triggered_at.isoformat(),
        "completed_at": completed_at.isoformat() if completed_at else None,
        "is_active": completed_at is None,
    })


@require_POST
def task_rerun_update(request, rerun_id):
    rerun = get_object_or_404(SystemRerun, id=rerun_id)
    try:
        system_id = int(request.POST.get("system", ""))
        triggered_at_str = request.POST.get("triggered_at", "").strip()
        completed_at_str = request.POST.get("completed_at", "").strip() or None
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "Invalid parameters"}, status=400)

    system = get_object_or_404(System, id=system_id)
    if not triggered_at_str:
        return JsonResponse({"ok": False, "error": "triggered_at is required"}, status=400)

    try:
        from django.utils.dateparse import parse_datetime
        triggered_at = parse_datetime(triggered_at_str)
        if triggered_at is None:
            raise ValueError
        if not timezone.is_aware(triggered_at):
            triggered_at = timezone.make_aware(triggered_at)
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "Invalid triggered_at datetime"}, status=400)

    completed_at = None
    if completed_at_str:
        try:
            completed_at = parse_datetime(completed_at_str)
            if completed_at is None:
                raise ValueError
            if not timezone.is_aware(completed_at):
                completed_at = timezone.make_aware(completed_at)
            if completed_at < triggered_at:
                return JsonResponse(
                    {"ok": False, "error": "completed_at must not be earlier than triggered_at"},
                    status=400,
                )
        except (ValueError, TypeError):
            return JsonResponse({"ok": False, "error": "Invalid completed_at datetime"}, status=400)

    old_system_name = rerun.system.name
    rerun.system = system
    rerun.triggered_at = triggered_at
    rerun.completed_at = completed_at
    rerun.save()

    AuditLog.objects.create(
        task=rerun.task,
        task_name=rerun.task.task_name,
        action="rerun_updated",
        changes={
            "system": system.name,
            "triggered_at": triggered_at.isoformat(),
        },
    )
    return JsonResponse({
        "ok": True,
        "id": rerun.id,
        "system_id": system.id,
        "system_name": system.name,
        "triggered_at": triggered_at.isoformat(),
        "completed_at": completed_at.isoformat() if completed_at else None,
        "is_active": completed_at is None,
    })


@require_POST
def task_rerun_delete(request, rerun_id):
    rerun = get_object_or_404(SystemRerun, id=rerun_id)
    task = rerun.task
    system_name = rerun.system.name
    triggered_at = rerun.triggered_at
    rerun.delete()
    AuditLog.objects.create(
        task=task,
        task_name=task.task_name,
        action="rerun_deleted",
        changes={
            "system": system_name,
            "triggered_at": triggered_at.isoformat(),
        },
    )
    return JsonResponse({"ok": True})


@require_POST
def task_rerun_list(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    reruns = task.system_reruns.select_related("system").all()
    data = []
    for r in reruns:
        data.append({
            "id": r.id,
            "system_id": r.system.id,
            "system_name": r.system.name,
            "triggered_at": r.triggered_at.isoformat(),
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "is_active": r.completed_at is None,
        })
    return JsonResponse({"ok": True, "reruns": data})


# --- Dashboard (E1 stats are also on main page now) ---

def dashboard(request):
    month = _get_current_month(request)
    tasks = Task.objects.filter(month=month)
    today = timezone.localdate()

    total = tasks.count()
    completed = tasks.filter(finished=True).count()
    pending = tasks.filter(finished=False).count()
    overdue = sum(
        1 for t in tasks
        if not t.finished and t.scheduled_date is not None and t.scheduled_date < today
    )
    finished_late_count = sum(
        1 for t in tasks
        if t.finished and t.completion_date and t.scheduled_date and t.completion_date > t.scheduled_date
    )
    on_time_count = completed - finished_late_count
    completion_rate = round(completed / total * 100, 1) if total > 0 else 0

    # System rerun statistics — month-overlap scoping
    month_start_dt = timezone.make_aware(datetime.combine(month, time.min))
    next_month_d = date(month.year + 1, 1, 1) if month.month == 12 else date(month.year, month.month + 1, 1)
    month_end_dt = timezone.make_aware(datetime.combine(next_month_d, time.min))
    today_local = timezone.localdate()
    today_dt = timezone.make_aware(datetime.combine(today_local, time.min))
    month_reruns = SystemRerun.objects.filter(
        triggered_at__lt=month_end_dt,
    ).filter(
        Q(completed_at__isnull=True, triggered_at__lt=today_dt + timedelta(days=1)) |
        Q(completed_at__gte=month_start_dt)
    ).select_related("system", "task")
    total_reruns = month_reruns.count()
    completed_reruns = month_reruns.filter(completed_at__isnull=False).count()
    active_reruns = total_reruns - completed_reruns
    distinct_tasks = month_reruns.values("task").distinct().count()
    distinct_systems = month_reruns.values("system").distinct().count()

    durations = []
    for r in month_reruns:
        end = r.completed_at or timezone.now()
        dur = (end - r.triggered_at).total_seconds()
        durations.append(dur)
    avg_duration = sum(durations) / len(durations) if durations else 0
    max_duration = max(durations) if durations else 0

    # Detailed rerun entries for the table
    rerun_entries = month_reruns.order_by("-triggered_at")
    for r in rerun_entries:
        end = r.completed_at or timezone.now()
        r.duration_seconds = (end - r.triggered_at).total_seconds()
        r.duration_str = _format_duration(r.duration_seconds)
    rerun_stats = {
        "total": total_reruns,
        "completed": completed_reruns,
        "active": active_reruns,
        "distinct_tasks": distinct_tasks,
        "distinct_systems": distinct_systems,
        "avg_duration": _format_duration(avg_duration),
        "max_duration": _format_duration(max_duration),
    }

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
        "finished_late_count": finished_late_count,
        "on_time_count": on_time_count,
        "completion_rate": completion_rate,
        "month": month,
        "months": list(range(1, 13)),
        "audit_logs": audit_logs,
        "months_data": months_data,
        "rerun_stats": rerun_stats,
        "rerun_entries": rerun_entries,
    })


# --- Generate next month ---

@require_POST
def generate_next_month(request):
    current_month = _get_current_month(request)
    if current_month.month == 12:
        next_month = date(current_month.year + 1, 1, 1)
    else:
        next_month = date(current_month.year, current_month.month + 1, 1)

    existing = Task.objects.filter(month=next_month).count()
    if existing > 0:
        messages.warning(request, f"Tasks already exist for {next_month.strftime('%B %Y')}.")
        return redirect("task_list")

    templates = TaskTemplate.objects.all()
    if templates.exists():
        for tmpl in templates:
            if tmpl.sla_days is not None:
                scheduled = calculate_scheduled_date(next_month, tmpl.sla_days, tmpl.sla_type)
            else:
                scheduled = None
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
            if t.sla_days is not None:
                scheduled = calculate_scheduled_date(next_month, t.sla_days, t.sla_type)
            else:
                scheduled = None
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
    return redirect("task_list")


@require_POST
def set_month(request):
    year = int(request.POST.get("year"))
    month_num = int(request.POST.get("month"))
    request.session["current_month"] = date(year, month_num, 1).isoformat()
    # Honor a `next` form field if it's a safe same-origin path; default to task list.
    next_url = request.POST.get("next", "").strip()
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect("task_list")


# --- Export ---

def export_csv(request):
    month = _get_current_month(request)
    tasks = Task.objects.filter(month=month)
    import csv

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="tasks_{month.year}_{month.month:02d}.csv"'
    writer = csv.writer(response)
    writer.writerow(["Task Name", "Assigned To", "SLA Days", "SLA Type", "Scheduled Date", "Finished", "Completion Date", "Comments"])
    for t in tasks:
        writer.writerow([t.task_name, t.assigned_to, t.sla_days or "", t.sla_type, t.scheduled_date or "", t.finished, t.completion_date or "", t.comments])
    return response


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

def template_list(request):
    templates = TaskTemplate.objects.select_related("group").all()
    groups = Group.objects.all()
    return render(
        request,
        "tracker/template_list.html",
        {"templates": templates, "groups": groups, "systems": System.objects.all()},
    )


def _parse_int_field(value, default=None):
    """Return int(value) or default if value is missing/blank/non-numeric."""
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_optional_sla(value):
    """Return an integer SLA, or None for a deliberately blank SLA field."""
    if value is None or not str(value).strip():
        return None
    return int(value)


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


def template_add(request):
    if request.method == "POST":
        requested = _parse_int_field(request.POST.get("sort_order"))
        actual, shifted = _assign_template_sort_order(requested)
        TaskTemplate.objects.create(
            task_name=request.POST["task_name"],
            assigned_to=request.POST["assigned_to"],
            sla_days=_parse_optional_sla(request.POST.get("sla_days")),
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
        return redirect("template_list")
    return render(
        request,
        "tracker/template_form.html",
        {"groups": Group.objects.all()},
    )


def template_edit(request, template_id):
    tmpl = get_object_or_404(TaskTemplate, id=template_id)
    if request.method == "POST":
        tmpl.task_name = request.POST["task_name"]
        tmpl.assigned_to = request.POST["assigned_to"]
        tmpl.sla_days = _parse_optional_sla(request.POST.get("sla_days"))
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
        return redirect("template_list")
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
    if "sla_days" in payload:
        tmpl.sla_days = _parse_optional_sla(payload.get("sla_days"))
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
    return redirect("template_list")


@require_POST
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
        return redirect("template_list")

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
        return redirect("template_list")

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "saved": saved_ids, "shifted": total_shifted})
    messages.success(request, f"Updated {len(saved_ids)} template(s).")
    if total_shifted:
        messages.info(
            request,
            f"Reordered {total_shifted} template(s) to accommodate unique sort orders.",
        )
    return redirect("template_list")


@require_POST
def template_delete(request, template_id):
    tmpl = get_object_or_404(TaskTemplate, id=template_id)
    tmpl.delete()
    messages.success(request, "Template deleted.")
    return redirect("template_list")


# --- Group management ---

# System rerun choices are maintained on the Templates tab so task rerun
# dropdowns always draw from values users have explicitly provided.
@require_POST
def system_add(request):
    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "System name is required.")
        return redirect("template_list")
    if System.objects.filter(name__iexact=name).exists():
        messages.error(request, f"A system named '{name}' already exists.")
        return redirect("template_list")
    current_max = System.objects.aggregate(m=Max("sort_order"))["m"] or 0
    system = System.objects.create(name=name, sort_order=current_max + 1)
    messages.success(request, f"System '{system.name}' added. It is now available for rerun logging.")
    return redirect("template_list")


@require_POST
def system_inline_save(request, system_id):
    system = get_object_or_404(System, id=system_id)
    name = (request.POST.get("name") or "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "System name is required."}, status=400)
    if System.objects.filter(name__iexact=name).exclude(id=system.id).exists():
        return JsonResponse({"ok": False, "error": "A system with that name already exists."}, status=400)
    system.name = name
    system.save(update_fields=["name"])
    return JsonResponse({"ok": True, "name": system.name})


@require_POST
def system_delete(request, system_id):
    system = get_object_or_404(System, id=system_id)
    name = system.name
    try:
        system.delete()
    except ProtectedError:
        messages.error(request, f"System '{name}' cannot be deleted because rerun history uses it.")
    else:
        messages.success(request, f"System '{name}' deleted.")
    return redirect("template_list")

def _parse_group_id(value):
    """Return int(value), or None if blank/missing/non-numeric."""
    if value in (None, "", "null", "None"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@require_POST
def group_add(request):
    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "Group name is required.")
        return redirect("template_list")
    if Group.objects.filter(name__iexact=name).exists():
        messages.error(request, f"A group named '{name}' already exists.")
        return redirect("template_list")
    requested = _parse_int_field(request.POST.get("sort_order"))
    actual, shifted = _assign_group_sort_order(requested)
    group = Group.objects.create(name=name, sort_order=actual)
    if shifted:
        messages.info(
            request,
            f"Reordered {shifted} group(s) to make room for order {actual}.",
        )
    messages.success(request, f"Group '{group.name}' added.")
    return redirect("template_list")


@require_POST
def group_edit(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "Group name is required.")
        return redirect("template_list")
    if Group.objects.filter(name__iexact=name).exclude(id=group.id).exists():
        messages.error(request, f"A group named '{name}' already exists.")
        return redirect("template_list")
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
    return redirect("template_list")


@require_POST
def group_inline_save(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    name = (request.POST.get("name") or "").strip()
    if name:
        if Group.objects.filter(name__iexact=name).exclude(id=group.id).exists():
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"ok": False, "error": "name_taken"}, status=400)
            messages.error(request, f"A group named '{name}' already exists.")
            return redirect("template_list")
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
    return redirect("template_list")


@require_POST
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
    return redirect("template_list")


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
_BULK_REQUIRED = {"task_name", "assigned_to", "sla_type"}
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
            record["sla_days"] = _parse_optional_sla(record.get("sla_days"))
        except ValueError:
            warnings.append(f"Row {line_no}: SLA Days must be an integer when supplied, got '{record.get('sla_days', '')}' — skipped.")
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
def template_bulk_upload(request):
    csv_text, source = _resolve_csv_source(request)
    if not csv_text:
        messages.error(request, "Provide a CSV file or paste CSV text before uploading.")
        return redirect("template_list")

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
    return redirect("template_list")


# --- E6: Public holiday list ---

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
