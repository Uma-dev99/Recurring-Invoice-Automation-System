from django.apps import AppConfig


class AgreementsConfig(AppConfig):
    """Billing agreements: what a customer pays, how often, and for how long.

    Phase 3 covers the agreement and its lifecycle (active, paused, cancelled).
    The monthly billing periods it generates arrive in Phase 4 (apps.billing).
    """

    name = "apps.agreements"
    label = "agreements"
