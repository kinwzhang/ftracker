from django.db import models


class Group(models.Model):
    name = models.CharField(max_length=120, unique=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Task(models.Model):
    class SLAType(models.TextChoices):
        WORKING_DAY = "Working Day", "Working Day"
        CALENDAR_DAY = "Calendar Day", "Calendar Day"

    task_name = models.CharField(max_length=255)
    assigned_to = models.CharField(max_length=255)
    sla_days = models.IntegerField()
    sla_type = models.CharField(max_length=20, choices=SLAType.choices)
    scheduled_date = models.DateField()
    finished = models.BooleanField(default=False)
    completion_date = models.DateField(null=True, blank=True)
    completion_time = models.TimeField(null=True, blank=True)
    comments = models.TextField(blank=True, default="")
    month = models.DateField()
    group = models.ForeignKey(
        Group,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scheduled_date", "task_name"]

    def __str__(self):
        return self.task_name


class TaskTemplate(models.Model):
    class SLAType(models.TextChoices):
        WORKING_DAY = "Working Day", "Working Day"
        CALENDAR_DAY = "Calendar Day", "Calendar Day"

    task_name = models.CharField(max_length=255)
    assigned_to = models.CharField(max_length=255)
    sla_days = models.IntegerField()
    sla_type = models.CharField(max_length=20, choices=SLAType.choices)
    sort_order = models.IntegerField(default=0)
    group = models.ForeignKey(
        Group,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="templates",
    )

    class Meta:
        ordering = ["sort_order", "task_name"]

    def __str__(self):
        return self.task_name


class AuditLog(models.Model):
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True)
    task_name = models.CharField(max_length=255)
    action = models.CharField(max_length=50)
    changes = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def readable_message(self):
        if self.action == "created":
            return f"Created task '{self.task_name}'"
        if self.action == "deleted":
            return f"Deleted task '{self.task_name}'"
        if self.action == "updated":
            changes = self.changes
            if "old" not in changes or "new" not in changes:
                return f"Updated task '{self.task_name}'"
            parts = []
            old = changes["old"]
            new = changes["new"]
            field_labels = {
                "task_name": "Task Name", "assigned_to": "Assigned To",
                "sla_days": "SLA Days", "sla_type": "SLA Type",
                "finished": "Finished", "completion_date": "Completion Date",
                "completion_time": "Completion Time",
                "comments": "Comments",
            }
            for key in new:
                if key in old and str(old[key]) != str(new[key]):
                    label = field_labels.get(key, key)
                    old_val = old[key] if old[key] is not None else "(empty)"
                    new_val = new[key] if new[key] is not None else "(empty)"
                    parts.append(f"modified {label} from '{old_val}' to '{new_val}'")
            if parts:
                return f"{', '.join(parts)} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
            return f"Updated task '{self.task_name}'"
        return f"{self.action} - {self.task_name}"

    def __str__(self):
        return self.readable_message()
