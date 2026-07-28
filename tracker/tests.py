from datetime import date, time, timedelta
from datetime import datetime as dt
from zoneinfo import ZoneInfo

import json

from django.test import Client, TestCase
from django.utils import timezone

from .models import AuditLog, Group, System, SystemRerun, Task, TaskTemplate
from .views import _assign_template_sort_order, _build_group_block, task_status


class SortOrderShiftingTests(TestCase):
    """E4 — sort_order must remain unique; inserting a duplicate shifts
    existing rows with sort_order >= target up by one. The helper picks an
    order and shifts; the caller is responsible for actually creating /
    updating the row at that order. These tests mirror what the views do."""

    def setUp(self):
        # Existing rows at sort_orders 1, 2, 3.
        TaskTemplate.objects.create(task_name="A", assigned_to="x", sla_days=1, sla_type="Working Day", sort_order=1)
        TaskTemplate.objects.create(task_name="B", assigned_to="x", sla_days=1, sla_type="Working Day", sort_order=2)
        TaskTemplate.objects.create(task_name="C", assigned_to="x", sla_days=1, sla_type="Working Day", sort_order=3)

    def _orders(self):
        return list(
            TaskTemplate.objects.order_by("sort_order", "id").values_list("sort_order", "task_name")
        )

    def _add_at(self, name, requested_order):
        """Mirror what the views do: ask the helper for an order, then create the row."""
        actual, _shifted = _assign_template_sort_order(requested_order)
        TaskTemplate.objects.create(
            task_name=name, assigned_to="x", sla_days=1, sla_type="Working Day",
            sort_order=actual,
        )
        return actual

    def test_insert_at_taken_target_shifts_existing(self):
        # New row "X" wants order 2; B (was 2) -> 3; C (was 3) -> 4.
        actual = self._add_at("X", 2)
        self.assertEqual(actual, 2)
        self.assertEqual(
            self._orders(),
            [(1, "A"), (2, "X"), (3, "B"), (4, "C")],
        )

    def test_insert_at_free_target_no_shift(self):
        actual = self._add_at("X", 5)
        self.assertEqual(actual, 5)
        self.assertEqual(self._orders(), [(1, "A"), (2, "B"), (3, "C"), (5, "X")])

    def test_blank_requested_appends_at_end(self):
        actual = self._add_at("X", None)
        self.assertEqual(actual, 4)
        self.assertEqual(self._orders(), [(1, "A"), (2, "B"), (3, "C"), (4, "X")])

    def test_zero_requested_appends_at_end(self):
        actual = self._add_at("X", 0)
        self.assertEqual(actual, 4)
        self.assertEqual(self._orders(), [(1, "A"), (2, "B"), (3, "C"), (4, "X")])

    def test_edit_to_own_order_is_noop(self):
        # Edit A (currently at 1) to its own order 1.
        a_id = TaskTemplate.objects.get(task_name="A").id
        actual, shifted = _assign_template_sort_order(1, exclude_id=a_id)
        self.assertEqual(actual, 1)
        self.assertEqual(shifted, 0)
        # Caller writes the row at 1 — no observable change.
        TaskTemplate.objects.filter(id=a_id).update(sort_order=actual)
        self.assertEqual(self._orders(), [(1, "A"), (2, "B"), (3, "C")])

    def test_edit_into_taken_slot_shifts(self):
        a_id = TaskTemplate.objects.get(task_name="A").id
        actual, shifted = _assign_template_sort_order(3, exclude_id=a_id)
        self.assertEqual(actual, 3)
        self.assertEqual(shifted, 1)
        TaskTemplate.objects.filter(id=a_id).update(sort_order=actual)
        # B was at 2 (unchanged), C was at 3 -> 4, A now at 3.
        self.assertEqual(
            self._orders(),
            [(2, "B"), (3, "A"), (4, "C")],
        )

    def test_empty_table_assigns_one(self):
        TaskTemplate.objects.all().delete()
        actual, shifted = _assign_template_sort_order(None)
        self.assertEqual(actual, 1)
        self.assertEqual(shifted, 0)


class GroupBarLogicTests(TestCase):
    """E5 — group bar geometry, dominant status, and per-status counts."""

    def _make(self, name, scheduled_offset, finished=False, completion_offset=None):
        today = date(2026, 7, 10)
        scheduled = today + timedelta(days=scheduled_offset)
        completion = today + timedelta(days=completion_offset) if completion_offset is not None else None
        return Task.objects.create(
            task_name=f"task-{name}",
            assigned_to="x",
            sla_days=1,
            sla_type="Working Day",
            scheduled_date=scheduled,
            finished=finished,
            completion_date=completion,
            month=date(2026, 7, 1),
        )

    def _build(self, group, tasks, today=None):
        if today is None:
            today = date(2026, 7, 10)
        return _build_group_block(
            group, tasks, today, date(2026, 7, 1), pixel_per_day=28, total_days=31,
        )

    # --- E5: dominant status -------------------------------------------------

    def test_group_status_completed_when_all_done(self):
        group = Group.objects.create(name="G")
        t1 = self._make("a", -5, finished=True, completion_offset=-5)
        t2 = self._make("b", -3, finished=True, completion_offset=-3)
        for t in (t1, t2):
            t.group = group; t.save()
        block = self._build(group, [t1, t2])
        self.assertEqual(block["summary"]["status"], "completed")
        self.assertEqual(block["group_bar"]["status"], "completed")

    def test_group_status_overdue_when_any_overdue(self):
        group = Group.objects.create(name="G")
        t1 = self._make("a", -2)              # overdue
        t2 = self._make("b", 3)               # pending
        for t in (t1, t2):
            t.group = group; t.save()
        block = self._build(group, [t1, t2])
        self.assertEqual(block["summary"]["status"], "overdue")
        self.assertEqual(block["group_bar"]["status"], "overdue")

    def test_group_status_pending_when_no_overdue_no_completed(self):
        group = Group.objects.create(name="G")
        t1 = self._make("a", 1)
        t2 = self._make("b", 5)
        for t in (t1, t2):
            t.group = group; t.save()
        block = self._build(group, [t1, t2])
        self.assertEqual(block["summary"]["status"], "pending")
        self.assertEqual(block["group_bar"]["status"], "pending")

    def test_dominant_status_overdue_wins_over_completed(self):
        # 1 finished + 1 overdue → overdue wins (priority overdue > pending > completed).
        group = Group.objects.create(name="G")
        done = self._make("done", -5, finished=True, completion_offset=-5)
        overdue = self._make("late", -2)
        for t in (done, overdue):
            t.group = group; t.save()
        block = self._build(group, [done, overdue])
        self.assertEqual(block["summary"]["status"], "overdue")
        self.assertEqual(block["group_bar"]["status"], "overdue")

    def test_dominant_status_pending_wins_over_completed(self):
        # 1 finished + 1 pending (no overdue) → pending wins.
        group = Group.objects.create(name="G")
        done = self._make("done", -5, finished=True, completion_offset=-5)
        pending = self._make("soon", 3)
        for t in (done, pending):
            t.group = group; t.save()
        block = self._build(group, [done, pending])
        self.assertEqual(block["summary"]["status"], "pending")
        self.assertEqual(block["group_bar"]["status"], "pending")

    # --- E5: per-status counts ----------------------------------------------

    def test_counts_split_correctly_for_mixed_group(self):
        # 1 overdue, 2 pending, 1 completed → 4 total.
        group = Group.objects.create(name="G")
        overdue = self._make("o", -1)
        pending_a = self._make("pa", 2)
        pending_b = self._make("pb", 5)
        done = self._make("done", -3, finished=True, completion_offset=-3)
        for t in (overdue, pending_a, pending_b, done):
            t.group = group; t.save()
        block = self._build(group, [overdue, pending_a, pending_b, done])
        s = block["summary"]
        self.assertEqual(s["total"], 4)
        self.assertEqual(s["overdue"], 1)
        self.assertEqual(s["pending"], 2)
        self.assertEqual(s["completed"], 1)

    def test_counts_all_completed(self):
        group = Group.objects.create(name="G")
        t1 = self._make("a", -5, finished=True, completion_offset=-5)
        t2 = self._make("b", -3, finished=True, completion_offset=-3)
        for t in (t1, t2):
            t.group = group; t.save()
        block = self._build(group, [t1, t2])
        self.assertEqual(block["summary"]["completed"], 2)
        self.assertEqual(block["summary"]["pending"], 0)
        self.assertEqual(block["summary"]["overdue"], 0)

    def test_counts_all_overdue(self):
        group = Group.objects.create(name="G")
        t1 = self._make("a", -5)
        t2 = self._make("b", -2)
        for t in (t1, t2):
            t.group = group; t.save()
        block = self._build(group, [t1, t2])
        self.assertEqual(block["summary"]["overdue"], 2)
        self.assertEqual(block["summary"]["pending"], 0)
        self.assertEqual(block["summary"]["completed"], 0)

    # --- E5: bar geometry ----------------------------------------------------

    def test_group_bar_always_starts_at_day_one(self):
        # Per Round-3 clarification: bar always starts at day 1 of the month
        # even if the first unfinished task is later in the month.
        group = Group.objects.create(name="G")
        late = self._make("late", 15)
        earlier = self._make("earlier", 12)
        for t in (late, earlier):
            t.group = group; t.save()
        block = self._build(group, [late, earlier])
        seg = block["group_bar"]
        self.assertAlmostEqual(seg["start_offset"], (0.15 / 31) * 100, places=1)

    def test_group_bar_pending_spans_to_latest_unfinished(self):
        # All pending → bar from day 1 to latest pending scheduled_date.
        group = Group.objects.create(name="G")
        t1 = self._make("a", 1)
        t2 = self._make("b", 5)
        for t in (t1, t2):
            t.group = group; t.save()
        block = self._build(group, [t1, t2])
        seg = block["group_bar"]
        # Jul 1 → Jul 15 (today + 5) inclusive = 15 days.
        self.assertAlmostEqual(seg["width"], (15 - 0.3) / 31 * 100, places=1)
        self.assertEqual(seg["status"], "pending")

    def test_group_bar_completed_spans_to_latest_scheduled_date(self):
        # B7: even when all tasks are finished, the bar length tracks the
        # longest task's scheduled_date (not completion_date). This keeps
        # the group's bar visually aligned with its individual task bars,
        # which always span from day 1 to scheduled_date.
        group = Group.objects.create(name="G")
        t1 = self._make("a", -5, finished=True, completion_offset=-5)
        t2 = self._make("b", -3, finished=True, completion_offset=-3)
        for t in (t1, t2):
            t.group = group; t.save()
        block = self._build(group, [t1, t2])
        seg = block["group_bar"]
        # Latest scheduled_date = today-3 = Jul 7. Jul 1 → Jul 7 = 7 days.
        self.assertAlmostEqual(seg["width"], (7 - 0.3) / 31 * 100, places=1)
        self.assertEqual(seg["status"], "completed")

    def test_group_bar_includes_finished_tasks_scheduled_dates(self):
        # B7: a finished task with a LATER scheduled_date than the
        # unfinished tasks must extend the bar to that later date, even
        # though the finished task contributes no "unfinished work" to the
        # group's current status. Previously the bar only considered the
        # unfinished tasks' scheduled_dates.
        group = Group.objects.create(name="G")
        long_finished = self._make(
            "long-done", 10, finished=True, completion_offset=5,
        )
        # Unfinished tasks all within the next few days.
        short_pending = self._make("soon", 3)
        for t in (long_finished, short_pending):
            t.group = group; t.save()
        block = self._build(group, [long_finished, short_pending])
        seg = block["group_bar"]
        # The bar extends to Jul 20 (today + 10), the longest task in the
        # group, even though that task is finished.
        # Jul 1 → Jul 20 inclusive = 20 days.
        self.assertAlmostEqual(seg["width"], (20 - 0.3) / 31 * 100, places=1)

    def test_group_bar_overdue_uses_latest_unfinished_scheduled(self):
        # Has overdue → single overdue-colored bar from day 1 to latest unfinished.
        group = Group.objects.create(name="G")
        overdue_a = self._make("a", -5)
        overdue_b = self._make("b", -2)
        for t in (overdue_a, overdue_b):
            t.group = group; t.save()
        block = self._build(group, [overdue_a, overdue_b])
        seg = block["group_bar"]
        self.assertEqual(seg["status"], "overdue")
        # Jul 1 → Jul 8 (today + -2) = 8 days.
        self.assertAlmostEqual(seg["width"], (8 - 0.3) / 31 * 100, places=1)

    def test_completed_tasks_do_not_extend_mixed_group_bar(self):
        # A finished task earlier than the unfinished ones must not pull the
        # bar left; the bar still spans from day 1 to the latest unfinished.
        group = Group.objects.create(name="G")
        finished_far_ago = self._make(
            "done", -20, finished=True, completion_offset=-20,
        )
        pending_late = self._make("late", 4)
        early_pending = self._make("early", 2)
        for t in (finished_far_ago, pending_late, early_pending):
            t.group = group; t.save()
        block = self._build(group, [finished_far_ago, pending_late, early_pending])
        seg = block["group_bar"]
        # No overdue → single solid pending bar from day 1 to latest pending.
        self.assertEqual(seg["status"], "pending")
        # Jul 1 → Jul 14 (today + 4) = 14 days.
        self.assertAlmostEqual(seg["width"], (14 - 0.3) / 31 * 100, places=1)

    def test_ungrouped_block_renders_when_no_group(self):
        t1 = self._make("a", 1)
        block = self._build(None, [t1])
        self.assertIsNone(block["group"])
        self.assertEqual(block["id"], 0)
        self.assertEqual(block["summary"]["status"], "pending")
        self.assertIsNotNone(block["group_bar"])

    def test_empty_group_has_no_bar(self):
        # A group with zero tasks shouldn't render a bar at all.
        group = Group.objects.create(name="Empty")
        block = self._build(group, [])
        self.assertIsNone(block["group_bar"])
        self.assertEqual(block["summary"]["total"], 0)


class GroupReflectionTests(TestCase):
    """B2 — Groups are created and tasks are assigned with groups but the
    assignment never propagates to the Gantt chart or task lists.

    Root causes the tests guard against:
      * ``generate_next_month`` ignored the template's ``group_id``,
        so auto-generated tasks landed in "Ungrouped" forever.
      * Manual add / inline-save / full edit endpoints all dropped
        ``group_id``, so users could never reassign groups from the UI.
    """

    def setUp(self):
        self.month = date(2026, 7, 1)
        self.next_month = date(2026, 8, 1)
        self.g1 = Group.objects.create(name="G1", sort_order=1)
        self.g2 = Group.objects.create(name="G2", sort_order=2)

    # --- generate_next_month -------------------------------------------------

    def _set_session_month(self, client):
        session = client.session
        session["current_month"] = self.month.isoformat()
        session.save()

    def test_generate_next_month_copies_group_from_template(self):
        # Templates with groups should produce tasks with the same group.
        TaskTemplate.objects.create(
            task_name="T1", assigned_to="x", sla_days=1, sla_type="Working Day",
            sort_order=1, group=self.g1,
        )
        TaskTemplate.objects.create(
            task_name="T2", assigned_to="x", sla_days=1, sla_type="Working Day",
            sort_order=2, group=self.g2,
        )
        client = Client()
        self._set_session_month(client)
        client.post("/generate-next-month/")
        created = {t.task_name: t for t in Task.objects.filter(month=self.next_month)}
        self.assertEqual(created["T1"].group_id, self.g1.id)
        self.assertEqual(created["T2"].group_id, self.g2.id)
        # Now the Gantt/task-list view should put T1/T2 in their group blocks
        # rather than the synthetic ungrouped bucket.
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        # Both group names must appear as group-summary headers.
        self.assertIn("G1", body)
        self.assertIn("G2", body)

    def test_generate_next_month_copies_group_from_previous_month(self):
        # When there are no templates, group assignment on existing tasks
        # should propagate to the next month (so ungroups don't get reset).
        Task.objects.create(
            task_name="T1", assigned_to="x", sla_days=1, sla_type="Working Day",
            scheduled_date=self.month, month=self.month, group=self.g1,
        )
        client = Client()
        self._set_session_month(client)
        client.post("/generate-next-month/")
        t = Task.objects.get(task_name="T1", month=self.next_month)
        self.assertEqual(t.group_id, self.g1.id)

    # --- task_add ----------------------------------------------------------

    def test_task_add_persists_group(self):
        client = Client()
        self._set_session_month(client)
        response = client.post("/task/add/", {
            "task_name": "New task",
            "assigned_to": "Alice",
            "sla_days": "1",
            "sla_type": "Working Day",
            "comments": "",
            "group": str(self.g1.id),
        })
        self.assertEqual(response.status_code, 302)
        task = Task.objects.get(task_name="New task")
        self.assertEqual(task.group_id, self.g1.id)

    def test_task_add_blank_group_is_ungrouped(self):
        client = Client()
        self._set_session_month(client)
        client.post("/task/add/", {
            "task_name": "Ungrouped task",
            "assigned_to": "Alice",
            "sla_days": "1",
            "sla_type": "Working Day",
            "comments": "",
            "group": "",
        })
        task = Task.objects.get(task_name="Ungrouped task")
        self.assertIsNone(task.group_id)

    # --- task_inline_save --------------------------------------------------

    def test_task_inline_save_updates_group(self):
        task = Task.objects.create(
            task_name="X", assigned_to="x", sla_days=1, sla_type="Working Day",
            scheduled_date=self.month, month=self.month,
        )
        client = Client()
        self._set_session_month(client)
        response = client.post(
            f"/task/{task.id}/inline-save/",
            {
                "task_name": "X", "assigned_to": "x",
                "sla_days": "1", "sla_type": "Working Day",
                "completion_date": "", "comments": "",
                "group": str(self.g2.id),
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.group_id, self.g2.id)

    # --- task_edit ---------------------------------------------------------

    def test_task_edit_updates_group(self):
        task = Task.objects.create(
            task_name="X", assigned_to="x", sla_days=1, sla_type="Working Day",
            scheduled_date=self.month, month=self.month,
        )
        client = Client()
        self._set_session_month(client)
        client.post(
            f"/task/{task.id}/edit/",
            {
                "task_name": "X", "assigned_to": "x",
                "sla_days": "1", "sla_type": "Working Day",
                "completion_date": "", "comments": "",
                "group": str(self.g2.id),
            },
        )
        task.refresh_from_db()
        self.assertEqual(task.group_id, self.g2.id)

    # --- the Gantt/block view itself ---------------------------------------

    def test_task_list_view_puts_grouped_tasks_into_their_block(self):
        # Tasks assigned to g1 must appear in the g1 block, not Ungrouped.
        t1 = Task.objects.create(
            task_name="in-g1", assigned_to="x", sla_days=1, sla_type="Working Day",
            scheduled_date=date(2026, 7, 5), month=self.month, group=self.g1,
        )
        t2 = Task.objects.create(
            task_name="also-in-g1", assigned_to="x", sla_days=1, sla_type="Working Day",
            scheduled_date=date(2026, 7, 6), month=self.month, group=self.g1,
        )
        t_orphan = Task.objects.create(
            task_name="orphan", assigned_to="x", sla_days=1, sla_type="Working Day",
            scheduled_date=date(2026, 7, 7), month=self.month,
        )
        client = Client()
        self._set_session_month(client)
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        blocks = response.context["group_blocks"]
        # Find the g1 block.
        g1_blocks = [b for b in blocks if b["group"] and b["group"].id == self.g1.id]
        self.assertEqual(len(g1_blocks), 1)
        g1_task_ids = {t.id for t in g1_blocks[0]["tasks"]}
        self.assertIn(t1.id, g1_task_ids)
        self.assertIn(t2.id, g1_task_ids)
        # Ungrouped synthetic block holds the orphan.
        ungrouped = [b for b in blocks if b["group"] is None]
        self.assertEqual(len(ungrouped), 1)
        self.assertIn(t_orphan.id, {t.id for t in ungrouped[0]["tasks"]})


class BulkEditTests(TestCase):
    """E4 Round 2 — bulk-save endpoints take a JSON list of updates and
    apply them atomically. The single-row ``task_inline_save`` /
    ``template_inline_save`` flows stay intact (re-exercised by the rest of
    the suite); these tests focus on the new multi-row endpoints."""

    def setUp(self):
        self.month = date(2026, 7, 1)
        self.g1 = Group.objects.create(name="G1", sort_order=1)
        self.g2 = Group.objects.create(name="G2", sort_order=2)
        self.tasks = [
            Task.objects.create(
                task_name=f"task-{i}", assigned_to="x", sla_days=1, sla_type="Working Day",
                scheduled_date=self.month, month=self.month,
            )
            for i in range(3)
        ]
        self.tmpls = [
            TaskTemplate.objects.create(
                task_name=f"tmpl-{i}", assigned_to="x", sla_days=1, sla_type="Working Day",
                sort_order=i + 1,
            )
            for i in range(3)
        ]

    def _set_session_month(self, client):
        session = client.session
        session["current_month"] = self.month.isoformat()
        session.save()

    def _post_json(self, client, url, payload):
        return client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    # --- task_bulk_save -----------------------------------------------------

    def test_task_bulk_save_persists_each_row(self):
        client = Client()
        updates = [
            {"id": t.id, "task_name": f"renamed-{i}", "assigned_to": f"u-{i}",
             "sla_days": 2, "sla_type": "Calendar Day",
             "completion_date": "", "comments": f"c-{i}",
             "group": str(self.g1.id if i % 2 == 0 else self.g2.id)}
            for i, t in enumerate(self.tasks)
        ]
        response = self._post_json(client, "/task/bulk-save/", {"updates": updates})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(set(data["saved"]), {t.id for t in self.tasks})
        for i, t in enumerate(self.tasks):
            t.refresh_from_db()
            self.assertEqual(t.task_name, f"renamed-{i}")
            self.assertEqual(t.assigned_to, f"u-{i}")
            self.assertEqual(t.sla_days, 2)
            self.assertEqual(t.sla_type, "Calendar Day")
            self.assertEqual(t.comments, f"c-{i}")
            expected_group = self.g1.id if i % 2 == 0 else self.g2.id
            self.assertEqual(t.group_id, expected_group)
        # Audit log: one entry per task.
        for t in self.tasks:
            self.assertTrue(
                AuditLog.objects.filter(task=t, action="updated").exists(),
                f"missing audit log for task {t.id}",
            )

    def test_task_bulk_save_atomic_on_error(self):
        client = Client()
        before = {t.id: t.task_name for t in self.tasks}
        # Valid update for task 0, bad sla_days on task 1.
        updates = [
            {"id": self.tasks[0].id, "task_name": "valid-rename",
             "assigned_to": "x", "sla_days": 1, "sla_type": "Working Day",
             "completion_date": "", "comments": "", "group": ""},
            {"id": self.tasks[1].id, "task_name": "bad",
             "assigned_to": "x", "sla_days": "not-a-number", "sla_type": "Working Day",
             "completion_date": "", "comments": "", "group": ""},
        ]
        response = self._post_json(client, "/task/bulk-save/", {"updates": updates})
        self.assertEqual(response.status_code, 400)
        # Neither row was persisted.
        for t in self.tasks:
            t.refresh_from_db()
            self.assertEqual(t.task_name, before[t.id])
            self.assertEqual(
                AuditLog.objects.filter(task=t, action="updated").count(), 0,
            )

    def test_task_bulk_save_no_updates_returns_error(self):
        client = Client()
        response = self._post_json(client, "/task/bulk-save/", {"updates": []})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_template_bulk_save_shifts_sort_orders(self):
        client = Client()
        # tmpls[2] (currently sort_order=3) wants to take sort_order=1.
        # That should shift tmpls[0] 1->2 and tmpls[1] 2->3.
        updates = [
            {"id": self.tmpls[2].id, "task_name": self.tmpls[2].task_name,
             "assigned_to": "x", "sla_days": 1, "sla_type": "Working Day",
             "sort_order": 1, "group": ""},
        ]
        response = self._post_json(client, "/templates/bulk-save/", {"updates": updates})
        self.assertEqual(response.status_code, 200)
        # Reload and check shifts.
        self.tmpls[0].refresh_from_db()
        self.tmpls[1].refresh_from_db()
        self.tmpls[2].refresh_from_db()
        self.assertEqual(self.tmpls[0].sort_order, 2)
        self.assertEqual(self.tmpls[1].sort_order, 3)
        self.assertEqual(self.tmpls[2].sort_order, 1)

    def test_template_bulk_save_updates_group(self):
        client = Client()
        updates = [
            {"id": self.tmpls[0].id, "task_name": self.tmpls[0].task_name,
             "assigned_to": self.tmpls[0].assigned_to,
             "sla_days": self.tmpls[0].sla_days,
             "sla_type": self.tmpls[0].sla_type,
             "sort_order": self.tmpls[0].sort_order,
             "group": str(self.g2.id)},
        ]
        response = self._post_json(client, "/templates/bulk-save/", {"updates": updates})
        self.assertEqual(response.status_code, 200)
        self.tmpls[0].refresh_from_db()
        self.assertEqual(self.tmpls[0].group_id, self.g2.id)


class BulkUploadTests(TestCase):
    """Round-4 enhancement — bulk upload auto-creates groups referenced by
    the CSV that don't already exist (case-insensitive lookup). Templates
    still get linked to those freshly-created groups via the same code
    path that resolves existing ones."""

    def setUp(self):
        self.month = date(2026, 7, 1)

    def _set_session(self, client):
        s = client.session
        s.save()
        return client

    def _post_csv(self, client, csv_text):
        return client.post(
            "/templates/bulk-upload/",
            {"csv_text": csv_text},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_missing_groups_are_auto_created(self):
        # No groups exist beforehand. CSV references Finance, IT, Operations.
        client = self._set_session(Client())
        csv = (
            "task_name,assigned_to,sla_days,sla_type,sort_order,group\n"
            "T1,A,3,Working Day,1,Finance\n"
            "T2,B,5,Working Day,2,IT\n"
            "T3,C,2,Working Day,3,Operations\n"
        )
        response = self._post_csv(client, csv)
        self.assertEqual(response.status_code, 302)
        # Three groups should have been created.
        names = sorted(Group.objects.values_list("name", flat=True))
        self.assertEqual(names, ["Finance", "IT", "Operations"])
        # Every group has a distinct sort_order (auto-assigned by
        # _assign_group_sort_order).
        sort_orders = list(Group.objects.order_by("sort_order").values_list("sort_order", flat=True))
        self.assertEqual(len(set(sort_orders)), 3)
        # Every template landed in its group, not Ungrouped.
        for t in TaskTemplate.objects.all():
            self.assertIsNotNone(t.group_id, f"template {t.task_name} missing group_id")

    def test_existing_groups_are_reused_not_duplicated(self):
        Group.objects.create(name="Finance", sort_order=1)
        Group.objects.create(name="IT", sort_order=2)
        client = self._set_session(Client())
        csv = (
            "task_name,assigned_to,sla_days,sla_type,sort_order,group\n"
            "T1,A,3,Working Day,1,Finance\n"
            "T2,B,5,Working Day,2,IT\n"
        )
        self._post_csv(client, csv)
        # No new groups should have been added.
        self.assertEqual(Group.objects.count(), 2)
        # Templates link to the original groups (by id, not a new copy).
        finance_id = Group.objects.get(name="Finance").id
        it_id = Group.objects.get(name="IT").id
        t1 = TaskTemplate.objects.get(task_name="T1")
        t2 = TaskTemplate.objects.get(task_name="T2")
        self.assertEqual(t1.group_id, finance_id)
        self.assertEqual(t2.group_id, it_id)

    def test_case_insensitive_group_lookup_creates_when_missing(self):
        # "finance" (lowercase) is not the same as an existing "Finance" but
        # should be treated as the same group for the purposes of reuse.
        Group.objects.create(name="Finance", sort_order=1)
        client = self._set_session(Client())
        csv = (
            "task_name,assigned_to,sla_days,sla_type,sort_order,group\n"
            "T1,A,3,Working Day,1,finance\n"
        )
        self._post_csv(client, csv)
        # No duplicate — still only one Finance group.
        self.assertEqual(Group.objects.filter(name__iexact="finance").count(), 1)
        t1 = TaskTemplate.objects.get(task_name="T1")
        self.assertEqual(t1.group_id, Group.objects.get(name="Finance").id)

    def test_mixed_existing_and_missing_groups(self):
        # Finance already exists; IT and Operations are new.
        existing = Group.objects.create(name="Finance", sort_order=1)
        client = self._set_session(Client())
        csv = (
            "task_name,assigned_to,sla_days,sla_type,sort_order,group\n"
            "T1,A,3,Working Day,1,Finance\n"
            "T2,B,5,Working Day,2,IT\n"
            "T3,C,2,Working Day,3,Operations\n"
        )
        self._post_csv(client, csv)
        # Three groups total now: Finance (preserved), IT and Operations (new).
        self.assertEqual(Group.objects.count(), 3)
        # The two new groups have sort_orders > Finance's existing one.
        finance_sort = Group.objects.get(name="Finance").sort_order
        new_sorts = sorted(
            Group.objects.exclude(id=existing.id).values_list("sort_order", flat=True)
        )
        self.assertTrue(all(s > finance_sort for s in new_sorts))

    def test_ungrouped_rows_remain_ungrouped(self):
        # Rows with blank group should stay ungrouped even after the loop
        # creates groups for other rows.
        client = self._set_session(Client())
        csv = (
            "task_name,assigned_to,sla_days,sla_type,sort_order,group\n"
            "T1,A,3,Working Day,1,Finance\n"
            "T2,B,5,Working Day,2,\n"
        )
        self._post_csv(client, csv)
        self.assertEqual(Group.objects.count(), 1)
        t1 = TaskTemplate.objects.get(task_name="T1")
        t2 = TaskTemplate.objects.get(task_name="T2")
        self.assertEqual(t1.group_id, Group.objects.get(name="Finance").id)
        self.assertIsNone(t2.group_id)






class ToggleFinishedResponseTests(TestCase):
    """B9 — toggle-finished endpoint returns completion_display so the
    client can update the row + group summary in place (no location.reload).
    Round 5 follow-up: completion_display carries 'YYYY-MM-DD HH:MM'."""

    def setUp(self):
        self.month = date(2026, 7, 1)

    def _set_session(self, client):
        client.session.save()
        return client

    def test_toggle_finished_returns_completion_display_with_time(self):
        task = Task.objects.create(
            task_name="X", assigned_to="x", sla_days=1, sla_type="Working Day",
            scheduled_date=self.month, month=self.month,
        )
        client = self._set_session(Client())
        # Toggle ON: completion_display should be "YYYY-MM-DD HH:MM" for today.
        response = client.post(
            f"/task/{task.id}/toggle/",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["finished"])
        display = data["completion_display"]
        self.assertTrue(display.startswith(date.today().isoformat() + " "),
                        f"expected date prefix, got {display!r}")
        # Time portion should be HH:MM (5 chars).
        time_part = display.split(" ", 1)[1]
        self.assertEqual(len(time_part), 5)
        self.assertEqual(time_part[2], ":")
        # Toggle OFF: completion_display should be empty.
        response = client.post(
            f"/task/{task.id}/toggle/",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertFalse(data["finished"])
        self.assertEqual(data["completion_display"], "")



class CompletionDateTimeTests(TestCase):
    """Round 5 follow-up — completion carries both a date and an optional
    HH:MM time. Toggle-finished sets both; the edit form accepts either a
    date or datetime-local value via _parse_completion; display via
    _format_completion."""

    def test_parse_blank(self):
        from tracker.views import _parse_completion
        self.assertEqual(_parse_completion(""), (None, None))
        self.assertEqual(_parse_completion(None), (None, None))

    def test_parse_date_only(self):
        from tracker.views import _parse_completion
        d, t = _parse_completion("2026-07-10")
        self.assertEqual(d, date(2026, 7, 10))
        self.assertIsNone(t)

    def test_parse_datetime_local(self):
        from tracker.views import _parse_completion
        d, t = _parse_completion("2026-07-10T14:30")
        self.assertEqual(d, date(2026, 7, 10))
        self.assertEqual(t.strftime("%H:%M"), "14:30")

    def test_parse_datetime_local_with_seconds(self):
        from tracker.views import _parse_completion
        d, t = _parse_completion("2026-07-10T14:30:45")
        self.assertEqual(d, date(2026, 7, 10))
        self.assertEqual(t.strftime("%H:%M:%S"), "14:30:45")

    def test_format_with_time(self):
        from datetime import time
        from tracker.views import _format_completion
        # Build a fake task with the fields the helper reads.
        class _T: pass
        t = _T()
        t.completion_date = date(2026, 7, 10)
        t.completion_time = time(14, 30)
        self.assertEqual(_format_completion(t), "2026-07-10 14:30")

    def test_format_date_only(self):
        from tracker.views import _format_completion
        class _T: pass
        t = _T()
        t.completion_date = date(2026, 7, 10)
        t.completion_time = None
        self.assertEqual(_format_completion(t), "2026-07-10")

    def test_format_empty(self):
        from tracker.views import _format_completion
        class _T: pass
        t = _T()
        t.completion_date = None
        t.completion_time = None
        self.assertEqual(_format_completion(t), "")

    def test_toggle_sets_completion_time(self):
        # Round 5 follow-up: toggle-finished sets completion_time to the
        # local clock value, not just the date.
        task = Task.objects.create(
            task_name="X", assigned_to="x", sla_days=1, sla_type="Working Day",
            scheduled_date=date(2026, 7, 1), month=date(2026, 7, 1),
        )
        client = Client()
        client.session.save()
        response = client.post(
            f"/task/{task.id}/toggle/",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertTrue(task.finished)
        self.assertEqual(task.completion_date, date.today())
        self.assertIsNotNone(task.completion_time)





class CalculateScheduledDateTests(TestCase):
    """Calendar Day SLA pins to a day-of-month regardless of weekends or
    public holidays (B10). Working Day counts forward and skips both.
    Calendar Day semantics: sla_days = N → due on the Nth day of the month."""

    def test_calendar_day_one_due_on_first_of_month(self):
        from tracker.holidays import calculate_scheduled_date
        # sla_days = 1 → 1st of the month, even if it's a public holiday.
        month = date(2026, 7, 1)
        self.assertEqual(calculate_scheduled_date(month, 1, "Calendar Day"), month)

    def test_calendar_day_thirteen_due_on_thirteenth(self):
        from tracker.holidays import calculate_scheduled_date
        month = date(2026, 7, 1)
        self.assertEqual(
            calculate_scheduled_date(month, 13, "Calendar Day"), date(2026, 7, 13),
        )

    def test_calendar_day_pins_to_exact_day_regardless_of_holiday(self):
        # July 1, 2026 is HK SAR Establishment Day. sla_days = 1 still
        # returns July 1 (it pins to the day-of-month, not "next non-holiday").
        from tracker.holidays import calculate_scheduled_date, hk_public_holidays
        month = date(2026, 7, 1)
        self.assertIn(date(2026, 7, 1), hk_public_holidays(2026))
        self.assertEqual(calculate_scheduled_date(month, 1, "Calendar Day"), month)

    def test_calendar_day_pins_to_weekend(self):
        # sla_days = 4 → July 4 (Sat). Weekend doesn't get skipped.
        from tracker.holidays import calculate_scheduled_date
        month = date(2026, 7, 1)
        self.assertEqual(
            calculate_scheduled_date(month, 4, "Calendar Day"), date(2026, 7, 4),
        )

    def test_calendar_day_zero_falls_back_to_month_start(self):
        # Defensive: sla_days <= 0 → month_start (no off-by-one surprises).
        from tracker.holidays import calculate_scheduled_date
        month = date(2026, 7, 1)
        self.assertEqual(calculate_scheduled_date(month, 0, "Calendar Day"), month)

    def test_calendar_day_out_of_range_clamps_to_last_day(self):
        # sla_days = 31 in February (28 days in 2026) → Feb 28.
        from tracker.holidays import calculate_scheduled_date
        month = date(2026, 2, 1)
        self.assertEqual(
            calculate_scheduled_date(month, 31, "Calendar Day"), date(2026, 2, 28),
        )

    def test_working_day_skips_holidays_and_weekends(self):
        # Working Day 3 from Wed July 1 → Mon July 6.
        # Skips Jul 1 (HK SAR Day), Jul 4-5 (weekend).
        from tracker.holidays import calculate_scheduled_date
        month = date(2026, 7, 1)
        self.assertEqual(
            calculate_scheduled_date(month, 3, "Working Day"), date(2026, 7, 6),
        )

    def test_calendar_day_spans_lunar_new_year_holidays(self):
        # sla_days = 21 → Feb 21 (Lunar New Year holidays Feb 17-19 don't shift it).
        from tracker.holidays import calculate_scheduled_date
        month = date(2026, 2, 1)
        self.assertEqual(
            calculate_scheduled_date(month, 21, "Calendar Day"), date(2026, 2, 21),
        )

    def test_task_add_persists_calendar_day_scheduled_date_exactly(self):
        # End-to-end: a Calendar Day task created via task_add has a
        # scheduled_date equal to month_start.replace(day=sla_days).
        from tracker.models import Task
        Task.objects.all().delete()
        client = Client()
        client.session.save()
        client.post("/task/add/", {
            "task_name": "CD test",
            "assigned_to": "Alice",
            "sla_days": "5",
            "sla_type": "Calendar Day",
            "comments": "",
            "group": "",
        })
        task = Task.objects.get(task_name="CD test")
        self.assertEqual(task.sla_type, "Calendar Day")
        # The default month is the current month (1st of the month).
        from django.utils import timezone
        expected_month = timezone.localdate().replace(day=1)
        self.assertEqual(task.scheduled_date, expected_month.replace(day=5))




class HolidayCalendarTests(TestCase):
    """B5 — recalibrate HK public holidays against the gazetted 2026/2027
    lists. Each test pins one specific date so any drift in the table is
    caught on the next run."""

    def test_2026_lunar_new_year_three_weekdays(self):
        from tracker.holidays import hk_public_holidays
        self.assertEqual(
            hk_public_holidays(2026) & {
                date(2026, 2, 17), date(2026, 2, 18), date(2026, 2, 19),
            },
            {date(2026, 2, 17), date(2026, 2, 18), date(2026, 2, 19)},
        )

    def test_2026_good_friday_and_day_after(self):
        from tracker.holidays import hk_public_holidays
        self.assertIn(date(2026, 4, 3), hk_public_holidays(2026))
        self.assertIn(date(2026, 4, 4), hk_public_holidays(2026))

    def test_2026_observed_ching_ming_skips_sunday(self):
        from tracker.holidays import hk_public_holidays
        # Ching Ming 2026 falls on Sunday Apr 5; the observed day is Apr 6 (Mon).
        self.assertIn(date(2026, 4, 6), hk_public_holidays(2026))
        self.assertNotIn(date(2026, 4, 5), hk_public_holidays(2026))

    def test_2026_observed_easter_monday_skipping_sunday(self):
        from tracker.holidays import hk_public_holidays
        # Easter Sunday 2026 = Apr 5; Easter Monday = Apr 6 (Sun). The
        # "day following Easter Monday" observed holiday is Apr 7 (Tue).
        # Apr 6 is also the observed Ching Ming day, so it is in the
        # holiday list — but as Ching Ming, not Easter Monday.
        self.assertIn(date(2026, 4, 7), hk_public_holidays(2026))

    def test_2026_buddhas_birthday_observed(self):
        from tracker.holidays import hk_public_holidays
        self.assertIn(date(2026, 5, 25), hk_public_holidays(2026))

    def test_2026_mid_autumn_following_day(self):
        from tracker.holidays import hk_public_holidays
        self.assertIn(date(2026, 9, 26), hk_public_holidays(2026))
        # The actual festival (Sep 25, Fri) is itself a weekday — only the
        # "day following" is in the gazetted list.
        self.assertNotIn(date(2026, 9, 25), hk_public_holidays(2026))

    def test_2026_chung_yeung_following_day(self):
        from tracker.holidays import hk_public_holidays
        self.assertIn(date(2026, 10, 19), hk_public_holidays(2026))

    def test_2026_christmas_first_weekday_after(self):
        from tracker.holidays import hk_public_holidays
        self.assertIn(date(2026, 12, 25), hk_public_holidays(2026))
        self.assertIn(date(2026, 12, 26), hk_public_holidays(2026))

    def test_2027_lunar_new_year_skips_sunday(self):
        from tracker.holidays import hk_public_holidays
        # 2027 LNY: day 1 Sat Feb 6, day 2 Sun Feb 7 (skipped, already off),
        # day 3 Mon Feb 8, day 4 Tue Feb 9.
        self.assertEqual(
            hk_public_holidays(2027) & {
                date(2027, 2, 6), date(2027, 2, 7),
                date(2027, 2, 8), date(2027, 2, 9),
            },
            {date(2027, 2, 6), date(2027, 2, 8), date(2027, 2, 9)},
        )

    def test_2027_good_friday_and_day_after(self):
        from tracker.holidays import hk_public_holidays
        self.assertIn(date(2027, 3, 26), hk_public_holidays(2027))
        self.assertIn(date(2027, 3, 27), hk_public_holidays(2027))

    def test_2027_easter_monday_weekday(self):
        from tracker.holidays import hk_public_holidays
        self.assertIn(date(2027, 3, 29), hk_public_holidays(2027))

    def test_2027_buddhas_birthday(self):
        from tracker.holidays import hk_public_holidays
        self.assertIn(date(2027, 5, 13), hk_public_holidays(2027))

    def test_2027_mid_autumn_following_day(self):
        from tracker.holidays import hk_public_holidays
        self.assertIn(date(2027, 9, 16), hk_public_holidays(2027))

    def test_2027_christmas_first_weekday_after(self):
        from tracker.holidays import hk_public_holidays
        self.assertIn(date(2027, 12, 25), hk_public_holidays(2027))
        self.assertIn(date(2027, 12, 27), hk_public_holidays(2027))
        self.assertNotIn(date(2027, 12, 26), hk_public_holidays(2027))

    def test_labour_day_is_a_holiday_each_year(self):
        from tracker.holidays import hk_public_holidays
        # New for B5: May 1 is in the gazetted list every year.
        self.assertIn(date(2026, 5, 1), hk_public_holidays(2026))
        self.assertIn(date(2027, 5, 1), hk_public_holidays(2027))

    def test_business_day_excludes_observed_holidays(self):
        from tracker.holidays import is_business_day
        # Pin a couple of dates that would otherwise look like weekdays.
        self.assertFalse(is_business_day(date(2026, 4, 6)))  # Ching Ming observed
        self.assertFalse(is_business_day(date(2026, 4, 7)))  # day-after Easter
        self.assertFalse(is_business_day(date(2027, 12, 27)))  # day-after Christmas
        # And confirm the inverse: an actual weekday in the same month.
        self.assertTrue(is_business_day(date(2026, 4, 9)))
        self.assertTrue(is_business_day(date(2027, 12, 28)))


# =============================================================================
# 2026-07-28 Enhancement: Status / Finished Late / Rerun / Comment tests
# =============================================================================


class TaskStatusTests(TestCase):
    """Status classification: overdue, pending, completed, finished_late."""

    def setUp(self):
        self.today = date(2026, 7, 10)

    def _make(self, finished=False, scheduled_offset=0, completion_offset=None):
        t = Task(
            task_name="X", assigned_to="x", sla_days=1, sla_type="Working Day",
            scheduled_date=self.today + timedelta(days=scheduled_offset),
            finished=finished,
            completion_date=(
                self.today + timedelta(days=completion_offset)
                if completion_offset is not None else None
            ),
            month=date(2026, 7, 1),
        )
        return t

    def test_pending_unfinished_future(self):
        t = self._make(finished=False, scheduled_offset=3)
        self.assertEqual(task_status(t, self.today), "pending")

    def test_overdue_unfinished_past(self):
        t = self._make(finished=False, scheduled_offset=-3)
        self.assertEqual(task_status(t, self.today), "overdue")

    def test_completed_on_time(self):
        t = self._make(finished=True, scheduled_offset=-5, completion_offset=-5)
        self.assertEqual(task_status(t, self.today), "completed")

    def test_completed_before_scheduled(self):
        t = self._make(finished=True, scheduled_offset=3, completion_offset=-2)
        self.assertEqual(task_status(t, self.today), "completed")

    def test_finished_late_after_scheduled(self):
        t = self._make(finished=True, scheduled_offset=-5, completion_offset=1)
        self.assertEqual(task_status(t, self.today), "finished_late")

    def test_completed_on_scheduled_day(self):
        t = self._make(finished=True, scheduled_offset=0, completion_offset=0)
        self.assertEqual(task_status(t, self.today), "completed")

    def test_legacy_finished_no_completion_date(self):
        t = self._make(finished=True, scheduled_offset=-5, completion_offset=None)
        self.assertEqual(task_status(t, self.today), "completed")

    def test_toggle_response_includes_status(self):
        task = Task.objects.create(
            task_name="ToggleStatus", assigned_to="x", sla_days=1,
            sla_type="Working Day",
            scheduled_date=date(2026, 7, 5), month=date(2026, 7, 1),
        )
        client = Client()
        client.session.save()
        response = client.post(
            f"/task/{task.id}/toggle/",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("is_late", data)


class GroupFinishedLateTests(TestCase):
    """Group status logic with finished_late."""

    def _make(self, name, scheduled_offset, finished=False, completion_offset=None):
        today = date(2026, 7, 10)
        scheduled = today + timedelta(days=scheduled_offset)
        completion = today + timedelta(days=completion_offset) if completion_offset is not None else None
        return Task.objects.create(
            task_name=f"task-{name}", assigned_to="x", sla_days=1, sla_type="Working Day",
            scheduled_date=scheduled, finished=finished, completion_date=completion,
            month=date(2026, 7, 1),
        )

    def _build(self, group, tasks):
        return _build_group_block(
            group, tasks, date(2026, 7, 10), date(2026, 7, 1),
            pixel_per_day=28, total_days=31,
        )

    def test_all_finished_all_on_time(self):
        group = Group.objects.create(name="G")
        t1 = self._make("a", -5, finished=True, completion_offset=-5)
        t2 = self._make("b", -3, finished=True, completion_offset=-3)
        for t in (t1, t2):
            t.group = group; t.save()
        block = self._build(group, [t1, t2])
        self.assertEqual(block["summary"]["status"], "completed")
        self.assertEqual(block["summary"]["finished_late"], 0)
        self.assertEqual(block["summary"]["on_time"], 2)

    def test_all_finished_mixed_late_and_on_time(self):
        group = Group.objects.create(name="G")
        t1 = self._make("a", -5, finished=True, completion_offset=-5)
        t2 = self._make("b", -3, finished=True, completion_offset=1)
        for t in (t1, t2):
            t.group = group; t.save()
        block = self._build(group, [t1, t2])
        self.assertEqual(block["summary"]["status"], "finished_late")
        self.assertEqual(block["summary"]["finished_late"], 1)
        self.assertEqual(block["summary"]["on_time"], 1)

    def test_unfinished_overdue_dominates_late_completed(self):
        group = Group.objects.create(name="G")
        late = self._make("late", -2)
        done_late = self._make("done-late", -5, finished=True, completion_offset=1)
        for t in (late, done_late):
            t.group = group; t.save()
        block = self._build(group, [late, done_late])
        self.assertEqual(block["summary"]["status"], "overdue")

    def test_unfinished_pending_dominates_late_completed(self):
        group = Group.objects.create(name="G")
        pending = self._make("pending", 2)
        done_late = self._make("done-late", -5, finished=True, completion_offset=1)
        for t in (pending, done_late):
            t.group = group; t.save()
        block = self._build(group, [pending, done_late])
        self.assertEqual(block["summary"]["status"], "pending")


class RerunModelAndEndpointTests(TestCase):
    """System rerun CRUD tests."""

    def setUp(self):
        self.month = date(2026, 7, 1)
        self.task = Task.objects.create(
            task_name="RerunTask", assigned_to="x", sla_days=1,
            sla_type="Working Day", scheduled_date=date(2026, 7, 10),
            month=self.month,
        )
        self.system = System.objects.create(name="TestSystem", sort_order=1)
        self.system2 = System.objects.create(name="OtherSystem", sort_order=2)
        self.client = Client()
        self.client.session.save()

    def _triggered(self, day=5, hour=10):
        return dt(2026, 7, day, hour, 0, 0, tzinfo=timezone.get_current_timezone())

    def test_create_one_rerun(self):
        response = self.client.post(
            f"/task/{self.task.id}/reruns/create/",
            {
                "system": str(self.system.id),
                "triggered_at": self._triggered(5).isoformat(),
                "completed_at": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(SystemRerun.objects.count(), 1)
        rerun = SystemRerun.objects.first()
        self.assertEqual(rerun.task_id, self.task.id)
        self.assertEqual(rerun.system_id, self.system.id)

    def test_create_multiple_reruns(self):
        for i in range(3):
            self.client.post(
                f"/task/{self.task.id}/reruns/create/",
                {
                    "system": str(self.system.id),
                    "triggered_at": self._triggered(5 + i).isoformat(),
                    "completed_at": "",
                },
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(SystemRerun.objects.count(), 3)

    def test_update_rerun(self):
        rerun = SystemRerun.objects.create(
            task=self.task, system=self.system,
            triggered_at=self._triggered(5),
        )
        response = self.client.post(
            f"/reruns/{rerun.id}/update/",
            {
                "system": str(self.system2.id),
                "triggered_at": self._triggered(6).isoformat(),
                "completed_at": self._triggered(6, 12).isoformat(),
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        rerun.refresh_from_db()
        self.assertEqual(rerun.system_id, self.system2.id)
        self.assertIsNotNone(rerun.completed_at)

    def test_delete_requires_post_and_removes_target(self):
        r1 = SystemRerun.objects.create(
            task=self.task, system=self.system, triggered_at=self._triggered(5),
        )
        r2 = SystemRerun.objects.create(
            task=self.task, system=self.system, triggered_at=self._triggered(6),
        )
        response = self.client.post(
            f"/reruns/{r1.id}/delete/",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(SystemRerun.objects.count(), 1)
        self.assertIsNone(SystemRerun.objects.filter(id=r1.id).first())

    def test_missing_system_rejected(self):
        response = self.client.post(
            f"/task/{self.task.id}/reruns/create/",
            {"system": "999", "triggered_at": self._triggered(5).isoformat(), "completed_at": ""},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 404)

    def test_invalid_datetime_rejected(self):
        response = self.client.post(
            f"/task/{self.task.id}/reruns/create/",
            {"system": str(self.system.id), "triggered_at": "not-a-date", "completed_at": ""},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_completion_earlier_than_trigger_rejected(self):
        response = self.client.post(
            f"/task/{self.task.id}/reruns/create/",
            {
                "system": str(self.system.id),
                "triggered_at": self._triggered(10).isoformat(),
                "completed_at": self._triggered(5).isoformat(),
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_incomplete_rerun_is_active(self):
        rerun = SystemRerun.objects.create(
            task=self.task, system=self.system, triggered_at=self._triggered(5),
        )
        self.assertIsNone(rerun.completed_at)

    def test_cross_task_tampering_rejected(self):
        other_task = Task.objects.create(
            task_name="Other", assigned_to="x", sla_days=1,
            sla_type="Working Day", scheduled_date=date(2026, 7, 10),
            month=self.month,
        )
        rerun = SystemRerun.objects.create(
            task=other_task, system=self.system, triggered_at=self._triggered(5),
        )
        response = self.client.post(
            f"/reruns/{rerun.id}/update/",
            {
                "system": str(self.system.id),
                "triggered_at": self._triggered(6).isoformat(),
                "completed_at": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)

    def test_month_scoping(self):
        next_month = date(2026, 8, 1)
        task_next = Task.objects.create(
            task_name="Next", assigned_to="x", sla_days=1, sla_type="Working Day",
            scheduled_date=date(2026, 8, 10), month=next_month,
        )
        SystemRerun.objects.create(
            task=self.task, system=self.system, triggered_at=self._triggered(5),
        )
        SystemRerun.objects.create(
            task=task_next, system=self.system, triggered_at=dt(2026, 8, 5, 10, 0, 0, tzinfo=timezone.get_current_timezone()),
        )
        month_reruns = SystemRerun.objects.filter(task__month=self.month)
        self.assertEqual(month_reruns.count(), 1)


class RerunGanttTests(TestCase):
    """Rerun Gantt bar geometry and grouping."""

    def setUp(self):
        self.month = date(2026, 7, 1)
        self.task = Task.objects.create(
            task_name="GanttRerun", assigned_to="x", sla_days=1,
            sla_type="Working Day", scheduled_date=date(2026, 7, 10),
            month=self.month,
        )
        self.system = System.objects.create(name="SysA", sort_order=1)

    def _rerun(self, day, hour=10, completed_day=None, completed_hour=None):
        from datetime import datetime as dt
        triggered = dt(2026, 7, day, hour, 0, 0, tzinfo=timezone.get_current_timezone())
        completed = None
        if completed_day is not None:
            completed = dt(2026, 7, completed_day, completed_hour or hour, 0, 0, tzinfo=timezone.get_current_timezone())
        return SystemRerun.objects.create(
            task=self.task, system=self.system,
            triggered_at=triggered, completed_at=completed,
        )

    def test_same_day_rerun_produces_bar(self):
        from tracker.views import _gantt_rerun_bar
        rerun = self._rerun(5, 10, 5, 12)
        bar = _gantt_rerun_bar(rerun, self.month, 31, 28)
        self.assertIsNotNone(bar)
        self.assertEqual(bar["system_name"], "SysA")
        self.assertFalse(bar["is_active"])

    def test_multi_day_rerun_span(self):
        from tracker.views import _gantt_rerun_bar
        rerun = self._rerun(5, 10, 8, 12)
        bar = _gantt_rerun_bar(rerun, self.month, 31, 28)
        self.assertIsNotNone(bar)
        self.assertEqual(bar["trigger_date"], date(2026, 7, 5))
        self.assertEqual(bar["end_date"], date(2026, 7, 8))

    def test_active_rerun_ends_at_today(self):
        from tracker.views import _gantt_rerun_bar
        rerun = self._rerun(5, 10)
        bar = _gantt_rerun_bar(rerun, self.month, 31, 28)
        self.assertIsNotNone(bar)
        self.assertTrue(bar["is_active"])

    def test_collapsed_total_and_expanded_grouping(self):
        from tracker.views import _build_rerun_gantt
        r1 = self._rerun(5, 10, 5, 12)
        r2 = self._rerun(8, 10, 8, 14)
        reruns = SystemRerun.objects.all()
        gantt = _build_rerun_gantt(reruns, self.month, 31, 28)
        self.assertEqual(gantt["total"], 2)
        self.assertEqual(len(gantt["collapsed_bars"]), 2)
        self.assertEqual(len(gantt["expanded_systems"]), 1)

    def test_multiple_reruns_per_system_distinct(self):
        from tracker.views import _build_rerun_gantt
        self._rerun(5, 10, 5, 12)
        self._rerun(10, 10, 12, 14)
        reruns = SystemRerun.objects.all()
        gantt = _build_rerun_gantt(reruns, self.month, 31, 28)
        self.assertEqual(len(gantt["expanded_systems"][0]["bars"]), 2)

    def test_empty_rerun_gantt(self):
        from tracker.views import _build_rerun_gantt
        gantt = _build_rerun_gantt([], self.month, 31, 28)
        self.assertEqual(gantt["total"], 0)
        self.assertEqual(len(gantt["collapsed_bars"]), 0)
        self.assertEqual(len(gantt["expanded_systems"]), 0)

    def test_accessible_text_includes_info(self):
        from tracker.views import _gantt_rerun_bar
        rerun = self._rerun(5, 10, 5, 12)
        bar = _gantt_rerun_bar(rerun, self.month, 31, 28)
        self.assertIn("SysA", bar["system_name"])
        self.assertIn("GanttRerun", bar["task_name"])


class CommentTests(TestCase):
    """Multiline comments, comment table, and HTML escaping."""

    def setUp(self):
        self.month = date(2026, 7, 1)
        self.task = Task.objects.create(
            task_name="CommentTask", assigned_to="x", sla_days=1,
            sla_type="Working Day", scheduled_date=date(2026, 7, 10),
            month=self.month, comments="",
        )
        self.client = Client()
        session = self.client.session
        session["current_month"] = self.month.isoformat()
        session.save()

    def test_multiline_comment_persists(self):
        multiline = "Line one\nLine two\nLine three"
        response = self.client.post(
            f"/task/{self.task.id}/comment/",
            {"comments": multiline},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.task.refresh_from_db()
        self.assertEqual(self.task.comments, multiline)

    def test_comment_table_absent_with_no_comments(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["comment_tasks"]), 0)

    def test_comment_table_present_with_substantive_comment(self):
        self.task.comments = "Has content"
        self.task.save()
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.context["comment_tasks"]), 0)
        body = response.content.decode()
        self.assertIn("Has content", body)

    def test_whitespace_only_comment_empty(self):
        self.task.comments = "   \n  \n  "
        self.task.save()
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["comment_tasks"]), 0)

    def test_html_comment_content_is_escaped(self):
        self.task.comments = "<script>alert('xss')</script>"
        self.task.save()
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("&lt;script&gt;", body)
        self.assertIn("&lt;/script&gt;", body)


class NoSLAFixesTests(TestCase):
    """Confirmed 2026-07-28 behavior for explicitly blank SLAs."""

    def setUp(self):
        self.month = date(2026, 7, 1)
        self.task = Task.objects.create(
            task_name="No SLA", assigned_to="x", sla_days=None,
            sla_type="Working Day", scheduled_date=None, month=self.month,
        )

    def test_no_sla_is_never_overdue_or_late(self):
        self.assertEqual(task_status(self.task, date(2030, 1, 1)), "pending")
        self.task.finished = True
        self.task.completion_date = date(2030, 1, 1)
        self.assertEqual(task_status(self.task, date(2030, 1, 1)), "completed")

    def test_mixed_sla_group_builds_without_type_error(self):
        dated = Task.objects.create(
            task_name="Dated", assigned_to="x", sla_days=1,
            sla_type="Working Day", scheduled_date=date(2026, 7, 2), month=self.month,
        )
        block = _build_group_block(
            None, [self.task, dated], date(2026, 7, 10), self.month, 28, 31,
        )
        self.assertEqual(len(block["tasks"]), 2)
        self.assertEqual(len(block["gantt_tasks"]), 1)

    def test_inline_blank_sla_clears_deadline(self):
        self.task.sla_days = 3
        self.task.scheduled_date = date(2026, 7, 3)
        self.task.save()
        response = Client().post(
            f"/task/{self.task.id}/inline-save/",
            {"task_name": self.task.task_name, "assigned_to": "x", "sla_days": "",
             "sla_type": "Working Day", "completion_date": "", "comments": ""},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertIsNone(self.task.sla_days)
        self.assertIsNone(self.task.scheduled_date)

    def test_blank_sla_csv_creates_no_sla_template(self):
        response = Client().post(
            "/templates/bulk-upload/",
            {"csv_text": "task_name,assigned_to,sla_days,sla_type\nNo deadline,Alice,,Working Day\n"},
        )
        self.assertEqual(response.status_code, 302)
        template = TaskTemplate.objects.get(task_name="No deadline")
        self.assertIsNone(template.sla_days)

    def test_zero_sla_remains_distinct_from_blank(self):
        template = TaskTemplate.objects.create(
            task_name="Zero", assigned_to="x", sla_days=0, sla_type="Calendar Day",
        )
        self.assertEqual(template.sla_days, 0)


class SystemManagementTests(TestCase):
    def test_dashboard_renders(self):
        response = Client().get("/dashboard/")
        self.assertEqual(response.status_code, 200)

    def test_template_tab_adds_user_provided_system_for_rerun_dropdown(self):
        response = Client().post("/systems/add/", {"name": "Settlement Engine"})
        self.assertEqual(response.status_code, 302)
        system = System.objects.get(name="Settlement Engine")
        Task.objects.create(
            task_name="Needs rerun", assigned_to="x", sla_days=1,
            sla_type="Working Day", scheduled_date=date(2026, 7, 1),
            month=date(2026, 7, 1),
        )
        page = Client().get("/")
        self.assertContains(page, f'<option value="{system.id}">Settlement Engine</option>', html=False)

    def test_duplicate_system_name_is_not_created(self):
        System.objects.create(name="Gateway")
        Client().post("/systems/add/", {"name": " gateway "})
        self.assertEqual(System.objects.filter(name__iexact="gateway").count(), 1)

    def test_system_can_be_renamed_inline(self):
        system = System.objects.create(name="Before")
        response = Client().post(
            f"/systems/{system.id}/inline-save/", {"name": "After"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        system.refresh_from_db()
        self.assertEqual(system.name, "After")

    def test_system_without_reruns_can_be_deleted(self):
        system = System.objects.create(name="Unused")
        response = Client().post(f"/systems/{system.id}/delete/")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(System.objects.filter(id=system.id).exists())

    def test_system_with_reruns_cannot_be_deleted(self):
        system = System.objects.create(name="Used")
        task = Task.objects.create(
            task_name="Task", assigned_to="x", sla_days=1, sla_type="Working Day",
            scheduled_date=date(2026, 7, 1), month=date(2026, 7, 1),
        )
        SystemRerun.objects.create(task=task, system=system, triggered_at=timezone.now())
        response = Client().post(f"/systems/{system.id}/delete/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(System.objects.filter(id=system.id).exists())
