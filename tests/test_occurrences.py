"""Which dates an assignment happens on, and the table that will hold them."""
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from database.db import SessionLocal
from database.models import AssignmentOccurrence, AssignmentStatus
from services.occurrence_service import OccurrenceService

# Nov 2, 2026 is a Monday.
MON = date(2026, 11, 2)
WED = date(2026, 11, 4)
FRI = date(2026, 11, 6)
SUN = date(2026, 11, 8)
NEXT_WED = date(2026, 11, 11)


def recurring(pattern, start, end):
    return OccurrenceService.dates_for("Recurring", pattern, start, end)


def days(*numbers, month=11):
    return [date(2026, month, number) for number in numbers]


# ----- One-time work -----


def test_one_time_work_happens_once_on_its_date():
    assert OccurrenceService.dates_for("One Time", None, WED) == [WED]


def test_one_time_work_ignores_any_pattern_or_end_date():
    assert OccurrenceService.dates_for("One Time", "Every Day", WED, NEXT_WED) == [WED]


# ----- Recurring patterns -----


def test_daily_includes_weekends_and_both_ends():
    assert recurring("Every Day", FRI, SUN) == days(6, 7, 8)


def test_weekdays_skips_the_weekend():
    assert recurring("Weekdays", FRI, date(2026, 11, 10)) == days(6, 9, 10)


def test_weekly_repeats_on_the_start_dates_weekday():
    assert recurring("Weekly", WED, date(2026, 11, 18)) == days(4, 11, 18)


@pytest.mark.parametrize(
    "pattern, expected",
    [
        ("Every Monday", days(2, 9)),
        ("Every Tuesday", days(3, 10)),
        ("Every Wednesday", days(4, 11)),
        ("Every Thursday", days(5, 12)),
        ("Every Friday", days(6, 13)),
    ],
)
def test_every_weekday_patterns(pattern, expected):
    assert recurring(pattern, MON, date(2026, 11, 15)) == expected


def test_a_named_weekday_starts_at_the_first_match_after_the_start():
    assert recurring("Every Monday", WED, date(2026, 11, 16)) == days(9, 16)


def test_runs_across_the_new_year():
    assert recurring("Every Friday", date(2026, 12, 25), date(2027, 1, 8)) == [
        date(2026, 12, 25),
        date(2027, 1, 1),
        date(2027, 1, 8),
    ]


# ----- Monthly -----


def test_monthly_keeps_the_day_of_the_month():
    assert recurring("Monthly", date(2026, 11, 15), date(2027, 1, 15)) == [
        date(2026, 11, 15),
        date(2026, 12, 15),
        date(2027, 1, 15),
    ]


def test_monthly_on_the_31st_uses_the_last_day_then_returns_to_the_31st():
    assert recurring("Monthly", date(2027, 1, 31), date(2027, 4, 30)) == [
        date(2027, 1, 31),
        date(2027, 2, 28),
        date(2027, 3, 31),
        date(2027, 4, 30),
    ]


def test_monthly_uses_february_29th_in_a_leap_year():
    assert recurring("Monthly", date(2028, 1, 31), date(2028, 2, 29)) == [
        date(2028, 1, 31),
        date(2028, 2, 29),
    ]


def test_monthly_stops_before_a_date_past_the_end():
    assert recurring("Monthly", date(2026, 11, 15), date(2026, 12, 14)) == [
        date(2026, 11, 15)
    ]


# ----- Edges -----


@pytest.mark.parametrize("pattern", ["Every Day", "Weekly", "Monthly", "Weekdays", "Every Friday"])
def test_an_end_before_the_start_gives_no_dates(pattern):
    assert recurring(pattern, FRI, WED) == []


def test_a_single_day_range_that_misses_the_pattern_gives_no_dates():
    assert recurring("Every Monday", WED, WED) == []


def test_recurring_work_needs_an_end_date():
    with pytest.raises(ValueError):
        OccurrenceService.dates_for("Recurring", "Every Day", WED)


@pytest.mark.parametrize("pattern", [None, "Every Saturday"])
def test_recurring_work_needs_a_known_pattern(pattern):
    with pytest.raises(ValueError):
        recurring(pattern, WED, NEXT_WED)


@pytest.mark.parametrize(
    "today, expected",
    [
        (date(2026, 1, 1), date(2026, 12, 31)),
        (date(2026, 11, 4), date(2026, 12, 31)),
        (date(2026, 12, 31), date(2026, 12, 31)),
    ],
)
def test_default_end_date_is_the_end_of_this_year(today, expected):
    assert OccurrenceService.default_end_date(today) == expected


# ----- The table -----


def _save(**fields):
    db = SessionLocal()
    try:
        row = AssignmentOccurrence(**fields)
        db.add(row)
        db.commit()
        return row
    finally:
        db.close()


def test_a_new_occurrence_starts_not_started_and_empty(world):
    row = _save(assignment_id=world.essay, student_id=world.ann, occurrence_date=WED)

    assert row.status == AssignmentStatus.NOT_STARTED.value
    assert row.completed_at is None
    assert row.notes is None
    assert row.score is None


def test_each_date_can_have_its_own_note_and_score(world):
    _save(
        assignment_id=world.essay,
        student_id=world.ann,
        occurrence_date=MON,
        notes="Chapter 1",
        score=95.5,
    )
    tuesday = _save(
        assignment_id=world.essay,
        student_id=world.ann,
        occurrence_date=WED,
        notes="Chapter 2 instead",
    )

    assert tuesday.notes == "Chapter 2 instead"
    assert tuesday.score is None


def test_a_student_cant_have_the_same_assignment_twice_on_a_date(world):
    fields = dict(assignment_id=world.essay, student_id=world.ann, occurrence_date=WED)
    _save(**fields)

    with pytest.raises(IntegrityError):
        _save(**fields)


def test_two_students_can_share_an_assignment_and_date(world):
    _save(assignment_id=world.essay, student_id=world.ann, occurrence_date=WED)
    _save(assignment_id=world.essay, student_id=world.bob, occurrence_date=WED)


@pytest.mark.parametrize("missing", ["assignment_id", "student_id", "occurrence_date"])
def test_required_fields_cant_be_empty(world, missing):
    fields = dict(assignment_id=world.essay, student_id=world.ann, occurrence_date=WED)
    del fields[missing]

    with pytest.raises(IntegrityError):
        _save(**fields)
