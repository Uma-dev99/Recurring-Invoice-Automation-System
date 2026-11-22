from django.conf import settings
from django.db import models

from apps.core.models import UUIDModel


class AuditLog(UUIDModel):
    """Append-only record of a change: who did what, to which record, and when.

    Rows are written by service functions inside the SAME transaction as the change
    they describe, so a change can never be committed without its audit row (and a
    rolled-back change leaves no audit row behind).

    Design choices:
      * entity_type + entity_id instead of a ForeignKey/GenericForeignKey: one table
        can describe any model, and the history survives even if a model is renamed.
        entity_type holds the model label, e.g. "customers.customer".
      * actor is nullable: background jobs (Phase 7) act as "the system", not a person.
      * actor uses PROTECT: a staff user who ever changed financial data cannot be
        hard-deleted. Deactivate users (is_active=False) instead.
      * No updated_at: an audit row is never updated.
    """

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",  # no reverse accessor on User; query AuditLog directly
    )
    action = models.CharField(max_length=100)  # "<entity>.<verb>", e.g. "customer.created"
    entity_type = models.CharField(max_length=100)
    entity_id = models.UUIDField()
    # {"field": {"old": ..., "new": ...}} for updates; the created values for creations.
    changes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # "Show the history of customer X" (the most common audit question).
            models.Index(
                fields=["entity_type", "entity_id", "-created_at"], name="audit_entity_idx"
            ),
            # "What did user Y change?"
            models.Index(fields=["actor", "-created_at"], name="audit_actor_idx"),
        ]

    def save(self, *args, **kwargs) -> None:
        # Immutability guard for code that goes through the ORM instance. It does NOT
        # cover queryset.update()/delete() or raw SQL; a database-level guard can be
        # added during production hardening (Phase 10) if required.
        if not self._state.adding:
            raise RuntimeError("AuditLog rows are append-only and cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("AuditLog rows are append-only and cannot be deleted.")

    def __str__(self) -> str:
        return f"{self.action} {self.entity_type}:{self.entity_id}"


class OutboxEvent(UUIDModel):
    """A unit of background work, stored in the SAME transaction as the change it follows.

    Why: if a service committed its change and then sent a message to a queue as a
    separate step, a crash in between would lose the work for ever (or, sending before
    committing, a worker could act on a change that then rolls back). Writing the event
    into the database together with the change makes "change happened" and "work is
    queued" one atomic fact. A dispatcher (operations/outbox.py) later claims pending
    events and runs their handler, retrying until it succeeds.

    PostgreSQL is the source of truth for pending work. From Phase 7 Redis only carries
    wake-up messages; if one is lost, the periodic sweep still finds the PENDING row.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        DONE = "DONE", "Done"
        FAILED = "FAILED", "Failed"  # gave up after too many attempts; needs a human

    event_type = models.CharField(max_length=100)  # e.g. "invoice.submit"
    # IDs only, never copies of data: the handler re-reads current state, so a stale or
    # duplicated event can't carry outdated amounts.
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    # Not before this moment (used for retry backoff and scheduled retries).
    available_at = models.DateTimeField()
    # While PROCESSING: if this passes, the dispatcher that claimed it is presumed dead.
    locked_until = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["available_at"]
        indexes = [
            # The dispatcher's question: "which PENDING events are available now?"
            models.Index(
                fields=["available_at"],
                condition=models.Q(status="PENDING"),
                name="outbox_pending_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["PENDING", "PROCESSING", "DONE", "FAILED"]),
                name="outbox_status_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} [{self.status}]"
