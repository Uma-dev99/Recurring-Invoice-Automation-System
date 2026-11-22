"""Business-calendar helpers.

Timestamps are stored in UTC, but billing works in calendar days, and which day it is
depends on where you are: at 00:30 on 1 February in Amsterdam it is still 31 January
in UTC. Every "is this date in the past / due today?" question uses billing_today().
"""

import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone


def billing_today() -> datetime.date:
    """Today's date in settings.BILLING_TIME_ZONE."""
    return timezone.localdate(timezone=ZoneInfo(settings.BILLING_TIME_ZONE))
