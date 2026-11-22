from django.urls import path

from apps.agreements.views import (
    AgreementCancelView,
    AgreementChangeAmountView,
    AgreementDetailView,
    AgreementListCreateView,
    AgreementPauseView,
    AgreementResumeView,
)

urlpatterns = [
    path("", AgreementListCreateView.as_view(), name="agreement-list"),
    path("<uuid:pk>/", AgreementDetailView.as_view(), name="agreement-detail"),
    path("<uuid:pk>/pause/", AgreementPauseView.as_view(), name="agreement-pause"),
    path("<uuid:pk>/resume/", AgreementResumeView.as_view(), name="agreement-resume"),
    path("<uuid:pk>/cancel/", AgreementCancelView.as_view(), name="agreement-cancel"),
    path(
        "<uuid:pk>/change-amount/",
        AgreementChangeAmountView.as_view(),
        name="agreement-change-amount",
    ),
]
