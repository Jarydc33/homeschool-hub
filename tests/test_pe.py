"""Students log P.E. activities, and parents can log for several at once."""
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from database.db import SessionLocal
from database.models import ActivityLog, AssignmentOccurrence, Student, User, UserRole
from services.activity_service import ActivityService
from services.current_user import CurrentUser
from services.pe_service import PEService
from services.session_service import SessionService

ROOT = Path(__file__).resolve().parent.parent

# A Thursday. The week started on Sunday, Nov 1.
TODAY = date(2026, 11, 5)
YESTERDAY = date(2026, 11, 4)


@pytest.fixture
def parent(smith_parent):
    with mock.patch.object(CurrentUser, "get_today", return_value=TODAY):
        yield smith_parent


def log(students, activity="Soccer", minutes=30, day=TODAY):
    return PEService.log_activity(students, day, activity, minutes)


def all_logs():
    db = SessionLocal()
    try:
        return db.query(ActivityLog).order_by(ActivityLog.id).all()
    finally:
        db.close()


def entry(day, minutes=30, activity="Soccer"):
    return SimpleNamespace(log_date=day, minutes=minutes, activity=activity)


# ----- Reading the numbers -----


@pytest.mark.parametrize(
    "minutes, expected",
    [(0, "0 min"), (45, "45 min"), (60, "1 hr"), (90, "1 hr 30 min"), (600, "10 hr")],
)
def test_describe_minutes(minutes, expected):
    assert PEService.describe_minutes(minutes) == expected


def test_this_week_starts_on_sunday_and_counts_active_days():
    logs = [
        entry(date(2026, 10, 31), 100),
        entry(date(2026, 11, 1), 20),
        entry(TODAY, 30),
        entry(TODAY, 15, "Walk"),
    ]

    result = PEService.summary(logs, TODAY)

    assert result["minutes_this_week"] == 65
    assert result["active_days_this_week"] == 2
    assert result["total_minutes"] == 165


def test_hour_badges():
    def earned(minutes):
        return {
            badge["key"]
            for badge in PEService.summary([entry(TODAY, minutes)], TODAY)["badges"]
            if badge["earned"]
        }

    assert earned(599) == set()
    assert earned(600) == {"pe_hours_10"}


def test_known_activities_are_most_used_first_ignoring_capitals():
    logs = [
        entry(TODAY, activity="Walk"),
        entry(TODAY, activity="Soccer"),
        entry(TODAY, activity="soccer"),
        entry(TODAY, activity="Bike ride"),
    ]

    assert PEService.known_activities(logs) == ["Soccer", "Bike ride", "Walk"]


# ----- Logging -----


def test_logging_saves_the_entry(parent):
    assert log([parent.bob], " Bike ride ", 45, YESTERDAY) == 1

    saved = all_logs()[0]
    assert saved.family_id == parent.smith
    assert saved.student_id == parent.bob
    assert saved.activity == "Bike ride"
    assert saved.minutes == 45
    assert saved.log_date == YESTERDAY


def test_a_parent_logs_for_several_kids_at_once(parent):
    assert log([parent.ann, parent.bob], "Hike", 90) == 2

    assert sorted(entry.student_id for entry in all_logs()) == sorted(
        [parent.ann, parent.bob]
    )


def test_several_activities_can_share_a_day(parent):
    log([parent.bob], "Soccer")
    log([parent.bob], "Walk")

    assert len(PEService.get_logs(parent.bob)) == 2


@pytest.mark.parametrize(
    "day, activity, minutes, expected",
    [
        (None, "Soccer", 30, "date"),
        (TODAY + timedelta(days=1), "Soccer", 30, "future"),
        (TODAY, "  ", 30, "enter an activity"),
        (TODAY, None, 30, "enter an activity"),
        (TODAY, "x" * 101, 30, "shorter"),
        (TODAY, "Soccer", None, "minutes"),
        (TODAY, "Soccer", 0, "minutes"),
        (TODAY, "Soccer", 601, "minutes"),
    ],
)
def test_bad_entries_say_whats_wrong_and_save_nothing(
    parent, day, activity, minutes, expected
):
    assert expected in PEService.log_error(day, activity, minutes)
    assert PEService.log_activity([parent.bob], day, activity, minutes) is None
    assert all_logs() == []


def test_no_students_saves_nothing(parent):
    assert log([]) is None


def test_deleting_removes_an_entry(parent):
    log([parent.bob])

    assert PEService.delete_log(all_logs()[0].id)

    assert all_logs() == []


def test_newest_entries_come_first(parent):
    log([parent.bob], "Old", day=YESTERDAY)
    log([parent.bob], "New", day=TODAY)

    assert [e.activity for e in PEService.get_logs(parent.bob)] == ["New", "Old"]


# ----- Who can do what -----


def test_student_logs_and_deletes_their_own(parent, login):
    login(parent.smith, role=UserRole.STUDENT, student_id=parent.bob)

    assert log([parent.bob]) == 1
    assert len(PEService.get_logs(parent.bob)) == 1
    assert PEService.delete_log(all_logs()[0].id)


def test_student_cant_log_for_or_touch_a_sibling(parent, login):
    log([parent.ann])

    login(parent.smith, role=UserRole.STUDENT, student_id=parent.bob)

    assert log([parent.ann]) is None
    assert log([parent.ann, parent.bob]) is None
    assert PEService.get_logs(parent.ann) == []
    assert PEService.delete_log(all_logs()[0].id) is False
    assert len(all_logs()) == 1


def test_one_family_cant_see_log_or_delete_anothers(parent, login):
    log([parent.bob])

    login(parent.jones)

    assert log([parent.bob]) is None
    assert log([parent.jones_kid, parent.bob]) is None
    assert PEService.get_logs(parent.bob) == []
    assert PEService.delete_log(all_logs()[0].id) is False
    assert len(all_logs()) == 1


def test_archived_students_are_left_out(parent):
    log([parent.bob])

    db = SessionLocal()
    try:
        db.get(Student, parent.bob).active = False
        db.commit()
    finally:
        db.close()

    assert PEService.get_logs(parent.bob) == []
    assert log([parent.bob]) is None
    assert log([parent.ann, parent.bob]) is None
    assert not [
        text
        for _, entries in ActivityService.get_recent(TODAY)
        for text in entries
        if text.startswith("🏃")
    ]


def test_admins_cant_use_it(parent, login):
    log([parent.bob])

    login(None, role=UserRole.ADMIN)

    assert PEService.get_logs(parent.bob) == []
    assert log([parent.bob]) is None


# ----- Recent activity -----


def test_pe_shows_in_recent_activity(parent):
    # Keep the shared sample work out of the list.
    db = SessionLocal()
    try:
        db.get(AssignmentOccurrence, parent.ann_essay_day).completed_at = None
        db.commit()
    finally:
        db.close()

    log([parent.bob], "Soccer", 30)
    log([parent.ann], "Stretching", 1, YESTERDAY)

    assert ActivityService.get_recent(TODAY) == [
        (TODAY, ["🏃 Bob did 30 minutes of **Soccer**"]),
        (YESTERDAY, ["🏃 Ann did 1 minute of **Stretching**"]),
    ]


# ----- The pages -----


@pytest.fixture
def page_as(world):
    def _open(name, role, student_id=None):
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


def _labelled(widgets, label):
    return next(widget for widget in widgets if widget.label == label)


def _metric(at, label):
    return next(m for m in at.metric if label in m.label).value


def _text(at):
    return " ".join(item.value for item in at.markdown)


def _seed(w, login, students, activity="Soccer", minutes=30):
    login(w.smith)
    with mock.patch.object(CurrentUser, "get_today", return_value=date.today()):
        PEService.log_activity(students, date.today(), activity, minutes)
    mock.patch.stopall()


def test_student_logs_a_known_activity(world, login, page_as):
    _seed(world, login, [world.bob], "Soccer", 20)

    at = page_as("PE", "Student", student_id=world.bob).run()

    assert not at.exception
    assert "Select Student" not in [box.label for box in at.selectbox]
    assert not [box for box in at.multiselect if box.label == "Who Did It?"]
    assert "Soccer" in _labelled(at.selectbox, "Activity").options

    _labelled(at.selectbox, "Activity").set_value("Soccer")
    _labelled(at.number_input, "Minutes").set_value(25)
    next(b for b in at.button if b.label == "Save Activity").click().run()

    assert not at.exception
    assert _metric(at, "This Week") == "45 min"
    assert _metric(at, "Active Days") == "1 of 7"


def test_missing_minutes_shows_a_friendly_error(world, login, page_as):
    _seed(world, login, [world.bob])

    at = page_as("PE", "Student", student_id=world.bob).run()

    _labelled(at.selectbox, "Activity").set_value("Soccer")
    next(b for b in at.button if b.label == "Save Activity").click().run()

    assert not at.exception
    assert any("minutes" in error.value for error in at.error)


def test_deleting_from_the_page(world, login, page_as):
    _seed(world, login, [world.bob])

    at = page_as("PE", "Student", student_id=world.bob).run()
    at.button(key=f"delete_{all_logs()[0].id}").click().run()

    assert not at.exception
    assert all_logs() == []
    assert any("Nothing logged yet" in box.value for box in at.info)


def test_parent_sees_only_the_chosen_child(world, login, page_as):
    _seed(world, login, [world.ann], "Ann's swim")
    _seed(world, login, [world.bob], "Bob's run")

    at = page_as("PE", "Parent").run()
    at.selectbox(key="pe_student").set_value(world.bob).run()

    assert not at.exception
    assert "Bob's run" in _text(at)
    assert "Ann's swim" not in _text(at)


def test_student_dashboard_shows_pe_and_its_badges(world, login, page_as):
    _seed(world, login, [world.bob], "Soccer", 45)

    at = page_as("Student_Dashboard", "Student", student_id=world.bob).run()

    assert not at.exception
    assert next(m for m in at.metric if "P.E." in m.label).value == "45 min"
    assert any("1 of 7 days active" in c.value for c in at.caption)
    assert any("On the Move" in item.value for item in at.markdown)
