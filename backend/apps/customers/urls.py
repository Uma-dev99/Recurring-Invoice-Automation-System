from django.urls import path

from apps.customers.views import (
    CustomerDeactivateView,
    CustomerDetailView,
    CustomerListCreateView,
    CustomerReactivateView,
)

# <uuid:pk> only matches a valid UUID, so /customers/abc/ is a clean 404 before any
# view or database query runs.
urlpatterns = [
    path("", CustomerListCreateView.as_view(), name="customer-list"),
    path("<uuid:pk>/", CustomerDetailView.as_view(), name="customer-detail"),
    path("<uuid:pk>/deactivate/", CustomerDeactivateView.as_view(), name="customer-deactivate"),
    path("<uuid:pk>/reactivate/", CustomerReactivateView.as_view(), name="customer-reactivate"),
]
