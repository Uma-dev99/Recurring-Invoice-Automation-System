"""Business-rule violations for customers.

Each subclass carries a stable `code` the React client can branch on. The core
exception handler turns them into HTTP 422 with the standard error envelope.
"""

from apps.core.exceptions import DomainError


class CustomerAlreadyInactive(DomainError):
    code = "customer_already_inactive"


class CustomerAlreadyActive(DomainError):
    code = "customer_already_active"


class CustomerHasLiveAgreements(DomainError):
    code = "customer_has_live_agreements"
