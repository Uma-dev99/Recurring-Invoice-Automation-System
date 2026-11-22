"""Write operations on billing periods.

These are building blocks, called by the agreement services INSIDE their transaction
(create, resume, cancel, price change), and later by the daily billing job (Phase 7).
They never open user-facing flows of their own and never write audit rows: the caller
audits the business action ("agreement.cancelled") and includes what happened to the
periods in that one audit row.

Status changes use CONDITIONAL updates (UPDATE ... WHERE status = 'SCHEDULED'). A row
only changes if it is still in the expected state at the moment the database touches
it, so the daily job and a person clicking "Resume" can't both change the same period.
"""

import datetime
from decimal import Decimal

from apps.agreements.models import BillingAgreement
from apps.billing.exceptions import NoUnbilledPeriods, PeriodsAlreadyInvoiced
from apps.billing.models import BillingPeriod
from apps.billing.schedule import build_schedule

Status = BillingPeriod.Status


def generate_periods(*, agreement: BillingAgreement) -> list[BillingPeriod]:
    """Create the agreement's missing periods. Safe to call again: existing ones stay.

    New periods snapshot the agreement's current amount and currency. For a cancelled
    agreement (only reachable through the backfill of old data) they start CANCELLED.
    Two concurrent calls can both compute the same "missing" months; the database's
    unique (agreement, cycle_number) constraint then rejects the second insert loudly
    instead of creating duplicates.
    """
    existing = set(agreement.periods.values_list("cycle_number", flat=True))
    initial_status = (
        Status.CANCELLED
        if agreement.status == BillingAgreement.Status.CANCELLED
        else Status.SCHEDULED
    )
    new_periods = [
        BillingPeriod(
            agreement=agreement,
            cycle_number=dates.cycle_number,
            period_start=dates.start,
            period_end=dates.end,
            amount=agreement.amount,
            currency=agreement.currency,
            status=initial_status,
        )
        for dates in build_schedule(agreement.anchor_date, agreement.total_cycles)
        if dates.cycle_number not in existing
    ]
    # One INSERT for all rows instead of one per month.
    return BillingPeriod.objects.bulk_create(new_periods)


def skip_periods_due_while_paused(*, agreement: BillingAgreement, today: datetime.date) -> int:
    """Mark SCHEDULED periods that started on or before `today` as SKIPPED.

    Called on resume (before the agreement becomes active again) and on cancelling a
    paused agreement: months that fell due while billing was paused are never billed.
    Returns how many periods were skipped.
    """
    return agreement.periods.filter(status=Status.SCHEDULED, period_start__lte=today).update(
        status=Status.SKIPPED
    )


def cancel_open_periods(*, agreement: BillingAgreement) -> int:
    """Cancel every period that hasn't started invoicing. Returns how many.

    INVOICING and INVOICED periods are left alone: they belong to Riverty's process.
    """
    return agreement.periods.filter(status=Status.SCHEDULED).update(status=Status.CANCELLED)


def reprice_periods(*, agreement: BillingAgreement, from_cycle: int, amount: Decimal) -> int:
    """Set `amount` on the SCHEDULED periods from month `from_cycle` onwards.

    Refused if any month in that range is INVOICING or INVOICED: an invoice that went
    (or is going) out with the old price must never disagree with its period. SKIPPED
    and CANCELLED months are ignored. Returns how many periods changed.
    """
    in_range = agreement.periods.filter(cycle_number__gte=from_cycle)
    locked_by_invoicing = in_range.filter(status__in=[Status.INVOICING, Status.INVOICED])
    if locked_by_invoicing.exists():
        first = locked_by_invoicing.order_by("cycle_number").first()
        raise PeriodsAlreadyInvoiced(
            f"Month {first.cycle_number} is already invoiced. Choose a later month.",
            details={"first_invoiced_cycle": first.cycle_number},
        )

    changed = in_range.filter(status=Status.SCHEDULED).update(amount=amount)
    if changed == 0:
        raise NoUnbilledPeriods(f"No months from month {from_cycle} onwards can still be billed.")
    return changed
