from django.contrib import admin

from apps.operations.models import AuditLog, OutboxEvent


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only view of the audit trail. Nobody, not even a superuser, edits history."""

    list_display = ("created_at", "action", "entity_type", "entity_id", "actor")
    list_filter = ("action", "entity_type")
    search_fields = ("entity_id", "action")
    list_select_related = ("actor",)
    date_hierarchy = "created_at"

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(OutboxEvent)
class OutboxEventAdmin(admin.ModelAdmin):
    """Read-only: shows queued, failed and finished background work."""

    list_display = (
        "created_at",
        "event_type",
        "status",
        "attempts",
        "available_at",
        "processed_at",
    )
    list_filter = ("status", "event_type")
    readonly_fields = ("last_error",)

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
