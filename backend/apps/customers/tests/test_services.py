"""Service tests: business behaviour without any HTTP.

These call the functions exactly as a view, a background job or a script would.
"""

from unittest import mock

import pytest
from django.core.exceptions import ValidationError

from apps.customers import services
from apps.customers.exceptions import CustomerAlreadyActive, CustomerAlreadyInactive
from apps.customers.models import DUPLICATE_EXTERNAL_ID_MESSAGE, Customer
from apps.customers.tests.factories import customer_data, make_customer
from apps.operations.models import AuditLog

pytestmark = pytest.mark.django_db


def _audit_rows(customer: Customer) -> list[AuditLog]:
    return list(AuditLog.objects.filter(entity_id=customer.pk).order_by("created_at"))


# --- create_customer ----------------------------------------------------------------


def test_create_customer_saves_and_audits(user):
    customer = services.create_customer(data=customer_data(name="Acme B.V."), actor=user)

    customer.refresh_from_db()
    assert customer.name == "Acme B.V."
    assert customer.status == Customer.Status.ACTIVE

    [audit] = _audit_rows(customer)
    assert audit.action == "customer.created"
    assert audit.entity_type == "customers.customer"
    assert audit.actor == user
    assert audit.changes["name"] == "Acme B.V."


def test_create_customer_normalizes_input(user):
    customer = services.create_customer(
        data=customer_data(
            name="  Acme B.V. ",
            email="Billing@ACME.Example",
            country_code="nl",
            city=" Utrecht ",
        ),
        actor=user,
    )

    assert customer.name == "Acme B.V."
    assert customer.email == "Billing@acme.example"  # domain lower-cased, mailbox kept
    assert customer.country_code == "NL"
    assert customer.city == "Utrecht"


def test_create_customer_rejects_invalid_input_and_writes_nothing(user):
    with pytest.raises(ValidationError) as exc_info:
        services.create_customer(
            data=customer_data(email="not-an-email", country_code="Netherlands"), actor=user
        )

    assert {"email", "country_code"} <= set(exc_info.value.message_dict)
    assert Customer.objects.count() == 0
    assert AuditLog.objects.count() == 0


def test_create_customer_rejects_duplicate_external_id(user):
    services.create_customer(data=customer_data(external_customer_id="C-1"), actor=user)

    with pytest.raises(ValidationError) as exc_info:
        services.create_customer(data=customer_data(external_customer_id="C-1"), actor=user)

    assert exc_info.value.message_dict == {"external_customer_id": [DUPLICATE_EXTERNAL_ID_MESSAGE]}


def test_concurrent_duplicate_caught_by_database_gives_same_error(user):
    # Simulates the double-click race: the Python uniqueness check passes for both
    # requests, so only the database's unique index can stop the second insert.
    services.create_customer(data=customer_data(external_customer_id="C-1"), actor=user)

    with mock.patch.object(Customer, "validate_unique"):  # pretend the check saw nothing
        with pytest.raises(ValidationError) as exc_info:
            services.create_customer(data=customer_data(external_customer_id="C-1"), actor=user)

    assert exc_info.value.message_dict == {"external_customer_id": [DUPLICATE_EXTERNAL_ID_MESSAGE]}
    assert Customer.objects.count() == 1


def test_customer_is_not_saved_when_audit_write_fails(user):
    # The core promise of the service layer: change + audit commit together or not at all.
    with mock.patch.object(services, "record_audit_event", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            services.create_customer(data=customer_data(), actor=user)

    assert Customer.objects.count() == 0


def test_create_customer_does_not_accept_status(user):
    with pytest.raises(ValueError):
        services.create_customer(data=customer_data(status="INACTIVE"), actor=user)


# --- update_customer ----------------------------------------------------------------


def test_update_customer_audits_only_changed_fields(user):
    customer = make_customer(name="Old Name", city="Amsterdam")

    updated = services.update_customer(
        customer=customer,
        data={"name": "New Name", "city": "Amsterdam"},  # city is unchanged
        actor=user,
    )

    assert updated.name == "New Name"
    [audit] = _audit_rows(customer)
    assert audit.action == "customer.updated"
    assert audit.changes == {"name": {"old": "Old Name", "new": "New Name"}}


def test_update_with_no_real_change_writes_nothing(user):
    customer = make_customer(city="Amsterdam")
    updated_at_before = customer.updated_at

    services.update_customer(customer=customer, data={"city": " Amsterdam "}, actor=user)

    customer.refresh_from_db()
    assert customer.updated_at == updated_at_before
    assert _audit_rows(customer) == []


def test_update_uses_current_database_values_not_a_stale_instance(user):
    customer = make_customer(name="Original")
    stale = Customer.objects.get(pk=customer.pk)
    Customer.objects.filter(pk=customer.pk).update(name="Changed Elsewhere")

    services.update_customer(customer=stale, data={"name": "Final"}, actor=user)

    [audit] = _audit_rows(customer)
    assert audit.changes["name"]["old"] == "Changed Elsewhere"


def test_update_rejects_invalid_value_and_keeps_database_unchanged(user):
    customer = make_customer(email="ok@example.com")

    with pytest.raises(ValidationError):
        services.update_customer(customer=customer, data={"email": "broken"}, actor=user)

    customer.refresh_from_db()
    assert customer.email == "ok@example.com"
    assert _audit_rows(customer) == []


@pytest.mark.parametrize("field", ["external_customer_id", "status"])
def test_update_rejects_fields_that_cannot_be_edited(user, field):
    customer = make_customer()

    with pytest.raises(ValueError):
        services.update_customer(customer=customer, data={field: "X-1"}, actor=user)


# --- deactivate / reactivate ----------------------------------------------------------


def test_deactivate_customer(user):
    customer = make_customer()

    result = services.deactivate_customer(customer=customer, actor=user)

    assert result.status == Customer.Status.INACTIVE
    [audit] = _audit_rows(customer)
    assert audit.action == "customer.deactivated"
    assert audit.changes == {"status": {"old": "ACTIVE", "new": "INACTIVE"}}


def test_deactivating_an_inactive_customer_is_a_domain_error(user):
    customer = make_customer(status=Customer.Status.INACTIVE)

    with pytest.raises(CustomerAlreadyInactive) as exc_info:
        services.deactivate_customer(customer=customer, actor=user)

    assert exc_info.value.code == "customer_already_inactive"
    assert _audit_rows(customer) == []


def test_reactivate_customer(user):
    customer = make_customer(status=Customer.Status.INACTIVE)

    result = services.reactivate_customer(customer=customer, actor=user)

    assert result.status == Customer.Status.ACTIVE
    assert _audit_rows(customer)[0].action == "customer.reactivated"


def test_reactivating_an_active_customer_is_a_domain_error(user):
    with pytest.raises(CustomerAlreadyActive):
        services.reactivate_customer(customer=make_customer(), actor=user)


def test_system_actor_is_allowed(db):
    # Background jobs (Phase 7) act without a user.
    customer = services.create_customer(data=customer_data(), actor=None)

    assert _audit_rows(customer)[0].actor is None
