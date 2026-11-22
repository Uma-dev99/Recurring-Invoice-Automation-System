from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Cross-cutting building blocks shared by every domain app.

    Contains no business concepts: only base models, API conventions (errors,
    pagination) and infrastructure endpoints such as the health check.
    """

    name = "apps.core"
    label = "core"

    def ready(self) -> None:
        # Background tasks get a request id too (their task id), so their log lines can
        # be traced the same way as web requests.
        from apps.core.request_id import connect_celery_signals

        connect_celery_signals()
