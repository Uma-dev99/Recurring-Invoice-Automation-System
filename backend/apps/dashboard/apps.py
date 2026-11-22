from django.apps import AppConfig


class DashboardConfig(AppConfig):
    """Read-only KPIs for the dashboard. No models: it only reads other apps' data.

    Every figure is computed here, in the database (exact decimals), never in the
    browser. It sits at the TOP of the dependency graph: it may read every app, and no
    app depends on it.
    """

    name = "apps.dashboard"
    label = "dashboard"
