from django.contrib import admin
from .models import Task, TaskTemplate, AuditLog


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["task_name", "assigned_to", "sla_days", "sla_type", "scheduled_date", "finished", "month"]
    list_filter = ["finished", "month", "sla_type"]


@admin.register(TaskTemplate)
class TaskTemplateAdmin(admin.ModelAdmin):
    list_display = ["task_name", "assigned_to", "sla_days", "sla_type", "sort_order"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "action", "task_name"]
    list_filter = ["action"]
