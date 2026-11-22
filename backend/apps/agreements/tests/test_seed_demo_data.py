from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from apps.agreements.management.commands.seed_demo_data import DEMO_CUSTOMERS
from apps.agreements.models import BillingAgreement
from apps.customers.models import Customer
from apps.operations.models import AuditLog

pytestmark = pytest.mark.django_db

EXPECTED_CUSTOMERS = len(DEMO_CUSTOMERS)
EXPECTED_AGREEMENTS = sum(len(c.agreements) for c in DEMO_CUSTOMERS)


def run() -> str:
    out = StringIO()
    call_command("seed_demo_data", stdout=out)
    return out.getvalue()


def test_creates_customers_and_agreements_through_the_services(settings):
    settings.DEBUG = True

    output = run()

    assert Customer.objects.count() == EXPECTED_CUSTOMERS
    assert BillingAgreement.objects.count() == EXPECTED_AGREEMENTS
    assert f"{EXPECTED_CUSTOMERS} customers" in output
    # Created via services, so every change is audited (by the system: actor is None).
    assert AuditLog.objects.filter(action="customer.created").count() == EXPECTED_CUSTOMERS
    assert not AuditLog.objects.exclude(actor=None).exists()


def test_demo_data_covers_every_interesting_state(settings):
    settings.DEBUG = True

    run()

    statuses = set(BillingAgreement.objects.values_list("status", flat=True))
    assert statuses == {"ACTIVE", "PAUSED", "CANCELLED"}
    assert Customer.objects.filter(status=Customer.Status.INACTIVE).count() == 1
    assert AuditLog.objects.filter(
        action="agreement.cancelled", changes__reason="Contract ended"
    ).exists()


def test_running_twice_creates_nothing_new(settings):
    settings.DEBUG = True
    run()

    output = run()

    assert Customer.objects.count() == EXPECTED_CUSTOMERS
    assert BillingAgreement.objects.count() == EXPECTED_AGREEMENTS
    assert f"{EXPECTED_CUSTOMERS} customers already present" in output


def test_refuses_to_run_without_debug(settings):
    settings.DEBUG = False

    with pytest.raises(CommandError):
        run()

    assert Customer.objects.count() == 0


def test_demo_agreements_come_with_their_schedules(settings):
    settings.DEBUG = True

    run()

    for agreement in BillingAgreement.objects.all():
        assert agreement.periods.count() == agreement.total_cycles
