# Monthly Activities Tracker — API & Project Structure

## Project Structure

```
ftracker/
├── config/                                  # Django project configuration
│   ├── __init__.py
│   ├── asgi.py                              # ASGI entry point
│   ├── settings.py                          # Django settings (DB, apps, static, etc.)
│   ├── urls.py                              # Root URL config (routes to tracker.urls)
│   └── wsgi.py                              # WSGI entry point
├── documentation/
│   ├── 0_file_naming_convention.md
│   └── 20260709_api_project_structure.md
├── feat_requirements/
│   └── 20260709_initial_requirement.md
├── tracker/                                 # Main application
│   ├── __init__.py
│   ├── admin.py                             # Admin panel registration
│   ├── apps.py                              # App config
│   ├── holidays.py                          # HK public holiday data + SLA date calculator
│   ├── models.py                            # Task, TaskTemplate, AuditLog models
│   ├── tests.py                             # Placeholder for tests
│   ├── urls.py                              # App-level URL routing
│   ├── views.py                             # All view functions
│   ├── migrations/
│   │   └── 0001_initial.py
│   └── templates/
│       └── tracker/
│           ├── base.html                    # Base template (Bootstrap 5 shell + nav)
│           ├── dashboard.html               # Dashboard with stats, trend, audit log
│           ├── export_report.html           # HTML export template
│           ├── task_form.html               # Add/Edit task form (full page)
│           ├── task_list.html               # Task table + Gantt chart + inline editing
│           ├── template_list.html           # TaskTemplate CRUD list
│           ├── template_form.html           # Add/Edit template form
│           └── holiday_list.html            # HK public holiday browser
├── db.sqlite3                               # SQLite database
├── main.py                                  # Legacy placeholder
├── manage.py                                # Django management script
└── pyproject.toml                           # Python project metadata
```

---

## Database Schema

### Table: `tracker_task`

Stores individual tasks for a given month.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `BIGINT` | `PRIMARY KEY`, `AUTO INCREMENT` | |
| `task_name` | `VARCHAR(255)` | `NOT NULL` | |
| `assigned_to` | `VARCHAR(255)` | `NOT NULL` | |
| `sla_days` | `INTEGER` | `NOT NULL` | Number of days for SLA |
| `sla_type` | `VARCHAR(20)` | `NOT NULL` | `"Business Day"` or `"Calendar Day"` |
| `scheduled_date` | `DATE` | `NOT NULL` | Calculated by `calculate_scheduled_date()` |
| `finished` | `BOOLEAN` | `NOT NULL`, `DEFAULT FALSE` | |
| `completion_date` | `DATE` | `NULLABLE` | Auto-populated when toggled finished |
| `comments` | `TEXT` | `NOT NULL`, `DEFAULT ''` | |
| `month` | `DATE` | `NOT NULL` | First day of the tracking month (e.g. `2026-07-01`) |
| `created_at` | `DATETIME` | `NOT NULL` | Auto-set on insert |
| `updated_at` | `DATETIME` | `NOT NULL` | Auto-updated on update |

**Indexes**: `month`, `finished`, `scheduled_date`

---

### Table: `tracker_tasktemplate`

Template definitions used to generate tasks for new months.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `BIGINT` | `PRIMARY KEY`, `AUTO INCREMENT` | |
| `task_name` | `VARCHAR(255)` | `NOT NULL` | |
| `assigned_to` | `VARCHAR(255)` | `NOT NULL` | |
| `sla_days` | `INTEGER` | `NOT NULL` | |
| `sla_type` | `VARCHAR(20)` | `NOT NULL` | `"Business Day"` or `"Calendar Day"` |
| `sort_order` | `INTEGER` | `NOT NULL`, `DEFAULT 0` | Display ordering |

**Default ordering**: `sort_order ASC`, `task_name ASC`

---

### Table: `tracker_auditlog`

Audit trail recording all task create/update/delete actions.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `BIGINT` | `PRIMARY KEY`, `AUTO INCREMENT` | |
| `task_id` | `BIGINT` | `NULLABLE` | FK → `tracker_task.id`, `ON DELETE SET NULL` |
| `task_name` | `VARCHAR(255)` | `NOT NULL` | Denormalised (preserved after task deletion) |
| `action` | `VARCHAR(50)` | `NOT NULL` | `"created"`, `"updated"`, `"deleted"` |
| `changes` | `JSON` | `NOT NULL` | Stores old/new values for diffs |
| `timestamp` | `DATETIME` | `NOT NULL` | Auto-set on insert |

**Default ordering**: `timestamp DESC`

**`changes` JSON structure**:
- `created`: `{"task_name": "...", "assigned_to": "...", ...}`
- `updated`: `{"old": {...}, "new": {...}}` (only fields that changed)
- `deleted`: `{"task_name": "...", "month": "..."}`

**`readable_message()` method** generates human-readable text like:
- `"Created task 'Monthly Reporting'"`
- `"modified SLA Days from '5' to '10', modified Assigned To from 'Alice' to 'Bob' at 2026-07-09 15:30"`
- `"Deleted task 'Old Task'"`

---

## Entity Relationship

```
TaskTemplate (1) ── used by ──▶ Task (many)
                                    │
                                    │ tracked by
                                    ▼
                               AuditLog (many)
```

- A `Task` belongs to one month (`month` column).
- `TaskTemplate` is standalone; tasks are generated from templates via "Generate Next Month".
- `AuditLog` references `Task` via nullable FK (preserved as `task_name` string when task is deleted).

---

## API Endpoints

| Method | Route | View | Auth | Description |
|---|---|---|---|---|
| GET | `/` | `task_list` | No | Main page: stats bar, Gantt chart, task table |
| POST | `/task/<id>/toggle/` | `task_toggle_finished` | No | Inline toggle finished; auto-sets/clears completion_date |
| POST | `/task/<id>/comment/` | `task_save_comment` | No | Inline save comment (via blur/Enter) |
| GET | `/task/add/` | `task_add` | No | Show full-page add-task form |
| POST | `/task/add/` | `task_add` | No | Create a new task |
| GET | `/task/<id>/edit/` | `task_edit` | No | Show edit form |
| POST | `/task/<id>/edit/` | `task_edit` | No | Update task (recalculates scheduled_date) |
| POST | `/task/<id>/delete/` | `task_delete` | No | Delete a task |
| GET | `/dashboard/` | `dashboard` | No | Summary stats + 6-month trend + audit log |
| POST | `/set-month/` | `set_month` | No | Switch month (`year`, `month` in POST body) |
| POST | `/generate-next-month/` | `generate_next_month` | No | Generate tasks for next month from templates |
| GET | `/templates/` | `template_list` | No | List all task templates |
| GET | `/templates/add/` | `template_add` | No | Show add-template form |
| POST | `/templates/add/` | `template_add` | No | Create a template |
| GET | `/templates/<id>/edit/` | `template_edit` | No | Show edit-template form |
| POST | `/templates/<id>/edit/` | `template_edit` | No | Update template |
| POST | `/templates/<id>/delete/` | `template_delete` | No | Delete template |
| GET | `/holidays/` | `holiday_list` | No | Browse HK public holidays (query: `year`, `month`) |
| GET | `/export/csv/` | `export_csv` | No | Download current month tasks as CSV |
| GET | `/export/html/` | `export_html` | No | Download full report as HTML (tasks + audit trail) |
| GET | `/admin/` | Django admin | Yes | Admin panel |

### Session

The selected month is stored in `request.session["current_month"]` as ISO date `YYYY-MM-DD`. Defaults to the current calendar month.

---

## SLA Date Calculation

`tracker/holidays.calculate_scheduled_date(month_start, sla_days, sla_type)`

- **Calendar Day**: `month_start + sla_days`
- **Business Day**: Counts forward from `month_start`, skipping weekends and HK public holidays, until `sla_days` business days are counted. The day where the count reaches `sla_days` is the scheduled date.

Supported HK public holidays: 2025–2030 (fixed dates + Lunar New Year, Ching Ming, Easter Monday, Buddha's Birthday, Dragon Boat, Mid-Autumn, Chung Yeung, National Day, SAR Establishment Day, Christmas).

---

## Customisation

### Changing the Application Title

The application title "Monthly Activities Tracker" appears in these files:

| File | Location |
|---|---|
| `tracker/templates/tracker/base.html` | `<title>` tag and navbar brand link |
| `tracker/templates/tracker/export_report.html` | `<h1>` heading and footer |
| `documentation/20260709_api_project_structure.md` | Document title |

To change it, search and replace "Monthly Activities Tracker" across those files.

---

## Running the App

```bash
/usr/bin/python3 manage.py runserver 0.0.0.0:8000
```

Admin credentials: `admin` / `admin123`
