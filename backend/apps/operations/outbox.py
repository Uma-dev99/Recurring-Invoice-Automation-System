"""The transactional outbox: enqueue background work atomically, deliver it reliably.

    enqueue(...)          inside a service's transaction.atomic(): adds a PENDING row
    process_outbox(...)   claims available events and runs their handlers

Handlers are registered by the app that owns the work (e.g. invoicing registers
"invoice.submit" in its AppConfig.ready()). This app therefore never imports
invoicing, keeping operations at the bottom of the dependency graph.

Delivery is AT-LEAST-ONCE: a handler may run more than once for the same event (a
dispatcher can crash after the handler succeeded but before marking the event DONE).
Every handler must therefore be idempotent: re-check the current state and do nothing
if the work is already done.

Delivery paths (Phase 7):
  * fast path  enqueue() asks for a dispatcher run right AFTER the transaction commits
               (transaction.on_commit), so new work starts within seconds;
  * safety net Celery Beat runs the dispatcher every minute. If a wake-up message is
               lost (Redis restarted, broker down), the PENDING row is still found.
The run_billing_cycle command calls process_outbox() directly (development/manual use).
"""

import datetime
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.operations.models import OutboxEvent
from apps.operations.services import record_audit_event

logger = logging.getLogger(__name__)

Handler = Callable[[dict], None]
_HANDLERS: dict[str, Handler] = {}

MAX_ATTEMPTS = 8
CLAIM_TIMEOUT = datetime.timedelta(minutes=5)


def register_handler(event_type: str, handler: Handler) -> None:
    """Called once per event type, from the owning app's AppConfig.ready()."""
    _HANDLERS[event_type] = handler


def enqueue(
    event_type: str, payload: dict, *, available_at: datetime.datetime | None = None
) -> OutboxEvent:
    """Add work to the outbox. Call INSIDE the transaction of the change it belongs to."""
    if event_type not in _HANDLERS:
        # Fail at the source, not hours later in the dispatcher.
        raise ValueError(f"No outbox handler registered for {event_type!r}.")
    now = timezone.now()
    event = OutboxEvent.objects.create(
        event_type=event_type,
        payload=payload,
        available_at=available_at or now,
    )
    if event.available_at <= now:
        # AFTER commit, never before: a worker woken now could look for a row that the
        # still-open transaction hasn't made visible yet (or that then rolls back).
        transaction.on_commit(wake_dispatcher)
    return event


def wake_dispatcher() -> None:
    """Fast path: ask a worker to run the dispatcher now. Never raises.

    Runs after the business transaction has committed, so the change is already safe.
    If the broker is unreachable, log it and move on: the every-minute sweep will
    deliver the event anyway. A Redis outage must not turn a saved change into an error.
    """
    try:
        from apps.operations.tasks import dispatch_outbox  # avoid an import cycle

        dispatch_outbox.delay()
    except Exception:  # noqa: BLE001
        logger.warning("Could not wake the outbox dispatcher; the periodic sweep will run it.")


def backoff(attempt: int, *, base_seconds: int = 30, cap_seconds: int = 3600) -> datetime.timedelta:
    """Exponential backoff with jitter: about 30s, 60s, 2m, 4m ... capped at 1 hour.

    The random factor (0.5-1.0) spreads retries out, so 300 events that failed during the
    same outage don't all retry in the same second and cause the next outage.
    """
    delay = min(cap_seconds, base_seconds * 2 ** max(attempt - 1, 0))
    return datetime.timedelta(seconds=delay * random.uniform(0.5, 1.0))  # noqa: S311


@dataclass
class OutboxRunResult:
    done: int = 0
    retried: int = 0
    failed: int = 0
    recovered: int = 0


def process_outbox(*, limit: int = 100) -> OutboxRunResult:
    """Claim up to `limit` available events and run each handler once."""
    result = OutboxRunResult(recovered=_recover_stuck_events())
    for event_id in _claim(limit):
        _run(event_id, result)
    return result


def _recover_stuck_events() -> int:
    """PROCESSING events whose claim expired: the dispatcher died; make them PENDING."""
    return OutboxEvent.objects.filter(
        status=OutboxEvent.Status.PROCESSING, locked_until__lt=timezone.now()
    ).update(status=OutboxEvent.Status.PENDING, locked_until=None)


def _claim(limit: int) -> list:
    """Mark available events PROCESSING and return their ids.

    SELECT ... FOR UPDATE SKIP LOCKED: two dispatchers running at the same time each
    take different rows instead of waiting on, or double-processing, the same ones.
    The claim is committed BEFORE any handler runs, so no lock is held during slow work.
    """
    now = timezone.now()
    with transaction.atomic():
        ids = list(
            OutboxEvent.objects.select_for_update(skip_locked=True)
            .filter(status=OutboxEvent.Status.PENDING, available_at__lte=now)
            .order_by("available_at")
            .values_list("id", flat=True)[:limit]
        )
        OutboxEvent.objects.filter(id__in=ids).update(
            status=OutboxEvent.Status.PROCESSING, locked_until=now + CLAIM_TIMEOUT
        )
    return ids


def _run(event_id, result: OutboxRunResult) -> None:
    event = OutboxEvent.objects.get(pk=event_id)
    handler = _HANDLERS.get(event.event_type)
    try:
        if handler is None:
            raise LookupError(f"No handler registered for {event.event_type!r}.")
        handler(event.payload)
    except Exception as exc:  # noqa: BLE001 - any handler failure is retried, then FAILED
        logger.exception("Outbox event failed", extra={"event_id": str(event.pk)})
        event.attempts += 1
        event.last_error = f"{type(exc).__name__}: {exc}"[:2000]
        event.locked_until = None
        if event.attempts >= MAX_ATTEMPTS:
            event.status = OutboxEvent.Status.FAILED
            result.failed += 1
        else:
            event.status = OutboxEvent.Status.PENDING
            event.available_at = timezone.now() + backoff(event.attempts)
            result.retried += 1
        event.save(
            update_fields=["attempts", "last_error", "locked_until", "status", "available_at"]
        )
        return

    event.status = OutboxEvent.Status.DONE
    event.processed_at = timezone.now()
    event.locked_until = None
    event.save(update_fields=["status", "processed_at", "locked_until"])
    result.done += 1


def requeue_failed_event(*, event_id, reason: str, actor) -> OutboxEvent:
    """An operator sends a FAILED event round again (after fixing the cause).

    Fresh attempt budget, available now, and a wake-up after commit. Audited with the
    operator and their reason. Only FAILED events can be requeued.
    """
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValidationError({"reason": ["Explain briefly why (it is kept in the audit log)."]})
    with transaction.atomic():
        event = OutboxEvent.objects.select_for_update().get(pk=event_id)
        if event.status != OutboxEvent.Status.FAILED:
            raise ValidationError(
                {"status": [f"Only failed events can be requeued (this one is {event.status})."]}
            )
        previous_error = event.last_error
        event.status = OutboxEvent.Status.PENDING
        event.attempts = 0
        event.available_at = timezone.now()
        event.last_error = ""
        event.save(update_fields=["status", "attempts", "available_at", "last_error"])
        record_audit_event(
            action="outbox.operator_requeued",
            instance=event,
            actor=actor,
            changes={
                "reason": reason,
                "event_type": event.event_type,
                "previous_error": previous_error[:500],
            },
        )
        transaction.on_commit(wake_dispatcher)
    return event
