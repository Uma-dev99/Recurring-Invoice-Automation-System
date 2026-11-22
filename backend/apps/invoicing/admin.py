from django.contrib import admin

from apps.invoicing.models import InvoiceSubmission, ProcessingAttempt


class ProcessingAttemptInline(admin.TabularInline):
    model = ProcessingAttempt
    extra = 0
    fields = (
        "attempt_number",
        "outcome",
        "error_category",
        "error_message",
        "started_at",
        "finished_at",
    )
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(InvoiceSubmission)
class InvoiceSubmissionAdmin(admin.ModelAdmin):
    """Read-only: submissions change only through the invoicing services."""

    list_display = (
        "merchant_reference",
        "status",
        "amount",
        "attempt_count",
        "external_invoice_id",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("merchant_reference", "external_invoice_id")
    inlines = [ProcessingAttemptInline]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
