"""Allowed status moves for an invoice submission. Pure Python, no database.

Every status change in services.py and operator.py goes through move(); a move that
isn't in this table is a bug, so it raises instead of silently writing an impossible
state. Moves marked (operator) are only made by a person, via operator.py.
"""

from apps.invoicing.models import InvoiceSubmission

S = InvoiceSubmission.Status

ALLOWED: dict[str, frozenset[str]] = {
    S.PENDING: frozenset({S.SUBMITTING, S.NEEDS_ATTENTION}),
    S.SUBMITTING: frozenset(
        {S.ACCEPTED, S.REJECTED, S.RETRY_SCHEDULED, S.UNKNOWN, S.NEEDS_ATTENTION}
    ),
    S.RETRY_SCHEDULED: frozenset({S.SUBMITTING, S.NEEDS_ATTENTION}),
    # UNKNOWN is resolved by reconciliation: found at Riverty -> ACCEPTED; provably not
    # there -> safe to retry; can't tell for too long -> a human decides. An operator can
    # also confirm it either way, or (after checking it isn't at Riverty) cancel it.
    S.UNKNOWN: frozenset({S.ACCEPTED, S.RETRY_SCHEDULED, S.NEEDS_ATTENTION, S.CANCELLED}),
    # (operator) retry, confirm received, or give up on this month.
    S.NEEDS_ATTENTION: frozenset({S.RETRY_SCHEDULED, S.ACCEPTED, S.CANCELLED}),
    # (operator) after the data was fixed: retry; or give up on this month.
    S.REJECTED: frozenset({S.RETRY_SCHEDULED, S.CANCELLED}),
    S.ACCEPTED: frozenset(),  # final: an accepted invoice is never "un-accepted"
    S.CANCELLED: frozenset(),  # final
}


class InvalidSubmissionTransition(RuntimeError):
    """A programming error: code tried a status move the table above forbids."""


def move(submission: InvoiceSubmission, new_status: str) -> None:
    """Set the new status, or raise if the move isn't allowed. Caller saves."""
    if new_status not in ALLOWED[submission.status]:
        raise InvalidSubmissionTransition(f"{submission.status} -> {new_status} is not allowed.")
    submission.status = new_status
