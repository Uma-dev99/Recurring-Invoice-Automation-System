from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

api_v1_patterns = [
    path("", include("apps.core.urls")),
    path("auth/", include("apps.accounts.urls")),
    path("customers/", include("apps.customers.urls")),
    path("agreements/", include("apps.agreements.urls")),
    path("agreements/", include("apps.billing.urls")),  # .../agreements/<id>/periods/
    path("invoices/", include("apps.invoicing.urls")),
    path("attention/", include("apps.invoicing.attention_urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("audit-logs/", include("apps.operations.urls")),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1_patterns)),
]
