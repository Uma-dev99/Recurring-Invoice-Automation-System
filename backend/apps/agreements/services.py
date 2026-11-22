"""Write operations for billing agreements: one function per use case.

Same rules as apps/customers/services.py (keyword-only arguments, full_clean(), change
+ audit in one transaction, row locks, no HTTP), plus two more:

  * Optimistic locking. Every write takes `expected_version`: the version the caller
    saw when it loaded the agreement. If the row's version differs, someone else changed
    it in the meantime and the write is refused (AgreementVersionConflict, HTTP 409).
    Every successful write increments the version.
  * Lifecycle rules live in lifecycle.py; services only apply its answer.

Phase 3 scope: amount, start date and number of cycles are fixed once created. Changing
the amount "from month N" needs the billing periods of Phase 4. Until then, a wrong
amount or date is fixed by cancelling and creating a new agreement.
"""

from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.agreements.exceptions import AgreementClosed, AgreementVersionConflict, CustomerNotActive
from apps.agreements.lifecycle import PAST_TENSE, TERMINAL_STATUSES, Action, next_status
from apps.agreements.models import BillingAgreement
from apps.core.dates import billing_today
from apps.customers.models import Customer
from apps.operations.services import record_audit_event

CREATABLE_FIELDS = frozenset({"description", "amount", "anchor_date", "total_cycles"})
UPDATABLE_FIELDS = frozenset({"description"})

START_IN_PAST_MESSAGE = "The first billing date cannot be in the past."


def _check_fields(data: dict, allowed: frozenset[str]) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"Unsupported agreement fields: {sorted(unknown)}")


def _lock(agreement: BillingAgreement, expected_version: int) -> BillingAgreement:
    """Re-read the agreement under a row lock and check nobody changed it meanwhile.

    Must be called inside transaction.atomic(). The row lock stops two writes running at
    the same moment; the version check stops a write based on an old copy of the data
    (e.g. a browser tab opened an hour ago).
    """
    locked = BillingAgreement.objects.select_for_update().get(pk=agreement.pk)
    if locked.version != expected_version:
        raise AgreementVersionConflict(
            "This agreement was changed by someone else. Reload it and try again.",
            details={"expected_version": expected_version, "current_version": locked.version},
        )
    return locked


def create_agreement(
    *, customer: Customer, data: dict, actor: AbstractBaseUser | None
) -> BillingAgreement:
    _check_fields(data, CREATABLE_FIELDS)

    with transaction.atomic():
        # Lock the customer row: deactivate_customer() locks the same row, so "create an
        # agreement" and "deactivate the customer" can never both succeed at once.
        locked_customer = Customer.objects.select_for_update().get(pk=customer.pk)
        if locked_customer.status != Customer.Status.ACTIVE:
            raise CustomerNotActive("Agreements can only be created for active customers.")

        agreement = BillingAgreement(customer=locked_customer, **data)
        agreement.description = (agreement.description or "").strip()

        # A past start date would make Phase 4 bill the missed months immediately, and
        # with Riverty a period can only be invoiced inside its own dates.
        if agreement.anchor_date is not None and agreement.anchor_date < billing_today():
            raise ValidationError({"anchor_date": [START_IN_PAST_MESSAGE]})

        agreement.full_clean()
        agreement.save(force_insert=True)
        record_audit_event(
            action="agreement.created",
            instance=agreement,
            actor=actor,
            changes={
                "customer_id": agreement.customer_id,
                "description": agreement.description,
                "amount": agreement.amount,
                "currency": agreement.currency,
                "anchor_date": agreement.anchor_date,
                "total_cycles": agreement.total_cycles,
            },
        )
    return agreement


def update_agreement(
    *,
    agreement: BillingAgreement,
    data: dict,
    expected_version: int,
    actor: AbstractBaseUser | None,
) -> BillingAgreement:
    """Change editable fields (Phase 3: description only). Audits only real changes."""
    _check_fields(data, UPDATABLE_FIELDS)

    with transaction.atomic():
        locked = _lock(agreement, expected_version)
        if locked.status in TERMINAL_STATUSES:
            raise AgreementClosed(
                f"A {locked.get_status_display().lower()} agreement can no longer be changed."
            )

        before = {field: getattr(locked, field) for field in data}
        for field, value in data.items():
            setattr(locked, field, value.strip() if isinstance(value, str) else value)

        changes = {
            field: {"old": before[field], "new": getattr(locked, field)}
            for field in data
            if getattr(locked, field) != before[field]
        }
        if not changes:
            return locked

        locked.full_clean()
        locked.version += 1
        locked.save(update_fields=[*changes, "version", "updated_at"])
        record_audit_event(
            action="agreement.updated", instance=locked, actor=actor, changes=changes
        )
    return locked


def pause_agreement(
    *, agreement: BillingAgreement, expected_version: int, actor: AbstractBaseUser | None
) -> BillingAgreement:
    """Stop billing for now. Bills that fall due while paused are skipped (Phase 4)."""
    return _transition(agreement, Action.PAUSE, expected_version, actor)


def resume_agreement(
    *, agreement: BillingAgreement, expected_version: int, actor: AbstractBaseUser | None
) -> BillingAgreement:
    """Continue billing on the original schedule. Skipped months are not billed back."""
    return _transition(agreement, Action.RESUME, expected_version, actor)


def cancel_agreement(
    *,
    agreement: BillingAgreement,
    expected_version: int,
    actor: AbstractBaseUser | None,
    reason: str = "",
) -> BillingAgreement:
    """End the agreement for good. Already-sent invoices are untouched (Riverty owns them)."""
    return _transition(agreement, Action.CANCEL, expected_version, actor, reason=reason.strip())


def _transition(
    agreement: BillingAgreement,
    action: Action,
    expected_version: int,
    actor: AbstractBaseUser | None,
    reason: str = "",
) -> BillingAgreement:
    with transaction.atomic():
        locked = _lock(agreement, expected_version)
        old_status = locked.status
        locked.status = next_status(old_status, action)  # raises if not allowed
        update_fields = ["status", "version", "updated_at"]
        if action is Action.CANCEL:
            locked.cancelled_at = timezone.now()
            update_fields.append("cancelled_at")

        locked.version += 1
        locked.save(update_fields=update_fields)

        changes: dict = {"status": {"old": old_status, "new": locked.status}}
        if reason:
            changes["reason"] = reason
        record_audit_event(
            action=f"agreement.{PAST_TENSE[action]}",
            instance=locked,
            actor=actor,
            changes=changes,
        )
    return locked
