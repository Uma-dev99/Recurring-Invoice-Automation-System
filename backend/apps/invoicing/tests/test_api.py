import uuid

import pytest
from django.urls import reverse

from apps.invoicing import services
from apps.invoicing.gateway import Outcome, SubmitResult
from apps.invoicing.tests.helpers import StubGateway, first_period, make_billable_agreement

pytestmark = pytest.mark.django_db

LIST_URL = reverse("invoice-list")


def invoice_for(agreement, gateway=None):
    submission = services.create_submission(period_id=first_period(agreement).pk)
    if gateway:
        services.submit(submission_id=submission.pk, gateway=gateway)
    submission.refresh_from_db()
    return submission


def test_requires_login(api_client):
    assert api_client.get(LIST_URL).status_code == 401
    assert api_client.get(reverse("invoice-detail", kwargs={"pk": uuid.uuid4()})).status_code == 401


def test_list_shows_invoice_with_its_context(authenticated_client):
    agreement = make_billable_agreement(description="Gold plan")
    submission = invoice_for(agreement, StubGateway())

    [row] = authenticated_client.get(LIST_URL).json()["results"]

    assert row["merchant_reference"] == submission.merchant_reference
    assert row["status"] == "ACCEPTED"
    assert row["amount"] == "49.95"
    assert row["external_invoice_id"] == "RIV-1"
    assert row["period"]["cycle_number"] == 1
    assert row["agreement"] == {"id": str(agreement.pk), "description": "Gold plan"}
    assert row["customer"]["name"] == agreement.customer.name
    assert "attempts" not in row  # only on the detail endpoint


def test_list_filters(authenticated_client):
    accepted = invoice_for(make_billable_agreement(), StubGateway())
    rejected_agreement = make_billable_agreement(description="Silver")
    rejected = invoice_for(rejected_agreement, StubGateway(SubmitResult(Outcome.REJECTED)))

    def ids(params):
        return [r["id"] for r in authenticated_client.get(LIST_URL, params).json()["results"]]

    assert ids({"status": "REJECTED"}) == [str(rejected.pk)]
    assert ids({"agreement": str(rejected_agreement.pk)}) == [str(rejected.pk)]
    assert ids({"search": accepted.merchant_reference}) == [str(accepted.pk)]


@pytest.mark.parametrize("params", [{"status": "PAID"}, {"agreement": "x"}, {"ordering": "amount"}])
def test_list_rejects_invalid_filters(authenticated_client, params):
    assert authenticated_client.get(LIST_URL, params).status_code == 400


def test_detail_includes_attempts(authenticated_client):
    submission = invoice_for(
        make_billable_agreement(),
        StubGateway(
            SubmitResult(Outcome.REJECTED, error_category="validation", error_message="Bad")
        ),
    )

    body = authenticated_client.get(reverse("invoice-detail", kwargs={"pk": submission.pk})).json()

    assert body["status"] == "REJECTED"
    assert body["last_error_message"] == "Bad"
    [attempt] = body["attempts"]
    assert attempt["outcome"] == "REJECTED"
    assert attempt["request_summary"]["merchant_reference"] == submission.merchant_reference


def test_detail_query_count_does_not_grow_with_attempts(
    authenticated_client, django_assert_max_num_queries
):
    submission = invoice_for(make_billable_agreement(), StubGateway())

    with django_assert_max_num_queries(4):  # session/user + submission + attempts
        authenticated_client.get(reverse("invoice-detail", kwargs={"pk": submission.pk}))


def test_unknown_invoice_is_404(authenticated_client):
    response = authenticated_client.get(reverse("invoice-detail", kwargs={"pk": uuid.uuid4()}))

    assert response.status_code == 404


def test_invoices_are_read_only(authenticated_client):
    submission = invoice_for(make_billable_agreement())
    url = reverse("invoice-detail", kwargs={"pk": submission.pk})

    assert authenticated_client.post(LIST_URL, {}).status_code == 405
    assert authenticated_client.patch(url, {"status": "ACCEPTED"}).status_code == 405
    assert authenticated_client.delete(url).status_code == 405


# --- operator actions and the attention screen (Phase 8) ------------------------------------


def _rejected_invoice():
    agreement = make_billable_agreement()
    return invoice_for(agreement, StubGateway(SubmitResult(Outcome.REJECTED, error_message="Bad")))


def test_detail_tells_the_screen_which_actions_are_possible(authenticated_client):
    submission = _rejected_invoice()

    body = authenticated_client.get(reverse("invoice-detail", kwargs={"pk": submission.pk})).json()

    assert body["available_actions"] == ["retry", "cancel"]
    assert body["may_exist_at_riverty"] is False


def test_retry_via_api_returns_fresh_detail(authenticated_client):
    submission = _rejected_invoice()

    response = authenticated_client.post(
        reverse("invoice-retry", kwargs={"pk": submission.pk}),
        {"expected_status": "REJECTED", "reason": "Address corrected"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "RETRY_SCHEDULED"
    assert response.json()["available_actions"] == []


def test_stale_expected_status_is_409(authenticated_client):
    submission = _rejected_invoice()

    response = authenticated_client.post(
        reverse("invoice-cancel", kwargs={"pk": submission.pk}),
        {"expected_status": "NEEDS_ATTENTION", "reason": "Give up on it"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invoice_changed"


def test_unknown_invoice_retry_without_check_is_422(authenticated_client):
    submission = invoice_for(make_billable_agreement(), StubGateway(SubmitResult(Outcome.UNKNOWN)))

    response = authenticated_client.post(
        reverse("invoice-retry", kwargs={"pk": submission.pk}),
        {"expected_status": "UNKNOWN", "reason": "Trying again"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "riverty_check_required"


def test_action_without_reason_is_400(authenticated_client):
    submission = _rejected_invoice()

    response = authenticated_client.post(
        reverse("invoice-retry", kwargs={"pk": submission.pk}), {"expected_status": "REJECTED"}
    )

    assert response.status_code == 400
    assert "reason" in response.json()["error"]["details"]


def test_attention_summary_endpoint(authenticated_client):
    _rejected_invoice()

    body = authenticated_client.get(reverse("attention-summary")).json()

    assert body["rejected"] == 1
    assert body["total"] == 1


def test_stuck_filter(authenticated_client):
    from datetime import timedelta

    from django.utils import timezone

    from apps.invoicing.models import InvoiceSubmission

    stuck = invoice_for(make_billable_agreement())  # PENDING, never sent
    InvoiceSubmission.objects.filter(pk=stuck.pk).update(
        created_at=timezone.now() - timedelta(hours=1)
    )
    invoice_for(make_billable_agreement(description="Fresh"))

    results = authenticated_client.get(LIST_URL, {"stuck": "true"}).json()["results"]

    assert [row["id"] for row in results] == [str(stuck.pk)]


def test_attention_endpoints_require_login(api_client):
    assert api_client.get(reverse("attention-summary")).status_code == 401
    assert api_client.get(reverse("attention-missed-periods")).status_code == 401
    assert api_client.get(reverse("attention-failed-events")).status_code == 401
