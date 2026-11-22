import datetime

import pytest
from django.utils import timezone

from apps.operations import outbox
from apps.operations.models import OutboxEvent

pytestmark = pytest.mark.django_db


@pytest.fixture
def calls():
    """Registers a test handler that records payloads, and can be told to fail."""
    received: list[dict] = []
    state = {"fail": False}

    def handler(payload: dict) -> None:
        received.append(payload)
        if state["fail"]:
            raise RuntimeError("handler broke")

    outbox.register_handler("test.event", handler)
    yield received, state
    outbox._HANDLERS.pop("test.event", None)


def test_enqueue_refuses_unknown_event_types():
    with pytest.raises(ValueError):
        outbox.enqueue("nobody.handles.this", {})


def test_event_is_delivered_once_and_marked_done(calls):
    received, _ = calls
    event = outbox.enqueue("test.event", {"id": "42"})

    result = outbox.process_outbox()
    outbox.process_outbox()  # a second run finds nothing new

    event.refresh_from_db()
    assert received == [{"id": "42"}]
    assert event.status == OutboxEvent.Status.DONE
    assert event.processed_at is not None
    assert result.done == 1


def test_event_scheduled_for_later_waits(calls):
    received, _ = calls
    outbox.enqueue("test.event", {}, available_at=timezone.now() + datetime.timedelta(hours=1))

    outbox.process_outbox()

    assert received == []


def test_failed_handler_is_retried_later_with_backoff(calls):
    _, state = calls
    state["fail"] = True
    event = outbox.enqueue("test.event", {})

    result = outbox.process_outbox()

    event.refresh_from_db()
    assert result.retried == 1
    assert event.status == OutboxEvent.Status.PENDING
    assert event.attempts == 1
    assert event.available_at > timezone.now()  # not immediately: backoff
    assert "handler broke" in event.last_error


def test_event_fails_for_good_after_max_attempts(calls):
    _, state = calls
    state["fail"] = True
    event = outbox.enqueue("test.event", {})
    OutboxEvent.objects.filter(pk=event.pk).update(attempts=outbox.MAX_ATTEMPTS - 1)

    outbox.process_outbox()

    event.refresh_from_db()
    assert event.status == OutboxEvent.Status.FAILED


def test_stuck_processing_event_is_recovered(calls):
    received, _ = calls
    event = outbox.enqueue("test.event", {"id": "1"})
    # A dispatcher claimed it and died: PROCESSING with an expired claim.
    OutboxEvent.objects.filter(pk=event.pk).update(
        status=OutboxEvent.Status.PROCESSING,
        locked_until=timezone.now() - datetime.timedelta(minutes=1),
    )

    result = outbox.process_outbox()

    assert result.recovered == 1
    assert received == [{"id": "1"}]


@pytest.mark.parametrize("attempt", [1, 2, 5, 10, 50])
def test_backoff_grows_with_jitter_and_is_capped(attempt):
    expected = min(3600, 30 * 2 ** (attempt - 1))

    delays = {outbox.backoff(attempt).total_seconds() for _ in range(20)}

    assert all(expected * 0.5 <= d <= expected for d in delays)
