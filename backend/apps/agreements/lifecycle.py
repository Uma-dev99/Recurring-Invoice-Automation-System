"""The agreement lifecycle as a small state machine.

Pure Python: no database, no Django ORM. That keeps the rules in one place, readable
as a table, and testable in microseconds. Services call next_status() before changing
anything; if the transition isn't allowed, nothing is written.

    ACTIVE ──pause──▶ PAUSED ──resume──▶ ACTIVE
      │                  │
      └──────cancel──────┴──▶ CANCELLED   (terminal)

    COMPLETED is reached when every cycle has been billed (Phase 5) and is terminal.
"""

from enum import StrEnum

from apps.agreements.exceptions import InvalidAgreementTransition
from apps.agreements.models import BillingAgreement

Status = BillingAgreement.Status


class Action(StrEnum):
    PAUSE = "pause"
    RESUME = "resume"
    CANCEL = "cancel"


# action -> (statuses it may start from, status it leads to)
TRANSITIONS: dict[Action, tuple[frozenset[str], str]] = {
    Action.PAUSE: (frozenset({Status.ACTIVE}), Status.PAUSED),
    Action.RESUME: (frozenset({Status.PAUSED}), Status.ACTIVE),
    Action.CANCEL: (frozenset({Status.ACTIVE, Status.PAUSED}), Status.CANCELLED),
}

TERMINAL_STATUSES = frozenset({Status.CANCELLED, Status.COMPLETED})
# Agreements that may still produce bills. Used e.g. to stop a customer with live
# agreements from being deactivated.
LIVE_STATUSES = frozenset({Status.ACTIVE, Status.PAUSED})


# Used in error messages and audit actions ("agreement.paused").
PAST_TENSE: dict[Action, str] = {
    Action.PAUSE: "paused",
    Action.RESUME: "resumed",
    Action.CANCEL: "cancelled",
}


def next_status(current: str, action: Action) -> str:
    """The status `action` leads to from `current`, or InvalidAgreementTransition."""
    allowed_from, target = TRANSITIONS[action]
    if current not in allowed_from:
        label = Status(current).label.lower()
        article = "An" if label[0] in "aeiou" else "A"  # "An active", "A paused"
        raise InvalidAgreementTransition(
            f"{article} {label} agreement cannot be {PAST_TENSE[action]}.",
            details={"status": current, "action": str(action)},
        )
    return target
