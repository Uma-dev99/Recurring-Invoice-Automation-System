import datetime
import uuid

import pytest
from django.urls import reverse

from apps.operations.models import AuditLog

pytestmark = pytest.mark.django_db

URL = reverse("audit-log-list")


def entry(
    action="customer.created", entity_type="customers.customer", entity_id=None, actor=None, at=None
):
    row = AuditLog.objects.create(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id or uuid.uuid4(),
        actor=actor,
        changes={"name": "Acme"},
    )
    if at:
        # .update() writes directly, bypassing the append-only save(): test setup only.
        AuditLog.objects.filter(pk=row.pk).update(created_at=at)
    return row


def ids(client, params=None):
    return [r["id"] for r in client.get(URL, params or {}).json()["results"]]


def test_list_newest_first_with_actor(authenticated_client, user):
    utc = datetime.UTC
    old = entry(actor=user, at=datetime.datetime(2027, 1, 1, tzinfo=utc))
    new = entry(action="agreement.paused", at=datetime.datetime(2027, 2, 1, tzinfo=utc))

    rows = authenticated_client.get(URL).json()["results"]

    assert [r["id"] for r in rows] == [str(new.pk), str(old.pk)]
    assert rows[0]["actor"] is None  # system
    assert rows[1]["actor"] == {
        "id": str(user.pk),
        "email": user.email,
        "full_name": "Olivia Operator",
    }
    assert rows[1]["changes"] == {"name": "Acme"}


def test_filters(authenticated_client, user):
    target = uuid.uuid4()
    by_user = entry(actor=user, entity_id=target)
    by_system = entry(action="invoice.accepted", entity_type="invoicing.invoicesubmission")

    assert ids(authenticated_client, {"action": "invoice.accepted"}) == [str(by_system.pk)]
    assert ids(authenticated_client, {"entity_type": "customers.customer"}) == [str(by_user.pk)]
    assert ids(authenticated_client, {"entity_id": str(target)}) == [str(by_user.pk)]
    assert ids(authenticated_client, {"actor": str(user.pk)}) == [str(by_user.pk)]
    assert ids(authenticated_client, {"actor": "system"}) == [str(by_system.pk)]


def test_date_range_uses_billing_days(authenticated_client):
    utc = datetime.UTC
    # 23:30 UTC on 31 Jan is already 1 Feb in Amsterdam.
    feb_first = entry(at=datetime.datetime(2027, 1, 31, 23, 30, tzinfo=utc))
    entry(at=datetime.datetime(2027, 1, 31, 12, 0, tzinfo=utc))

    assert ids(authenticated_client, {"date_from": "2027-02-01", "date_to": "2027-02-01"}) == [
        str(feb_first.pk)
    ]


@pytest.mark.parametrize(
    "params, field",
    [
        ({"actor": "not-a-uuid"}, "actor"),
        ({"entity_id": "x"}, "entity_id"),
        ({"date_from": "2027-02-02", "date_to": "2027-02-01"}, "date_to"),
    ],
)
def test_invalid_filters_are_400(authenticated_client, params, field):
    response = authenticated_client.get(URL, params)

    assert response.status_code == 400
    assert field in response.json()["error"]["details"]


def test_filter_options_lists_distinct_values(authenticated_client):
    entry(action="customer.created")
    entry(action="customer.created")
    entry(action="agreement.paused", entity_type="agreements.billingagreement")

    body = authenticated_client.get(reverse("audit-log-filters")).json()

    assert body == {
        "actions": ["agreement.paused", "customer.created"],
        "entity_types": ["agreements.billingagreement", "customers.customer"],
    }


def test_audit_log_is_read_only_over_http(authenticated_client):
    assert authenticated_client.post(URL, {}).status_code == 405


def test_query_count_does_not_grow_with_rows(
    authenticated_client, user, django_assert_max_num_queries
):
    for _ in range(10):
        entry(actor=user)

    with django_assert_max_num_queries(3):  # count + page (actor joined in)
        authenticated_client.get(URL)


def test_requires_login(api_client):
    assert api_client.get(URL).status_code == 401
