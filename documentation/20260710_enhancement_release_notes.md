# Enhancement Release Notes — 2026-07-10

This release implements the items in
`feat_requirements/20260710_enhancement.md`. Highlights: a new `Group`
dimension for tasks and templates, collapsible group UI in both the
task table and the Gantt chart, Prev/Next month navigation, and a
correctness fix for Gantt bar alignment.

## What's new for users

### 1. Prev / Next month buttons
The Tasks and Dashboard tabs both gain two buttons flanking the existing
year/month picker: **‹ Prev** and **Next ›**. Clicking either submits
the existing month form with the prior or subsequent month pre-filled,
so the session-stored month (and the underlying `set_month` endpoint)
does the actual switch. The Year input and **Go** button still work as
before — nothing about the existing flow changed.

### 2. Groups (E2 / E2.1 / E3)
Tasks and templates can now be assigned to a named Group. A Group is
pure organizational metadata — it does not affect SLA calculation or
generation.

**Templates tab — new "Manage Groups" section.** A collapsible panel
above the templates table lets you add, edit, and delete groups.
Each group row exposes name + sort_order + a count of linked
templates; deleting a group unlinks (does not delete) any linked
templates or tasks. The existing templates table also gains a "Group"
column with an inline-edit dropdown.

**Tasks tab — collapsible groups.** The Tasks tab is reorganised by
group. The Gantt chart and the task table now both render one
`<details>` block per group:

```
[Gantt]  [▾ Alpha   2/5 done  ╞═════════════╡ ]   ← group summary row + bar
              Monthly report   ████
              Backup check     ███
[Gantt]  [▾ Beta    3/3 done  ╞═════════════════╡ ]
              …
[Table]  ┌──────────────────────────────────────┐
         │ ▾ Alpha — 2/5 done                   │   ← click to expand
         │   …child task rows…                  │
         ├──────────────────────────────────────┤
         │ ▸ Beta — 3/3 done                    │
         └──────────────────────────────────────┘
```

Each block is collapsible. An "Expand all" / "Collapse all" button
sits in the Gantt card header and affects every block at once.

**Group bar (E2.1).** When a group is collapsed, the Gantt shows a
single bar for the whole group:
- **Start** = earliest `scheduled_date` in the group.
- **End** = the next-closest upcoming unfinished `scheduled_date`. If
  everything is past-due, falls back to the latest `scheduled_date`.
  If everything is completed, falls back to the latest
  `completion_date`.
- **Color** = green if every task in the group is finished, red if any
  task is past-due, amber otherwise.

When a group is expanded, child task bars render under the group bar.

**Synthetic "Ungrouped" bucket.** Tasks without a `group` row up at
the end in a single collapsible block labelled `Ungrouped`. There is no
real `Group` row for this — it's handled in the view layer so the
group-management UI doesn't show a confusing entry.

### 3. sort_order uniqueness (E4)
`TaskTemplate.sort_order` is no longer allowed to contain duplicates.
Submitting an order that's already in use shifts the existing row at
that order (and every row above it) up by 1, so the new template lands
at the requested slot:

```
Before:  A=1, B=2, C=3
Add new template with sort_order=2
After:   A=1, NEW=2, B=3, C=4
```

This applies everywhere a sort_order is written: `template_add`,
`template_edit`, `template_inline_save`, and `template_bulk_upload`.
Empty / zero / negative inputs append at the end. When a shift
happens, a `messages.info` line tells you how many rows were
reordered.

Pre-existing duplicates in the dev DB (rows at the same sort_order
from before this rule) are left in place — they will normalize
themselves the next time you add or edit a row whose order lands in
the same range.

### 4. Gantt bar / day-rule alignment (B1)
The bars in the Gantt chart now line up with the day-rule across the
top regardless of viewport size. Previously, the day cells stretched
with `flex: 1` while bars stayed at a fixed pixel width — they
diverged whenever the window wasn't exactly the right size. The Gantt
is now wrapped in a single canvas with an explicit computed width, so
both the header cells and the bars share one coordinate system.

---

## Schema changes (migration `0003_group_task_group_tasktemplate_group`)

A new `Group` model and two nullable FKs. All additive — existing rows
get `group=NULL`.

| Table | Column | Type | Notes |
|---|---|---|---|
| `tracker_group` | `id` | `BIGINT PK` | auto-increment |
| `tracker_group` | `name` | `VARCHAR(120)` | `UNIQUE` (case-sensitive) |
| `tracker_group` | `sort_order` | `INTEGER` | default `0`, ordering key |
| `tracker_group` | `created_at` | `DATETIME` | `auto_now_add` |
| `tracker_task` | `group_id` | `BIGINT NULL FK→tracker_group` | `ON DELETE SET NULL` |
| `tracker_tasktemplate` | `group_id` | `BIGINT NULL FK→tracker_group` | `ON DELETE SET NULL` |

`Group` is exposed in Django admin with inline `sort_order` editing;
`Task` / `TaskTemplate` admin list views gain `group` as a filterable
column.

---

## New endpoints

| Method | Route | View | Description |
|---|---|---|---|
| POST | `/groups/add/` | `group_add` | Create a group; runs the same `sort_order` shifting as templates. |
| POST | `/groups/<id>/edit/` | `group_edit` | Update name + sort_order. |
| POST | `/groups/<id>/inline-save/` | `group_inline_save` | AJAX-friendly edit (JSON response). |
| POST | `/groups/<id>/delete/` | `group_delete` | Delete; reports unlinked template/task counts. |

There is no `GET /groups/` route — group CRUD is reached via the
"Manage Groups" section embedded in `/templates/`.

`template_form.html`, `template_add`, `template_edit`,
`template_inline_save`, and `template_bulk_upload` all gained an
optional `group` (or `group_id`) form field. Omitting it leaves the
template ungrouped.

---

## Implementation notes

- **Group-bar algorithm** lives in `_build_group_block` in
  `tracker/views.py:46`. The function is the single source of truth
  for both the Gantt geometry and the summary counts; the template
  iterates the resulting `group_blocks` for both sections.
- **Sync between Gantt `<details>` and table `<tr>`s** is handled by
  a small JS handler at the bottom of `task_list.html` that listens
  for native `toggle` events and propagates them. Expand-all /
  Collapse-all just iterate both selectors at once.
- **sort_order shifting helper** is `_assign_template_sort_order` in
  `tracker/views.py:454`; the same algorithm is mirrored as
  `_assign_group_sort_order` for groups. Both run inside
  `transaction.atomic()` and use `F('sort_order') + 1` for the shift
  so concurrent edits don't race.
- **Canvas width** for the Gantt is computed in `task_list` and
  passed as `canvas_width` / `canvas_total_width`. Day cells use
  `flex: 0 0 28px`; tracks get the same width inline. See
  `tracker/static/tracker/css/main.css` lines 44–55.

---

## Tests

`tracker/tests.py` was previously a placeholder. It now ships with
**12 unit tests** across two classes:

- `SortOrderShiftingTests` (7) — collision shifting, free-target
  no-op, blank/zero append-at-end, edit-to-own-order no-op,
  edit-into-taken-slot shifting, empty-table assignment.
- `GroupBarLogicTests` (5) — completed / overdue / pending statuses,
  bar length uses next-closest upcoming due date, bar length uses
  latest when all overdue, ungrouped synthetic block.

Run with:

```bash
uv run python manage.py test tracker
```

---

## Out of scope (flagged in design, deferred)

- **Case-insensitive group-name uniqueness.** Currently `unique=True`
  on the column, which is case-sensitive. "Alpha" and "alpha" are
  distinct. Easy to switch to a `clean()` validator if needed.
- **Collapsible-state persistence.** Native `<details>` state lives
  only on the current page. A cookie or session key could remember
  per-user expansion if that becomes desired.
- **Audit logs for group CRUD.** The existing `AuditLog` is
  Task-only. Group changes are not logged; if needed, the pattern in
  `tracker/views.py:159-164` (`AuditLog.objects.create(task=…,
  action=…, changes=…)`) extends naturally to groups.
- **Bulk-upload `group_name` column.** The templates bulk-upload
  parser accepts a `group_id` (integer) but not `group_name` (string
  lookup). Templates are intended to be assigned to groups via the
  inline-edit dropdown on the templates table; bulk-creating with
  group lookup is a reasonable future addition.

---

## Files touched

```
tracker/admin.py
tracker/migrations/0003_group_task_group_tasktemplate_group.py   (new)
tracker/models.py
tracker/static/tracker/css/main.css
tracker/templates/tracker/dashboard.html
tracker/templates/tracker/task_form.html
tracker/templates/tracker/task_list.html
tracker/templates/tracker/template_form.html
tracker/templates/tracker/template_list.html
tracker/tests.py
tracker/urls.py
tracker/views.py
```

Commits, oldest to newest: `48e5723` (C1/B1), `d484ef5` (C2/E1),
`7c28087` (C3/E4), `656e4be` (C4 — model + migration),
`cecbbe8` (C5 — group CRUD UI), `f662429` (C6 — group-by UI),
`5cde4e6` (C7 — tests).