"""Write operations for customers: one function per use case.

Rules every function here follows:
  * Keyword-only arguments, so call sites read like sentences and can't swap values.
  * Validate with the model's own rules (full_clean), because callers are not only
    the API: background jobs and scripts will call these too, without a serializer.
  * The change and its AuditLog row are written in ONE transaction.
  * Rows being changed are locked with select_for_update(), so two simultaneous edits
    can't overwrite each other or record a wrong "old" value in the audit log.
  * No HTTP here: no Request, no Response, no status codes. Errors are raised as
    Django ValidationError (bad input) or DomainError (a business rule says no).
"""

from collections.abc import Callable

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

# Customers ask the agreements app a read-only question ("any live agreements?") through
# its selector, rather than querying agreement statuses themselves.
from apps.agreements.selectors import has_live_agreements
from apps.customers.exceptions import (
    CustomerAlreadyActive,
    CustomerAlreadyInactive,
    CustomerHasLiveAgreements,
)
from apps.customers.models import DUPLICATE_EXTERNAL_ID_MESSAGE, Customer
from apps.operations.services import record_audit_event

# Fields a caller provides when creating a customer. `status` is not one of them:
# every customer starts ACTIVE and changes status only via deactivate/reactivate.
CREATABLE_FIELDS = frozenset(
    {
        "external_customer_id",
        "customer_type",
        "name",
        "email",
        "phone",
        "address_line1",
        "address_line2",
        "postal_code",
        "city",
        "country_code",
    }
)
# external_customer_id is fixed after creation: it is the link to the business's own
# system, and later phases (agreements, Riverty) identify the customer by it.
UPDATABLE_FIELDS = CREATABLE_FIELDS - {"external_customer_id"}


def _check_fields(data: dict, allowed: frozenset[str]) -> None:
    # Unknown keys are a programming error (the serializer decides which keys exist),
    # not user input, so this is a ValueError and would surface as a 500 in tests.
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"Unsupported customer fields: {sorted(unknown)}")


def _normalize(customer: Customer) -> None:
    """Clean up input the way staff would expect, before validation."""
    for field in CREATABLE_FIELDS - {"customer_type"}:
        setattr(customer, field, (getattr(customer, field) or "").strip())
    customer.country_code = customer.country_code.upper()
    # Lower-cases the domain only; the part before "@" is left as entered.
    customer.email = BaseUserManager.normalize_email(customer.email)


def create_customer(*, data: dict, actor: AbstractBaseUser | None) -> Customer:
    _check_fields(data, CREATABLE_FIELDS)

    customer = Customer(**data)
    _normalize(customer)
    # Field validators, choices, max lengths, email format and the unique external id.
    customer.full_clean()

    try:
        with transaction.atomic():
            customer.save(force_insert=True)
            record_audit_event(
                action="customer.created",
                instance=customer,
                actor=actor,
                changes={field: getattr(customer, field) for field in sorted(CREATABLE_FIELDS)},
            )
    except IntegrityError:
        # full_clean() checked uniqueness, but two requests at the same moment (a
        # double-click) can both pass that check. The database's unique index stops the
        # second insert; we turn that into the same friendly error the first check gives.
        if Customer.objects.filter(external_customer_id=customer.external_customer_id).exists():
            raise ValidationError(
                {"external_customer_id": [DUPLICATE_EXTERNAL_ID_MESSAGE]}
            ) from None
        raise
    return customer


def update_customer(*, customer: Customer, data: dict, actor: AbstractBaseUser | None) -> Customer:
    """Apply `data` (any subset of UPDATABLE_FIELDS). Records only fields that changed."""
    _check_fields(data, UPDATABLE_FIELDS)

    with transaction.atomic():
        # Re-read under a row lock: `customer` may be stale (loaded earlier in the
        # request), and the audit "old" values must be the ones actually replaced.
        locked = Customer.objects.select_for_update().get(pk=customer.pk)
        before = {field: getattr(locked, field) for field in data}

        for field, value in data.items():
            setattr(locked, field, value)
        _normalize(locked)

        changes = {
            field: {"old": before[field], "new": getattr(locked, field)}
            for field in data
            if getattr(locked, field) != before[field]
        }
        if not changes:
            # Nothing really changed: no write, no audit noise, updated_at untouched.
            return locked

        locked.full_clean()
        locked.save(update_fields=[*changes, "updated_at"])
        record_audit_event(action="customer.updated", instance=locked, actor=actor, changes=changes)
    return locked


def deactivate_customer(*, customer: Customer, actor: AbstractBaseUser | None) -> Customer:
    """Mark a customer INACTIVE. History stays; customers are never deleted.

    Refused while the customer has active or paused agreements: those still produce
    bills, so they must be cancelled first.
    """

    def no_live_agreements(locked: Customer) -> None:
        # Checked while holding the customer's row lock; create_agreement() takes the same
        # lock, so no agreement can be created between this check and the status change.
        if has_live_agreements(locked):
            raise CustomerHasLiveAgreements(
                "This customer has active or paused agreements. Cancel them first."
            )

    return _change_status(
        customer=customer,
        actor=actor,
        new_status=Customer.Status.INACTIVE,
        action="customer.deactivated",
        already_error=CustomerAlreadyInactive("This customer is already inactive."),
        precondition=no_live_agreements,
    )


def reactivate_customer(*, customer: Customer, actor: AbstractBaseUser | None) -> Customer:
    return _change_status(
        customer=customer,
        actor=actor,
        new_status=Customer.Status.ACTIVE,
        action="customer.reactivated",
        already_error=CustomerAlreadyActive("This customer is already active."),
    )


def _change_status(
    *,
    customer: Customer,
    actor: AbstractBaseUser | None,
    new_status: str,
    action: str,
    already_error: Exception,
    precondition: Callable[[Customer], None] | None = None,
) -> Customer:
    with transaction.atomic():
        locked = Customer.objects.select_for_update().get(pk=customer.pk)
        if locked.status == new_status:
            raise already_error
        if precondition:
            precondition(locked)
        old_status = locked.status
        locked.status = new_status
        locked.save(update_fields=["status", "updated_at"])
        record_audit_event(
            action=action,
            instance=locked,
            actor=actor,
            changes={"status": {"old": old_status, "new": new_status}},
        )
    return locked
