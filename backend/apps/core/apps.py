from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Cross-cutting building blocks shared by every domain app.

    Contains no business concepts: only base models, API conventions (errors,
    pagination) and infrastructure endpoints such as the health check.
    """

    name = "apps.core"
    label = "core"
