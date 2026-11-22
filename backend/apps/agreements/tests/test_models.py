"""Model tests: defaults, money handling, and the guarantees the DATABASE enforces.

As in apps/customers, most tests insert without full_clean() on purpose, to prove
PostgreSQL itself refuses invalid data.
"""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.utils import timezone

from apps.agreements.models import BillingAgreement
from apps.agreements.tests.factories import agreement_data, make_agreement
from apps.customers.tests.factories import make_customer

pytestmark = pytest.mark.django_db

Status = BillingAgreement.Status


def test_new_agreement_defaults():
    agreement = BillingAgreement.objects.create(
        customer=make_customer(),
        description="Gold plan",
        amount=Decimal("10.00"),
        anchor_date="2027-03-01",
    )

    assert agreement.status == Status.ACTIVE
    assert agreement.currency == "EUR"
    assert agreement.total_cycles == 12
    assert agreement.version == 1
    assert agreement.cancelled_at is None


def test_amount_is_stored_exactly():
    agreement = make_agreement(amount=Decimal("19.99"))
    agreement.refresh_from_db()

    assert agreement.amount == Decimal("19.99")
    assert isinstance(agreement.amount, Decimal)


def test_customer_has_reverse_relation_to_agreements():
    customer = make_customer()
    agreement = make_agreement(customer=customer)

    assert list(customer.agreements.all()) == [agreement]


@pytest.mark.parametrize(
    "status, cancelled",
    [
        (Status.ACTIVE, False),
        (Status.PAUSED, False),
        (Status.COMPLETED, False),
        (Status.CANCELLED, True),
    ],
)
def test_every_status_is_accepted_by_the_database(status, cancelled):
    # Guards against the CHECK constraint drifting from Status.
    make_agreement(status=status, cancelled_at=timezone.now() if cancelled else None)


# --- Database constraints -----------------------------------------------------------


@pytest.mark.parametrize("amount", [Decimal("0.00"), Decimal("-5.00")])
def test_non_positive_amount_is_rejected(amount):
    with pytest.raises(IntegrityError):
        make_agreement(amount=amount)


@pytest.mark.parametrize("currency", ["USD", "GBP", "eur", ""])
def test_only_eur_is_accepted_by_the_database(currency):
    with pytest.raises(IntegrityError):
        make_agreement(currency=currency)


def test_full_clean_rejects_non_eur_currency():
    agreement = BillingAgreement(customer=make_customer(), **agreement_data(currency="USD"))

    with pytest.raises(ValidationError) as exc_info:
        agreement.full_clean()

    assert "currency" in exc_info.value.message_dict


@pytest.mark.parametrize("total_cycles", [0, 121])
def test_total_cycles_outside_range_is_rejected(total_cycles):
    with pytest.raises(IntegrityError):
        make_agreement(total_cycles=total_cycles)


def test_unknown_status_is_rejected():
    with pytest.raises(IntegrityError):
        make_agreement(status="DELETED")


def test_cancelled_agreement_must_have_cancelled_at():
    with pytest.raises(IntegrityError):
        make_agreement(status=Status.CANCELLED, cancelled_at=None)


def test_live_agreement_must_not_have_cancelled_at():
    with pytest.raises(IntegrityError):
        make_agreement(status=Status.ACTIVE, cancelled_at=timezone.now())


def test_description_cannot_be_empty():
    with pytest.raises(IntegrityError):
        make_agreement(description="")


def test_customer_with_agreements_cannot_be_deleted():
    customer = make_customer()
    make_agreement(customer=customer)

    with pytest.raises(ProtectedError):
        customer.delete()


# --- Python-level validation (what the service layer relies on) ---------------------


def test_full_clean_rejects_more_than_two_decimals():
    # Without this check, PostgreSQL's NUMERIC(12, 2) would silently ROUND 19.999 to
    # 20.00. For money, refusing is correct; rounding without telling anyone is not.
    agreement = BillingAgreement(
        customer=make_customer(), **agreement_data(amount=Decimal("19.999"))
    )

    with pytest.raises(ValidationError) as exc_info:
        agreement.full_clean()

    assert "amount" in exc_info.value.message_dict


def test_full_clean_rejects_amount_too_large():
    agreement = BillingAgreement(
        customer=make_customer(), **agreement_data(amount=Decimal("10000000000.00"))
    )

    with pytest.raises(ValidationError) as exc_info:
        agreement.full_clean()

    assert "amount" in exc_info.value.message_dict


def test_full_clean_accepts_valid_agreement():
    BillingAgreement(customer=make_customer(), **agreement_data()).full_clean()
