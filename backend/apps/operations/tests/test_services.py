import datetime
import uuid
from decimal import Decimal

import pytest

from apps.customers.tests.factories import make_customer
from apps.operations.services import record_audit_event

pytestmark = pytest.mark.django_db


def test_records_entity_type_and_id_from_the_instance(user):
    customer = make_customer()

    entry = record_audit_event(action="customer.created", instance=customer, actor=user)

    assert entry.entity_type == "customers.customer"
    assert entry.entity_id == customer.pk
    assert entry.actor == user
    assert entry.changes == {}


def test_changes_are_stored_json_safe_and_decimals_stay_exact():
    customer = make_customer()
    some_id = uuid.uuid4()

    entry = record_audit_event(
        action="agreement.updated",
        instance=customer,
        actor=None,
        changes={
            "amount": {"old": Decimal("10.10"), "new": Decimal("12.50")},
            "anchor_date": datetime.date(2027, 1, 31),
            "ref": some_id,
        },
    )
    entry.refresh_from_db()

    assert entry.changes == {
        "amount": {"old": "10.10", "new": "12.50"},  # strings, never floats like 12.5
        "anchor_date": "2027-01-31",
        "ref": str(some_id),
    }
