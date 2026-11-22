from django.apps import AppConfig


class BillingConfig(AppConfig):
    """Billing periods: the monthly obligations an agreement generates.

    One BillingPeriod per month of an agreement. Each is invoiced at most once
    (Phase 5 builds the invoice submission on top of it).
    """

    name = "apps.billing"
    label = "billing"
