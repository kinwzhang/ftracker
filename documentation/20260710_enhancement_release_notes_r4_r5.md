# Enhancement Release Notes — Round 4 & 5 (2026-07-10)

This release covers the items in the **Round 4** and **Round 5** sections
of `feat_requirements/20260710_enhancement.md`, plus a few follow-up
polish items that came out of testing.

Round 4 focused on the **Gantt group bar UX** — counts, color-coding,
expand/collapse parity with the task table, and date-bar alignment.
Round 5 tightened the **group bar geometry** and the **expand/collapse
state model**, and added a **Completed At** datetime column. A later
follow-up changed **Calendar Day** SLA semantics to day-of-month and
made the **day-header** more readable.

---

## What's new for users

### 1. Round 4 — Gantt group bar polish

#### E5: Counts + color on the group bar

When the Gantt renders a group, it now shows three pieces of information
on top of the bar:

- The bar's **background color** matches the group's dominant status
  (priority: overdue > pending > completed). Red for any overdue, blue
  for any pending, green if every task is finished.
- A **count overlay** sits inside the bar in white text:
  `x overdue`, `y in progress`, `z completed`. Items with a count of
  zero are hidden so the bar only shows what actually exists in the
  group.
- A matching badge appears on the table's group-summary row using
  saturated solid colors so the heavy text reads on the white card.

The same color and shadow recipe is used as for the per-task bars, so
a group's bar visually reads as "made of these task items".

#### E6: Expand / Collapse all in the task list

The Tasks tab's **Task List** card now has its own `Expand all` /
`Collapse all` buttons, sitting next to `Edit All` in the card header.
The Gantt chart card already had the same pair; each pair only affects
its own card (see B8 below).

#### B6: Date bar / task bar alignment

The day-rule across the top of the Gantt chart now lines up with the
bars below. A 200px placeholder (`day-header-spacer`) inside the
day-header mirrors the `gantt-label` width so the day cells start at
the same x-coordinate as the gantt-track. Resizing the window keeps
both in lockstep.

### 2. Round 5 — Bar geometry + state model

#### B7: Group bar length = longest task

The group bar's **width** now tracks `max(scheduled_date)` across every
task in the group — finished or not. Previously the bar used
`completion_date` for all-completed groups and only unfinished tasks'
`scheduled_date` otherwise, which made the bar shorter than the longest
task in either case.

The bar's **color** is unchanged: dominant status wins
(overdue > pending > completed).

#### B8: Decoupled Gantt / Table expand-collapse

Before: clicking `Expand all` (or a single group) toggled both the
Gantt chart and the task table. The two were kept in sync at all times.

After: each card has its own `Expand all` / `Collapse all`. The Gantt
chart and the task table each maintain their own expand/collapse state.
You can collapse a group in the Gantt while leaving the table view
expanded (or vice versa).

#### B9: Toggle-finished preserves expand state

Before: clicking the **Done** checkbox on a row did
`location.reload()`, which reset every group to "expanded" on the next
paint.

After: the toggle runs in-place. The row's status class updates
(`row-completed` / `row-pending` / `row-overdue`), the **Completed At**
cell updates with the new datetime, and the group's bar + summary
counts are recomputed locally so the whole view stays consistent. Your
expand/collapse choices survive the toggle.

### 3. Round 5 follow-up — Completed At + day-of-month Calendar Day

#### Completed At with HH:MM

- Column header renamed: **Completion** → **Completed At**.
- `Task.completion_time` (a `TimeField`) added via migration
  `0004_task_completion_time`. `Task.completion_date` is unchanged.
- Toggle-finished now stamps both fields with `timezone.localtime()`
  (date + time). The Completed At cell renders
  `YYYY-MM-DD HH:MM` when a time is set, or just `YYYY-MM-DD` for
  date-only rows.
- The edit form's input changed from `type=date` to
  `type=datetime-local`. A new `_parse_completion` helper accepts both
  `"YYYY-MM-DD"` and `"YYYY-MM-DDTHH:MM[:SS]"` and returns
  `(date, time)`.
- The toggle endpoint's JSON response now returns a pre-formatted
  `completion_display` string so the JS can update the cell without
  reloading.

#### Calendar Day = day-of-month (B10)

`Calendar Day, sla_days = N` now means **"due on the Nth day of the
month"**:

| sla_days | Result |
|---|---|
| `1` | 1st of the month |
| `13` | 13th of the month |
| `0` or negative | falls back to `month_start` (defensive) |
| larger than the month has days | clamped to the last day (e.g. Feb 31 → Feb 28) |

The branch never consults `hk_public_holidays` or weekday checks — a
Calendar Day task due on July 1 stays on July 1 even though that's HK
SAR Establishment Day. Working Day semantics are unchanged.

This was previously `month_start + timedelta(days=sla_days)` (offset
semantics: 1 → 2nd, 13 → 14th). All existing tasks retain their stored
`scheduled_date`; only future saves honor the new semantics.

### 4. Day-header readability

The day-rule across the top of the Gantt chart now uses **3-letter
weekday abbreviations** (`Mon`, `Tue`, `Wed`, `Thu`, `Fri`, `Sat`,
`Sun`) instead of single letters, so a quick glance tells you which
side of the weekend you're on.

Public holidays (from `hk_public_holidays(month.year)`) are flagged
with the `holiday` class and rendered in **amber-yellow** so they
stand out from regular red weekend cells. A holiday on a weekend still
reads as a holiday (yellow wins over red).

---

## Schema changes

### Migration `0004_task_completion_time`

| Table | Column | Type | Notes |
|---|---|---|---|
| `tracker_task` | `completion_time` | `TIME NULL` | Set by `task_toggle_finished` alongside `completion_date`. |

No data is backfilled; existing rows have `completion_time = NULL` and
display as date-only in the Completed At cell.

---

## Helper additions in `tracker/views.py`

| Helper | Purpose |
|---|---|
| `_format_completion(task)` | Returns `"YYYY-MM-DD HH:MM"` when time is set, `"YYYY-MM-DD"` for date-only, `""` otherwise. |
| `_parse_completion(value)` | Parses `""`, `"YYYY-MM-DD"`, or `"YYYY-MM-DDTHH:MM[:SS]"` into `(date, time)`. |
| `_assign_group_sort_order(requested, exclude_id=None)` | Same shifting helper as templates, scoped to the `Group` model. Used by the auto-create-groups logic in `template_bulk_upload`. |

The `calculate_scheduled_date` helper in `tracker/holidays.py` was
extended: the `Calendar Day` branch now uses `month_start.replace(day=sla_days)`
with clamping for out-of-range values. The `Working Day` branch is
unchanged. The function's docstring spells out both semantics.

---

## Bulk-upload enhancement — auto-create missing groups

The Templates tab's Bulk Upload modal now **auto-creates any group
referenced in the CSV that doesn't already exist**. Group names are
matched case-insensitively against existing groups; missing names are
created with auto-assigned `sort_order` (slotted in via
`_assign_group_sort_order` so collisions don't happen).

After the upload, the success message lists any auto-created groups:

```
Bulk upload from pasted text: created 13 template(s).
Auto-created group(s): Finance, IT, Operations.
```

This removes the manual "create groups first" step from the bulk
upload workflow.

---

## Implementation notes

- **Group bar rendering** lives in `_build_group_block` in
  `tracker/views.py`. After Round 5 (B7) the function is much smaller
  — the single bar uses `bar_end = max(t.scheduled_date for t in tasks_in_group)`
  clamped to month end, with `status` driven by the dominant-status
  priority.
- **Counts overlay** is rendered inline in `task_list.html` around the
  `<div class="gantt-bar group">`; each count is wrapped in a
  `{% if count %}…{% endif %}` so zero counts are hidden. The
  `gantt-bar-label` flex container keeps the visible counts left-aligned
  with `white-space: nowrap` + `text-overflow: ellipsis` for narrow
  bars.
- **Expand/collapse state model** (B8): the JS now has two helpers,
  `setGanttGroupExpanded` and `setTableGroupExpanded`, each touching
  only one side. The button classes were renamed to
  `js-gantt-{expand,collapse}-all` and `js-table-{expand,collapse}-all`
  so each pair is independently scoped.
- **In-place toggle** (B9): the JS handler at the bottom of
  `task_list.html` walks the group's rows after a successful toggle,
  recomputes `overdue / pending / completed` counts from the DOM, and
  rewrites the table group-summary row's class + counts + the Gantt
  bar's class + overlay text + title tooltip. Adding/removing count
  spans happens via a small `updateCountSpans` helper.
- **Day-header readability**: `views.py:task_list` now populates
  `is_holiday` on each `days_in_month` entry by checking
  `hk_public_holidays(month.year)`. The template applies the
  `holiday` class and the CSS sets amber-yellow font color.

---

## Tests

`tracker/tests.py` now ships with **74 unit tests** across nine
classes:

| Class | Count | Scope |
|---|---|---|
| `SortOrderShiftingTests` | 7 | E4 sort-order shifting. |
| `GroupBarLogicTests` | 11 | E5 + B7: dominant status, per-status counts, bar length uses longest task. |
| `GroupReflectionTests` | 8 | B2: groups propagate to Gantt + task list. |
| `BulkEditTests` | 6 | E4 round 2 + bulk save atomic. |
| `BulkUploadTests` | 5 | Auto-create-groups on CSV upload. |
| `ToggleFinishedResponseTests` | 1 | B9: AJAX response includes `completion_display`. |
| `CompletionDateTimeTests` | 8 | Round-5 follow-up: `_parse_completion`, `_format_completion`, toggle-finished sets time. |
| `CalculateScheduledDateTests` | 9 | B10 + day-of-month semantics for Calendar Day, Working Day skips holidays/weekends. |
| `HolidayCalendarTests` | 16 | B5: HK 2026/2027 holiday gazette pin-down. |

Run with:

```bash
uv run python manage.py test tracker
```

---

## Out of scope / deferred

- **Persist expand/collapse state across reloads.** Currently the
  expand/collapse state is purely client-side. After a hard reload, the
  server still renders every group open. A small session key or cookie
  could remember per-user expansion if that becomes desired; the
  existing `set-month` session pattern extends naturally.
- **Bulk-save `completion_time`.** The bulk-save path reuses
  `_apply_task_updates` which already parses both date and datetime-local
  values via `_parse_completion`, so editing the Completed At column in
  bulk-edit mode works automatically. A regression test for the
  datetime-local branch in bulk-save would be a small addition.
- **Calendar Day semantic for existing tasks.** Existing tasks with
  `scheduled_date = month_start + N` retain that date; only future
  saves use the new day-of-month semantics. A one-shot data migration
  to recompute stored dates could be added if desired.
- **Day-header holiday on weekend precedence.** A holiday-on-weekend
  cell is yellow (holiday wins) rather than red. The current CSS uses
  `.day-cell.holiday.weekend { color: #b45309; }` explicitly. No
  behavioral ambiguity, just noting the rule.

---

## Files touched

```
documentation/20260710_enhancement_release_notes_r4_r5.md  (new)
feat_requirements/20260710_enhancement.md
tracker/holidays.py
tracker/models.py
tracker/migrations/0004_task_completion_time.py           (new)
tracker/static/tracker/css/main.css
tracker/templates/tracker/dashboard.html
tracker/templates/tracker/task_form.html
tracker/templates/tracker/task_list.html
tracker/templates/tracker/template_list.html
tracker/tests.py
tracker/urls.py
tracker/views.py
trigger.py
```