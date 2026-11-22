"""The state machine on its own: no database, so these run in milliseconds.

The table below IS the specification: every (status, action) pair is listed, so adding
a status or an action without deciding its rules makes a test fail.
"""

import pytest

from apps.agreements.exceptions import InvalidAgreementTransition
from apps.agreements.lifecycle import Action, next_status
from apps.agreements.models import BillingAgreement

S = BillingAgreement.Status

EXPECTED = {
    (S.ACTIVE, Action.PAUSE): S.PAUSED,
    (S.ACTIVE, Action.RESUME): None,
    (S.ACTIVE, Action.CANCEL): S.CANCELLED,
    (S.PAUSED, Action.PAUSE): None,
    (S.PAUSED, Action.RESUME): S.ACTIVE,
    (S.PAUSED, Action.CANCEL): S.CANCELLED,
    (S.CANCELLED, Action.PAUSE): None,
    (S.CANCELLED, Action.RESUME): None,
    (S.CANCELLED, Action.CANCEL): None,
    (S.COMPLETED, Action.PAUSE): None,
    (S.COMPLETED, Action.RESUME): None,
    (S.COMPLETED, Action.CANCEL): None,
}  # None = not allowed


def test_table_covers_every_status_and_action():
    assert set(EXPECTED) == {(status, action) for status in S for action in Action}


@pytest.mark.parametrize(("status", "action"), list(EXPECTED))
def test_transition(status, action):
    expected = EXPECTED[(status, action)]

    if expected is None:
        with pytest.raises(InvalidAgreementTransition):
            next_status(status, action)
    else:
        assert next_status(status, action) == expected


def test_refusal_explains_itself():
    with pytest.raises(InvalidAgreementTransition) as exc_info:
        next_status(S.CANCELLED, Action.PAUSE)

    assert exc_info.value.message == "A cancelled agreement cannot be paused."
    assert exc_info.value.code == "invalid_agreement_transition"


def test_refusal_uses_the_right_article():
    with pytest.raises(InvalidAgreementTransition) as exc_info:
        next_status(S.ACTIVE, Action.RESUME)

    assert exc_info.value.message == "An active agreement cannot be resumed."
