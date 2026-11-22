from django.contrib import admin

from apps.customers.models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """Read-only in the admin: changes must go through the API so they are audited.

    Editing here would call Customer.save() directly and skip the service layer, which
    means no AuditLog row. The React dashboard is the place to change customers.
    """

    list_display = ("name", "external_customer_id", "customer_type", "email", "city", "status")
    list_filter = ("status", "customer_type", "country_code")
    search_fields = ("name", "external_customer_id", "email")
    readonly_fields = ("id", "created_at", "updated_at")

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
