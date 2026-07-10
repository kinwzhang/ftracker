import csv
import io
import json
from datetime import date, timedelta

from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from .holidays import calculate_scheduled_date, hk_public_holidays, hk_public_holidays_named
from .models import AuditLog, Task, TaskTemplate


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


def task_list(request):
    month = _get_current_month(request)
    tasks_raw = Task.objects.filter(month=month)
    unfinished = [t for t in tasks_raw if not t.finished]
    finished = [t for t in tasks_raw if t.finished]
    unfinished.sort(key=lambda t: t.scheduled_date)
    finished.sort(key=lambda t: t.completion_date or t.scheduled_date)
    tasks = unfinished + finished
    templates = TaskTemplate.objects.all()
    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    today = timezone.localdate()

    days_in_month = []
    if month.month == 12:
        next_month = date(month.year + 1, 1, 1)
    else:
        next_month = date(month.year, month.month + 1, 1)
    total_days = (next_month - month).days
    for day in range(1, total_days + 1):
        d = date(month.year, month.month, day)
        days_in_month.append({"date": d, "weekday": weekdays[d.weekday()]})

    gantt_tasks = []
    pixel_per_day = 28
    canvas_width = total_days * pixel_per_day
    canvas_total_width = 200 + canvas_width
    today_offset = None
    if month <= today <= date(month.year, month.month, total_days):
        today_offset = (today - month).days * pixel_per_day

    for task in tasks:
        start = task.month
        end = task.scheduled_date if task.scheduled_date >= start else start
        duration = (end - start).days + 1
        offset = (start - month).days
        if offset < 0:
            offset = 0
        gantt_tasks.append({
            "task": task,
            "start_offset": offset * pixel_per_day + 4,
            "duration": duration * pixel_per_day - 4,
        })

    total = len(tasks)
    completed = sum(1 for t in tasks if t.finished)
    pending = sum(1 for t in tasks if not t.finished)
    overdue = sum(1 for t in tasks if not t.finished and t.scheduled_date < today)

    return render(request, "tracker/task_list.html", {
        "tasks": tasks,
        "templates": templates,
        "month": month,
        "months": list(range(1, 13)),
        "days_in_month": days_in_month,
        "gantt_tasks": gantt_tasks,
        "canvas_width": canvas_width,
        "canvas_total_width": canvas_total_width,
        "total_days": total_days,
        "today": today,
        "today_offset": today_offset,
        "total_count": total,
        "completed_count": completed,
        "pending_count": pending,
        "overdue_count": overdue,
    })


# --- Inline toggle finished (E3, E4) ---

@require_POST
def task_toggle_finished(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    old_finished = task.finished
    task.finished = not task.finished
    if task.finished and not task.completion_date:
        task.completion_date = timezone.localdate()
    elif not task.finished:
        task.completion_date = None
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
        return JsonResponse({"ok": True, "finished": task.finished})
    return redirect("task_list")


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
        sla_days = int(request.POST.get("sla_days", 0))
        sla_type = request.POST.get("sla_type", "Working Day")
        comments = request.POST.get("comments", "")
        month = _get_current_month(request)
        scheduled_date = calculate_scheduled_date(month, sla_days, sla_type)

        task = Task.objects.create(
            task_name=task_name,
            assigned_to=assigned_to,
            sla_days=sla_days,
            sla_type=sla_type,
            scheduled_date=scheduled_date,
            month=month,
            comments=comments,
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
            "comments": task.comments,
        }
        task.task_name = request.POST.get("task_name", task.task_name)
        task.assigned_to = request.POST.get("assigned_to", task.assigned_to)
        task.sla_days = int(request.POST.get("sla_days", task.sla_days))
        task.sla_type = request.POST.get("sla_type", task.sla_type)
        finished = request.POST.get("finished") == "on"
        task.finished = finished
        comp_date = request.POST.get("completion_date", "")
        task.completion_date = date.fromisoformat(comp_date) if comp_date else None
        task.comments = request.POST.get("comments", "")
        task.scheduled_date = calculate_scheduled_date(task.month, task.sla_days, task.sla_type)
        task.save()

        new_values = {
            "task_name": task.task_name,
            "assigned_to": task.assigned_to,
            "sla_days": task.sla_days,
            "sla_type": task.sla_type,
            "finished": task.finished,
            "completion_date": str(task.completion_date) if task.completion_date else None,
            "comments": task.comments,
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
    })


@require_POST
def task_inline_save(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    old_values = {
        "task_name": task.task_name,
        "assigned_to": task.assigned_to,
        "sla_days": task.sla_days,
        "sla_type": task.sla_type,
        "completion_date": str(task.completion_date) if task.completion_date else None,
        "comments": task.comments,
    }
    task.task_name = request.POST.get("task_name", task.task_name)
    task.assigned_to = request.POST.get("assigned_to", task.assigned_to)
    task.sla_days = int(request.POST.get("sla_days", task.sla_days))
    task.sla_type = request.POST.get("sla_type", task.sla_type)
    comp_date = request.POST.get("completion_date", "")
    task.completion_date = date.fromisoformat(comp_date) if comp_date else None
    task.comments = request.POST.get("comments", task.comments)
    task.scheduled_date = calculate_scheduled_date(task.month, task.sla_days, task.sla_type)
    task.save()
    new_values = {
        "task_name": task.task_name,
        "assigned_to": task.assigned_to,
        "sla_days": task.sla_days,
        "sla_type": task.sla_type,
        "completion_date": str(task.completion_date) if task.completion_date else None,
        "comments": task.comments,
    }
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


# --- Dashboard (E1 stats are also on main page now) ---

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
            scheduled = calculate_scheduled_date(next_month, tmpl.sla_days, tmpl.sla_type)
            Task.objects.create(
                task_name=tmpl.task_name,
                assigned_to=tmpl.assigned_to,
                sla_days=tmpl.sla_days,
                sla_type=tmpl.sla_type,
                scheduled_date=scheduled,
                month=next_month,
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
        writer.writerow([t.task_name, t.assigned_to, t.sla_days, t.sla_type, t.scheduled_date, t.finished, t.completion_date or "", t.comments])
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
    templates = TaskTemplate.objects.all()
    return render(request, "tracker/template_list.html", {"templates": templates})


def template_add(request):
    if request.method == "POST":
        TaskTemplate.objects.create(
            task_name=request.POST["task_name"],
            assigned_to=request.POST["assigned_to"],
            sla_days=int(request.POST["sla_days"]),
            sla_type=request.POST["sla_type"],
            sort_order=int(request.POST.get("sort_order", 0)),
        )
        messages.success(request, "Template added.")
        return redirect("template_list")
    return render(request, "tracker/template_form.html")


def template_edit(request, template_id):
    tmpl = get_object_or_404(TaskTemplate, id=template_id)
    if request.method == "POST":
        tmpl.task_name = request.POST["task_name"]
        tmpl.assigned_to = request.POST["assigned_to"]
        tmpl.sla_days = int(request.POST["sla_days"])
        tmpl.sla_type = request.POST["sla_type"]
        tmpl.sort_order = int(request.POST.get("sort_order", 0))
        tmpl.save()
        messages.success(request, "Template updated.")
        return redirect("template_list")
    return render(request, "tracker/template_form.html", {"tmpl": tmpl})


@require_POST
def template_inline_save(request, template_id):
    tmpl = get_object_or_404(TaskTemplate, id=template_id)
    tmpl.task_name = request.POST.get("task_name", tmpl.task_name)
    tmpl.assigned_to = request.POST.get("assigned_to", tmpl.assigned_to)
    tmpl.sla_days = int(request.POST.get("sla_days", tmpl.sla_days))
    tmpl.sla_type = request.POST.get("sla_type", tmpl.sla_type)
    tmpl.sort_order = int(request.POST.get("sort_order", tmpl.sort_order))
    tmpl.save()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    return redirect("template_list")


@require_POST
def template_delete(request, template_id):
    tmpl = get_object_or_404(TaskTemplate, id=template_id)
    tmpl.delete()
    messages.success(request, "Template deleted.")
    return redirect("template_list")


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
        positional = ["task_name", "assigned_to", "sla_days", "sla_type", "sort_order"]
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
def template_bulk_upload(request):
    csv_text, source = _resolve_csv_source(request)
    if not csv_text:
        messages.error(request, "Provide a CSV file or paste CSV text before uploading.")
        return redirect("template_list")

    _, records, warnings = _parse_bulk_csv(csv_text)

    created = 0
    for record in records:
        TaskTemplate.objects.create(
            task_name=record["task_name"],
            assigned_to=record["assigned_to"],
            sla_days=record["sla_days"],
            sla_type=record["sla_type"],
            sort_order=record.get("sort_order", 0),
        )
        created += 1

    if created:
        messages.success(
            request,
            f"Bulk upload from {source}: created {created} template(s)."
            + (f" {len(warnings)} warning(s)." if warnings else ""),
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
