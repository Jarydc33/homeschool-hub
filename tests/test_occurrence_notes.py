"""A parent can give one date of an assignment its own note."""
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from database.db import SessionLocal
from database.models import AssignmentOccurrence, User, UserRole
from services.assignment_service import AssignmentService
from services.current_user import CurrentUser
from services.occurrence_service import OccurrenceService
from services.session_service import SessionService
from services.student_service import StudentService

TODAY = date(2026, 11, 4)
TUESDAY = date(2026, 11, 10)
NEXT_WEEK = TODAY + timedelta(days=7)
ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def parent(smith_parent):
    with mock.patch.object(CurrentUser, "get_today", return_value=TODAY):
        yield smith_parent


@pytest.fixture
def work(parent):
    w = parent
    return AssignmentService.create_assignment(
        subject_id=w.art,
        title="Daily Math",
        student_ids=[w.ann, w.bob],
        due_date=TODAY,
        assignment_type="Recurring",
        recurrence_pattern="Every Day",
        end_date=NEXT_WEEK,
    )


def notes_by_key(assignment_id):
    db = SessionLocal()
    try:
        return {
            (row.student_id, row.occurrence_date): row.notes
            for row in db.query(AssignmentOccurrence).filter_by(assignment_id=assignment_id)
        }
    finally:
        db.close()


def test_a_note_lands_on_only_that_date(parent, work):
    w = parent

    saved = AssignmentService.set_occurrence_note(work.id, TUESDAY, [w.ann, w.bob], "Chapter 3")

    assert saved == 2
    notes = notes_by_key(work.id)
    assert notes[(w.ann, TUESDAY)] == "Chapter 3"
    assert notes[(w.bob, TUESDAY)] == "Chapter 3"
    assert [key for key, note in notes.items() if note] == [(w.ann, TUESDAY), (w.bob, TUESDAY)]


def test_a_note_can_be_for_one_student(parent, work):
    w = parent

    assert AssignmentService.set_occurrence_note(work.id, TUESDAY, [w.ann], "Just Ann") == 1

    notes = notes_by_key(work.id)
    assert notes[(w.ann, TUESDAY)] == "Just Ann"
    assert notes[(w.bob, TUESDAY)] is None


def test_a_blank_note_removes_it_and_the_row_counts_as_untouched(parent, work):
    w = parent
    AssignmentService.set_occurrence_note(work.id, TUESDAY, [w.ann], "Chapter 3")

    assert AssignmentService.set_occurrence_note(work.id, TUESDAY, [w.ann], "   ") == 1

    assert notes_by_key(work.id)[(w.ann, TUESDAY)] is None
    rows = AssignmentService.get_note_rows(work.id)
    row = next(r for r in rows if r.student_id == w.ann and r.occurrence_date == TUESDAY)
    assert OccurrenceService.is_untouched(row)


def test_a_note_is_trimmed(parent, work):
    w = parent

    AssignmentService.set_occurrence_note(work.id, TUESDAY, [w.ann], "  Chapter 3 \n")

    assert notes_by_key(work.id)[(w.ann, TUESDAY)] == "Chapter 3"


def test_a_note_keeps_its_date_when_the_schedule_ends_earlier(parent, work):
    w = parent
    AssignmentService.set_occurrence_note(work.id, TUESDAY, [w.ann], "Keep me")

    AssignmentService.update_assignment(
        assignment_id=work.id,
        title="Daily Math",
        description=None,
        due_date=TODAY,
        subject_id=w.art,
        student_ids=[w.ann, w.bob],
        assignment_type="Recurring",
        recurrence_pattern="Every Day",
        end_date=TODAY,
    )

    notes = notes_by_key(work.id)
    assert notes[(w.ann, TUESDAY)] == "Keep me"
    assert (w.bob, TUESDAY) not in notes


def test_a_note_stays_when_work_is_checked_and_unchecked(parent, work):
    w = parent
    AssignmentService.set_occurrence_note(work.id, TUESDAY, [w.ann], "Chapter 3")
    rows = AssignmentService.get_note_rows(work.id)
    row = next(r for r in rows if r.student_id == w.ann and r.occurrence_date == TUESDAY)

    StudentService.update_occurrence_status(row.id, True)
    StudentService.update_occurrence_status(row.id, False)

    assert notes_by_key(work.id)[(w.ann, TUESDAY)] == "Chapter 3"


def test_a_date_with_no_row_saves_nothing(parent, work):
    assert (
        AssignmentService.set_occurrence_note(work.id, date(2030, 1, 1), [parent.ann], "Nope")
        is None
    )


def test_a_student_not_on_the_assignment_gets_no_note(parent, work):
    assert AssignmentService.set_occurrence_note(work.id, TUESDAY, [parent.cat], "Nope") is None


def test_another_familys_assignment_cant_get_a_note(parent):
    w = parent

    assert AssignmentService.get_note_rows(w.jones_work) == []
    assert AssignmentService.set_occurrence_note(w.jones_work, w.due, [w.jones_kid], "Nope") is None
    assert notes_by_key(w.jones_work)[(w.jones_kid, w.due)] is None


def test_an_archived_assignment_cant_get_a_note(parent):
    w = parent

    assert AssignmentService.set_occurrence_note(w.archived, w.due, [w.ann], "Nope") is None


def test_an_archived_student_isnt_offered(parent):
    w = parent

    assert {row.student.name for row in AssignmentService.get_note_rows(w.essay)} == {"Ann", "Bob"}
    assert AssignmentService.set_occurrence_note(w.essay, w.due, [w.gone], "Nope") is None


def test_a_student_cant_write_notes(world, login):
    login(world.smith, UserRole.STUDENT, world.ann)

    assert AssignmentService.get_note_rows(world.essay) == []
    assert AssignmentService.set_occurrence_note(world.essay, world.due, [world.ann], "Mine") is None


@pytest.mark.parametrize(
    "dates, expected",
    [
        ([TODAY, NEXT_WEEK], TODAY),
        ([TODAY - timedelta(days=1), NEXT_WEEK], NEXT_WEEK),
        ([TODAY - timedelta(days=2), TODAY - timedelta(days=1)], TODAY - timedelta(days=1)),
    ],
    ids=["today", "next", "all-past"],
)
def test_note_dialog_starts_on_the_next_date(dates, expected):
    assert OccurrenceService.default_note_date(dates, TODAY) == expected


# ----- The real pages -----


@pytest.fixture
def page_as():
    def _open(name, family_id, role, student_id=None):
        db = SessionLocal()
        try:
            user = User(
                family_id=family_id,
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


def test_student_sees_the_note_on_that_date_only(world, login, page_as):
    w = world
    today = date.today()
    login(w.smith)
    with mock.patch.object(CurrentUser, "get_today", return_value=today):
        work = AssignmentService.create_assignment(
            subject_id=w.art,
            title="Daily Math",
            student_ids=[w.bob],
            due_date=today,
            assignment_type="Recurring",
            recurrence_pattern="Every Day",
            end_date=today + timedelta(days=3),
        )
    AssignmentService.set_occurrence_note(work.id, today, [w.bob], "Chapter 3 today")
    mock.patch.stopall()

    at = page_as("Student_Dashboard", w.smith, "Student", w.bob).run()

    assert not at.exception
    assert [i.value for i in at.info if "Chapter 3" in i.value] == ["Chapter 3 today"]


def test_student_sees_the_assignments_description(world, login, page_as):
    w = world
    today = date.today()
    login(w.smith)
    with mock.patch.object(CurrentUser, "get_today", return_value=today):
        AssignmentService.create_assignment(
            subject_id=w.art,
            title="Daily Math",
            student_ids=[w.bob],
            description="Work through the next lesson",
            due_date=today,
        )
    mock.patch.stopall()

    at = page_as("Student_Dashboard", w.smith, "Student", w.bob).run()

    assert not at.exception
    assert any("Work through the next lesson" in c.value for c in at.caption)


def test_parent_saves_a_note_from_the_assignments_page(world, login, page_as):
    # A dialog's second click needs the browser, so the clicks are stood in for.
    w = world
    today = date.today()
    login(w.smith)
    with mock.patch.object(CurrentUser, "get_today", return_value=today):
        work = AssignmentService.create_assignment(
            subject_id=w.art,
            title="Daily Math",
            student_ids=[w.bob],
            due_date=today,
            assignment_type="Recurring",
            recurrence_pattern="Every Day",
            end_date=today + timedelta(days=3),
        )
    mock.patch.stopall()

    wanted = {f"note_{work.id}", "💾 Save Note"}

    def click(label, *args, key=None, **kwargs):
        for name in (key, label):
            if name in wanted:
                wanted.remove(name)
                return True
        return False

    real_text_area = st.text_area

    def type_note(label, *args, **kwargs):
        return "Chapter 3" if label == "Note" else real_text_area(label, *args, **kwargs)

    with (
        mock.patch.object(st, "dialog", lambda title: lambda fn: fn),
        mock.patch.object(st, "button", click),
        mock.patch.object(st, "text_area", type_note),
    ):
        at = page_as("Assignments", w.smith, "Parent").run()

    assert not at.exception
    assert not wanted
    assert notes_by_key(work.id)[(w.bob, today)] == "Chapter 3"
