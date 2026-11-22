"""The Celery application: background workers that run THIS codebase.

    celery -A config worker   runs tasks
    celery -A config beat     the clock: sends scheduled tasks (CELERY_BEAT_SCHEDULE)

Settings come from Django settings with the CELERY_ prefix (config/settings/base.py).
Tasks live in each app's tasks.py and are found automatically.

Rule for every task in this project: it is a THIN entry point. It receives ids (never
data), calls one service function, and holds no business logic of its own. The same
service can therefore run from a task, a management command or a button, identically.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
