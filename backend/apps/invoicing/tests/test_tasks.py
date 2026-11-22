"""Background jobs: thin tasks, the beat schedule, and the outbox fast path."""

import datetime
from unittest import mock

import pytest
from django.conf import settings
from django.utils import timezone

from apps.invoicing import tasks
from apps.invoicing.models import InvoiceSubmission
from apps.invoicing.services import create_submission
from apps.invoicing.tests.helpers import TODAY, first_period, make_billable_agreement
from apps.operations import outbox
from apps.operations import tasks as operations_tasks
from apps.operations.models import OutboxEvent
from config.celery import app as celery_app

pytestmark = pytest.mark.django_db


# --- the schedule ---------------------------------------------------------------------


def test_every_scheduled_task_exists():
    # A typo in a task name would make Beat send messages no worker understands.
    celery_app.loader.import_default_modules()
    registered = set(celery_app.tasks)

    for name, entry in settings.CELERY_BEAT_SCHEDULE.items():
        assert entry["task"] in registered, name


def test_schedule_runs_in_the_billing_time_zone():
    assert settings.CELERY_TIMEZONE == settings.BILLING_TIME_ZONE


# --- tasks are thin: they call the service ----------------------------------------------


def test_enqueue_task_uses_billing_today():
    make_billable_agreement()

    with mock.patch.object(tasks, "billing_today", return_value=TODAY):
        created = tasks.enqueue_due_periods()

    assert created == 1
    assert InvoiceSubmission.objects.count() == 1


@pytest.mark.parametrize(
    "task, service",
    [
        (tasks.sweep_due_retries, "sweep_due_retries"),
        (tasks.recover_expired_leases, "recover_expired_leases"),
    ],
)
def test_tasks_delegate_to_services(task, service):
    with mock.patch.object(tasks.services, service, return_value=7) as called:
        assert task() == 7
    called.assert_called_once()


def test_dispatch_task_runs_the_outbox():
    with mock.patch.object(operations_tasks, "process_outbox") as process:
        process.return_value = outbox.OutboxRunResult(done=2)
        assert operations_tasks.dispatch_outbox()["done"] == 2


# --- outbox fast path -------------------------------------------------------------------


def test_new_work_wakes_a_worker_only_after_commit(django_capture_on_commit_callbacks):
    period = first_period(make_billable_agreement())

    with mock.patch.object(operations_tasks.dispatch_outbox, "delay") as delay:
        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            create_submission(period_id=period.pk)
            delay.assert_not_called()  # not before the commit

        for callback in callbacks:
            callback()  # "commit"
        delay.assert_called()


def test_future_work_does_not_wake_a_worker(django_capture_on_commit_callbacks):
    outbox.register_handler("test.later", lambda payload: None)
    try:
        with django_capture_on_commit_callbacks() as callbacks:
            outbox.enqueue(
                "test.later", {}, available_at=timezone.now() + datetime.timedelta(hours=1)
            )
        assert callbacks == []  # the every-minute sweep picks it up when it's due
    finally:
        outbox._HANDLERS.pop("test.later", None)


def test_broker_down_never_breaks_the_saved_change(django_capture_on_commit_callbacks):
    outbox.register_handler("test.now", lambda payload: None)
    try:
        with mock.patch.object(
            operations_tasks.dispatch_outbox, "delay", side_effect=ConnectionError("redis down")
        ):
            with django_capture_on_commit_callbacks(execute=True):
                event = outbox.enqueue("test.now", {})
        # No exception escaped, and the work is safely stored for the periodic sweep.
        assert OutboxEvent.objects.get(pk=event.pk).status == OutboxEvent.Status.PENDING
    finally:
        outbox._HANDLERS.pop("test.now", None)
