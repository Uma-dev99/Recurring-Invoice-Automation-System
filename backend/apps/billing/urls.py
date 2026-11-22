from django.urls import path

from apps.billing.views import AgreementPeriodListView

# Included under /api/v1/agreements/ next to the agreements app's own URLs, so the
# schedule reads as part of its agreement while the code stays in the billing app.
urlpatterns = [
    path(
        "<uuid:agreement_id>/periods/",
        AgreementPeriodListView.as_view(),
        name="agreement-periods",
    ),
]
