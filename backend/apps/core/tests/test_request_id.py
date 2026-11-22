import json
import logging

import pytest
from django.urls import reverse

from apps.core.log_format import JsonFormatter
from apps.core.request_id import RequestIDLogFilter, request_id_var

pytestmark = pytest.mark.django_db

URL = reverse("health-live")


def test_every_response_gets_a_request_id(api_client):
    response = api_client.get(URL)

    assert len(response["X-Request-ID"]) == 32  # a fresh uuid4 hex


def test_id_from_nginx_is_kept(api_client):
    response = api_client.get(URL, HTTP_X_REQUEST_ID="abc123def456")

    assert response["X-Request-ID"] == "abc123def456"


@pytest.mark.parametrize("bad", ["short", "has space and more", "x" * 65, "line\nbreak-injected"])
def test_malformed_incoming_id_is_replaced(api_client, bad):
    # A client must not be able to write arbitrary text into our logs.
    response = api_client.get(URL, HTTP_X_REQUEST_ID=bad)

    assert response["X-Request-ID"] != bad
    assert len(response["X-Request-ID"]) == 32


def test_json_log_line_carries_request_id_and_extra_fields():
    record = logging.makeLogRecord(
        {
            "name": "apps.test",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "msg": "Sent %s",
            "args": ("inv",),
        }
    )
    record.submission_id = "s-1"  # as if passed with extra={"submission_id": ...}
    token = request_id_var.set("req-42")
    try:
        RequestIDLogFilter().filter(record)
    finally:
        request_id_var.reset(token)

    line = json.loads(JsonFormatter().format(record))

    assert line["message"] == "Sent inv"
    assert line["request_id"] == "req-42"
    assert line["submission_id"] == "s-1"
    assert line["level"] == "INFO"


def test_liveness_answers_without_touching_dependencies(api_client, django_assert_num_queries):
    with django_assert_num_queries(0):
        response = api_client.get(URL)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
