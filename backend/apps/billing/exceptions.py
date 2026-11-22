"""Business-rule violations for billing periods (HTTP 422)."""

from apps.core.exceptions import DomainError


class PeriodsAlreadyInvoiced(DomainError):
    """A price change would touch a month that is being or has been invoiced."""

    code = "periods_already_invoiced"


class NoUnbilledPeriods(DomainError):
    """A price change from month N finds no months left that could still change."""

    code = "no_unbilled_periods"
