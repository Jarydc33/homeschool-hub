"""Each student keeps their own books, and logs pages to keep a streak alive."""
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from database.db import SessionLocal
from database.models import Book, ReadingLog, Student, User, UserRole
from services.auth_service import AuthService
from services.reading_service import ReadingService
from services.session_service import SessionService

ROOT = Path(__file__).resolve().parent.parent

# A Thursday. The week started on Sunday, Nov 1.
TODAY = date(2026, 11, 5)
YESTERDAY = date(2026, 11, 4)
TOMORROW = date(2026, 11, 6)


def ago(days):
    return TODAY - timedelta(days=days)


@pytest.fixture
def parent(smith_parent):
    with mock.patch.object(AuthService, "get_today", return_value=TODAY):
        yield smith_parent


def add(student_id, title="Charlotte's Web", **kwargs):
    return ReadingService.add_book(student_id, title, **kwargs)


def summary_of(student_id):
    return ReadingService.summary(ReadingService.get_books(student_id), TODAY)


def earned(student_id):
    return {
        badge["key"]
        for badge in summary_of(student_id)["badges"]
        if badge["earned"]
    }


def logs_of(book_id):
    db = SessionLocal()
    try:
        return {
            log.log_date: log.pages
            for log in db.query(ReadingLog).filter_by(book_id=book_id)
        }
    finally:
        db.close()


# ----- Streaks -----


def test_no_reading_means_no_streak():
    assert ReadingService.streaks(set(), TODAY) == (0, 0)


def test_days_in_a_row_count():
    assert ReadingService.streaks({ago(2), ago(1), TODAY}, TODAY) == (3, 3)


def test_not_reading_yet_today_doesnt_break_the_streak():
    assert ReadingService.streaks({ago(2), ago(1)}, TODAY) == (2, 2)


def test_a_full_day_off_breaks_the_streak_and_best_is_kept():
    days = {ago(6), ago(5), ago(4), ago(2)}

    assert ReadingService.streaks(days, TODAY) == (0, 3)


def test_reading_again_after_a_break_starts_over():
    days = {ago(6), ago(5), ago(4), TODAY}

    assert ReadingService.streaks(days, TODAY) == (1, 3)


def test_weekends_count_and_can_break_the_streak():
    # Saturday and Sunday are in the run.
    friday = date(2026, 10, 30)
    run = {friday + timedelta(days=offset) for offset in range(7)}

    assert ReadingService.streaks(run, TODAY) == (7, 7)

    # Without Sunday, the run restarts on Monday.
    run.remove(date(2026, 11, 1))

    assert ReadingService.streaks(run, TODAY) == (4, 4)


def test_future_days_are_ignored():
    assert ReadingService.streaks({TODAY, TOMORROW}, TODAY) == (1, 1)


# ----- Books -----


def test_adding_saves_the_details(parent, fetch):
    book = add(parent.bob, " Hatchet ", author=" Gary Paulsen ", total_pages=195)

    saved = fetch(Book, book.id)
    assert saved.family_id == parent.smith
    assert saved.student_id == parent.bob
    assert saved.title == "Hatchet"
    assert saved.author == "Gary Paulsen"
    assert saved.total_pages == 195
    assert saved.finished_on is None


def test_author_and_pages_are_optional(parent, fetch):
    saved = fetch(Book, add(parent.bob).id)

    assert saved.author is None
    assert saved.total_pages is None


@pytest.mark.parametrize(
    "title, pages",
    [("", None), ("   ", None), ("Book", 0), ("Book", -1), ("Book", 1000000)],
)
def test_bad_details_save_nothing(parent, title, pages):
    assert ReadingService.add_book(parent.bob, title, total_pages=pages) is None


def test_editing_changes_details_and_keeps_pages_logged(parent, fetch):
    book = add(parent.bob)
    ReadingService.log_pages(book.id, TODAY, 10)

    assert ReadingService.update_book(book.id, "Hatchet", "Gary Paulsen", 195)

    saved = fetch(Book, book.id)
    assert saved.title == "Hatchet"
    assert saved.total_pages == 195
    assert logs_of(book.id) == {TODAY: 10}


def test_a_bad_edit_changes_nothing(parent, fetch):
    book = add(parent.bob)

    assert ReadingService.update_book(book.id, "  ") is None
    assert fetch(Book, book.id).title == "Charlotte's Web"


def test_archiving_hides_it_and_takes_out_its_pages(parent, fetch):
    book = add(parent.bob)
    ReadingService.log_pages(book.id, TODAY, 10)

    assert ReadingService.archive_book(book.id)

    assert ReadingService.get_books(parent.bob) == []
    assert summary_of(parent.bob)["total_pages"] == 0
    assert summary_of(parent.bob)["streak"] == 0
    assert fetch(Book, book.id).active is False
    assert logs_of(book.id) == {TODAY: 10}


def test_finishing_dates_it_and_reopening_clears_it(parent, fetch):
    book = add(parent.bob)

    assert ReadingService.set_finished(book.id, True)
    assert fetch(Book, book.id).finished_on == TODAY

    assert ReadingService.set_finished(book.id, False)
    assert fetch(Book, book.id).finished_on is None


# ----- Logging -----


def test_logging_saves_and_saving_again_replaces(parent):
    book = add(parent.bob)

    assert ReadingService.log_pages(book.id, TODAY, 10)
    assert logs_of(book.id) == {TODAY: 10}

    assert ReadingService.log_pages(book.id, TODAY, 25)
    assert logs_of(book.id) == {TODAY: 25}


def test_zero_pages_removes_that_date(parent):
    book = add(parent.bob)
    ReadingService.log_pages(book.id, TODAY, 10)

    assert ReadingService.log_pages(book.id, TODAY, 0)
    assert logs_of(book.id) == {}
    assert ReadingService.log_pages(book.id, YESTERDAY, 0)


def test_a_forgotten_day_can_be_logged_and_repairs_the_streak(parent):
    book = add(parent.bob)
    ReadingService.log_pages(book.id, ago(2), 5)
    ReadingService.log_pages(book.id, TODAY, 5)

    assert summary_of(parent.bob)["streak"] == 1

    assert ReadingService.log_pages(book.id, ago(1), 5)

    assert summary_of(parent.bob)["streak"] == 3


def test_a_future_date_is_refused(parent):
    book = add(parent.bob)

    assert ReadingService.log_pages(book.id, TOMORROW, 5) is False
    assert logs_of(book.id) == {}


@pytest.mark.parametrize("pages", [-1, 5001])
def test_a_number_out_of_range_is_refused(parent, pages):
    book = add(parent.bob)

    assert ReadingService.log_pages(book.id, TODAY, pages) is False


def test_a_finished_book_cant_be_logged_until_reopened(parent):
    book = add(parent.bob)
    ReadingService.set_finished(book.id, True)

    assert ReadingService.log_pages(book.id, TODAY, 5) is False

    ReadingService.set_finished(book.id, False)

    assert ReadingService.log_pages(book.id, TODAY, 5) is True


# ----- Totals and badges -----


def test_any_book_keeps_the_day_alive(parent):
    first = add(parent.bob, "First")
    second = add(parent.bob, "Second")
    ReadingService.log_pages(first.id, ago(1), 5)
    ReadingService.log_pages(second.id, TODAY, 5)

    assert summary_of(parent.bob)["streak"] == 2


def test_finished_books_still_count_towards_the_streak(parent):
    book = add(parent.bob)
    ReadingService.log_pages(book.id, TODAY, 5)
    ReadingService.set_finished(book.id, True)

    assert summary_of(parent.bob)["streak"] == 1


def test_each_student_has_their_own_totals(parent):
    book = add(parent.bob)
    ReadingService.log_pages(book.id, TODAY, 5)

    assert summary_of(parent.bob)["total_pages"] == 5
    assert summary_of(parent.ann)["total_pages"] == 0


def test_pages_this_week_starts_on_sunday(parent):
    book = add(parent.bob)
    ReadingService.log_pages(book.id, date(2026, 10, 31), 100)
    ReadingService.log_pages(book.id, date(2026, 11, 1), 7)
    ReadingService.log_pages(book.id, TODAY, 3)

    result = summary_of(parent.bob)

    assert result["pages_this_week"] == 10
    assert result["total_pages"] == 110


def test_finished_book_badges(parent):
    assert "reading_books_1" not in earned(parent.bob)

    for number in range(5):
        ReadingService.set_finished(add(parent.bob, f"Book {number}").id, True)

    assert {"reading_books_1", "reading_books_5"} <= earned(parent.bob)


def test_page_badge(parent):
    book = add(parent.bob)
    ReadingService.log_pages(book.id, ago(1), 999)
    assert "reading_pages_1000" not in earned(parent.bob)

    ReadingService.log_pages(book.id, TODAY, 1)
    assert "reading_pages_1000" in earned(parent.bob)


def test_reading_streak_badge_stays_after_a_break(parent):
    book = add(parent.bob)
    for days in range(10, 17):
        ReadingService.log_pages(book.id, ago(days), 1)

    assert summary_of(parent.bob)["streak"] == 0
    assert "reading_streak_7" in earned(parent.bob)
    assert "reading_streak_30" not in earned(parent.bob)


# ----- Who can do what -----


def test_student_uses_their_own_books(parent, login, fetch):
    login(parent.smith, role=UserRole.STUDENT, student_id=parent.bob)

    book = add(parent.bob)

    assert book
    assert ReadingService.log_pages(book.id, TODAY, 5)
    assert ReadingService.set_finished(book.id, True)
    assert len(ReadingService.get_books(parent.bob)) == 1


def test_student_cant_touch_a_siblings_books(parent, login, fetch):
    book = add(parent.ann)

    login(parent.smith, role=UserRole.STUDENT, student_id=parent.bob)

    assert add(parent.ann, "Sneaky") is None
    assert ReadingService.get_books(parent.ann) == []
    assert ReadingService.log_pages(book.id, TODAY, 5) is False
    assert ReadingService.update_book(book.id, "Sneaky") is None
    assert ReadingService.set_finished(book.id, True) is None
    assert ReadingService.archive_book(book.id) is None
    assert fetch(Book, book.id).title == "Charlotte's Web"
    assert logs_of(book.id) == {}


def test_parent_uses_their_childrens_books(parent):
    book = add(parent.bob)

    assert ReadingService.log_pages(book.id, TODAY, 5)
    assert [b.id for b in ReadingService.get_books(parent.bob)] == [book.id]


def test_one_family_cant_see_or_change_anothers_books(parent, login, fetch):
    book = add(parent.bob)

    login(parent.jones)

    assert add(parent.bob, "Sneaky") is None
    assert ReadingService.get_books(parent.bob) == []
    assert ReadingService.log_pages(book.id, TODAY, 5) is False
    assert ReadingService.update_book(book.id, "Sneaky") is None
    assert ReadingService.set_finished(book.id, True) is None
    assert ReadingService.archive_book(book.id) is None
    assert fetch(Book, book.id).active is True
    assert logs_of(book.id) == {}


def test_archived_students_books_arent_available_to_a_parent(parent):
    book = add(parent.bob)

    db = SessionLocal()
    try:
        db.get(Student, parent.bob).active = False
        db.commit()
    finally:
        db.close()

    assert ReadingService.get_books(parent.bob) == []
    assert ReadingService.log_pages(book.id, TODAY, 5) is False
    assert add(parent.bob, "New") is None


def test_admins_cant_use_books(parent, login):
    book = add(parent.bob)

    login(None, role=UserRole.ADMIN)

    assert ReadingService.get_books(parent.bob) == []
    assert add(parent.bob, "Sneaky") is None
    assert ReadingService.log_pages(book.id, TODAY, 5) is False


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


def test_student_adds_a_book_and_logs_pages(world, page_as):
    at = page_as("Reading", "Student", student_id=world.bob).run()

    assert not at.exception
    assert any("No books in progress" in box.value for box in at.info)
    assert not [box for box in at.selectbox if box.label == "Select Student"]

    _labelled(at.text_input, "Title").set_value("Hatchet")
    next(b for b in at.button if b.label == "Add Book").click().run()

    assert not at.exception
    assert "Hatchet" in _text(at)

    db = SessionLocal()
    try:
        book_id = db.query(Book).filter_by(title="Hatchet").one().id
    finally:
        db.close()

    today = date.today()
    at.number_input(key=f"pages_{book_id}_{today}").set_value(12)
    at.button(key=f"save_{book_id}").click().run()

    assert not at.exception
    assert logs_of(book_id) == {today: 12}
    assert _metric(at, "Reading Streak") == "1 day"
    assert _metric(at, "Pages This Week") == "12"


def test_a_blank_title_shows_a_friendly_error(world, page_as):
    at = page_as("Reading", "Student", student_id=world.bob).run()

    next(b for b in at.button if b.label == "Add Book").click().run()

    assert not at.exception
    assert any("enter a title" in error.value for error in at.error)


def test_finished_book_moves_to_the_list_and_can_be_reopened(world, page_as):
    at = page_as("Reading", "Student", student_id=world.bob).run()

    _labelled(at.text_input, "Title").set_value("Hatchet")
    next(b for b in at.button if b.label == "Add Book").click().run()

    db = SessionLocal()
    try:
        book_id = db.query(Book).filter_by(title="Hatchet").one().id
    finally:
        db.close()

    at.button(key=f"finish_{book_id}").click().run()

    assert not at.exception
    assert _metric(at, "Books Finished") == "1"
    assert any("Finished Books (1)" in e.label for e in at.expander)
    assert not [b for b in at.button if b.key == f"save_{book_id}"]

    at.button(key=f"reopen_{book_id}").click().run()

    assert not at.exception
    assert _metric(at, "Books Finished") == "0"
    assert at.button(key=f"save_{book_id}")


def test_parent_picks_a_child_and_only_sees_their_books(world, login, page_as):
    login(world.smith)
    with mock.patch.object(AuthService, "get_today", return_value=date.today()):
        add(world.ann, "Ann's book")
        add(world.bob, "Bob's book")
    mock.patch.stopall()

    at = page_as("Reading", "Parent").run()

    assert not at.exception

    at.selectbox(key="reading_student").set_value(world.bob).run()

    assert not at.exception
    assert "Bob's book" in _text(at)
    assert "Ann's book" not in _text(at)


def test_student_dashboard_shows_reading_and_its_badges(world, login, page_as):
    today = date.today()
    login(world.smith)
    with mock.patch.object(AuthService, "get_today", return_value=today):
        book = add(world.bob)
        ReadingService.log_pages(book.id, today, 15)
    mock.patch.stopall()

    at = page_as("Student_Dashboard", "Student", student_id=world.bob).run()

    assert not at.exception
    assert "1-day reading streak" in _text(at)
    assert "15 pages this week" in _text(at)
    assert any("Week of Reading" in item.value for item in at.markdown)
