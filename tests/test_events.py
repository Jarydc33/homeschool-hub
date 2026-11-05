"""Parents manage events, and each student sees only their own."""
from datetime import date, time, timedelta
from pathlib import Path
from unittest import mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from database.db import SessionLocal
from database.models import Event, EventStudent, User, UserRole
from services.auth_service import AuthService
from services.event_service import EventService
from services.session_service import SessionService
from services.student_service import StudentService

ROOT = Path(__file__).resolve().parent.parent

# A Thursday.
TODAY = date(2026, 11, 5)
TOMORROW = date(2026, 11, 6)
NEXT_WEEK = date(2026, 11, 12)
LAST_WEEK = date(2026, 10, 29)
NEXT_TUESDAY = date(2026, 11, 10)
YEAR_END = date(2026, 12, 31)


@pytest.fixture
def parent(smith_parent):
    with mock.patch.object(AuthService, "get_today", return_value=TODAY):
        yield smith_parent


def add(title="Field trip", start=NEXT_WEEK, **kwargs):
    return EventService.create_event(title=title, start_date=start, **kwargs)


def titles(events):
    return [event.title for event in events]


def links_of(event_id):
    db = SessionLocal()
    try:
        return {
            link.student_id
            for link in db.query(EventStudent).filter_by(event_id=event_id)
        }
    finally:
        db.close()


# ----- Dates -----


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"start_date": None}, "choose a date"),
        ({"start_date": TODAY, "end_date": LAST_WEEK}, "last day"),
        ({"start_date": TODAY, "end_date": date(2030, 1, 1)}, "two years"),
        ({"start_date": TODAY, "recurrence_pattern": "Whenever"}, "how often"),
        ({"start_date": TODAY, "recurrence_pattern": "Weekly"}, "stops repeating"),
        (
            {
                "start_date": TODAY,
                "recurrence_pattern": "Weekly",
                "repeat_until": LAST_WEEK,
            },
            "before its first date",
        ),
        (
            {
                "start_date": TODAY,
                "recurrence_pattern": "Weekly",
                "repeat_until": date(2030, 1, 1),
            },
            "two years",
        ),
        (
            {
                "start_date": TODAY,
                "recurrence_pattern": "Every Monday",
                "repeat_until": TOMORROW,
            },
            "any date",
        ),
    ],
)
def test_bad_dates_say_whats_wrong(kwargs, expected):
    assert expected in EventService.schedule_error(**kwargs)


def test_good_dates_have_no_error():
    assert EventService.schedule_error(TODAY) is None
    assert EventService.schedule_error(TODAY, NEXT_WEEK) is None
    assert EventService.schedule_error(TODAY, None, "Weekly", YEAR_END) is None


def _event(**kwargs):
    fields = dict(
        start_date=NEXT_WEEK,
        end_date=None,
        start_time=None,
        recurrence_pattern=None,
        repeat_until=None,
    )
    fields.update(kwargs)
    return Event(**fields)


def test_next_date_of_a_one_day_event():
    assert EventService.next_date(_event(), TODAY) == NEXT_WEEK
    assert EventService.next_date(_event(start_date=TODAY), TODAY) == TODAY
    assert EventService.next_date(_event(start_date=LAST_WEEK), TODAY) is None


def test_a_multi_day_event_stays_until_its_last_day():
    camp = _event(start_date=LAST_WEEK, end_date=TODAY)
    assert EventService.next_date(camp, TODAY) == LAST_WEEK
    assert EventService.next_date(camp, TOMORROW) is None


def test_next_date_of_a_repeating_event():
    coop = _event(
        start_date=LAST_WEEK,
        recurrence_pattern="Every Tuesday",
        repeat_until=YEAR_END,
    )
    assert EventService.next_date(coop, TODAY) == NEXT_TUESDAY
    assert EventService.next_date(coop, date(2027, 1, 1)) is None


@pytest.mark.parametrize(
    "kwargs, day, expected",
    [
        ({}, NEXT_TUESDAY, "Tue, Nov 10"),
        ({"start_time": time(14, 0)}, NEXT_TUESDAY, "Tue, Nov 10 at 2:00 PM"),
        ({"start_time": time(9, 30)}, NEXT_TUESDAY, "Tue, Nov 10 at 9:30 AM"),
        ({"end_date": NEXT_WEEK}, NEXT_TUESDAY, "Tue, Nov 10 to Thu, Nov 12"),
    ],
)
def test_describe_when(kwargs, day, expected):
    assert EventService.describe_when(_event(**kwargs), day) == expected


# ----- Creating and editing -----


def test_creating_saves_the_details(parent, fetch):
    event = add(
        description=" Bring lunch ",
        end_date=date(2026, 11, 13),
        start_time=time(9, 0),
        student_ids=[parent.ann],
    )

    saved = fetch(Event, event.id)
    assert saved.family_id == parent.smith
    assert saved.description == "Bring lunch"
    assert saved.end_date == date(2026, 11, 13)
    assert saved.start_time == time(9, 0)
    assert links_of(event.id) == {parent.ann}


def test_no_students_means_the_whole_family(parent):
    event = add()

    assert links_of(event.id) == set()
    assert titles(EventService.get_visible_events(parent.ann)) == ["Field trip"]


def test_a_blank_title_or_bad_date_saves_nothing(parent):
    assert add(title="   ") is None
    assert add(end_date=LAST_WEEK) is None


def test_a_repeating_event_has_no_last_day(parent, fetch):
    event = add(
        end_date=NEXT_WEEK,
        recurrence_pattern="Weekly",
        repeat_until=YEAR_END,
    )

    assert fetch(Event, event.id).end_date is None


def test_a_one_off_event_has_no_repeat_until(parent, fetch):
    event = add(repeat_until=YEAR_END)

    assert fetch(Event, event.id).repeat_until is None


def test_archived_students_cant_be_chosen(parent):
    assert add(student_ids=[parent.gone]) is None


def test_editing_changes_only_the_links_that_changed(parent):
    event = add(student_ids=[parent.ann, parent.bob])

    db = SessionLocal()
    try:
        ann_link = (
            db.query(EventStudent)
            .filter_by(event_id=event.id, student_id=parent.ann)
            .one()
            .id
        )
    finally:
        db.close()

    assert EventService.update_event(
        event.id, "New name", NEXT_WEEK, student_ids=[parent.ann, parent.cat]
    )

    assert links_of(event.id) == {parent.ann, parent.cat}

    db = SessionLocal()
    try:
        assert db.get(EventStudent, ann_link) is not None
    finally:
        db.close()


def test_editing_keeps_a_link_to_an_archived_student(parent):
    event = add(student_ids=[parent.ann])

    db = SessionLocal()
    try:
        db.add(EventStudent(event_id=event.id, student_id=parent.gone))
        db.commit()
    finally:
        db.close()

    assert EventService.update_event(
        event.id, "Field trip", NEXT_WEEK, student_ids=[parent.bob]
    )

    assert links_of(event.id) == {parent.bob, parent.gone}


def test_a_new_archived_student_cant_be_added_by_editing(parent):
    event = add()

    assert (
        EventService.update_event(
            event.id, "Field trip", NEXT_WEEK, student_ids=[parent.gone]
        )
        is None
    )


def test_making_an_event_for_everyone_removes_all_links(parent):
    event = add(student_ids=[parent.ann])

    assert EventService.update_event(event.id, "Field trip", NEXT_WEEK)

    assert links_of(event.id) == set()


def test_archiving_hides_the_event_but_keeps_the_row(parent, fetch):
    event = add()

    assert EventService.archive_event(event.id)

    assert EventService.get_visible_events() == []
    assert EventService.get_event_by_id(event.id) is None
    assert fetch(Event, event.id).active is False


# ----- Who sees what -----


def test_parent_sees_every_event(parent):
    add("For Ann", student_ids=[parent.ann])
    add("For Bob", student_ids=[parent.bob])
    add("For everyone")

    assert sorted(titles(EventService.get_visible_events())) == [
        "For Ann",
        "For Bob",
        "For everyone",
    ]


def test_parent_can_view_one_students_events(parent):
    add("For Ann", student_ids=[parent.ann])
    add("For Bob", student_ids=[parent.bob])
    add("For everyone")

    assert sorted(titles(EventService.get_visible_events(parent.bob))) == [
        "For Bob",
        "For everyone",
    ]


def test_student_sees_only_their_own_whatever_is_asked_for(parent, login):
    add("For Ann", student_ids=[parent.ann])
    add("For Bob", student_ids=[parent.bob])
    add("For everyone")

    login(parent.smith, role=UserRole.STUDENT, student_id=parent.bob)

    for asked_for in (None, parent.bob, parent.ann):
        assert sorted(titles(EventService.get_visible_events(asked_for))) == [
            "For Bob",
            "For everyone",
        ]


def test_students_cant_change_events(parent, login):
    event = add()

    login(parent.smith, role=UserRole.STUDENT, student_id=parent.bob)

    assert add("Sneaky") is None
    assert EventService.update_event(event.id, "Sneaky", NEXT_WEEK) is None
    assert EventService.archive_event(event.id) is None
    assert EventService.get_event_by_id(event.id) is None


def test_admins_see_no_events(parent, login):
    add()

    login(None, role=UserRole.ADMIN)

    assert EventService.get_visible_events() == []


def test_one_family_cant_see_or_change_anothers_events(parent, login, fetch):
    event = add()

    login(parent.jones)

    assert EventService.get_visible_events() == []
    assert EventService.get_visible_events(parent.ann) == []
    assert EventService.get_event_by_id(event.id) is None
    assert EventService.update_event(event.id, "Taken", NEXT_WEEK) is None
    assert EventService.archive_event(event.id) is None
    assert fetch(Event, event.id).title == "Field trip"
    assert fetch(Event, event.id).active is True


def test_one_family_cant_add_anothers_students(parent):
    assert add(student_ids=[parent.jones_kid]) is None

    event = add()

    assert (
        EventService.update_event(
            event.id, "Field trip", NEXT_WEEK, student_ids=[parent.jones_kid]
        )
        is None
    )


def test_archived_students_arent_named(parent):
    event = add(student_ids=[parent.ann])

    db = SessionLocal()
    try:
        db.add(EventStudent(event_id=event.id, student_id=parent.gone))
        db.commit()
    finally:
        db.close()

    loaded = EventService.get_event_by_id(event.id)

    assert EventService.audience(loaded) == "Ann"


def test_audience_says_whole_family(parent):
    event = add()

    assert (
        EventService.audience(EventService.get_event_by_id(event.id))
        == "Whole family"
    )


# ----- Lists -----


def test_upcoming_is_soonest_first_with_all_day_events_leading(parent):
    add("Later", NEXT_WEEK)
    add("Afternoon", TOMORROW, start_time=time(14, 0))
    add("Morning", TOMORROW, start_time=time(9, 0))
    add("All day", TOMORROW)

    upcoming, past = EventService.split_by_date(
        EventService.get_visible_events(), TODAY
    )

    assert [entry["event"].title for entry in upcoming] == [
        "All day",
        "Morning",
        "Afternoon",
        "Later",
    ]
    assert past == []


def test_a_repeating_event_shows_once_under_its_next_date(parent):
    add(
        "Co-op",
        LAST_WEEK,
        recurrence_pattern="Every Tuesday",
        repeat_until=YEAR_END,
    )

    upcoming = EventService.get_upcoming(TODAY)

    assert len(upcoming) == 1
    assert upcoming[0]["date"] == NEXT_TUESDAY


def test_finished_events_are_past(parent):
    add("Old", LAST_WEEK)

    upcoming, past = EventService.split_by_date(
        EventService.get_visible_events(), TODAY
    )

    assert upcoming == []
    assert titles(past) == ["Old"]


def test_dashboards_only_look_30_days_ahead(parent):
    add("Soon", TODAY + timedelta(days=30))
    add("Too far", TODAY + timedelta(days=31))

    assert [
        entry["event"].title for entry in EventService.get_upcoming(TODAY)
    ] == ["Soon"]


# ----- The pages -----


@pytest.fixture
def page_as(world):
    def _open(name, role, student_id=None, family_id=None):
        db = SessionLocal()
        try:
            user = User(
                family_id=world.smith if family_id is None else family_id,
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
            str(next((ROOT / "pages").glob(f"*_{name}.py"))), default_timeout=30
        )
        at.session_state["current_user_id"] = user_id
        return at

    with (
        mock.patch.object(SessionService, "sync_browser", return_value=None),
        mock.patch.object(st, "page_link"),
        mock.patch.object(st, "switch_page"),
    ):
        yield _open


def _add_real(w, login, title, **kwargs):
    """Real dates, since the pages use the real clock."""
    login(w.smith)
    event = EventService.create_event(
        title=title,
        start_date=date.today() + timedelta(days=2),
        **kwargs,
    )
    mock.patch.stopall()
    return event


def _labelled(widgets, label):
    return next(widget for widget in widgets if widget.label == label)


def test_parent_creates_an_event_on_the_page(world, page_as):
    at = page_as("Events", "Parent").run()

    assert not at.exception
    assert any("No upcoming events" in box.value for box in at.info)

    _labelled(at.text_input, "Title").set_value("Science co-op")
    next(b for b in at.button if b.label == "Create Event").click().run()

    assert not at.exception
    assert any("Science co-op" in text.value for text in at.markdown)
    assert any("Whole family" in caption.value for caption in at.caption)


def test_a_blank_title_shows_a_friendly_error(world, page_as):
    at = page_as("Events", "Parent").run()

    next(b for b in at.button if b.label == "Create Event").click().run()

    assert not at.exception
    assert any("enter a title" in error.value for error in at.error)


def test_repeat_choice_shows_repeat_until(world, page_as):
    at = page_as("Events", "Parent").run()

    at.selectbox(key="create_event_repeat").set_value("Every Tuesday").run()

    assert not at.exception
    assert _labelled(at.date_input, "Repeats Until").value.month == 12


def test_parent_edits_from_the_page(world, login, page_as):
    # A dialog's second click needs the browser, so the clicks are stood in for.
    event = _add_real(world, login, "Field trip")

    wanted = {f"edit_{event.id}", "💾 Save Changes"}

    def click(label, *args, key=None, **kwargs):
        for name in (key, label):
            if name in wanted:
                wanted.remove(name)
                return True
        return False

    real_text_input = st.text_input

    def type_title(label, *args, **kwargs):
        if label == "Title" and "value" in kwargs:
            return "Renamed"
        return real_text_input(label, *args, **kwargs)

    with (
        mock.patch.object(st, "dialog", lambda title: lambda fn: fn),
        mock.patch.object(st, "button", click),
        mock.patch.object(st, "text_input", type_title),
    ):
        at = page_as("Events", "Parent").run()

    assert not at.exception
    assert not wanted

    db = SessionLocal()
    try:
        assert db.get(Event, event.id).title == "Renamed"
    finally:
        db.close()


def test_student_page_is_read_only_and_only_theirs(world, login, page_as):
    _add_real(world, login, "For Bob", student_ids=[world.bob])
    _add_real(world, login, "For Ann", student_ids=[world.ann])

    at = page_as("Events", "Student", student_id=world.bob).run()

    assert not at.exception
    text = " ".join(item.value for item in at.markdown)
    assert "For Bob" in text
    assert "For Ann" not in text
    assert not [b for b in at.button if b.label in ("Create Event", "✏️", "📦")]


def test_student_dashboard_shows_only_their_events(world, login, page_as):
    _add_real(world, login, "For Bob", student_ids=[world.bob])
    _add_real(world, login, "For Ann", student_ids=[world.ann])

    at = page_as("Student_Dashboard", "Student", student_id=world.bob).run()

    assert not at.exception
    text = " ".join(item.value for item in at.markdown)
    assert "For Bob" in text
    assert "For Ann" not in text


def test_parent_dashboard_shows_events_and_who_theyre_for(world, login, page_as):
    _add_real(world, login, "For Bob", student_ids=[world.bob])

    at = page_as("Parent_Dashboard", "Parent").run()

    assert not at.exception
    assert any("For Bob" in item.value for item in at.markdown)
    assert not any("coming soon" in box.value.lower() and "Event" in box.value for box in at.info)
