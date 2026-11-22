from django.contrib import admin

from apps.billing.models import BillingPeriod


@admin.register(BillingPeriod)
class BillingPeriodAdmin(admin.ModelAdmin):
    """Read-only: periods are generated and changed only by the billing services."""

    list_display = (
        "agreement",
        "cycle_number",
        "period_start",
        "period_end",
        "amount",
        "status",
    )
    list_filter = ("status",)
    search_fields = ("agreement__description", "agreement__customer__name")
    list_select_related = ("agreement",)
    date_hierarchy = "period_start"

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
