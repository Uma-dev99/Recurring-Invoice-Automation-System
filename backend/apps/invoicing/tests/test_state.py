import pytest

from apps.invoicing.models import InvoiceSubmission
from apps.invoicing.state import ALLOWED, InvalidSubmissionTransition, move

S = InvoiceSubmission.Status


def test_every_status_has_a_rule():
    assert set(ALLOWED) == set(S)


def test_accepted_is_final():
    assert ALLOWED[S.ACCEPTED] == frozenset()


@pytest.mark.parametrize(
    "current, new",
    [
        (S.PENDING, S.ACCEPTED),  # must go through SUBMITTING
        (S.UNKNOWN, S.SUBMITTING),  # never resend blindly; reconcile first
        (S.ACCEPTED, S.RETRY_SCHEDULED),
        (S.RETRY_SCHEDULED, S.ACCEPTED),
    ],
)
def test_forbidden_moves_raise(current, new):
    submission = InvoiceSubmission(status=current)

    with pytest.raises(InvalidSubmissionTransition):
        move(submission, new)


def test_allowed_move_sets_status():
    submission = InvoiceSubmission(status=S.PENDING)

    move(submission, S.SUBMITTING)

    assert submission.status == S.SUBMITTING
