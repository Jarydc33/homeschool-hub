"""The calendar shows work and events by date, to the right people."""
from datetime import date, time, timedelta
from pathlib import Path
from unittest import mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from database.db import SessionLocal
from database.models import AssignmentOccurrence, Student, User, UserRole
from services.assignment_service import AssignmentService
from services.current_user import CurrentUser
from services.calendar_service import CalendarService
from services.event_service import EventService
from services.session_service import SessionService

ROOT = Path(__file__).resolve().parent.parent

# A Thursday.
TODAY = date(2026, 11, 5)
SUNDAY = date(2026, 11, 1)
SATURDAY = date(2026, 11, 7)
YESTERDAY = date(2026, 11, 4)
TOMORROW = date(2026, 11, 6)


@pytest.fixture
def parent(smith_parent):
    with mock.patch.object(CurrentUser, "get_today", return_value=TODAY):
        yield smith_parent


def one_time(w, title="Essay", due=TODAY, students=None):
    return AssignmentService.create_assignment(
        subject_id=w.art,
        title=title,
        student_ids=[w.ann] if students is None else students,
        due_date=due,
    )


def titles(items, day):
    return [item["title"] for item in items.get(day, [])]


# ----- Dates -----


def test_a_week_runs_sunday_to_saturday():
    days = CalendarService.week_days(TODAY)

    assert days[0] == SUNDAY
    assert days[-1] == SATURDAY
    assert CalendarService.week_days(SUNDAY) == days
    assert CalendarService.week_days(SATURDAY) == days


def test_month_weeks_cover_the_whole_month():
    weeks = CalendarService.month_weeks(date(2026, 2, 14))

    assert weeks[0][0] == date(2026, 2, 1)
    assert weeks[-1][-1] == date(2026, 2, 28)
    assert len(weeks) == 4


def test_month_weeks_include_days_from_nearby_months():
    weeks = CalendarService.month_weeks(TODAY)

    # November 2026 starts on a Sunday and ends on a Monday.
    assert weeks[0][0] == SUNDAY
    assert weeks[-1][0] == date(2026, 11, 29)
    assert weeks[-1][-1] == date(2026, 12, 5)


@pytest.mark.parametrize(
    "day, months, step, expected",
    [
        (TODAY, False, 1, date(2026, 11, 12)),
        (TODAY, False, -1, date(2026, 10, 29)),
        (TODAY, True, 1, date(2026, 12, 1)),
        (date(2026, 1, 31), True, 1, date(2026, 2, 1)),
        (date(2026, 12, 15), True, 1, date(2027, 1, 1)),
        (date(2026, 1, 15), True, -1, date(2025, 12, 1)),
    ],
)
def test_moving_between_weeks_and_months(day, months, step, expected):
    assert CalendarService.shift(day, months, step) == expected


# ----- What's on it -----


def test_status_follows_the_work(parent):
    one_time(parent, "Late", YESTERDAY)
    one_time(parent, "Due today", TODAY)

    done = one_time(parent, "Finished", TOMORROW)
    db = SessionLocal()
    try:
        row = db.query(AssignmentOccurrence).filter_by(assignment_id=done.id).one()
        row.status = "Complete"
        db.commit()
    finally:
        db.close()

    items = CalendarService.get_items(SUNDAY, SATURDAY)

    assert items[YESTERDAY][0]["status"] == "overdue"
    assert items[TODAY][0]["status"] == "to_do"
    assert items[TOMORROW][0]["status"] == "done"


def test_a_past_recurring_day_is_missed(parent):
    AssignmentService.create_assignment(
        subject_id=parent.art,
        title="Reading",
        student_ids=[parent.ann],
        due_date=YESTERDAY,
        assignment_type="Recurring",
        recurrence_pattern="Every Day",
        end_date=TODAY,
    )

    items = CalendarService.get_items(SUNDAY, SATURDAY)

    assert items[YESTERDAY][0]["status"] == "missed"
    assert items[TODAY][0]["status"] == "to_do"


def test_curriculum_lessons_show_their_numbers_and_subject(parent):
    AssignmentService.create_assignment(
        subject_id=parent.math,
        title="Saxon Math",
        student_ids=[parent.ann],
        due_date=TODAY,
        assignment_type="Curriculum",
        recurrence_pattern="Thu,Fri",
        lesson_count=2,
    )

    items = CalendarService.get_items(SUNDAY, SATURDAY)

    assert items[TODAY][0]["title"] == "Saxon Math: Lesson 1"
    assert items[TODAY][0]["detail"] == "Math"
    assert items[TODAY][0]["student"] == "Ann"
    assert items[TOMORROW][0]["title"] == "Saxon Math: Lesson 2"


def test_only_the_range_asked_for_comes_back(parent):
    one_time(parent, "This week", TODAY)
    one_time(parent, "Next week", date(2026, 11, 12))

    items = CalendarService.get_items(SUNDAY, SATURDAY)

    assert list(items) == [TODAY]


def test_events_come_first_by_time_then_work_by_student(parent):
    one_time(parent, "Bob's work", TODAY, [parent.bob])
    one_time(parent, "Ann's work", TODAY, [parent.ann])
    EventService.create_event("Afternoon", TODAY, start_time=time(14, 0))
    EventService.create_event("Morning", TODAY, start_time=time(9, 0))
    EventService.create_event("All day", TODAY)

    items = CalendarService.get_items(SUNDAY, SATURDAY)

    assert titles(items, TODAY) == [
        "All day",
        "Morning",
        "Afternoon",
        "Ann's work",
        "Bob's work",
    ]
    assert items[TODAY][1]["detail"] == "9:00 AM"
    assert items[TODAY][0]["detail"] == "All day"


def test_a_multi_day_event_shows_on_each_day_in_range(parent):
    EventService.create_event(
        "Camp", date(2026, 10, 30), end_date=date(2026, 11, 2)
    )

    items = CalendarService.get_items(SUNDAY, SATURDAY)

    assert titles(items, SUNDAY) == ["Camp"]
    assert titles(items, date(2026, 11, 2)) == ["Camp"]
    assert titles(items, date(2026, 11, 3)) == []


def test_a_repeating_event_shows_on_each_date_including_past_ones(parent):
    EventService.create_event(
        "Co-op",
        date(2026, 10, 1),
        recurrence_pattern="Every Tuesday",
        repeat_until=date(2026, 12, 31),
    )

    items = CalendarService.get_items(date(2026, 10, 25), SATURDAY)

    assert sorted(items) == [date(2026, 10, 27), date(2026, 11, 3)]


def test_label_names_the_student_only_when_asked():
    item = {
        "status": "to_do",
        "title": "Essay",
        "detail": "Art",
        "student": "Ann",
    }

    assert CalendarService.label(item, True) == "📋 Essay (Ann)"
    assert CalendarService.label(item, False) == "📋 Essay"


# ----- What's left off -----


def test_archived_work_is_left_off(parent):
    work = one_time(parent)
    AssignmentService.archive_assignment(work.id)

    assert CalendarService.get_items(SUNDAY, SATURDAY) == {}


def test_archived_events_are_left_off(parent):
    event = EventService.create_event("Trip", TODAY)
    EventService.archive_event(event.id)

    assert CalendarService.get_items(SUNDAY, SATURDAY) == {}


def test_archived_students_work_is_left_off(parent):
    one_time(parent)

    db = SessionLocal()
    try:
        db.get(Student, parent.ann).active = False
        db.commit()
    finally:
        db.close()

    assert CalendarService.get_items(SUNDAY, SATURDAY) == {}


def test_work_for_a_student_taken_off_it_is_left_off(parent):
    work = one_time(parent, students=[parent.ann, parent.bob])
    db = SessionLocal()
    try:
        row = (
            db.query(AssignmentOccurrence)
            .filter_by(assignment_id=work.id, student_id=parent.bob)
            .one()
        )
        row.notes = "Keeps this row"
        db.commit()
    finally:
        db.close()

    AssignmentService.update_assignment(
        assignment_id=work.id,
        title="Essay",
        description=None,
        due_date=TODAY,
        subject_id=parent.art,
        student_ids=[parent.ann],
        assignment_type="One Time",
        recurrence_pattern=None,
    )

    items = CalendarService.get_items(SUNDAY, SATURDAY)

    assert [item["student"] for item in items[TODAY]] == ["Ann"]


# ----- Who sees what -----


def test_parent_sees_the_whole_family_or_one_student(parent):
    one_time(parent, "Ann's", TODAY, [parent.ann])
    one_time(parent, "Bob's", TODAY, [parent.bob])
    EventService.create_event("Ann's trip", TODAY, student_ids=[parent.ann])
    EventService.create_event("Family trip", TODAY)

    assert sorted(titles(CalendarService.get_items(SUNDAY, SATURDAY), TODAY)) == [
        "Ann's",
        "Ann's trip",
        "Bob's",
        "Family trip",
    ]

    assert sorted(
        titles(CalendarService.get_items(SUNDAY, SATURDAY, parent.bob), TODAY)
    ) == ["Bob's", "Family trip"]


def test_student_sees_only_their_own_whatever_is_asked_for(parent, login):
    one_time(parent, "Ann's", TODAY, [parent.ann])
    one_time(parent, "Bob's", TODAY, [parent.bob])
    EventService.create_event("Ann's trip", TODAY, student_ids=[parent.ann])
    EventService.create_event("Family trip", TODAY)

    login(parent.smith, role=UserRole.STUDENT, student_id=parent.bob)

    for asked_for in (None, parent.bob, parent.ann):
        assert sorted(
            titles(CalendarService.get_items(SUNDAY, SATURDAY, asked_for), TODAY)
        ) == ["Bob's", "Family trip"]


def test_one_family_cant_see_anothers_calendar(parent, login):
    one_time(parent)
    EventService.create_event("Trip", TODAY)

    login(parent.jones)

    assert CalendarService.get_items(SUNDAY, SATURDAY) == {}
    assert CalendarService.get_items(SUNDAY, SATURDAY, parent.ann) == {}


def test_admins_see_nothing(parent, login):
    one_time(parent)

    login(None, role=UserRole.ADMIN)

    assert CalendarService.get_items(SUNDAY, SATURDAY) == {}


# ----- The page -----


@pytest.fixture
def page_as(world):
    def _open(role, student_id=None):
        db = SessionLocal()
        try:
            user = User(
                family_id=world.smith,
                student_id=student_id,
                email=f"{role.lower()}@x.test",
                auth_user_id="00000000-0000-0000-0000-00000000000a",
                role=role,
            )
            db.add(user)
            db.commit()
            user_id = user.id
        finally:
            db.close()

        at = AppTest.from_file(
            str(next((ROOT / "pages").glob("*_Calendar.py"))), default_timeout=30
        )
        at.session_state["current_user_id"] = user_id
        return at

    with (
        mock.patch.object(SessionService, "sync_browser", return_value=None),
        mock.patch.object(st, "page_link"),
        mock.patch.object(st, "switch_page"),
    ):
        yield _open


def _add(w, login, title, students, day=None):
    """Real dates, since the page uses the real clock."""
    login(w.smith)
    with mock.patch.object(CurrentUser, "get_today", return_value=date.today()):
        one_time(w, title, day or date.today(), students)
    mock.patch.stopall()


def _text(at):
    return " ".join(item.value for item in at.markdown)


def test_empty_calendar_says_so(world, page_as):
    at = page_as("Parent").run()

    assert not at.exception
    assert any("Nothing is scheduled" in box.value for box in at.info)
    assert "(Today)" in _text(at)


def test_family_view_names_the_student_and_one_child_view_doesnt(
    world, login, page_as
):
    _add(world, login, "Ann's essay", [world.ann])

    at = page_as("Parent").run()

    assert not at.exception
    assert "Ann's essay (Ann)" in _text(at)

    at.selectbox(key="calendar_student").set_value(world.ann).run()

    assert not at.exception
    assert "Ann's essay" in _text(at)
    assert "(Ann)" not in _text(at)

    at.selectbox(key="calendar_student").set_value(world.bob).run()

    assert "Ann's essay" not in _text(at)


def test_buttons_move_the_week(world, login, page_as):
    _add(world, login, "Far off", [world.ann], date.today() + timedelta(days=7))

    at = page_as("Parent").run()
    assert "Far off" not in _text(at)

    at.button(key="calendar_next").click().run()
    assert not at.exception
    assert "Far off" in _text(at)
    assert "(Today)" not in _text(at)

    at.button(key="calendar_today").click().run()
    assert "Far off" not in _text(at)
    assert "(Today)" in _text(at)

    at.button(key="calendar_previous").click().run()
    assert not at.exception
    assert "(Today)" not in _text(at)


def test_month_view_limits_each_day(world, login, page_as):
    for number in range(5):
        _add(world, login, f"Work {number}", [world.ann])

    at = page_as("Parent").run()
    assert "Work 4" in _text(at)

    at.radio(key="calendar_view").set_value("Month").run()

    assert not at.exception
    assert "Work 2" in _text(at)
    assert "Work 3" not in _text(at)
    assert any("+2 more" in caption.value for caption in at.caption)


def test_student_gets_no_picker_and_only_their_work(world, login, page_as):
    _add(world, login, "Bob's essay", [world.bob])
    _add(world, login, "Ann's essay", [world.ann])

    at = page_as("Student", student_id=world.bob).run()

    assert not at.exception
    assert "Whose Schedule?" not in [box.label for box in at.selectbox]
    assert "Bob's essay" in _text(at)
    assert "(Bob)" not in _text(at)
    assert "Ann's essay" not in _text(at)
