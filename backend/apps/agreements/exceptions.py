"""Business-rule violations for billing agreements (HTTP 422 unless stated otherwise)."""

from rest_framework import status

from apps.core.exceptions import DomainError


class CustomerNotActive(DomainError):
    code = "customer_not_active"


class InvalidAgreementTransition(DomainError):
    """E.g. pausing a cancelled agreement. Raised by lifecycle.next_status()."""

    code = "invalid_agreement_transition"


class AgreementClosed(DomainError):
    """Cancelled and completed agreements are history: they can't be edited."""

    code = "agreement_closed"


class AgreementVersionConflict(DomainError):
    """Someone else changed the agreement after this client loaded it.

    409 Conflict, not 422: the request itself is fine, it was just based on an old
    copy. The client should reload and try again.
    """

    status_code = status.HTTP_409_CONFLICT
    code = "agreement_version_conflict"
