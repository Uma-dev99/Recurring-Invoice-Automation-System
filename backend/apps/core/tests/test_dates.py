import datetime
from unittest import mock

from apps.core import dates


def _utc(*args) -> datetime.datetime:
    return datetime.datetime(*args, tzinfo=datetime.UTC)


def test_billing_today_uses_the_billing_time_zone(settings):
    settings.BILLING_TIME_ZONE = "Europe/Amsterdam"
    # 23:30 UTC on 31 January is already 00:30 on 1 February in Amsterdam.
    with mock.patch("django.utils.timezone.now", return_value=_utc(2027, 1, 31, 23, 30)):
        assert dates.billing_today() == datetime.date(2027, 2, 1)


def test_billing_today_same_day_when_no_boundary_is_crossed(settings):
    settings.BILLING_TIME_ZONE = "Europe/Amsterdam"
    with mock.patch("django.utils.timezone.now", return_value=_utc(2027, 1, 31, 12, 0)):
        assert dates.billing_today() == datetime.date(2027, 1, 31)
