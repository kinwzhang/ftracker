from datetime import date, timedelta

from django.test import TestCase

from .models import Group, Task, TaskTemplate
from .views import _assign_template_sort_order, _build_group_block


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
    """E2.1 — group bar geometry & status."""

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

    def test_group_status_completed_when_all_done(self):
        today = date(2026, 7, 10)
        group = Group.objects.create(name="G")
        t1 = self._make("a", -5, finished=True, completion_offset=-1)
        t2 = self._make("b", -3, finished=True, completion_offset=-2)
        t1.group = group; t1.save()
        t2.group = group; t2.save()
        block = _build_group_block(
            group, [t1, t2], today, date(2026, 7, 1), pixel_per_day=28,
        )
        self.assertEqual(block["summary"]["status"], "completed")
        self.assertEqual(block["group_bar"]["status"], "completed")

    def test_group_status_overdue_when_any_overdue(self):
        today = date(2026, 7, 10)
        group = Group.objects.create(name="G")
        t1 = self._make("a", -2)              # overdue
        t2 = self._make("b", 3)               # pending (3 days in future)
        t1.group = group; t1.save()
        t2.group = group; t2.save()
        block = _build_group_block(
            group, [t1, t2], today, date(2026, 7, 1), pixel_per_day=28,
        )
        self.assertEqual(block["summary"]["status"], "overdue")

    def test_group_bar_uses_next_closest_due_for_unfinished(self):
        today = date(2026, 7, 10)
        group = Group.objects.create(name="G")
        t1 = self._make("a", -2)              # overdue
        t2 = self._make("b", 1)               # 1 day future -> bar end
        t3 = self._make("c", 5)               # 5 days future
        t1.group = group; t1.save()
        t2.group = group; t2.save()
        t3.group = group; t3.save()
        block = _build_group_block(
            group, [t1, t2, t3], today, date(2026, 7, 1), pixel_per_day=28,
        )
        # Earliest scheduled = today - 2; bar end = today + 1; so width = 4 days.
        expected_width = 4 * 28 - 4
        self.assertEqual(block["group_bar"]["width"], expected_width)

    def test_group_bar_uses_latest_when_all_overdue(self):
        today = date(2026, 7, 10)
        group = Group.objects.create(name="G")
        t1 = self._make("a", -5)
        t2 = self._make("b", -2)
        t1.group = group; t1.save()
        t2.group = group; t2.save()
        block = _build_group_block(
            group, [t1, t2], today, date(2026, 7, 1), pixel_per_day=28,
        )
        # All overdue -> bar end = latest (today - 2); width = 4 days.
        self.assertEqual(block["group_bar"]["width"], 4 * 28 - 4)

    def test_ungrouped_block_renders_when_no_group(self):
        today = date(2026, 7, 10)
        t1 = self._make("a", 1)
        block = _build_group_block(
            None, [t1], today, date(2026, 7, 1), pixel_per_day=28,
        )
        self.assertIsNone(block["group"])
        self.assertEqual(block["id"], 0)
        self.assertEqual(block["summary"]["status"], "pending")
        self.assertIsNotNone(block["group_bar"])