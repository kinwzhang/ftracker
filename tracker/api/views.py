import csv
import json
from calendar import monthrange
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Count, F, Max
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from ..holidays import (
    calculate_scheduled_date,
    hk_public_holidays,
    hk_public_holidays_named,
)
from ..models import AuditLog, Group, Task, TaskTemplate
from ..views import (
    _assign_group_sort_order,
    _assign_template_sort_order,
    _apply_task_updates,
    _apply_template_updates,
    _bulk_payload_from_request,
    _build_group_block,
    _format_completion,
    _get_current_month,
    _gantt_bar_for_task,
    _parse_bulk_csv,
    _parse_completion,
    _parse_group_id,
    _parse_int_field,
    _resolve_csv_source,
)


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def _serialize_task(task):
    return {
        "id": task.id,
        "task_name": task.task_name,
        "assigned_to": task.assigned_to,
        "sla_days": task.sla_days,
        "sla_type": task.sla_type,
        "scheduled_date": task.scheduled_date.isoformat(),
        "finished": task.finished,
        "completion_date": task.completion_date.isoformat() if task.completion_date else None,
        "completion_time": task.completion_time.isoformat() if task.completion_time else None,
        "comments": task.comments,
        "month": task.month.isoformat(),
        "group_id": task.group_id,
    }


def _serialize_template(tmpl):
    return {
        "id": tmpl.id,
        "task_name": tmpl.task_name,
        "assigned_to": tmpl.assigned_to,
        "sla_days": tmpl.sla_days,
        "sla_type": tmpl.sla_type,
        "sort_order": tmpl.sort_order,
        "group_id": tmpl.group_id,
    }


def _serialize_group(group):
    return {
        "id": group.id,
        "name": group.name,
        "sort_order": group.sort_order,
    }


def _serialize_gantt_task(gt):
    return {
        "task_id": gt["task"].id,
        "start_offset": gt["start_offset"],
        "duration": gt["duration"],
    }


def _serialize_group_block(block):
    return {
        "id": block["id"],
        "group": _serialize_group(block["group"]) if block["group"] else None,
        "tasks": [_serialize_task(t) for t in block["tasks"]],
        "gantt_tasks": [_serialize_gantt_task(gt) for gt in block["gantt_tasks"]],
        "summary": block["summary"],
        "group_bar": block["group_bar"],
    }


def _parse_json_body(request):
    """Return parsed JSON body as a dict, or empty dict on failure."""
    if request.content_type and request.content_type.startswith("application/json"):
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return {}
    return {}


def _get_month_param(request):
    """Parse ?month=YYYY-MM from querystring, falling back to session."""
    month_str = request.GET.get("month")
    if month_str:
        try:
            parts = month_str.split("-")
            return date(int(parts[0]), int(parts[1]), 1)
        except (ValueError, IndexError):
            pass
    return _get_current_month(request)


# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------

@require_GET
def csrf_token(request):
    get_token(request)
    return JsonResponse({"ok": True})


# ---------------------------------------------------------------------------
# Task data (full page payload for the React frontend)
# ---------------------------------------------------------------------------

@require_GET
def task_data(request):
    month = _get_month_param(request)
    tasks_raw = list(Task.objects.filter(month=month).select_related("group"))
    today = timezone.localdate()
    holidays_set = hk_public_holidays(month.year)

    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    if month.month == 12:
        next_month = date(month.year + 1, 1, 1)
    else:
        next_month = date(month.year, month.month + 1, 1)
    total_days = (next_month - month).days

    days_in_month = []
    for day in range(1, total_days + 1):
        d = date(month.year, month.month, day)
        days_in_month.append({
            "date": d.isoformat(),
            "weekday": weekdays[d.weekday()],
            "is_holiday": d in holidays_set,
        })

    pixel_per_day = 28
    today_pct = None
    if month <= today <= date(month.year, month.month, total_days):
        today_pct = ((today - month).days + 0.5) / total_days * 100

    grouped = {}
    for t in tasks_raw:
        grouped.setdefault(t.group_id, []).append(t)
    groups_by_id = {g.id: g for g in Group.objects.all()}

    group_blocks = []
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
        raw_block = _build_group_block(
            groups_by_id[gid], gtasks, today, month, pixel_per_day, total_days
        )
        group_blocks.append(_serialize_group_block(raw_block))

    if None in grouped:
        raw_block = _build_group_block(
            None, grouped[None], today, month, pixel_per_day, total_days
        )
        group_blocks.append(_serialize_group_block(raw_block))

    all_tasks = []
    for block in group_blocks:
        all_tasks.extend(block["tasks"])

    total = len(tasks_raw)
    completed = sum(1 for t in tasks_raw if t.finished)
    pending = sum(1 for t in tasks_raw if not t.finished)
    overdue = sum(1 for t in tasks_raw if not t.finished and t.scheduled_date < today)

    return JsonResponse({
        "tasks": all_tasks,
        "group_blocks": group_blocks,
        "groups": [_serialize_group(g) for g in Group.objects.all()],
        "days_in_month": days_in_month,
        "month": month.isoformat(),
        "today": today.isoformat(),
        "today_pct": today_pct,
        "total_days": total_days,
        "stats": {
            "total": total,
            "completed": completed,
            "pending": pending,
            "overdue": overdue,
        },
    })


# ---------------------------------------------------------------------------
# Task CRUD
# ---------------------------------------------------------------------------

def task_list_api(request):
    """GET /api/v1/tasks/ → list tasks for the current month.
    POST /api/v1/tasks/ → create a new task."""
    if request.method == "POST":
        return _task_create(request)
    month = _get_month_param(request)
    tasks = Task.objects.filter(month=month).select_related("group")
    return JsonResponse({
        "tasks": [_serialize_task(t) for t in tasks],
        "month": month.isoformat(),
    })


def _task_create(request):
    data = _parse_json_body(request) or request.POST
    task_name = data.get("task_name", "")
    assigned_to = data.get("assigned_to", "")
    sla_days = int(data.get("sla_days", 0))
    sla_type = data.get("sla_type", "Working Day")
    comments = data.get("comments", "")
    month = _get_month_param(request)
    scheduled_date = calculate_scheduled_date(month, sla_days, sla_type)
    group_id = _parse_group_id(data.get("group"))

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
    return JsonResponse({"ok": True, "task": _serialize_task(task)}, status=201)


def task_detail_api(request, task_id):
    """PATCH /api/v1/tasks/<id>/ → update task. DELETE /api/v1/tasks/<id>/ → delete task."""
    if request.method == "PATCH":
        task = get_object_or_404(Task, id=task_id)
        data = _parse_json_body(request) or request.POST
        old_values, new_values = _apply_task_updates(task, data)
        AuditLog.objects.create(
            task=task,
            task_name=task.task_name,
            action="updated",
            changes={"old": old_values, "new": new_values},
        )
        return JsonResponse({"ok": True, "task": _serialize_task(task)})
    elif request.method == "DELETE":
        task = get_object_or_404(Task, id=task_id)
        AuditLog.objects.create(
            task=None,
            task_name=task.task_name,
            action="deleted",
            changes={"task_name": task.task_name, "month": str(task.month)},
        )
        task.delete()
        return JsonResponse({"ok": True})
    return JsonResponse({"error": "method_not_allowed"}, status=405)


# ---------------------------------------------------------------------------
# Task actions
# ---------------------------------------------------------------------------

@require_POST
def task_toggle_api(request, task_id):
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
    return JsonResponse({
        "ok": True,
        "finished": task.finished,
        "completion_display": _format_completion(task),
    })


@require_POST
def task_comment_api(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    data = _parse_json_body(request) or request.POST
    old_comments = task.comments
    task.comments = data.get("comments", "")
    task.save()
    AuditLog.objects.create(
        task=task,
        task_name=task.task_name,
        action="updated",
        changes={"old": {"comments": old_comments}, "new": {"comments": task.comments}},
    )
    return JsonResponse({"ok": True, "comments": task.comments})


@require_POST
def task_inline_save_api(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    data = _parse_json_body(request) or request.POST
    old_values, new_values = _apply_task_updates(task, data)
    AuditLog.objects.create(
        task=task,
        task_name=task.task_name,
        action="updated",
        changes={"old": old_values, "new": new_values},
    )
    return JsonResponse({
        "ok": True,
        "scheduled_date": task.scheduled_date.isoformat(),
        "sla_type_short": "WD" if task.sla_type == "Working Day" else "CD",
    })


@require_POST
def task_bulk_save_api(request):
    updates = _bulk_payload_from_request(request)
    if not updates:
        return JsonResponse({"ok": False, "error": "no_updates"}, status=400)

    saved_ids = []
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
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    return JsonResponse({"ok": True, "saved": saved_ids})


# ---------------------------------------------------------------------------
# Template CRUD
# ---------------------------------------------------------------------------

def template_list_api(request):
    """GET /api/v1/templates/ → list templates. POST /api/v1/templates/ → create template."""
    if request.method == "POST":
        return _template_create(request)
    templates = TaskTemplate.objects.select_related("group").all()
    groups = Group.objects.all()
    return JsonResponse({
        "templates": [_serialize_template(t) for t in templates],
        "groups": [_serialize_group(g) for g in groups],
    })


def _template_create(request):
    data = _parse_json_body(request) or request.POST
    requested = _parse_int_field(data.get("sort_order"))
    actual, shifted = _assign_template_sort_order(requested)
    tmpl = TaskTemplate.objects.create(
        task_name=data.get("task_name", ""),
        assigned_to=data.get("assigned_to", ""),
        sla_days=int(data.get("sla_days", 0)),
        sla_type=data.get("sla_type", "Working Day"),
        sort_order=actual,
        group_id=_parse_group_id(data.get("group")),
    )
    result = {"ok": True, "template": _serialize_template(tmpl)}
    if shifted:
        result["shifted"] = shifted
    return JsonResponse(result, status=201)


def template_detail_api(request, template_id):
    """PATCH/DELETE /api/v1/templates/<id>/."""
    if request.method == "PATCH":
        tmpl = get_object_or_404(TaskTemplate, id=template_id)
        data = _parse_json_body(request) or request.POST
        shifted, old_values, new_values = _apply_template_updates(tmpl, data)
        result = {"ok": True, "template": _serialize_template(tmpl)}
        if shifted:
            result["shifted"] = shifted
        return JsonResponse(result)
    elif request.method == "DELETE":
        tmpl = get_object_or_404(TaskTemplate, id=template_id)
        tmpl.delete()
        return JsonResponse({"ok": True})
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@require_POST
def template_inline_save_api(request, template_id):
    tmpl = get_object_or_404(TaskTemplate, id=template_id)
    data = _parse_json_body(request) or request.POST
    shifted, old_values, new_values = _apply_template_updates(tmpl, data)
    result = {"ok": True, "sort_order": tmpl.sort_order, "group_id": tmpl.group_id}
    if shifted:
        result["shifted"] = shifted
    return JsonResponse(result)


@require_POST
def template_bulk_save_api(request):
    updates = _bulk_payload_from_request(request)
    if not updates:
        return JsonResponse({"ok": False, "error": "no_updates"}, status=400)

    saved_ids = []
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
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    return JsonResponse({"ok": True, "saved": saved_ids, "shifted": total_shifted})


@require_POST
def template_bulk_upload_api(request):
    csv_text, source = _resolve_csv_source(request)
    if not csv_text:
        return JsonResponse(
            {"ok": False, "error": "Provide a CSV file or paste CSV text before uploading."},
            status=400,
        )

    _, records, warnings = _parse_bulk_csv(csv_text)

    created = 0
    total_shifted = 0
    auto_created_groups = []
    with transaction.atomic():
        existing_group_names = {g.name.lower() for g in Group.objects.all()}
        csv_group_names = []
        seen_in_csv = set()
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

    return JsonResponse({
        "ok": True,
        "created": created,
        "shifted": total_shifted,
        "warnings": warnings,
        "auto_created_groups": auto_created_groups,
        "source": source,
    })


# ---------------------------------------------------------------------------
# Group CRUD
# ---------------------------------------------------------------------------

def group_list_api(request):
    """GET /api/v1/groups/ → list groups. POST /api/v1/groups/ → create group."""
    if request.method == "POST":
        return _group_create(request)
    groups = Group.objects.annotate(template_count=Count("templates"))
    return JsonResponse({
        "groups": [
            {
                "id": g.id,
                "name": g.name,
                "sort_order": g.sort_order,
                "template_count": g.template_count,
            }
            for g in groups
        ],
    })


def _group_create(request):
    data = _parse_json_body(request) or request.POST
    name = (data.get("name") or "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "Group name is required."}, status=400)
    if Group.objects.filter(name__iexact=name).exists():
        return JsonResponse(
            {"ok": False, "error": f"A group named '{name}' already exists."},
            status=400,
        )
    requested = _parse_int_field(data.get("sort_order"))
    actual, shifted = _assign_group_sort_order(requested)
    group = Group.objects.create(name=name, sort_order=actual)
    result = {"ok": True, "group": _serialize_group(group)}
    if shifted:
        result["shifted"] = shifted
    return JsonResponse(result, status=201)


def group_detail_api(request, group_id):
    """PATCH/DELETE /api/v1/groups/<id>/."""
    if request.method == "PATCH":
        group = get_object_or_404(Group, id=group_id)
        data = _parse_json_body(request) or request.POST
        name = (data.get("name") or "").strip()
        if name:
            if Group.objects.filter(name__iexact=name).exclude(id=group.id).exists():
                return JsonResponse(
                    {"ok": False, "error": f"A group named '{name}' already exists."},
                    status=400,
                )
            group.name = name
        requested = _parse_int_field(data.get("sort_order"), default=group.sort_order)
        actual, shifted = _assign_group_sort_order(requested, exclude_id=group.id)
        group.sort_order = actual
        group.save()
        result = {"ok": True, "group": _serialize_group(group)}
        if shifted:
            result["shifted"] = shifted
        return JsonResponse(result)
    elif request.method == "DELETE":
        group = get_object_or_404(Group, id=group_id)
        template_count = group.templates.count()
        task_count = group.tasks.count()
        name = group.name
        group.delete()
        return JsonResponse({
            "ok": True,
            "unlinked_templates": template_count,
            "unlinked_tasks": task_count,
        })
    return JsonResponse({"error": "method_not_allowed"}, status=405)


@require_POST
def group_inline_save_api(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    data = _parse_json_body(request) or request.POST
    name = (data.get("name") or "").strip()
    if name:
        if Group.objects.filter(name__iexact=name).exclude(id=group.id).exists():
            return JsonResponse({"ok": False, "error": "name_taken"}, status=400)
        group.name = name
    requested = _parse_int_field(data.get("sort_order"), default=group.sort_order)
    actual, shifted = _assign_group_sort_order(requested, exclude_id=group.id)
    group.sort_order = actual
    group.save()
    return JsonResponse({"ok": True, "name": group.name, "sort_order": actual})


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@require_GET
def dashboard_api(request):
    month = _get_month_param(request)
    tasks = Task.objects.filter(month=month)
    today = timezone.localdate()

    total = tasks.count()
    completed = tasks.filter(finished=True).count()
    pending = tasks.filter(finished=False).count()
    overdue = tasks.filter(finished=False, scheduled_date__lt=today).count()
    completion_rate = round(completed / total * 100, 1) if total > 0 else 0

    audit_logs = AuditLog.objects.all()[:50]
    audit_data = [
        {
            "id": log.id,
            "task_name": log.task_name,
            "action": log.action,
            "changes": log.changes,
            "timestamp": log.timestamp.isoformat(),
            "message": log.readable_message(),
        }
        for log in audit_logs
    ]

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

    return JsonResponse({
        "month": month.isoformat(),
        "stats": {
            "total": total,
            "completed": completed,
            "pending": pending,
            "overdue": overdue,
        },
        "completion_rate": completion_rate,
        "months_data": months_data,
        "audit_logs": audit_data,
    })


# ---------------------------------------------------------------------------
# Holidays
# ---------------------------------------------------------------------------

@require_GET
def holiday_list_api(request):
    year = int(request.GET.get("year", timezone.localdate().year))
    month_num = int(request.GET.get("month", timezone.localdate().month))
    all_named = hk_public_holidays_named(year)
    all_named.sort(key=lambda h: h.date)
    month_holidays = [h for h in all_named if h.date.month == month_num] if month_num != 0 else []
    return JsonResponse({
        "year": year,
        "month": month_num,
        "month_holidays": [{"date": h.date.isoformat(), "name": h.name} for h in month_holidays],
        "all_year": [{"date": h.date.isoformat(), "name": h.name} for h in all_named],
    })


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

@require_POST
def generate_next_month_api(request):
    current_month = _get_current_month(request)
    if current_month.month == 12:
        next_month = date(current_month.year + 1, 1, 1)
    else:
        next_month = date(current_month.year, current_month.month + 1, 1)

    existing = Task.objects.filter(month=next_month).count()
    if existing > 0:
        return JsonResponse(
            {"ok": False, "error": f"Tasks already exist for {next_month.strftime('%B %Y')}."},
            status=409,
        )

    templates = TaskTemplate.objects.all()
    created = 0
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
            created += 1
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
            created += 1

    request.session["current_month"] = next_month.isoformat()
    return JsonResponse({
        "ok": True,
        "month": next_month.isoformat(),
        "created": created,
    })


@require_POST
def set_month_api(request):
    data = _parse_json_body(request) or request.POST
    year = int(data.get("year", 0))
    month_num = int(data.get("month", 0))
    if not year or not month_num:
        return JsonResponse({"ok": False, "error": "year and month are required"}, status=400)
    request.session["current_month"] = date(year, month_num, 1).isoformat()
    return JsonResponse({"ok": True, "month": date(year, month_num, 1).isoformat()})


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@require_GET
def export_csv_api(request):
    month = _get_month_param(request)
    tasks = Task.objects.filter(month=month)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="tasks_{month.year}_{month.month:02d}.csv"'
    writer = csv.writer(response)
    writer.writerow(["Task Name", "Assigned To", "SLA Days", "SLA Type", "Scheduled Date", "Finished", "Completion Date", "Comments"])
    for t in tasks:
        writer.writerow([
            t.task_name, t.assigned_to, t.sla_days, t.sla_type,
            t.scheduled_date, t.finished, t.completion_date or "", t.comments,
        ])
    return response


@require_GET
def export_html_api(request):
    month = _get_month_param(request)
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
