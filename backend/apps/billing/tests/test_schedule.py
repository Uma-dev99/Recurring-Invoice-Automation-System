"""The date maths on its own: no database, so hundreds of cases run in milliseconds."""

import datetime

import pytest

from apps.billing.schedule import add_months, build_schedule, period_dates

D = datetime.date


# --- add_months ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "day, months, expected",
    [
        (D(2027, 1, 15), 1, D(2027, 2, 15)),  # ordinary day
        (D(2027, 1, 31), 1, D(2027, 2, 28)),  # clamped to February's end
        (D(2028, 1, 31), 1, D(2028, 2, 29)),  # leap year
        (D(2027, 1, 31), 2, D(2027, 3, 31)),  # back to the 31st: counted from the anchor
        (D(2027, 3, 31), 1, D(2027, 4, 30)),  # 30-day month
        (D(2027, 11, 30), 2, D(2028, 1, 30)),  # crosses the year
        (D(2027, 12, 31), 12, D(2028, 12, 31)),  # a whole year
        (D(2027, 5, 10), 0, D(2027, 5, 10)),  # zero months
    ],
)
def test_add_months(day, months, expected):
    assert add_months(day, months) == expected


def test_add_months_refuses_negative():
    with pytest.raises(ValueError):
        add_months(D(2027, 1, 1), -1)


# --- periods ------------------------------------------------------------------------


def test_end_of_month_anchor_keeps_its_day_and_never_drifts():
    starts = [p.start for p in build_schedule(D(2027, 1, 31), 6)]

    assert starts == [
        D(2027, 1, 31),
        D(2027, 2, 28),
        D(2027, 3, 31),  # NOT 28 March: always counted from the anchor
        D(2027, 4, 30),
        D(2027, 5, 31),
        D(2027, 6, 30),
    ]


def test_each_period_ends_the_day_before_the_next_starts():
    schedule = build_schedule(D(2027, 1, 31), 4)

    assert [(p.start, p.end) for p in schedule] == [
        (D(2027, 1, 31), D(2027, 2, 27)),
        (D(2027, 2, 28), D(2027, 3, 30)),
        (D(2027, 3, 31), D(2027, 4, 29)),
        (D(2027, 4, 30), D(2027, 5, 30)),
    ]


def test_leap_year_february():
    first = period_dates(D(2028, 1, 31), 1)
    second = period_dates(D(2028, 1, 31), 2)

    assert first.end == D(2028, 2, 28)
    assert second.start == D(2028, 2, 29)


def test_schedule_has_one_period_per_cycle_numbered_from_one():
    schedule = build_schedule(D(2027, 3, 1), 12)

    assert [p.cycle_number for p in schedule] == list(range(1, 13))
    assert schedule[-1].start == D(2028, 2, 1)
    assert schedule[-1].end == D(2028, 2, 29)


def test_cycle_number_starts_at_one():
    with pytest.raises(ValueError):
        period_dates(D(2027, 1, 1), 0)


@pytest.mark.parametrize("anchor_day", [1, 15, 28, 29, 30, 31])
@pytest.mark.parametrize("anchor_month", range(1, 13))
def test_no_gaps_no_overlaps_for_every_kind_of_anchor(anchor_month, anchor_day):
    # 72 anchors x 24 months: the two rules hold everywhere, including leap years.
    try:
        anchor = D(2027, anchor_month, anchor_day)
    except ValueError:
        pytest.skip("not a real date (e.g. 30 February)")

    schedule = build_schedule(anchor, 24)

    for current, following in zip(schedule, schedule[1:], strict=False):
        assert current.end + datetime.timedelta(days=1) == following.start
    for period in schedule:
        assert period.start <= period.end
        assert 28 <= (period.end - period.start).days + 1 <= 31
