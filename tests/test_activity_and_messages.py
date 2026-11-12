"""The parent dashboard's recent activity, and the daily message."""
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from database.db import SessionLocal
from database.models import AssignmentOccurrence, Student, User, UserRole
from services.activity_service import ActivityService
from services.assignment_service import AssignmentService
from services.current_user import CurrentUser
from services.daily_message_service import DailyMessageService, MESSAGES
from services.reading_service import ReadingService
from services.session_service import SessionService

ROOT = Path(__file__).resolve().parent.parent

# A Thursday. The family's time zone is America/Chicago, 6 hours behind UTC.
TODAY = date(2026, 11, 5)
YESTERDAY = date(2026, 11, 4)


@pytest.fixture
def parent(smith_parent):
    # The shared sample work was finished this week. Move it out of the way.
    db = SessionLocal()
    try:
        db.get(AssignmentOccurrence, smith_parent.ann_essay_day).completed_at = (
            datetime(2026, 1, 1)
        )
        db.commit()
    finally:
        db.close()

    with mock.patch.object(CurrentUser, "get_today", return_value=TODAY):
        yield smith_parent


def finished_work(w, title="Essay", at=datetime(2026, 11, 5, 15, 0), student=None):
    """Saves work finished at a UTC time."""
    student = student or w.ann

    work = AssignmentService.create_assignment(
        subject_id=w.art,
        title=title,
        student_ids=[student],
        due_date=TODAY,
    )

    db = SessionLocal()
    try:
        row = db.query(AssignmentOccurrence).filter_by(assignment_id=work.id).one()
        row.status = "Complete"
        row.completed_at = at
        db.commit()
    finally:
        db.close()

    return work


def flat(grouped):
    return [text for _, entries in grouped for text in entries]


# ----- Activity -----


def test_nothing_done_means_no_activity(parent):
    AssignmentService.create_assignment(
        subject_id=parent.art,
        title="Not done",
        student_ids=[parent.ann],
        due_date=TODAY,
    )

    assert ActivityService.get_recent(TODAY) == []


def test_finished_work_names_the_student_and_work(parent):
    finished_work(parent)

    assert ActivityService.get_recent(TODAY) == [
        (TODAY, ["✅ Ann finished **Essay**"])
    ]


def test_a_lesson_shows_its_number(parent):
    work = AssignmentService.create_assignment(
        subject_id=parent.math,
        title="Saxon Math",
        student_ids=[parent.ann],
        due_date=TODAY,
        assignment_type="Curriculum",
        recurrence_pattern="Mon,Tue,Wed,Thu,Fri",
        lesson_count=1,
    )

    db = SessionLocal()
    try:
        row = db.query(AssignmentOccurrence).filter_by(assignment_id=work.id).one()
        row.status = "Complete"
        row.completed_at = datetime(2026, 11, 5, 15, 0)
        db.commit()
    finally:
        db.close()

    assert flat(ActivityService.get_recent(TODAY)) == [
        "✅ Ann finished **Saxon Math: Lesson 1**"
    ]


def test_the_day_uses_the_familys_time_zone(parent):
    # 3 AM UTC on the 5th is 9 PM on the 4th in Chicago.
    finished_work(parent, at=datetime(2026, 11, 5, 3, 0))

    assert ActivityService.get_recent(TODAY)[0][0] == YESTERDAY


def test_the_last_seven_days_count_in_local_time(parent):
    # Oct 30 is six days back. It begins at 5 AM UTC, during daylight time.
    finished_work(parent, "Just in", at=datetime(2026, 10, 30, 5, 30))
    finished_work(parent, "Just out", at=datetime(2026, 10, 30, 4, 30))

    assert flat(ActivityService.get_recent(TODAY)) == [
        "✅ Ann finished **Just in**"
    ]


def test_reading_and_finished_books_show(parent):
    book = ReadingService.add_book(parent.bob, "Hatchet")
    ReadingService.log_pages(book.id, TODAY, 15)
    ReadingService.log_pages(book.id, YESTERDAY, 1)
    ReadingService.set_finished(book.id, True)

    assert ActivityService.get_recent(TODAY) == [
        (
            TODAY,
            [
                "🎉 Bob finished the book **Hatchet**",
                "📖 Bob read 15 pages of **Hatchet**",
            ],
        ),
        (YESTERDAY, ["📖 Bob read 1 page of **Hatchet**"]),
    ]


def test_old_reading_is_left_out(parent):
    book = ReadingService.add_book(parent.bob, "Hatchet")
    ReadingService.log_pages(book.id, TODAY - timedelta(days=7), 15)

    assert ActivityService.get_recent(TODAY) == []


def test_days_are_newest_first_and_checkoffs_lead_reading(parent):
    book = ReadingService.add_book(parent.bob, "Hatchet")
    ReadingService.log_pages(book.id, TODAY, 15)
    finished_work(parent, "Earlier", at=datetime(2026, 11, 5, 14, 0))
    finished_work(parent, "Later", at=datetime(2026, 11, 5, 16, 0))
    finished_work(parent, "Yesterday's", at=datetime(2026, 11, 4, 16, 0))

    grouped = ActivityService.get_recent(TODAY)

    assert [day for day, _ in grouped] == [TODAY, YESTERDAY]
    assert grouped[0][1] == [
        "✅ Ann finished **Later**",
        "✅ Ann finished **Earlier**",
        "📖 Bob read 15 pages of **Hatchet**",
    ]


def test_at_most_twenty_items_keeping_the_newest(parent):
    for minute in range(25):
        finished_work(
            parent, f"Work {minute}", at=datetime(2026, 11, 5, 15, minute)
        )

    items = flat(ActivityService.get_recent(TODAY))

    assert len(items) == 20
    assert items[0] == "✅ Ann finished **Work 24**"
    assert "✅ Ann finished **Work 4**" not in items


def test_archived_work_books_and_students_are_left_out(parent):
    work = finished_work(parent, "Archived work")
    AssignmentService.archive_assignment(work.id)

    book = ReadingService.add_book(parent.bob, "Archived book")
    ReadingService.log_pages(book.id, TODAY, 5)
    ReadingService.archive_book(book.id)

    assert ActivityService.get_recent(TODAY) == []

    finished_work(parent, "Cat's work", student=parent.cat)
    cats_book = ReadingService.add_book(parent.cat, "Cat's book")
    ReadingService.log_pages(cats_book.id, TODAY, 5)

    db = SessionLocal()
    try:
        db.get(Student, parent.cat).active = False
        db.commit()
    finally:
        db.close()

    assert ActivityService.get_recent(TODAY) == []


def test_one_family_cant_see_anothers_activity(parent, login):
    finished_work(parent)
    book = ReadingService.add_book(parent.bob, "Hatchet")
    ReadingService.log_pages(book.id, TODAY, 5)

    login(parent.jones)

    assert ActivityService.get_recent(TODAY) == []


def test_students_and_admins_get_no_activity(parent, login):
    finished_work(parent)

    login(parent.smith, role=UserRole.STUDENT, student_id=parent.ann)
    assert ActivityService.get_recent(TODAY) == []

    login(None, role=UserRole.ADMIN)
    assert ActivityService.get_recent(TODAY) == []


@pytest.mark.parametrize(
    "day, expected",
    [
        (TODAY, "Today"),
        (YESTERDAY, "Yesterday"),
        (date(2026, 11, 2), "Mon, Nov 2"),
    ],
)
def test_day_labels(day, expected):
    assert ActivityService.day_label(day, TODAY) == expected


# ----- Daily message -----


def test_the_message_stays_the_same_all_day():
    assert DailyMessageService.get_message(TODAY) == DailyMessageService.get_message(
        date(2026, 11, 5)
    )


def test_every_message_shows_before_any_repeats():
    days = [TODAY + timedelta(days=offset) for offset in range(len(MESSAGES))]

    assert {DailyMessageService.get_message(day) for day in days} == set(MESSAGES)


def test_messages_arent_duplicated():
    assert len(MESSAGES) == len(set(MESSAGES))


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
                auth_user_id=(
                    "00000000-0000-0000-0000-00000000000a"
                    if role == "Parent"
                    else "00000000-0000-0000-0000-00000000000b"
                ),
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


def test_parent_dashboard_shows_activity_and_no_placeholder(world, login, page_as):
    login(world.smith)
    today = datetime.utcnow()
    work = AssignmentService.create_assignment(
        subject_id=world.art,
        title="Essay",
        student_ids=[world.ann],
        due_date=today.date(),
    )
    db = SessionLocal()
    try:
        row = db.query(AssignmentOccurrence).filter_by(assignment_id=work.id).one()
        row.status = "Complete"
        row.completed_at = today
        db.commit()
    finally:
        db.close()
    mock.patch.stopall()

    at = page_as("Parent_Dashboard", "Parent").run()

    assert not at.exception
    assert any("Ann finished **Essay**" in item.value for item in at.markdown)
    assert not any("coming soon" in box.value.lower() for box in at.info)


def test_parent_dashboard_with_no_activity_says_so(world, page_as):
    db = SessionLocal()
    try:
        db.get(AssignmentOccurrence, world.ann_essay_day).completed_at = (
            datetime(2020, 1, 1)
        )
        db.commit()
    finally:
        db.close()

    at = page_as("Parent_Dashboard", "Parent").run()

    assert not at.exception
    assert any("Nothing has been finished" in box.value for box in at.info)


def test_both_dashboards_show_a_daily_message(world, page_as):
    parent_page = page_as("Parent_Dashboard", "Parent").run()
    student_page = page_as("Student_Dashboard", "Student", student_id=world.bob).run()

    for at in (parent_page, student_page):
        assert not at.exception
        assert any(box.value in MESSAGES for box in at.info)
