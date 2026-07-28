# 2026-07-28 Enhancement examination and worker instruction

Source: [`feat_requirements/20260728_enhancement.md`](../feat_requirements/20260728_enhancement.md)

## Staffing decision

Use **one implementation worker** for this enhancement.

All three feature areas meet in the same integration points:

- `tracker/models.py` and a new migration
- `tracker/views.py`, especially `task_list`, `_build_group_block`, task AJAX handlers,
  and `dashboard`
- `tracker/templates/tracker/task_list.html`
- `tracker/templates/tracker/dashboard.html`
- `tracker/static/tracker/css/main.css`
- `tracker/tests.py`

Two implementation workers working concurrently would repeatedly edit the same monolithic view,
template, JavaScript block, CSS status rules, and test module. The rerun Gantt also needs to fit the
existing task/group Gantt geometry and month filtering, while finished-late changes the same status
calculation and live checkbox update path. Splitting by "backend/frontend" would merely introduce a
blocking contract hand-off; splitting by feature would create direct file conflicts.

If two workers are available, use them **sequentially**:

1. Worker 1 implements the complete enhancement and its tests using this instruction.
2. Worker 2 performs an independent requirement audit, browser/UI check, migration review, and
   regression-test review after Worker 1 has finished. Worker 2 fixes only confirmed omissions or
   regressions.

Do not have both workers implement separate feature slices concurrently.

## Existing behavior that matters

- A task's SLA deadline is currently stored only as `Task.scheduled_date`; there is no SLA-time
  field.
- `sla_days` and `scheduled_date` are currently required database fields. The fix must introduce
  an explicit null/blank representation for "no SLA"; do not overload `0`, because zero already
  has existing calculation behavior.
- A completion is split across `Task.completion_date` and nullable `Task.completion_time`.
- Comments already exist as `Task.comments`, and `task_save_comment` already saves by AJAX. The
  task table currently uses a single-line `<input>` and treats Enter as save.
- Gantt task bars and group summaries are built in `_gantt_bar_for_task` and `_build_group_block`.
  Existing dominant group priority is `overdue > pending > completed`.
- Toggling Done updates the task row and group summary in JavaScript without a page reload.
- The dashboard is month-scoped using the month stored in the session.
- The baseline before this enhancement is 74 passing Django tests.

## Confirmed product decisions

The following decision was confirmed by the product owner on 2026-07-28:

1. **A task may have no SLA. A task without an SLA is never overdue and is never finished late.**
   While unfinished it remains in progress/pending regardless of age; once finished it is a normal
   completed/on-time task.
2. Represent no SLA explicitly as `sla_days = NULL` and `scheduled_date = NULL` on `Task`, and
   `sla_days = NULL` on `TaskTemplate`. A blank form/CSV value means no SLA. Preserve numeric zero
   as a real SLA value with its existing semantics.
3. A no-SLA task has no deadline bar in the ordinary Gantt. It still appears in the group/task
   listing and status counts. Group-bar geometry ignores null scheduled dates; if a group contains
   only no-SLA tasks, render its summary without a deadline bar.

Apply the same behavior to add, edit, inline save, bulk save, bulk upload, next-month generation,
dashboard calculations, exports, and audit display. The migration must retain all existing SLA
values and scheduled dates; it only makes the relevant columns nullable.

## Product decisions still required before implementation

The source requirement does not define the following. Confirm them with the product owner rather
than embedding accidental behavior:

1. **Late cutoff:** There is no "set SLA time" in the schema. Recommended interpretation:
   combine `scheduled_date` with local end-of-day; a task is finished late only when its
   `completion_date` is after `scheduled_date`. A completion later on the scheduled day remains
   on time. If time-of-day lateness is required, add an explicit SLA-time requirement and decide
   whether it belongs to both `TaskTemplate` and `Task`.
2. **System dropdown source:** A dropdown needs a defined list. Recommended design: add a
   manageable `System` model (`name`, `sort_order`, unique name) and a small management UI, rather
   than hard-coding names. Confirm whether Django admin alone is acceptable or whether management
   must appear in the application.
3. **Rerun checkbox semantics:** Recommended behavior: the checkbox is checked when the task has
   one or more saved reruns; checking reveals an unsaved rerun row. Unchecking must not silently
   delete saved history. Saved rows get an explicit Delete action with confirmation.
4. **Incomplete reruns:** Recommended behavior: `triggered_at` is required,
   `completed_at` is nullable while a rerun is active, and `completed_at >= triggered_at` when
   supplied. An active Gantt bar ends at today, clamped to the displayed month.
5. **Dashboard wording:** Interpret "dashboard tag" as the existing **Dashboard tab**.
6. **Rerun statistics:** Recommended minimum statistics are total reruns, completed reruns,
   active reruns, distinct affected tasks, distinct systems, and duration for completed reruns
   (average and maximum). Confirm if another measure is intended.

Once confirmed, record the remaining decisions at the top of this file before coding. If the owner explicitly
accepts the recommended interpretations as a bundle, they become the implementation contract.

## Fix instruction for the current implementation

The first implementation passes its automated tests but is not ready for acceptance. Correct all
items below before doing further polish:

1. **Remove the comment injection path.** In the blur-save JavaScript, never assign user comment
   text to `innerHTML`. Put non-empty comments into `textContent`; create the empty placeholder
   element separately. Add a browser-level or JavaScript-capable regression test if the project
   gains that facility, while retaining server-render escaping tests.
2. **Implement the required per-task rerun checkbox in normal view mode.**
   - unchecked when the task has no saved reruns
   - checked when it has one or more saved reruns
   - checking reveals the System, Triggered At, and Completed At editor and prepares one new row
   - checking an already-populated task reveals its saved rows
   - unchecking only hides/cancels a new unsaved row; it must not delete saved reruns
   - saved reruns use an explicit confirmed Delete action
   Rerun entry must not depend on entering the general task-row Edit mode.
3. **Put `System rerun` inside the existing Gantt as a real collapsible group**, using the same day
   header and the existing Gantt Expand All/Collapse All controls. Do not render a second,
   disconnected Gantt card.
4. **Make every rerun occurrence distinguishable.** Do not stack 22px bars at one-pixel offsets in
   a 24px track. Allocate lanes/track height for overlapping intervals, or use another layout that
   leaves each interval individually visible and focusable in collapsed and expanded states.
5. **Use one explicit month rule.** For dashboard wording "rerun entries from the month", include
   reruns whose interval overlaps the selected calendar month, based on `triggered_at` through
   `completed_at` (or today for active reruns), regardless of the parent task's tracker month.
   Label the triggering task. Apply the same overlap population to the rerun Gantt and its total so
   the displayed count always equals the plotted entries.
6. **Make top-level status cards internally consistent.** `Completed` is the total of all finished
   tasks; present Finished Late clearly as a subset, or relabel the mutually exclusive green card
   as `Completed On Time`. Never display four cards as though they are exclusive when Completed
   already contains Finished Late. Group wording remains
   `x completed (y on time, z finished late)`.
7. **Keep the Comments table synchronized after blur-save.** Add, update, or remove that task's
   aggregation row immediately after a successful save, including creating/removing the entire
   table when the first/last substantive comment changes. Use DOM text APIs, not HTML interpolation.
8. **Format rerun duration for people.** Render compact days/hours/minutes, not raw seconds. Remove
   the current identical conditional branches. Show both average and maximum duration if those
   confirmed statistics remain in scope.
9. **Implement the confirmed no-SLA behavior** throughout the model, forms, views, Gantt,
   dashboard, generation/import flows, exports, and tests as described above. All comparisons and
   `max(scheduled_date)` operations must safely handle null.

After these corrections, execute the complete implementation contract and verification sections
below. Do not weaken tests merely to accept the current output.

## Implementation contract

### 1. Centralize task status and add Finished Late

1. Add one shared Python helper/property that classifies a task as exactly one of:
   `overdue`, `pending`, `completed`, or `finished_late`.
2. Under the recommended date-based cutoff:
   - no SLA and unfinished → `pending`, never `overdue`
   - no SLA and finished → `completed`, never `finished_late`
   - unfinished and `scheduled_date < today` → `overdue`
   - unfinished and not overdue → `pending`
   - finished and completion date after scheduled date → `finished_late`
   - all other finished tasks → `completed`
3. Handle legacy inconsistent data deterministically. A finished task without a completion date
   should remain `completed`, not crash and not become late.
4. Use the same classification in:
   - task-list row classes
   - individual Gantt bars
   - group summaries and group Gantt bars
   - top-level task counts
   - dashboard statistics where statuses are shown
   - AJAX responses and client-side recomputation after toggling Done
5. Add a fourth visual color which is clearly different from current green, blue, and red and
   remains readable in row tint, task bar, collapsed group bar, expanded group counts, and table
   summary. Amber/orange is the preferred family.
6. Preserve group priority while work is unfinished:
   `overdue > pending > finished_late/completed`.
   When every item is finished, the group status is `finished_late` if any member is late;
   otherwise it is `completed`.
7. For an all-finished group, show exactly the useful equivalent of:
   `x completed (y on time, z finished late)`.
   For groups with unfinished work, retain overdue/in-progress prominence while still making
   completed counts available under the existing responsive-space rules.
8. Update title/accessible text as well as color so late status is not color-only.

### 2. Persist and edit system reruns

1. Add the confirmed system-list model/source and a `SystemRerun` model related to `Task`.
   Recommended fields:
   - `task` foreign key with `related_name="system_reruns"` and cascade delete
   - `system` foreign key using a protective deletion rule
   - `triggered_at` timezone-aware `DateTimeField`
   - nullable `completed_at` timezone-aware `DateTimeField`
   - `created_at` and `updated_at`
2. Add database ordering that produces stable display (`triggered_at`, then primary key).
3. Create a normal Django migration. Do not edit an already-applied migration.
4. Validate on the server:
   - referenced task and system exist
   - triggered time is present and parseable
   - completed time is blank or not earlier than triggered time
   - malformed requests return a useful 400 JSON response for AJAX
5. Add explicit create, update, and delete POST endpoints. Protect all writes with CSRF and
   `@require_POST`. Do not implement writes through GET.
6. Add audit entries for rerun create/update/delete, including task name, system, and timestamps.
   Extend `AuditLog.readable_message` without breaking old log payloads.
7. In each task row:
   - show a System rerun checkbox
   - reveal an editor containing System, Rerun triggered at, and Rerun completed at
   - support multiple rows with a `+` control
   - show existing rows on page load
   - make save/error state visible
   - implement the confirmed non-destructive uncheck/delete behavior
8. Scope all displayed task/rerun data to the selected month through the parent task's `month`.
   Avoid N+1 queries by prefetching reruns and their systems.

### 3. Add the System rerun Gantt group

1. Add a separate collapsible Gantt block labelled `System rerun`; do not mix reruns into ordinary
   task groups.
2. Collapsed state:
   - show the total number of reruns for the selected month
   - plot every rerun occurrence
   - a same-day rerun is a visible one-day marker/bar
   - a multi-day rerun spans trigger day through completion day, inclusive
3. Expanded state:
   - render one row per system
   - show all rerun intervals for that system on its row
   - allow multiple non-overlapping/overlapping intervals without overwriting one another
4. Clip bars to the visible month. Include a rerun when its trigger-to-completion interval
   overlaps the selected calendar month, regardless of the parent task's tracker month. Active
   reruns use today as the provisional interval end. Use this same population for the collapsed
   count and dashboard aggregation.
5. Reuse the existing day header and percentage geometry. Extract a small geometry helper if that
   prevents duplicate date-clamping logic, but avoid an unrelated Gantt rewrite.
6. Give rerun bars and counts accessible labels/tooltips containing system, task, trigger time,
   completion/active state, and duration.

### 4. Add dashboard rerun aggregation

1. Add a System rerun section to `dashboard.html` for the selected month.
2. Render an aggregation table containing every rerun entry with at least:
   task, system, triggered at, completed at/status, and duration.
3. Render the confirmed summary statistics above or beside the entries.
4. Order entries predictably, newest trigger first.
5. Show a clear empty state rather than hiding the whole section.
6. Prefetch/select related records; do not query once per table row.

### 5. Finish the comment requirement

1. Replace the task-list single-line comment input with a `<textarea>`.
2. Enter inserts a newline. It must no longer submit/save the comment.
3. Save on blur through the existing comment endpoint. Preserve line breaks in storage and
   rendering; use escaped template output plus CSS such as `white-space: pre-wrap`, never
   `innerHTML` built from user comment text.
4. Handle failed saves visibly and preserve the user's unsaved text for retry.
5. Below the task list, render a Comments table only when at least one task in the selected month
   has a non-empty comment. Columns: `Task Name` and `Comment`.
6. Treat whitespace-only comments as empty for whether the table appears.
7. Render multiline text faithfully and safely. Do not mark user text safe.
8. Keep Edit All behavior functional with textarea values, or deliberately use the same textarea
   for quick edit and bulk edit so two controls cannot diverge.

## Tests and verification

Add focused tests before considering the work complete:

### Status tests

- unfinished no-SLA task remains pending before and after the current date
- finished no-SLA task is completed/on time, regardless of completion date
- blank SLA survives add/edit/inline save/bulk save/template upload/month generation
- numeric zero remains distinct from blank/no SLA
- no-SLA tasks do not crash individual/group Gantt geometry
- a group containing only no-SLA tasks renders a summary without a deadline bar
- completion before/on/after the scheduled date
- completion time on the scheduled date under the confirmed cutoff
- finished legacy task with no completion date
- all-finished group: all on time
- all-finished group: mixed on-time and late
- unfinished overdue/pending continues to dominate an otherwise late-completed group
- task-list and dashboard counts use the same classification
- toggle-finished JSON provides enough status/count data for a correct no-reload update

### Rerun model and endpoint tests

- create one and multiple reruns for a task
- update an existing rerun
- delete requires POST and removes only the target rerun
- missing/unknown system and invalid datetime are rejected
- completion earlier than trigger is rejected
- incomplete rerun behavior
- cross-task tampering cannot update/delete the wrong nested record
- selected-month scoping and query behavior

### Gantt tests

- same-day, multi-day, cross-month-clipped, and active rerun geometry
- collapsed total and expanded per-system grouping
- multiple reruns for one system remain distinct
- empty rerun group behavior
- accessible text includes task/system and interval state

### Comment tests

- multiline comment survives POST and rendering
- comment table is absent with no substantive comments
- comment table contains only current-month tasks with substantive comments
- HTML/script-like comment content is escaped

### Full verification

Run:

```bash
python manage.py makemigrations --check
python manage.py check
python manage.py test
```

Also perform a browser smoke check at narrow and desktop widths:

- create, edit, generate, and import tasks with a blank SLA; confirm they never turn red or amber
- toggle tasks among pending, overdue, completed, and finished late
- expand/collapse ordinary and rerun Gantt groups independently
- add/edit/delete multiple reruns
- enter a two-line comment and click elsewhere to save
- switch months and confirm no cross-month leakage
- inspect the Dashboard rerun table and statistics

## Scope guardrails

- Preserve existing task/template/group CRUD, CSV bulk upload, month generation, exports, holidays,
  group sorting, expand/collapse independence, and no-reload Done toggle.
- Do not change the meaning of Working Day or Calendar Day SLA calculations for numeric SLA values.
- Do not treat `0` as no SLA; no SLA is represented by null/blank.
- Do not add a frontend build system or external runtime dependency.
- Do not silently delete rerun history.
- Do not use color as the only status signal.
- Keep user-entered comments escaped.
- Avoid opportunistic refactors outside the touched behavior.
- Update exports only if the product owner confirms reruns/late status must be included; the source
  requirement names the task list, Gantt, comments table, and dashboard, but does not name exports.

## Likely files

- `tracker/models.py`
- `tracker/migrations/0005_*.py`
- `tracker/admin.py` (if systems are admin-managed)
- `tracker/views.py`
- `tracker/urls.py`
- `tracker/templates/tracker/task_list.html`
- `tracker/templates/tracker/dashboard.html`
- `tracker/static/tracker/css/main.css`
- `tracker/tests.py` (splitting new feature tests into dedicated modules is acceptable)
- `documentation/20260728_enhancement_release_notes.md`

## Worker completion report

The worker must report:

1. confirmed product decisions and any deviations from the recommended interpretations
2. schema and migration changes
3. endpoints and UI behavior added
4. automated test commands and exact results
5. browser checks performed
6. any remaining ambiguity, limitation, or follow-up
