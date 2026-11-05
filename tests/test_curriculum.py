"""A curriculum lays out one lesson per school day, for each student."""
from datetime import date, datetime
from pathlib import Path
from unittest import mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from database.db import SessionLocal
from database.models import Assignment, AssignmentOccurrence, User
from services.assignment_service import AssignmentService
from services.auth_service import AuthService
from services.dashboard_service import DashboardService
from services.occurrence_service import OccurrenceService
from services.session_service import SessionService

ROOT = Path(__file__).resolve().parent.parent

MON_TO_THU = "Mon,Tue,Wed,Thu"

# Monday.
MONDAY = date(2026, 11, 2)
TUESDAY = date(2026, 11, 3)
WEDNESDAY = date(2026, 11, 4)
THURSDAY = date(2026, 11, 5)
NEXT_MONDAY = date(2026, 11, 9)
NEXT_TUESDAY = date(2026, 11, 10)
NEXT_WEDNESDAY = date(2026, 11, 11)


@pytest.fixture
def parent(smith_parent):
    with mock.patch.object(AuthService, "get_today", return_value=MONDAY):
        yield smith_parent


def create(w, lessons=5, days=MON_TO_THU, start=MONDAY, students=None):
    return AssignmentService.create_assignment(
        subject_id=w.math,
        title="Saxon Math",
        student_ids=[w.ann, w.bob] if students is None else students,
        due_date=start,
        assignment_type="Curriculum",
        recurrence_pattern=days,
        lesson_count=lessons,
    )


def edit(w, work, lessons=5, days=MON_TO_THU, start=MONDAY, students=None, title="Saxon Math"):
    return AssignmentService.update_assignment(
        assignment_id=work.id,
        title=title,
        description=None,
        due_date=start,
        subject_id=w.math,
        student_ids=[w.ann, w.bob] if students is None else students,
        assignment_type="Curriculum",
        recurrence_pattern=days,
        lesson_count=lessons,
    )


def lessons_of(work, student_id):
    """Returns {lesson number: date} for one student."""
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


def row_of(work, student_id, lesson):
    db = SessionLocal()
    try:
        return (
            db.query(AssignmentOccurrence)
            .filter_by(assignment_id=work.id, student_id=student_id, lesson_number=lesson)
            .one()
        )
    finally:
        db.close()


# ----- Laying out the dates -----


def test_lessons_land_on_school_days_in_order():
    assert OccurrenceService.lesson_dates(MON_TO_THU, WEDNESDAY, 4) == [
        WEDNESDAY,
        THURSDAY,
        NEXT_MONDAY,
        NEXT_TUESDAY,
    ]


def test_lessons_skip_dates_already_taken():
    assert OccurrenceService.lesson_dates(
        MON_TO_THU, MONDAY, 2, {TUESDAY}
    ) == [MONDAY, WEDNESDAY]


def test_school_days_are_saved_in_weekday_order():
    assert OccurrenceService.school_days_value(["Thu", "Mon", "Tue"]) == "Mon,Tue,Thu"


@pytest.mark.parametrize(
    "days, lessons, expected",
    [
        (MON_TO_THU, None, "how many lessons"),
        (MON_TO_THU, 0, "how many lessons"),
        ("", 10, "school day"),
        ("Someday", 10, "school day"),
        (MON_TO_THU, 100000, "two years"),
        ("Mon", 200, "two years"),
    ],
)
def test_a_bad_curriculum_says_whats_wrong(days, lessons, expected):
    error = OccurrenceService.schedule_error(
        "Curriculum", days, MONDAY, lesson_count=lessons
    )

    assert expected in error


def test_a_good_curriculum_has_no_error():
    assert (
        OccurrenceService.schedule_error(
            "Curriculum", MON_TO_THU, MONDAY, lesson_count=120
        )
        is None
    )


# ----- Creating -----


def test_creating_lays_out_lessons_for_each_student(parent):
    work = create(parent)

    expected = {
        1: MONDAY,
        2: TUESDAY,
        3: WEDNESDAY,
        4: THURSDAY,
        5: NEXT_MONDAY,
    }
    assert lessons_of(work, parent.ann) == expected
    assert lessons_of(work, parent.bob) == expected


def test_creating_saves_the_school_days_and_no_end_date(parent, fetch):
    work = create(parent, days="Thu,Mon")

    saved = fetch(Assignment, work.id)
    assert saved.recurrence_pattern == "Mon,Thu"
    assert saved.end_date is None


def test_a_bad_curriculum_creates_nothing(parent, fetch):
    assert create(parent, days="") is None
    assert create(parent, lessons=0) is None


def test_one_family_cant_use_anothers_subject_or_student(parent):
    assert (
        AssignmentService.create_assignment(
            subject_id=parent.jones_subject,
            title="Saxon Math",
            student_ids=[parent.ann],
            due_date=MONDAY,
            assignment_type="Curriculum",
            recurrence_pattern=MON_TO_THU,
            lesson_count=3,
        )
        is None
    )
    assert create(parent, students=[parent.jones_kid]) is None


def test_one_family_cant_edit_anothers_curriculum(parent, login):
    work = create(parent)

    login(parent.jones)

    assert edit(parent, work, title="Taken") is None

    login(parent.smith)
    assert lessons_of(work, parent.ann)[1] == MONDAY


# ----- Editing -----


def test_changing_the_title_leaves_moved_lessons_alone(parent, fetch):
    work = create(parent)
    touch(work, parent.ann, 3, occurrence_date=NEXT_WEDNESDAY)

    assert edit(parent, work, title="New title")

    assert fetch(Assignment, work.id).title == "New title"
    assert lessons_of(work, parent.ann)[3] == NEXT_WEDNESDAY


def test_changing_school_days_moves_lessons_not_started(parent):
    work = create(parent, lessons=3)

    assert edit(parent, work, lessons=3, days="Mon,Wed")

    assert lessons_of(work, parent.ann) == {
        1: MONDAY,
        2: WEDNESDAY,
        3: NEXT_MONDAY,
    }


def test_moving_lessons_onto_each_others_dates_works(parent):
    """Lessons shift one date along, so each new date is held by another row."""
    work = create(parent, lessons=3)

    assert edit(parent, work, lessons=3, start=TUESDAY)

    assert lessons_of(work, parent.ann) == {
        1: TUESDAY,
        2: WEDNESDAY,
        3: THURSDAY,
    }


def test_moving_start_date_keeps_started_lessons_and_notes(parent):
    work = create(parent, lessons=3)
    done_at = datetime(2026, 11, 2, 9, 0)
    touch(work, parent.ann, 1, status="Complete", completed_at=done_at)
    touch(work, parent.ann, 2, notes="Bring a ruler")

    assert edit(parent, work, lessons=3, start=NEXT_MONDAY)

    assert lessons_of(work, parent.ann) == {
        1: MONDAY,
        2: NEXT_MONDAY,
        3: NEXT_TUESDAY,
    }
    assert row_of(work, parent.ann, 1).completed_at == done_at
    assert row_of(work, parent.ann, 2).notes == "Bring a ruler"


def test_past_lessons_not_done_stay_put_when_rescheduling(parent):
    work = create(parent, lessons=3)

    with mock.patch.object(AuthService, "get_today", return_value=TUESDAY):
        assert edit(parent, work, lessons=3, days="Tue,Thu")

    assert lessons_of(work, parent.ann) == {
        1: MONDAY,
        2: TUESDAY,
        3: THURSDAY,
    }


def test_each_student_is_rescheduled_around_their_own_work(parent):
    work = create(parent, lessons=2)
    touch(work, parent.ann, 2, status="Complete")

    assert edit(parent, work, lessons=2, start=WEDNESDAY)

    assert lessons_of(work, parent.ann) == {1: WEDNESDAY, 2: TUESDAY}
    assert lessons_of(work, parent.bob) == {1: WEDNESDAY, 2: THURSDAY}


def test_more_lessons_go_after_each_students_last_one(parent):
    work = create(parent, lessons=2)
    touch(work, parent.ann, 2, occurrence_date=NEXT_MONDAY)

    assert edit(parent, work, lessons=3)

    assert lessons_of(work, parent.ann)[3] == NEXT_TUESDAY
    assert lessons_of(work, parent.bob)[3] == WEDNESDAY


def test_fewer_lessons_only_removes_untouched_ones(parent):
    work = create(parent, lessons=4)
    touch(work, parent.ann, 4, status="Complete")

    assert edit(parent, work, lessons=2)

    assert sorted(lessons_of(work, parent.ann)) == [1, 2, 4]
    assert sorted(lessons_of(work, parent.bob)) == [1, 2]


def test_a_student_added_later_gets_every_lesson_from_today(parent):
    work = create(parent, lessons=2, students=[parent.ann])

    with mock.patch.object(AuthService, "get_today", return_value=WEDNESDAY):
        assert edit(parent, work, lessons=2, students=[parent.ann, parent.bob])

    assert lessons_of(work, parent.bob) == {1: WEDNESDAY, 2: THURSDAY}


def test_a_removed_student_keeps_only_touched_lessons(parent):
    work = create(parent, lessons=2)
    touch(work, parent.bob, 1, status="Complete")

    assert edit(parent, work, lessons=2, students=[parent.ann])

    assert sorted(lessons_of(work, parent.bob)) == [1]


def test_other_work_cant_become_a_curriculum_or_the_reverse(parent):
    work = create(parent)

    assert (
        AssignmentService.update_assignment(
            assignment_id=work.id,
            title="Saxon Math",
            description=None,
            due_date=MONDAY,
            subject_id=parent.math,
            student_ids=[parent.ann],
            assignment_type="One Time",
            recurrence_pattern=None,
        )
        is None
    )

    assert (
        AssignmentService.update_assignment(
            assignment_id=parent.essay,
            title="Essay",
            description=None,
            due_date=MONDAY,
            subject_id=parent.art,
            student_ids=[parent.ann],
            assignment_type="Curriculum",
            recurrence_pattern=MON_TO_THU,
            lesson_count=3,
        )
        is None
    )


# ----- Reading -----


def test_a_lesson_is_named_by_number(parent):
    work = create(parent, lessons=1, students=[parent.ann])
    row = row_of(work, parent.ann, 1)
    row.assignment = work

    assert OccurrenceService.work_title(row) == "Saxon Math: Lesson 1"


def test_other_work_keeps_its_plain_title():
    row = mock.Mock(lesson_number=None)
    row.assignment.title = "Essay"

    assert OccurrenceService.work_title(row) == "Essay"


def test_unfinished_lessons_are_overdue_and_only_the_next_is_upcoming(parent):
    work = create(parent, lessons=4, students=[parent.ann])

    db = SessionLocal()
    try:
        rows = (
            db.query(AssignmentOccurrence)
            .filter_by(assignment_id=work.id)
            .all()
        )
        for row in rows:
            row.assignment
        groups = OccurrenceService.group_for_student(rows, TUESDAY)
    finally:
        db.close()

    assert [row.lesson_number for row in groups["overdue"]] == [1]
    assert [row.lesson_number for row in groups["today"]] == [2]
    assert [row.lesson_number for row in groups["upcoming"]] == [3]
    assert groups["missed"] == []


def test_parent_dashboard_names_a_student_once_for_many_late_lessons(parent):
    create(parent, lessons=3, students=[parent.ann])

    with mock.patch.object(AuthService, "get_today", return_value=NEXT_MONDAY):
        data = DashboardService.get_dashboard_data()

    late = [
        entry
        for entry in data["overdue_assignments"]
        if entry["assignment"].title == "Saxon Math"
    ]
    assert late[0]["student_names"] == ["Ann"]


def test_lesson_count_and_finish_come_from_the_rows(parent):
    work = create(parent, lessons=3)
    touch(work, parent.bob, 3, occurrence_date=NEXT_WEDNESDAY)

    loaded = AssignmentService.get_assignment_by_id(work.id)

    assert OccurrenceService.lesson_count(loaded) == 3
    assert OccurrenceService.last_lesson_date(loaded) == NEXT_WEDNESDAY


# ----- The pages -----


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


def _labelled(widgets, label):
    return next(widget for widget in widgets if widget.label == label)


def test_form_shows_the_finish_date_and_creates_the_lessons(world, page_as):
    at = page_as("Assignments", world.smith, "Parent").run()

    at.selectbox(key="create_assignment_type").set_value("Curriculum").run()
    at.number_input(key="create_lesson_count").set_value(5).run()
    at.multiselect(key="create_school_days").set_value(["Mon", "Tue"]).run()
    at.date_input(key="create_curriculum_start").set_value(MONDAY).run()

    assert not at.exception
    assert any(
        "Lesson 5 lands on Monday, November 16, 2026" in box.value for box in at.info
    )

    _labelled(at.text_input, "Assignment Title").set_value("Saxon Math")
    _labelled(at.multiselect, "Assign To").set_value(
        [
            student
            for student in _labelled(at.multiselect, "Assign To").options
            if student == "Ann"
        ]
    )
    next(b for b in at.button if b.label == "Create Assignment").click().run()

    assert not at.exception

    db = SessionLocal()
    try:
        work = db.query(Assignment).filter_by(title="Saxon Math").one()
        assert work.assignment_type == "Curriculum"
        assert work.recurrence_pattern == "Mon,Tue"
        assert (
            db.query(AssignmentOccurrence).filter_by(assignment_id=work.id).count()
            == 5
        )
    finally:
        db.close()

    assert any("5 lessons, Mon, Tue" in caption.value for caption in at.caption)


def test_student_page_shows_the_lesson_number(smith_parent, page_as):
    w = smith_parent
    today = date.today()

    with mock.patch.object(AuthService, "get_today", return_value=today):
        create(
            w,
            lessons=2,
            days="Mon,Tue,Wed,Thu,Fri,Sat,Sun",
            start=today,
            students=[w.bob],
        )
    mock.patch.stopall()

    at = page_as("Student_Dashboard", w.smith, "Student", student_id=w.bob).run()

    assert not at.exception
    assert any(box.label.startswith("Saxon Math: Lesson 1") for box in at.checkbox)


def test_edit_dialog_shows_the_schedule_and_saves_changes(smith_parent, page_as):
    w = smith_parent

    with mock.patch.object(AuthService, "get_today", return_value=MONDAY):
        work = create(w, lessons=3, students=[w.ann])
    mock.patch.stopall()

    at = page_as("Assignments", w.smith, "Parent").run()
    at.button(key=f"edit_{work.id}").click().run()

    assert not at.exception
    assert _labelled(at.number_input, "Number of Lessons").value == 3
    assert _labelled(at.multiselect, "School Days").value == MON_TO_THU.split(",")
    # Only the create form has one, since a curriculum stays a curriculum.
    assert [box.label for box in at.selectbox].count("Assignment Type") == 1


def test_edit_dialog_saves_a_new_lesson_count(smith_parent, page_as):
    # A dialog's second click needs the browser, so the clicks are stood in for.
    w = smith_parent

    with mock.patch.object(AuthService, "get_today", return_value=MONDAY):
        work = create(w, lessons=3, students=[w.ann])
    mock.patch.stopall()

    wanted = {f"edit_{work.id}", "💾 Save Changes"}

    def click(label, *args, key=None, **kwargs):
        for name in (key, label):
            if name in wanted:
                wanted.remove(name)
                return True
        return False

    with (
        mock.patch.object(st, "dialog", lambda title: lambda fn: fn),
        mock.patch.object(st, "button", click),
        mock.patch.object(st, "number_input", lambda *args, **kwargs: 4),
    ):
        at = page_as("Assignments", w.smith, "Parent").run()

    assert not at.exception
    assert not wanted
    assert sorted(lessons_of(work, w.ann)) == [1, 2, 3, 4]
