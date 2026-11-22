"""API tests: the HTTP contract of /api/v1/customers/.

Business rules are covered in test_services.py. These tests check what only the HTTP
layer can get wrong: status codes, the error envelope, which methods exist, auth and
CSRF, query-parameter validation and response shape.
"""

import uuid

import pytest
from django.urls import reverse

from apps.customers.models import DUPLICATE_EXTERNAL_ID_MESSAGE, Customer
from apps.customers.tests.factories import customer_data, make_customer
from apps.operations.models import AuditLog

pytestmark = pytest.mark.django_db

LIST_URL = reverse("customer-list")


def detail_url(customer_id) -> str:
    return reverse("customer-detail", kwargs={"pk": customer_id})


def action_url(name: str, customer_id) -> str:
    return reverse(f"customer-{name}", kwargs={"pk": customer_id})


def _payload(**overrides) -> dict:
    data = customer_data(**overrides)
    # The API takes plain strings, not TextChoices members.
    data["customer_type"] = str(data["customer_type"])
    return data


# --- Authentication and CSRF ----------------------------------------------------------


@pytest.mark.parametrize(
    "method, url",
    [
        ("get", LIST_URL),
        ("post", LIST_URL),
        ("get", detail_url(uuid.uuid4())),
        ("patch", detail_url(uuid.uuid4())),
        ("post", action_url("deactivate", uuid.uuid4())),
    ],
)
def test_every_endpoint_requires_login(api_client, method, url):
    response = getattr(api_client, method)(url, {})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_writes_require_csrf_token_for_session_users(csrf_client, user):
    # A real browser session (not force_authenticate): DRF enforces CSRF here.
    csrf_client.force_login(user)

    response = csrf_client.post(LIST_URL, _payload(), format="json")

    assert response.status_code == 403
    assert Customer.objects.count() == 0


# --- List -----------------------------------------------------------------------------


def test_list_is_paginated_with_standard_envelope(authenticated_client):
    for name in ["Charlie", "Alpha", "Bravo"]:
        make_customer(name=name)

    response = authenticated_client.get(LIST_URL, {"page_size": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    assert body["total_pages"] == 2
    assert [c["name"] for c in body["results"]] == ["Alpha", "Bravo"]
    assert body["next"] is not None


def test_list_applies_search_filters_and_ordering(authenticated_client):
    make_customer(name="Acme Person")
    make_customer(name="Acme Company", customer_type=Customer.CustomerType.COMPANY)
    make_customer(name="Acme Old", status=Customer.Status.INACTIVE)
    make_customer(name="Globex")

    response = authenticated_client.get(
        LIST_URL, {"search": "acme", "status": "ACTIVE", "ordering": "-name"}
    )

    assert [c["name"] for c in response.json()["results"]] == ["Acme Person", "Acme Company"]


@pytest.mark.parametrize(
    "params, bad_field",
    [
        ({"status": "DELETED"}, "status"),
        ({"customer_type": "ROBOT"}, "customer_type"),
        ({"ordering": "email"}, "ordering"),
    ],
)
def test_list_rejects_invalid_query_parameters(authenticated_client, params, bad_field):
    response = authenticated_client.get(LIST_URL, params)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert bad_field in response.json()["error"]["details"]


# --- Create -----------------------------------------------------------------------------


def test_create_returns_201_with_full_customer_and_audits(authenticated_client, user):
    response = authenticated_client.post(LIST_URL, _payload(name="Acme B.V.", country_code="nl"))

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Acme B.V."
    assert body["country_code"] == "NL"  # normalized by the service
    assert body["status"] == "ACTIVE"
    assert {"id", "created_at", "updated_at"} <= set(body)

    audit = AuditLog.objects.get(entity_id=body["id"])
    assert audit.action == "customer.created"
    assert audit.actor == user


def test_create_reports_missing_and_invalid_fields(authenticated_client):
    response = authenticated_client.post(LIST_URL, {"name": "Only a name", "email": "nope"})

    assert response.status_code == 400
    details = response.json()["error"]["details"]
    assert {"external_customer_id", "email", "address_line1", "country_code"} <= set(details)


def test_create_reports_model_rule_violations_as_400(authenticated_client):
    # Shape is fine (2 characters) but the model's rule says letters only. The service's
    # full_clean() raises; the core handler turns it into the same 400 envelope.
    response = authenticated_client.post(LIST_URL, _payload(country_code="1A"))

    assert response.status_code == 400
    assert "country_code" in response.json()["error"]["details"]


def test_create_rejects_duplicate_external_id(authenticated_client):
    make_customer(external_customer_id="C-1")

    response = authenticated_client.post(LIST_URL, _payload(external_customer_id="C-1"))

    assert response.status_code == 400
    assert response.json()["error"]["details"] == {
        "external_customer_id": [DUPLICATE_EXTERNAL_ID_MESSAGE]
    }


def test_create_refuses_fields_that_are_not_part_of_the_api(authenticated_client):
    response = authenticated_client.post(LIST_URL, _payload(status="INACTIVE"))

    assert response.status_code == 400
    assert "status" in response.json()["error"]["details"]
    assert Customer.objects.count() == 0


# --- Detail and edit ---------------------------------------------------------------------


def test_detail_returns_customer(authenticated_client):
    customer = make_customer(name="Acme")

    response = authenticated_client.get(detail_url(customer.pk))

    assert response.status_code == 200
    assert response.json()["id"] == str(customer.pk)


def test_unknown_customer_is_404_in_envelope(authenticated_client):
    response = authenticated_client.get(detail_url(uuid.uuid4()))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_patch_changes_only_sent_fields(authenticated_client):
    customer = make_customer(name="Old", city="Amsterdam")

    response = authenticated_client.patch(detail_url(customer.pk), {"name": "New"})

    assert response.status_code == 200
    assert response.json()["name"] == "New"
    assert response.json()["city"] == "Amsterdam"
    audit = AuditLog.objects.get(entity_id=customer.pk)
    assert audit.changes == {"name": {"old": "Old", "new": "New"}}


@pytest.mark.parametrize(
    "field, value", [("external_customer_id", "C-NEW"), ("status", "INACTIVE")]
)
def test_patch_refuses_fields_that_cannot_be_edited(authenticated_client, field, value):
    customer = make_customer()

    response = authenticated_client.patch(detail_url(customer.pk), {field: value})

    assert response.status_code == 400
    assert field in response.json()["error"]["details"]


@pytest.mark.parametrize("method", ["put", "delete"])
def test_put_and_delete_are_not_offered(authenticated_client, method):
    customer = make_customer()

    response = getattr(authenticated_client, method)(detail_url(customer.pk), _payload())

    assert response.status_code == 405
    assert Customer.objects.filter(pk=customer.pk).exists()


# --- Status actions -------------------------------------------------------------------


def test_deactivate_and_reactivate(authenticated_client):
    customer = make_customer()

    deactivated = authenticated_client.post(action_url("deactivate", customer.pk))
    reactivated = authenticated_client.post(action_url("reactivate", customer.pk))

    assert deactivated.status_code == 200
    assert deactivated.json()["status"] == "INACTIVE"
    assert reactivated.json()["status"] == "ACTIVE"


def test_deactivating_twice_is_422_with_business_code(authenticated_client):
    customer = make_customer(status=Customer.Status.INACTIVE)

    response = authenticated_client.post(action_url("deactivate", customer.pk))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "customer_already_inactive"


def test_action_on_unknown_customer_is_404(authenticated_client):
    response = authenticated_client.post(action_url("deactivate", uuid.uuid4()))

    assert response.status_code == 404
