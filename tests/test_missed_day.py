"""Missed-day recovery moves one student's unfinished lessons forward."""
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from database.db import SessionLocal
from database.models import AssignmentOccurrence, User, UserRole
from services.assignment_service import AssignmentService
from services.auth_service import AuthService
from services.session_service import SessionService

ROOT = Path(__file__).resolve().parent.parent

MON_TO_THU = "Mon,Tue,Wed,Thu"

MONDAY = date(2026, 11, 2)
TUESDAY = date(2026, 11, 3)
WEDNESDAY = date(2026, 11, 4)
THURSDAY = date(2026, 11, 5)
FRIDAY = date(2026, 11, 6)
NEXT_MONDAY = date(2026, 11, 9)
NEXT_TUESDAY = date(2026, 11, 10)


@pytest.fixture
def parent(smith_parent):
    with mock.patch.object(AuthService, "get_today", return_value=WEDNESDAY):
        yield smith_parent


def create(w, lessons=4, start=MONDAY, students=None, title="Saxon Math"):
    return AssignmentService.create_assignment(
        subject_id=w.math,
        title=title,
        student_ids=[w.ann, w.bob] if students is None else students,
        due_date=start,
        assignment_type="Curriculum",
        recurrence_pattern=MON_TO_THU,
        lesson_count=lessons,
    )


def lessons_of(work, student_id):
    db = SessionLocal()
    try:
        return {
            row.lesson_number: row.occurrence_date
            for row in db.query(AssignmentOccurrence).filter_by(
                assignment_id=work.id, student_id=student_id
            )
        }
    finally:
        db.close()


def touch(work, student_id, lesson, **fields):
    db = SessionLocal()
    try:
        row = (
            db.query(AssignmentOccurrence)
            .filter_by(assignment_id=work.id, student_id=student_id, lesson_number=lesson)
            .one()
        )
        for name, value in fields.items():
            setattr(row, name, value)
        db.commit()
    finally:
        db.close()


def test_unfinished_lessons_pick_up_on_the_chosen_day(parent):
    work = create(parent)
    touch(work, parent.ann, 1, status="Complete")

    # Ann did Monday's lesson and missed Tuesday's, so 2 moves to today.
    assert AssignmentService.shift_lessons([parent.ann], WEDNESDAY) == 3

    assert lessons_of(work, parent.ann) == {
        1: MONDAY,
        2: WEDNESDAY,
        3: THURSDAY,
        4: NEXT_MONDAY,
    }


def test_only_the_chosen_student_moves(parent):
    work = create(parent)

    assert AssignmentService.shift_lessons([parent.ann], WEDNESDAY)

    assert lessons_of(work, parent.bob) == {
        1: MONDAY,
        2: TUESDAY,
        3: WEDNESDAY,
        4: THURSDAY,
    }


def test_a_sick_day_can_pick_up_tomorrow(parent):
    work = create(parent, start=WEDNESDAY, students=[parent.ann])

    assert AssignmentService.shift_lessons([parent.ann], THURSDAY) == 4

    assert lessons_of(work, parent.ann)[1] == THURSDAY


def test_picking_up_on_a_day_off_waits_for_the_next_school_day(parent):
    work = create(parent, students=[parent.ann])

    assert AssignmentService.shift_lessons([parent.ann], FRIDAY) == 4

    assert lessons_of(work, parent.ann)[1] == NEXT_MONDAY


def test_lessons_go_around_started_ones_and_keep_notes(parent):
    work = create(parent, students=[parent.ann])
    touch(work, parent.ann, 4, status="Complete")
    touch(work, parent.ann, 2, notes="Bring a ruler")

    AssignmentService.shift_lessons([parent.ann], WEDNESDAY)

    assert lessons_of(work, parent.ann) == {
        1: WEDNESDAY,
        2: NEXT_MONDAY,
        3: NEXT_TUESDAY,
        4: THURSDAY,
    }

    db = SessionLocal()
    try:
        row = (
            db.query(AssignmentOccurrence)
            .filter_by(assignment_id=work.id, lesson_number=2)
            .one()
        )
        assert row.notes == "Bring a ruler"
    finally:
        db.close()


def test_every_curriculum_for_the_student_moves_together(parent):
    math = create(parent, students=[parent.ann])
    reading = create(parent, students=[parent.ann], title="Reading")

    AssignmentService.shift_lessons([parent.ann], WEDNESDAY)

    assert lessons_of(math, parent.ann)[1] == WEDNESDAY
    assert lessons_of(reading, parent.ann)[1] == WEDNESDAY


def test_a_curriculum_that_hasnt_started_keeps_its_start_date(parent):
    work = create(parent, start=NEXT_MONDAY, lessons=2, students=[parent.ann])

    assert AssignmentService.shift_lessons([parent.ann], WEDNESDAY) == 0

    assert lessons_of(work, parent.ann) == {1: NEXT_MONDAY, 2: NEXT_TUESDAY}


def test_other_work_doesnt_move(parent):
    weekly = AssignmentService.create_assignment(
        subject_id=parent.math,
        title="Reading log",
        student_ids=[parent.ann],
        due_date=MONDAY,
        assignment_type="Recurring",
        recurrence_pattern="Every Day",
        end_date=THURSDAY,
    )

    assert AssignmentService.shift_lessons([parent.ann], WEDNESDAY) == 0

    db = SessionLocal()
    try:
        dates = {
            row.occurrence_date
            for row in db.query(AssignmentOccurrence).filter_by(assignment_id=weekly.id)
        }
    finally:
        db.close()

    assert MONDAY in dates


def test_archived_curricula_dont_move(parent):
    work = create(parent, students=[parent.ann])
    AssignmentService.archive_assignment(work.id)

    assert AssignmentService.shift_lessons([parent.ann], WEDNESDAY) == 0
    assert lessons_of(work, parent.ann)[1] == MONDAY


def test_a_student_no_longer_assigned_doesnt_move(parent):
    work = create(parent)
    touch(work, parent.bob, 1, notes="Kept")
    AssignmentService.update_assignment(
        assignment_id=work.id,
        title="Saxon Math",
        description=None,
        due_date=MONDAY,
        subject_id=parent.math,
        student_ids=[parent.ann],
        assignment_type="Curriculum",
        recurrence_pattern=MON_TO_THU,
        lesson_count=4,
    )

    assert AssignmentService.shift_lessons([parent.bob], WEDNESDAY) == 0
    assert lessons_of(work, parent.bob)[1] == MONDAY


def test_a_past_date_is_refused(parent):
    work = create(parent, students=[parent.ann])

    assert AssignmentService.shift_lessons([parent.ann], TUESDAY) is None
    assert lessons_of(work, parent.ann)[1] == MONDAY


def test_a_student_cant_shift_the_schedule(parent, login):
    work = create(parent, students=[parent.ann])

    login(parent.smith, role=UserRole.STUDENT, student_id=parent.ann)

    assert AssignmentService.shift_lessons([parent.ann], WEDNESDAY) is None
    assert AssignmentService.get_recovery_plan([parent.ann], WEDNESDAY) == []
    assert AssignmentService.get_students_behind(WEDNESDAY) == set()
    assert lessons_of(work, parent.ann)[1] == MONDAY


def test_one_family_cant_shift_or_see_anothers_lessons(parent, login):
    work = create(parent, students=[parent.ann])

    login(parent.jones)

    assert AssignmentService.get_recovery_plan([parent.ann], WEDNESDAY) == []
    assert AssignmentService.get_students_behind(WEDNESDAY) == set()
    assert AssignmentService.has_curriculum() is False
    assert AssignmentService.shift_lessons([parent.ann], WEDNESDAY) == 0
    assert lessons_of(work, parent.ann)[1] == MONDAY


def test_the_plan_shows_what_would_change_and_changes_nothing(parent):
    work = create(parent, students=[parent.ann])

    plan = AssignmentService.get_recovery_plan([parent.ann], WEDNESDAY)

    assert plan == [
        {
            "student_name": "Ann",
            "title": "Saxon Math",
            "next_lesson": 1,
            "next_date": WEDNESDAY,
            "old_finish": THURSDAY,
            "new_finish": NEXT_TUESDAY,
        }
    ]
    assert lessons_of(work, parent.ann)[1] == MONDAY


def test_students_behind_only_counts_late_unfinished_lessons(parent):
    work = create(parent)
    touch(work, parent.bob, 1, status="Complete")
    touch(work, parent.bob, 2, status="Complete")

    assert AssignmentService.get_students_behind(WEDNESDAY) == {parent.ann}


def test_shifting_clears_the_overdue_warning(parent):
    create(parent, students=[parent.ann])

    assert AssignmentService.get_students_behind(WEDNESDAY) == {parent.ann}

    AssignmentService.shift_lessons([parent.ann], WEDNESDAY)

    assert AssignmentService.get_students_behind(WEDNESDAY) == set()


# ----- The page -----


@pytest.fixture
def dashboard(world):
    db = SessionLocal()
    try:
        user = User(
            family_id=world.smith,
            email="pat@smith.test",
            auth_user_id="00000000-0000-0000-0000-00000000000a",
            role="Parent",
        )
        db.add(user)
        db.commit()
        user_id = user.id
    finally:
        db.close()

    def _open():
        at = AppTest.from_file(
            str(next((ROOT / "pages").glob("*_Parent_Dashboard.py"))),
            default_timeout=30,
        )
        at.session_state["current_user_id"] = user_id
        return at

    with (
        mock.patch.object(SessionService, "sync_browser", return_value=None),
        mock.patch.object(st, "page_link"),
        mock.patch.object(st, "switch_page"),
    ):
        yield _open


def test_button_only_shows_with_a_curriculum(world, dashboard):
    at = dashboard().run()

    assert not at.exception
    assert "🤒 Missed a Day?" not in [button.label for button in at.button]


def test_parent_shifts_from_the_dashboard(world, login, dashboard):
    # A dialog's second click needs the browser, so the clicks are stood in for.
    w = world
    today = date.today()
    start = today - timedelta(days=3)
    login(w.smith)
    with mock.patch.object(AuthService, "get_today", return_value=today):
        work = AssignmentService.create_assignment(
            subject_id=w.math,
            title="Saxon Math",
            student_ids=[w.ann],
            due_date=start,
            assignment_type="Curriculum",
            recurrence_pattern="Mon,Tue,Wed,Thu,Fri,Sat,Sun",
            lesson_count=4,
        )
    mock.patch.stopall()

    wanted = {"🤒 Missed a Day?", "Shift Schedule"}

    def click(label, *args, key=None, **kwargs):
        if label in wanted:
            wanted.remove(label)
            return True
        return False

    with (
        mock.patch.object(st, "dialog", lambda title: lambda fn: fn),
        mock.patch.object(st, "button", click),
    ):
        at = dashboard().run()

    assert not at.exception
    assert not wanted
    assert lessons_of(work, w.ann)[1] == today
