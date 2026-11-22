"""Business-rule violations raised by operator actions (HTTP 422, or 409 where stated)."""

from rest_framework import status

from apps.core.exceptions import DomainError


class InvoiceChanged(DomainError):
    """The invoice is no longer in the status the operator was looking at.

    409, like the agreement version conflict: the request was fine, but it was based on
    an old view (e.g. a background retry succeeded while the page was open).
    """

    status_code = status.HTTP_409_CONFLICT
    code = "invoice_changed"


class ActionNotAllowed(DomainError):
    """This action isn't possible in the invoice's current status."""

    code = "action_not_allowed"


class RivertyCheckRequired(DomainError):
    """Riverty may already have this invoice; the operator must confirm it doesn't.

    Raised for retry/cancel when the latest attempt ended without a clear answer. Without
    this check, a retry could invoice the customer twice.
    """

    code = "riverty_check_required"


class PeriodNotActionable(DomainError):
    code = "period_not_actionable"
