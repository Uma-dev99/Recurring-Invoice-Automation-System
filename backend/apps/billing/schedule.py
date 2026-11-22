"""Monthly billing date maths. Pure Python: no database, no Django.

Two rules decide every date:

1. Month n starts n-1 months after the anchor, ALWAYS counted from the anchor (never
   from the previous period), and is clamped to the last day of a shorter month:

       anchor 31 Jan 2027 -> 31 Jan, 28 Feb, 31 Mar, 30 Apr, 31 May ...

   Counting from the previous period instead would drift for good after February:
   31 Jan -> 28 Feb -> 28 Mar -> 28 Apr ...

2. A period ends the day before the next one starts, so periods follow each other
   with no gap and no overlap:

       31 Jan-27 Feb, 28 Feb-30 Mar, 31 Mar-29 Apr, 30 Apr-30 May ...

The invoice for a period may go out from its start date, and must go out by its end
date (Riverty refuses invoices outside the period, and charges back periods whose end
passes without one).
"""

import calendar
import datetime
from typing import NamedTuple


class PeriodDates(NamedTuple):
    cycle_number: int
    start: datetime.date
    end: datetime.date


def add_months(day: datetime.date, months: int) -> datetime.date:
    """`day` moved `months` calendar months on, clamped to the target month's last day.

    add_months(31 Jan 2027, 1) == 28 Feb 2027;  add_months(31 Jan 2028, 1) == 29 Feb 2028.
    """
    if months < 0:
        raise ValueError("months must be zero or positive")
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return datetime.date(year, month, min(day.day, last_day))


def period_dates(anchor: datetime.date, cycle_number: int) -> PeriodDates:
    """Start and end of month `cycle_number` (1 = the first month) of an agreement."""
    if cycle_number < 1:
        raise ValueError("cycle_number starts at 1")
    start = add_months(anchor, cycle_number - 1)
    next_start = add_months(anchor, cycle_number)
    return PeriodDates(cycle_number, start, next_start - datetime.timedelta(days=1))


def build_schedule(anchor: datetime.date, total_cycles: int) -> list[PeriodDates]:
    """Every period of an agreement, in order."""
    return [period_dates(anchor, n) for n in range(1, total_cycles + 1)]
