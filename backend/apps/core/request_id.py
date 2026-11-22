"""Request IDs: one id per request (or Celery task), on every log line it produces.

    browser -> nginx (sets X-Request-ID) -> Django (keeps it) -> logs + response header
    Celery task -> the task id is used as its request id

When a user reports "it failed at 10:42", the id in the response header (and in the
JSON error body) finds every log line of that request: one grep instead of guessing.

The id lives in a ContextVar: each request/thread/task sees its own value, and a log
filter copies it onto every log record.
"""

import logging
import re
import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

HEADER = "X-Request-ID"
# Accept an incoming id only if it looks like one. Anything else is replaced: a client
# must not be able to put arbitrary text (newlines, fake log lines) into our logs.
_VALID_ID = re.compile(r"[A-Za-z0-9._-]{8,64}")


def current_request_id() -> str:
    return request_id_var.get()


class RequestIDMiddleware:
    """Assign (or accept from nginx) a request id; return it in the response header."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.META.get("HTTP_X_REQUEST_ID", "")
        request_id = incoming if _VALID_ID.fullmatch(incoming) else uuid.uuid4().hex
        request.request_id = request_id
        token = request_id_var.set(request_id)
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response[HEADER] = request_id
        return response


class RequestIDLogFilter(logging.Filter):
    """Adds `request_id` to every log record (used by both log formats)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def connect_celery_signals() -> None:
    """Use the Celery task id as the request id while a task runs."""
    from celery.signals import task_postrun, task_prerun

    tokens: dict[str, object] = {}

    @task_prerun.connect(weak=False)
    def _set(task_id=None, **_kwargs):
        tokens[task_id] = request_id_var.set(f"task-{task_id}")

    @task_postrun.connect(weak=False)
    def _reset(task_id=None, **_kwargs):
        token = tokens.pop(task_id, None)
        if token is not None:
            request_id_var.reset(token)
