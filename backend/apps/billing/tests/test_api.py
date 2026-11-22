"""API tests for the schedule endpoint and the change-amount action."""

import datetime
import uuid
from unittest import mock

import pytest
from django.urls import reverse

from apps.agreements import services as agreement_services
from apps.agreements.tests.factories import make_agreement
from apps.billing.models import BillingPeriod
from apps.customers.tests.factories import make_customer

pytestmark = pytest.mark.django_db

TODAY = datetime.date(2027, 1, 15)


@pytest.fixture(autouse=True)
def fixed_today():
    with mock.patch.object(agreement_services, "billing_today", return_value=TODAY):
        yield


def periods_url(agreement_id) -> str:
    return reverse("agreement-periods", kwargs={"agreement_id": agreement_id})


def change_amount_url(agreement_id) -> str:
    return reverse("agreement-change-amount", kwargs={"pk": agreement_id})


def create_via_api(client, **overrides) -> dict:
    payload = {
        "customer_id": str(make_customer().pk),
        "description": "Gold plan",
        "amount": "10.00",
        "anchor_date": "2027-01-31",
        "total_cycles": 4,
        **overrides,
    }
    response = client.post(reverse("agreement-list"), payload)
    assert response.status_code == 201, response.json()
    return response.json()


def error(response) -> dict:
    return response.json()["error"]


# --- GET /agreements/<id>/periods/ ---------------------------------------------------


def test_schedule_lists_every_month_in_order(authenticated_client):
    agreement = create_via_api(authenticated_client)

    response = authenticated_client.get(periods_url(agreement["id"]))

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)  # not paginated: the whole schedule at once
    assert [p["cycle_number"] for p in body] == [1, 2, 3, 4]
    assert body[0] | {"id": None} == {
        "id": None,
        "cycle_number": 1,
        "period_start": "2027-01-31",
        "period_end": "2027-02-27",
        "amount": "10.00",
        "currency": "EUR",
        "status": "SCHEDULED",
    }
    assert body[1]["period_start"] == "2027-02-28"


def test_schedule_of_unknown_agreement_is_404(authenticated_client):
    response = authenticated_client.get(periods_url(uuid.uuid4()))

    assert response.status_code == 404
    assert error(response)["code"] == "not_found"


def test_agreement_without_periods_returns_empty_list(authenticated_client):
    agreement = make_agreement()  # factory skips the service, so no schedule

    assert authenticated_client.get(periods_url(agreement.pk)).json() == []


def test_schedule_requires_login(api_client):
    assert api_client.get(periods_url(uuid.uuid4())).status_code == 401


# --- POST /agreements/<id>/change-amount/ ---------------------------------------------


def test_change_amount_from_month_three(authenticated_client):
    agreement = create_via_api(authenticated_client)

    response = authenticated_client.post(
        change_amount_url(agreement["id"]), {"version": 1, "from_cycle": 3, "amount": "12.50"}
    )

    assert response.status_code == 200
    assert response.json()["amount"] == "12.50"
    assert response.json()["version"] == 2
    schedule = authenticated_client.get(periods_url(agreement["id"])).json()
    assert [p["amount"] for p in schedule] == ["10.00", "10.00", "12.50", "12.50"]


def test_change_amount_with_stale_version_is_409(authenticated_client):
    agreement = create_via_api(authenticated_client)
    authenticated_client.post(
        reverse("agreement-pause", kwargs={"pk": agreement["id"]}), {"version": 1}
    )

    response = authenticated_client.post(
        change_amount_url(agreement["id"]), {"version": 1, "from_cycle": 1, "amount": "5.00"}
    )

    assert response.status_code == 409


def test_change_amount_past_the_last_month_is_a_field_error(authenticated_client):
    agreement = create_via_api(authenticated_client, total_cycles=4)

    response = authenticated_client.post(
        change_amount_url(agreement["id"]), {"version": 1, "from_cycle": 5, "amount": "5.00"}
    )

    assert response.status_code == 400
    assert "from_cycle" in error(response)["details"]


def test_change_amount_over_invoiced_month_is_422(authenticated_client):
    agreement = create_via_api(authenticated_client)
    BillingPeriod.objects.filter(agreement_id=agreement["id"], cycle_number=2).update(
        status="INVOICED"
    )

    response = authenticated_client.post(
        change_amount_url(agreement["id"]), {"version": 1, "from_cycle": 1, "amount": "5.00"}
    )

    assert response.status_code == 422
    assert error(response)["code"] == "periods_already_invoiced"
    assert error(response)["details"] == {"first_invoiced_cycle": 2}


@pytest.mark.parametrize(
    "body, field",
    [
        ({"from_cycle": 1, "amount": "5.00"}, "version"),
        ({"version": 1, "amount": "5.00"}, "from_cycle"),
        ({"version": 1, "from_cycle": 1, "amount": "5.001"}, "amount"),
        ({"version": 1, "from_cycle": 1, "amount": "0"}, "amount"),
        ({"version": 1, "from_cycle": 1, "amount": "5.00", "currency": "USD"}, "currency"),
    ],
)
def test_change_amount_validates_the_body(authenticated_client, body, field):
    agreement = create_via_api(authenticated_client)

    response = authenticated_client.post(change_amount_url(agreement["id"]), body)

    assert response.status_code == 400
    assert field in error(response)["details"]


def test_change_amount_on_unknown_agreement_is_404(authenticated_client):
    response = authenticated_client.post(
        change_amount_url(uuid.uuid4()), {"version": 1, "from_cycle": 1, "amount": "5.00"}
    )

    assert response.status_code == 404
