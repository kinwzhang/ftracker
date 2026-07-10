from django.urls import path
from . import views

urlpatterns = [
    path("", views.task_list, name="task_list"),
    path("task/add/", views.task_add, name="task_add"),
    path("task/<int:task_id>/edit/", views.task_edit, name="task_edit"),
    path("task/<int:task_id>/delete/", views.task_delete, name="task_delete"),
    path("task/<int:task_id>/toggle/", views.task_toggle_finished, name="task_toggle_finished"),
    path("task/<int:task_id>/comment/", views.task_save_comment, name="task_save_comment"),
    path("task/<int:task_id>/inline-save/", views.task_inline_save, name="task_inline_save"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("templates/", views.template_list, name="template_list"),
    path("templates/add/", views.template_add, name="template_add"),
    path("templates/bulk-upload/", views.template_bulk_upload, name="template_bulk_upload"),
    path("templates/<int:template_id>/edit/", views.template_edit, name="template_edit"),
    path("templates/<int:template_id>/delete/", views.template_delete, name="template_delete"),
    path("templates/<int:template_id>/inline-save/", views.template_inline_save, name="template_inline_save"),
    path("holidays/", views.holiday_list, name="holiday_list"),
    path("generate-next-month/", views.generate_next_month, name="generate_next_month"),
    path("export/csv/", views.export_csv, name="export_csv"),
    path("export/html/", views.export_html, name="export_html"),
    path("set-month/", views.set_month, name="set_month"),
]
