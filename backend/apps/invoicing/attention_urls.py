from django.urls import path

from apps.invoicing.views import (
    AttentionSummaryView,
    FailedEventListView,
    FailedEventRequeueView,
    MissedPeriodInvoiceNowView,
    MissedPeriodListView,
    MissedPeriodSkipView,
)

# Mounted at /api/v1/attention/: everything the "Failed / pending jobs" screen needs.
urlpatterns = [
    path("summary/", AttentionSummaryView.as_view(), name="attention-summary"),
    path("missed-periods/", MissedPeriodListView.as_view(), name="attention-missed-periods"),
    path(
        "missed-periods/<uuid:pk>/invoice-now/",
        MissedPeriodInvoiceNowView.as_view(),
        name="attention-period-invoice-now",
    ),
    path(
        "missed-periods/<uuid:pk>/skip/",
        MissedPeriodSkipView.as_view(),
        name="attention-period-skip",
    ),
    path("failed-events/", FailedEventListView.as_view(), name="attention-failed-events"),
    path(
        "failed-events/<uuid:pk>/requeue/",
        FailedEventRequeueView.as_view(),
        name="attention-event-requeue",
    ),
]
