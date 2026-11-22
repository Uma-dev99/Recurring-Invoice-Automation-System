from django.urls import path

from apps.core.views import HealthCheckView, LivenessView

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("health/live/", LivenessView.as_view(), name="health-live"),
]
