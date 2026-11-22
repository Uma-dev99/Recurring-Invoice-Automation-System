from django.urls import path

from apps.invoicing.views import (
    InvoiceCancelView,
    InvoiceDetailView,
    InvoiceListView,
    InvoiceMarkReceivedView,
    InvoiceRetryView,
)

urlpatterns = [
    path("", InvoiceListView.as_view(), name="invoice-list"),
    path("<uuid:pk>/", InvoiceDetailView.as_view(), name="invoice-detail"),
    path("<uuid:pk>/retry/", InvoiceRetryView.as_view(), name="invoice-retry"),
    path(
        "<uuid:pk>/mark-received/", InvoiceMarkReceivedView.as_view(), name="invoice-mark-received"
    ),
    path("<uuid:pk>/cancel/", InvoiceCancelView.as_view(), name="invoice-cancel"),
]
