# Load the Celery app whenever Django starts, so tasks are registered and
# `task.delay()` from web code uses this configuration.
from config.celery import app as celery_app

__all__ = ("celery_app",)
