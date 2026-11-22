from django.apps import AppConfig


class InvoicingConfig(AppConfig):
    """Invoice submissions: getting exactly one invoice per billing period to Riverty."""

    name = "apps.invoicing"
    label = "invoicing"

    def ready(self) -> None:
        # Register this app's outbox handlers. Done here (not in operations) so the
        # generic outbox never has to import invoicing.
        from apps.invoicing import handlers  # noqa: F401 - imported for its side effect
