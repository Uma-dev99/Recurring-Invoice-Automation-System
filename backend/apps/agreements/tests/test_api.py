"""API tests: the HTTP contract of /api/v1/agreements/.

Business rules are covered in test_services.py and test_lifecycle.py. These check
status codes, the error envelope, money as strings, the version handshake, and which
methods exist.
"""

import datetime
import uuid
from unittest import mock

import pytest
from django.urls import reverse

from apps.agreements import services
from apps.agreements.models import BillingAgreement
from apps.agreements.tests.factories import make_agreement
from apps.customers.models import Customer
from apps.customers.tests.factories import make_customer
from apps.operations.models import AuditLog

pytestmark = pytest.mark.django_db

LIST_URL = reverse("agreement-list")
TODAY = datetime.date(2027, 1, 15)


@pytest.fixture(autouse=True)
def fixed_today():
    with mock.patch.object(services, "billing_today", return_value=TODAY):
        yield


def detail_url(agreement_id) -> str:
    return reverse("agreement-detail", kwargs={"pk": agreement_id})


def action_url(action: str, agreement_id) -> str:
    return reverse(f"agreement-{action}", kwargs={"pk": agreement_id})


def create_payload(customer: Customer, **overrides) -> dict:
    payload = {
        "customer_id": str(customer.pk),
        "description": "Gold plan",
        "amount": "49.95",
        "anchor_date": "2027-01-31",
        "total_cycles": 12,
    }
    payload.update(overrides)
    return payload


def error(response) -> dict:
    return response.json()["error"]


# --- Authentication ------------------------------------------------------------------


@pytest.mark.parametrize(
    "method, url",
    [
        ("get", LIST_URL),
        ("post", LIST_URL),
        ("patch", detail_url(uuid.uuid4())),
        ("post", action_url("pause", uuid.uuid4())),
    ],
)
def test_every_endpoint_requires_login(api_client, method, url):
    response = getattr(api_client, method)(url, {})

    assert response.status_code == 401


# --- List -----------------------------------------------------------------------------


def test_list_returns_customer_summary_and_amount_as_string(authenticated_client):
    customer = make_customer(name="Acme")
    make_agreement(customer=customer)

    [row] = authenticated_client.get(LIST_URL).json()["results"]

    assert row["amount"] == "49.95"  # a string, so no cent is lost in JavaScript
    assert row["currency"] == "EUR"
    assert row["customer"] == {
        "id": str(customer.pk),
        "name": "Acme",
        "external_customer_id": customer.external_customer_id,
        "status": "ACTIVE",
    }
    assert "email" not in row["customer"]


def test_list_filters_by_customer_and_status(authenticated_client):
    acme = make_customer()
    wanted = make_agreement(customer=acme)
    make_agreement(customer=acme, status=BillingAgreement.Status.PAUSED)
    make_agreement()

    response = authenticated_client.get(LIST_URL, {"customer": str(acme.pk), "status": "ACTIVE"})

    assert [row["id"] for row in response.json()["results"]] == [str(wanted.pk)]


@pytest.mark.parametrize(
    "params, field",
    [
        ({"customer": "not-a-uuid"}, "customer"),
        ({"status": "DELETED"}, "status"),
        ({"ordering": "id"}, "ordering"),
    ],
)
def test_list_rejects_invalid_query_parameters(authenticated_client, params, field):
    response = authenticated_client.get(LIST_URL, params)

    assert response.status_code == 400
    assert field in error(response)["details"]


# --- Create ---------------------------------------------------------------------------


def test_create_returns_201_and_audits(authenticated_client, user):
    customer = make_customer()

    response = authenticated_client.post(LIST_URL, create_payload(customer))

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ACTIVE"
    assert body["version"] == 1
    assert body["amount"] == "49.95"
    assert AuditLog.objects.get(entity_id=body["id"]).actor == user


def test_total_cycles_defaults_to_twelve(authenticated_client):
    payload = create_payload(make_customer())
    del payload["total_cycles"]

    assert authenticated_client.post(LIST_URL, payload).json()["total_cycles"] == 12


def test_create_with_unknown_customer_is_a_field_error(authenticated_client):
    payload = create_payload(make_customer(), customer_id=str(uuid.uuid4()))

    response = authenticated_client.post(LIST_URL, payload)

    assert response.status_code == 400
    assert "customer_id" in error(response)["details"]


def test_create_for_inactive_customer_is_422(authenticated_client):
    customer = make_customer(status=Customer.Status.INACTIVE)

    response = authenticated_client.post(LIST_URL, create_payload(customer))

    assert response.status_code == 422
    assert error(response)["code"] == "customer_not_active"


def test_create_with_past_start_date_is_a_field_error(authenticated_client):
    response = authenticated_client.post(
        LIST_URL, create_payload(make_customer(), anchor_date="2027-01-14")
    )

    assert response.status_code == 400
    assert error(response)["details"] == {"anchor_date": [services.START_IN_PAST_MESSAGE]}


@pytest.mark.parametrize("amount", ["19.999", "0.00", "-1.00", "abc"])
def test_create_rejects_invalid_amounts(authenticated_client, amount):
    response = authenticated_client.post(LIST_URL, create_payload(make_customer(), amount=amount))

    assert response.status_code == 400
    assert "amount" in error(response)["details"]


def test_create_refuses_currency_and_status(authenticated_client):
    payload = create_payload(make_customer(), currency="USD", status="PAUSED")

    response = authenticated_client.post(LIST_URL, payload)

    assert response.status_code == 400
    assert {"currency", "status"} <= set(error(response)["details"])


# --- Edit and the version handshake ----------------------------------------------------


def test_patch_description_with_current_version(authenticated_client):
    agreement = make_agreement(description="Old")

    response = authenticated_client.patch(
        detail_url(agreement.pk), {"version": 1, "description": "New"}
    )

    assert response.status_code == 200
    assert response.json()["description"] == "New"
    assert response.json()["version"] == 2


def test_patch_without_version_is_refused(authenticated_client):
    agreement = make_agreement()

    response = authenticated_client.patch(detail_url(agreement.pk), {"description": "New"})

    assert response.status_code == 400
    assert "version" in error(response)["details"]


def test_two_tabs_editing_the_same_agreement(authenticated_client):
    agreement = make_agreement(description="Original")
    url = detail_url(agreement.pk)

    first = authenticated_client.patch(url, {"version": 1, "description": "Tab one"})
    second = authenticated_client.patch(url, {"version": 1, "description": "Tab two"})

    assert first.status_code == 200
    assert second.status_code == 409
    assert error(second)["code"] == "agreement_version_conflict"
    assert error(second)["details"] == {"expected_version": 1, "current_version": 2}
    assert authenticated_client.get(url).json()["description"] == "Tab one"


@pytest.mark.parametrize("field, value", [("amount", "10.00"), ("anchor_date", "2027-06-01")])
def test_patch_refuses_fixed_fields(authenticated_client, field, value):
    agreement = make_agreement()

    response = authenticated_client.patch(detail_url(agreement.pk), {"version": 1, field: value})

    assert response.status_code == 400
    assert field in error(response)["details"]


@pytest.mark.parametrize("method", ["put", "delete"])
def test_put_and_delete_are_not_offered(authenticated_client, method):
    agreement = make_agreement()

    assert getattr(authenticated_client, method)(detail_url(agreement.pk)).status_code == 405


def test_unknown_agreement_is_404(authenticated_client):
    response = authenticated_client.get(detail_url(uuid.uuid4()))

    assert response.status_code == 404
    assert error(response)["code"] == "not_found"


# --- Lifecycle actions ---------------------------------------------------------------


def test_pause_resume_cancel_flow(authenticated_client):
    agreement = make_agreement()

    paused = authenticated_client.post(action_url("pause", agreement.pk), {"version": 1})
    resumed = authenticated_client.post(action_url("resume", agreement.pk), {"version": 2})
    cancelled = authenticated_client.post(
        action_url("cancel", agreement.pk), {"version": 3, "reason": "Customer request"}
    )

    assert [r.json()["status"] for r in (paused, resumed, cancelled)] == [
        "PAUSED",
        "ACTIVE",
        "CANCELLED",
    ]
    assert cancelled.json()["cancelled_at"] is not None
    assert (
        AuditLog.objects.get(action="agreement.cancelled").changes["reason"] == "Customer request"
    )


def test_invalid_transition_is_422(authenticated_client):
    agreement = make_agreement()

    response = authenticated_client.post(action_url("resume", agreement.pk), {"version": 1})

    assert response.status_code == 422
    assert error(response)["code"] == "invalid_agreement_transition"
    assert error(response)["message"] == "An active agreement cannot be resumed."


def test_action_with_stale_version_is_409(authenticated_client):
    agreement = make_agreement()
    authenticated_client.post(action_url("pause", agreement.pk), {"version": 1})

    response = authenticated_client.post(action_url("cancel", agreement.pk), {"version": 1})

    assert response.status_code == 409


def test_action_on_unknown_agreement_is_404(authenticated_client):
    response = authenticated_client.post(action_url("pause", uuid.uuid4()), {"version": 1})

    assert response.status_code == 404


# --- Cross-app rule through the customers API -------------------------------------------


def test_customer_with_live_agreement_cannot_be_deactivated_via_api(authenticated_client):
    customer = make_customer()
    make_agreement(customer=customer)

    response = authenticated_client.post(reverse("customer-deactivate", kwargs={"pk": customer.pk}))

    assert response.status_code == 422
    assert error(response)["code"] == "customer_has_live_agreements"
