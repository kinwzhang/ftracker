from django.contrib import admin
from .models import AuditLog, Group, Task, TaskTemplate


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ["name", "sort_order", "created_at"]
    list_editable = ["sort_order"]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["task_name", "assigned_to", "sla_days", "sla_type", "scheduled_date", "finished", "month", "group"]
    list_filter = ["finished", "month", "sla_type", "group"]


@admin.register(TaskTemplate)
class TaskTemplateAdmin(admin.ModelAdmin):
    list_display = ["task_name", "assigned_to", "sla_days", "sla_type", "sort_order", "group"]
    list_filter = ["group", "sla_type"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "action", "task_name"]
    list_filter = ["action"]
