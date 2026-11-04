"""Saving an assignment keeps its occurrences right, and keeps people's work."""
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from database.db import SessionLocal
from database.models import Assignment, AssignmentOccurrence, StudentAssignment, User
from services.assignment_service import AssignmentService
from services.auth_service import AuthService
from services.occurrence_service import OccurrenceService
from services.session_service import SessionService
from services.student_service import StudentService

ROOT = Path(__file__).resolve().parent.parent

# Wednesday.
TODAY = date(2026, 11, 4)
LAST_WEEK = date(2026, 10, 28)
NEXT_WEEK = date(2026, 11, 11)
TWO_WEEKS = date(2026, 11, 18)
THREE_WEEKS = date(2026, 11, 25)


@pytest.fixture
def parent(smith_parent):
    with mock.patch.object(AuthService, "get_today", return_value=TODAY):
        yield smith_parent


def rows_for(assignment_id, student_id=None):
    """Returns {(student, date): row} for an assignment."""
    db = SessionLocal()
    try:
        query = db.query(AssignmentOccurrence).filter(
            AssignmentOccurrence.assignment_id == assignment_id
        )
        if student_id:
            query = query.filter(AssignmentOccurrence.student_id == student_id)
        return {(row.student_id, row.occurrence_date): row for row in query}
    finally:
        db.close()


def dates_for(assignment_id, student_id):
    return sorted(day for (_, day) in rows_for(assignment_id, student_id))


def touch(assignment_id, student_id, day, **fields):
    db = SessionLocal()
    try:
        row = (
            db.query(AssignmentOccurrence)
            .filter_by(assignment_id=assignment_id, student_id=student_id, occurrence_date=day)
            .one()
        )
        for name, value in fields.items():
            setattr(row, name, value)
        db.commit()
    finally:
        db.close()


def create(w, start=TODAY, end=THREE_WEEKS, students=None, kind="Recurring", pattern="Weekly"):
    return AssignmentService.create_assignment(
        subject_id=w.art,
        title="Work",
        student_ids=[w.ann, w.bob] if students is None else students,
        due_date=start,
        assignment_type=kind,
        recurrence_pattern=pattern,
        end_date=end,
    )


def edit(w, assignment, start=TODAY, end=THREE_WEEKS, students=None, kind="Recurring", pattern="Weekly"):
    return AssignmentService.update_assignment(
        assignment_id=assignment.id,
        title="Work",
        description=None,
        due_date=start,
        subject_id=w.art,
        student_ids=[w.ann, w.bob] if students is None else students,
        assignment_type=kind,
        recurrence_pattern=pattern,
        end_date=end,
    )


# ----- Creating -----


def test_one_time_work_gets_one_row_per_student(parent):
    w = parent
    work = create(w, kind="One Time", pattern=None, end=None)

    assert set(rows_for(work.id)) == {(w.ann, TODAY), (w.bob, TODAY)}


def test_recurring_work_gets_a_row_per_student_per_date(parent):
    w = parent
    work = create(w)

    assert len(rows_for(work.id)) == 8
    assert dates_for(work.id, w.ann) == [TODAY, NEXT_WEEK, TWO_WEEKS, THREE_WEEKS]


def test_new_rows_start_untouched(parent):
    w = parent
    work = create(w)

    assert all(OccurrenceService.is_untouched(row) for row in rows_for(work.id).values())


def test_a_recurring_start_in_the_past_gets_its_past_dates(parent):
    w = parent
    work = create(w, start=LAST_WEEK, end=NEXT_WEEK, students=[w.ann])

    assert dates_for(work.id, w.ann) == [LAST_WEEK, TODAY, NEXT_WEEK]


def test_one_time_work_ignores_a_stray_pattern_and_end_date(parent, fetch):
    w = parent
    work = create(w, kind="One Time", pattern="Every Day", end=THREE_WEEKS, students=[w.ann])

    saved = fetch(Assignment, work.id)
    assert saved.recurrence_pattern is None
    assert saved.end_date is None
    assert dates_for(work.id, w.ann) == [TODAY]


def test_create_saves_everything_in_one_commit(parent):
    w = parent
    with mock.patch(
        "services.occurrence_service.OccurrenceService.sync", side_effect=RuntimeError
    ):
        with pytest.raises(RuntimeError):
            create(w)

    db = SessionLocal()
    try:
        assert db.query(Assignment).filter_by(title="Work").count() == 0
    finally:
        db.close()


@pytest.mark.parametrize(
    "fields",
    [
        dict(start=None),
        dict(end=None),
        dict(end=LAST_WEEK),
        dict(end=date(2029, 1, 1)),
        dict(pattern=None),
        dict(start=TODAY, end=date(2026, 11, 5), pattern="Every Monday"),
    ],
    ids=["no-start", "no-end", "end-before-start", "too-far", "no-pattern", "no-dates"],
)
def test_a_bad_schedule_saves_nothing(parent, fields):
    work = create(parent, **fields)

    assert work is None
    db = SessionLocal()
    try:
        assert db.query(Assignment).filter_by(title="Work").count() == 0
    finally:
        db.close()


def test_a_one_time_assignment_needs_a_due_date(parent):
    assert create(parent, start=None, kind="One Time", pattern=None, end=None) is None


# ----- Editing recurring work -----


def test_ending_earlier_removes_untouched_future_dates(parent):
    w = parent
    work = create(w)

    edit(w, work, end=NEXT_WEEK)

    assert dates_for(work.id, w.ann) == [TODAY, NEXT_WEEK]


def test_ending_later_adds_dates(parent):
    w = parent
    work = create(w, end=NEXT_WEEK)

    edit(w, work, end=THREE_WEEKS)

    assert dates_for(work.id, w.ann) == [TODAY, NEXT_WEEK, TWO_WEEKS, THREE_WEEKS]


@pytest.mark.parametrize(
    "fields",
    [
        dict(status="Complete", completed_at=datetime(2026, 11, 18, 9, 0)),
        dict(notes="Chapter 3"),
        dict(score=95),
    ],
    ids=["completed", "note", "score"],
)
def test_ending_earlier_keeps_a_touched_row(parent, fields):
    w = parent
    work = create(w)
    touch(work.id, w.ann, TWO_WEEKS, **fields)

    edit(w, work, end=NEXT_WEEK)

    assert TWO_WEEKS in dates_for(work.id, w.ann)
    assert THREE_WEEKS not in dates_for(work.id, w.ann)
    assert TWO_WEEKS not in dates_for(work.id, w.bob)


def test_past_rows_stay_when_the_schedule_changes(parent):
    w = parent
    work = create(w, start=LAST_WEEK, students=[w.ann])

    edit(w, work, start=TODAY, pattern="Every Friday", students=[w.ann])

    assert LAST_WEEK in dates_for(work.id, w.ann)


def test_changing_the_pattern_only_changes_today_and_later(parent):
    w = parent
    work = create(w, start=LAST_WEEK, end=TWO_WEEKS, students=[w.ann])
    friday = date(2026, 11, 6)
    next_friday = date(2026, 11, 13)

    edit(w, work, start=LAST_WEEK, end=TWO_WEEKS, pattern="Every Friday", students=[w.ann])

    assert dates_for(work.id, w.ann) == [LAST_WEEK, friday, next_friday]


def test_moving_the_start_earlier_doesnt_add_past_dates(parent):
    w = parent
    work = create(w, students=[w.ann])

    edit(w, work, start=LAST_WEEK, students=[w.ann])

    assert LAST_WEEK not in dates_for(work.id, w.ann)


def test_an_unchanged_edit_keeps_the_same_rows(parent):
    w = parent
    work = create(w)
    before = {key: row.id for key, row in rows_for(work.id).items()}

    edit(w, work)

    assert {key: row.id for key, row in rows_for(work.id).items()} == before


# ----- Changing students -----


def test_removing_a_student_removes_only_their_untouched_future_rows(parent):
    w = parent
    work = create(w, start=LAST_WEEK)
    touch(work.id, w.bob, TWO_WEEKS, notes="Keep me")

    edit(w, work, start=LAST_WEEK, students=[w.ann])

    assert dates_for(work.id, w.bob) == [LAST_WEEK, TWO_WEEKS]
    assert len(dates_for(work.id, w.ann)) == 5


def test_adding_a_student_gives_them_today_and_later(parent):
    w = parent
    work = create(w, start=LAST_WEEK, students=[w.ann])

    edit(w, work, start=LAST_WEEK, students=[w.ann, w.bob])

    assert dates_for(work.id, w.bob) == [TODAY, NEXT_WEEK, TWO_WEEKS, THREE_WEEKS]


def test_an_archived_students_link_still_follows_a_moved_due_date(parent):
    w = parent
    # The Essay link for Gone stays on edits, because the form doesn't offer them.
    db = SessionLocal()
    try:
        db.add(
            AssignmentOccurrence(
                assignment_id=w.essay, student_id=w.gone, occurrence_date=date(2026, 12, 1)
            )
        )
        db.commit()
    finally:
        db.close()

    AssignmentService.update_assignment(
        assignment_id=w.essay,
        title="Essay",
        description=None,
        due_date=date(2026, 12, 2),
        subject_id=w.art,
        student_ids=[w.ann, w.bob],
        assignment_type="One Time",
        recurrence_pattern=None,
    )

    assert dates_for(w.essay, w.gone) == [date(2026, 12, 2)]


# ----- One-time work and changing type -----


def test_moving_a_due_date_moves_the_row_and_keeps_its_progress(parent):
    w = parent
    work = create(w, start=NEXT_WEEK, kind="One Time", pattern=None, end=None, students=[w.ann])
    touch(work.id, w.ann, NEXT_WEEK, status="Complete", notes="Done early")
    before = rows_for(work.id)[(w.ann, NEXT_WEEK)].id

    edit(w, work, start=LAST_WEEK, kind="One Time", pattern=None, end=None, students=[w.ann])

    row = rows_for(work.id)[(w.ann, LAST_WEEK)]
    assert row.id == before
    assert row.status == "Complete"
    assert row.notes == "Done early"
    assert len(rows_for(work.id)) == 1


def test_adding_a_student_to_overdue_one_time_work_gives_them_the_date(parent):
    w = parent
    work = create(w, start=LAST_WEEK, kind="One Time", pattern=None, end=None, students=[w.ann])

    edit(w, work, start=LAST_WEEK, kind="One Time", pattern=None, end=None)

    assert dates_for(work.id, w.bob) == [LAST_WEEK]


def test_recurring_to_one_time_keeps_only_touched_rows_and_the_due_date(parent):
    w = parent
    work = create(w, start=LAST_WEEK, students=[w.ann])
    touch(work.id, w.ann, TODAY, status="Complete")

    edit(w, work, start=TWO_WEEKS, kind="One Time", pattern=None, end=None, students=[w.ann])

    assert dates_for(work.id, w.ann) == [TODAY, TWO_WEEKS]


def test_one_time_to_recurring_keeps_the_row_and_adds_dates(parent):
    w = parent
    work = create(w, kind="One Time", pattern=None, end=None, students=[w.ann])
    touch(work.id, w.ann, TODAY, status="Complete")

    edit(w, work, end=NEXT_WEEK, students=[w.ann])

    rows = rows_for(work.id)
    assert set(day for (_, day) in rows) == {TODAY, NEXT_WEEK}
    assert rows[(w.ann, TODAY)].status == "Complete"


# ----- Other families and refused edits -----


def test_refused_edit_changes_no_rows(parent):
    w = parent
    work = create(w, students=[w.ann])
    before = dates_for(work.id, w.ann)

    assert edit(w, work, students=[w.jones_kid]) is None

    assert dates_for(work.id, w.ann) == before


def test_another_familys_assignment_cant_be_changed(parent):
    w = parent
    db = SessionLocal()
    try:
        db.add(
            AssignmentOccurrence(
                assignment_id=w.jones_work, student_id=w.jones_kid, occurrence_date=TWO_WEEKS
            )
        )
        db.commit()
    finally:
        db.close()

    updated = AssignmentService.update_assignment(
        assignment_id=w.jones_work,
        title="Taken",
        description=None,
        due_date=TODAY,
        subject_id=w.art,
        student_ids=[w.ann],
        assignment_type="One Time",
        recurrence_pattern=None,
    )

    assert updated is None
    assert dates_for(w.jones_work, w.jones_kid) == [TWO_WEEKS]
    assert dates_for(w.jones_work, w.ann) == []


# ----- Checking work off -----


def _link_id(assignment_id, student_id):
    db = SessionLocal()
    try:
        return (
            db.query(StudentAssignment)
            .filter_by(assignment_id=assignment_id, student_id=student_id)
            .one()
            .id
        )
    finally:
        db.close()


def test_checking_off_one_time_work_updates_its_occurrence(parent):
    w = parent
    work = create(w, kind="One Time", pattern=None, end=None, students=[w.ann])

    StudentService.update_assignment_status(_link_id(work.id, w.ann), True)

    row = rows_for(work.id)[(w.ann, TODAY)]
    assert row.status == "Complete"
    assert row.completed_at is not None

    StudentService.update_assignment_status(_link_id(work.id, w.ann), False)

    row = rows_for(work.id)[(w.ann, TODAY)]
    assert row.status == "Not Started"
    assert row.completed_at is None


def test_checking_off_only_changes_that_student(parent):
    w = parent
    work = create(w, kind="One Time", pattern=None, end=None)

    StudentService.update_assignment_status(_link_id(work.id, w.ann), True)

    assert rows_for(work.id)[(w.bob, TODAY)].status == "Not Started"


def test_checking_off_recurring_work_leaves_its_dates_alone(parent):
    w = parent
    work = create(w, students=[w.ann])

    StudentService.update_assignment_status(_link_id(work.id, w.ann), True)

    assert all(row.status == "Not Started" for row in rows_for(work.id).values())


# ----- The Assignments page -----


@pytest.fixture
def assignments_page(world):
    db = SessionLocal()
    try:
        parent = User(
            family_id=world.smith,
            email="pat@smith.test",
            auth_user_id="00000000-0000-0000-0000-00000000000a",
            role="Parent",
        )
        db.add(parent)
        db.commit()
        parent_id = parent.id
    finally:
        db.close()

    page = next((ROOT / "pages").glob("*_Assignments.py"))

    with (
        mock.patch.object(SessionService, "sync_browser", return_value=None),
        mock.patch.object(st, "page_link"),
        mock.patch.object(st, "switch_page"),
    ):
        at = AppTest.from_file(str(page), default_timeout=30)
        at.session_state["current_user_id"] = parent_id
        at.run()
        at.selectbox(key="create_assignment_type").set_value("Recurring").run()
        yield at


def _labelled(widgets, label):
    return next(widget for widget in widgets if widget.label == label)


def _create_button(at):
    return next(button for button in at.button if button.label == "Create Assignment")


def test_page_shows_recurring_fields_with_a_year_end_default(assignments_page):
    at = assignments_page

    assert not at.exception
    assert "Every Day" in _labelled(at.selectbox, "Frequency").options
    assert "Daily" not in _labelled(at.selectbox, "Frequency").options
    start = _labelled(at.date_input, "Starts On").value
    assert _labelled(at.date_input, "Ends On").value == date(start.year, 12, 31)


def test_page_creates_recurring_work_with_its_dates(assignments_page, world):
    at = assignments_page
    start = _labelled(at.date_input, "Starts On").value

    _labelled(at.text_input, "Assignment Title").set_value("Daily math")
    _labelled(at.multiselect, "Assign To").select(
        next(o for o in _labelled(at.multiselect, "Assign To").options if "Ann" in str(o))
    )
    _labelled(at.date_input, "Ends On").set_value(start + timedelta(days=2))
    _create_button(at).click().run()

    assert not at.exception
    db = SessionLocal()
    try:
        work = db.query(Assignment).filter_by(title="Daily math").one()
        assert work.end_date == start + timedelta(days=2)
        assert work.recurrence_pattern == "Every Day"
    finally:
        db.close()
    assert len(rows_for(work.id, world.ann)) == 3


def test_page_explains_a_bad_end_date_and_saves_nothing(assignments_page):
    at = assignments_page
    start = _labelled(at.date_input, "Starts On").value

    _labelled(at.text_input, "Assignment Title").set_value("Backwards")
    _labelled(at.date_input, "Ends On").set_value(start - timedelta(days=1))
    _create_button(at).click().run()

    assert "can't be before the start date" in " ".join(e.value for e in at.error)
    db = SessionLocal()
    try:
        assert db.query(Assignment).filter_by(title="Backwards").count() == 0
    finally:
        db.close()
