from django.urls import path

from apps.operations.views import AuditFilterOptionsView, AuditLogListView

urlpatterns = [
    path("", AuditLogListView.as_view(), name="audit-log-list"),
    path("filters/", AuditFilterOptionsView.as_view(), name="audit-log-filters"),
]
