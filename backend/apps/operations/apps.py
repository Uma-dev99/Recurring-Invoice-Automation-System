from django.apps import AppConfig


class OperationsConfig(AppConfig):
    """Operational records that explain what the system did and who did it.

    Phase 2 adds only AuditLog. ProcessingAttempt, OutboxEvent and WebhookEvent
    join this app in later phases (see docs/architecture.md §A.8).
    """

    name = "apps.operations"
    label = "operations"
