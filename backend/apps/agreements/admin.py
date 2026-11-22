from django.contrib import admin

from apps.agreements.models import BillingAgreement


@admin.register(BillingAgreement)
class BillingAgreementAdmin(admin.ModelAdmin):
    """Read-only: changes go through the API so lifecycle rules and auditing apply."""

    list_display = (
        "description",
        "customer",
        "amount",
        "currency",
        "anchor_date",
        "total_cycles",
        "status",
    )
    list_filter = ("status", "currency")
    search_fields = ("description", "customer__name", "customer__external_customer_id")
    list_select_related = ("customer",)  # one query for the list, not one per row
    readonly_fields = ("id", "created_at", "updated_at", "version", "cancelled_at")

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
