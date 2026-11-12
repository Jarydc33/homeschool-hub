"""Scores become grades per subject, overall, and per grading period."""
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from database.db import SessionLocal
from database.models import (
    Assignment,
    AssignmentOccurrence,
    GradingPeriod,
    Student,
    User,
    UserRole,
)
from services.assignment_service import AssignmentService
from services.current_user import CurrentUser
from services.grade_service import GradeService
from services.session_service import SessionService

ROOT = Path(__file__).resolve().parent.parent

TODAY = date(2026, 11, 5)
YESTERDAY = date(2026, 11, 4)


@pytest.fixture
def parent(smith_parent):
    with mock.patch.object(CurrentUser, "get_today", return_value=TODAY):
        yield smith_parent


def work(
    w,
    title="Test",
    subject=None,
    student=None,
    due=YESTERDAY,
    graded=True,
    done=False,
):
    """Creates one-time work, and returns (assignment, its one occurrence id)."""
    student = student or w.ann

    assignment = AssignmentService.create_assignment(
        subject_id=subject or w.math,
        title=title,
        student_ids=[student],
        due_date=due,
        graded=graded,
    )

    db = SessionLocal()
    try:
        row = (
            db.query(AssignmentOccurrence)
            .filter_by(assignment_id=assignment.id)
            .one()
        )
        if done:
            row.status = "Complete"
            db.commit()
        return assignment, row.id
    finally:
        db.close()


def graded(w, earned, total=100, **kwargs):
    assignment, row_id = work(w, **kwargs)
    assert GradeService.set_grade(row_id, earned, total)
    return assignment, row_id


def row_of(row_id):
    db = SessionLocal()
    try:
        return db.get(AssignmentOccurrence, row_id)
    finally:
        db.close()


def scored(percent_score, total=100, subject="Math", day=YESTERDAY):
    return SimpleNamespace(
        score=percent_score,
        points_possible=total,
        occurrence_date=day,
        assignment=SimpleNamespace(subject=SimpleNamespace(name=subject)),
    )


# ----- Working out grades -----


@pytest.mark.parametrize(
    "percent, letter",
    [
        (100, "A"),
        (90, "A"),
        (89.6, "A"),
        (89.4, "B"),
        (80, "B"),
        (79, "C"),
        (70, "C"),
        (69, "D"),
        (60, "D"),
        (59, "F"),
        (0, "F"),
        (110, "A"),
    ],
)
def test_letters(percent, letter):
    assert GradeService.letter(percent) == letter


def test_a_grade_reads_with_its_letter():
    assert GradeService.describe(91.6) == "92% (A)"


def test_each_item_counts_equally_in_a_subject():
    rows = [scored(18, 20), scored(10, 50)]

    # 90% and 20%, not 28 out of 70.
    assert GradeService.subject_percents(rows) == {"Math": 55}


def test_overall_averages_subjects_not_items():
    rows = [
        scored(100, subject="Art"),
        scored(50, subject="Math"),
        scored(50, subject="Math"),
        scored(50, subject="Math"),
    ]

    percents = GradeService.subject_percents(rows)

    assert GradeService.overall_percent(percents) == 75


def test_nothing_to_average_has_no_overall():
    assert GradeService.overall_percent({}) is None


def test_rows_in_a_period_include_both_ends():
    period = SimpleNamespace(
        start_date=date(2026, 9, 1), end_date=date(2026, 9, 30)
    )
    rows = [
        scored(1, day=date(2026, 8, 31)),
        scored(2, day=date(2026, 9, 1)),
        scored(3, day=date(2026, 9, 30)),
        scored(4, day=date(2026, 10, 1)),
    ]

    assert [r.score for r in GradeService.rows_in_period(rows, period)] == [2, 3]
    assert len(GradeService.rows_in_period(rows, None)) == 4


def test_comparison_lines_periods_up_by_subject():
    fall = SimpleNamespace(
        id=1, start_date=date(2026, 9, 1), end_date=date(2026, 12, 31)
    )
    spring = SimpleNamespace(
        id=2, start_date=date(2027, 1, 1), end_date=date(2027, 5, 31)
    )
    empty = SimpleNamespace(
        id=3, start_date=date(2027, 6, 1), end_date=date(2027, 8, 31)
    )
    rows = [
        scored(90, subject="Math", day=date(2026, 10, 1)),
        scored(70, subject="Art", day=date(2026, 10, 1)),
        scored(80, subject="Math", day=date(2027, 2, 1)),
    ]

    result = GradeService.comparison(rows, [fall, spring, empty])

    assert result["subjects"] == {
        "Art": {1: 70},
        "Math": {1: 90, 2: 80},
    }
    assert result["overall"] == {1: 80, 2: 80}


# ----- Entering grades -----


def test_a_grade_saves_and_doesnt_check_off_the_work(parent):
    _, row_id = work(parent)

    assert GradeService.set_grade(row_id, 18, 20)

    row = row_of(row_id)
    assert float(row.score) == 18
    assert float(row.points_possible) == 20
    assert row.status == "Not Started"
    assert row.completed_at is None


def test_saving_again_replaces_the_grade(parent):
    _, row_id = graded(parent, 18, 20)

    assert GradeService.set_grade(row_id, 19, 20)

    assert float(row_of(row_id).score) == 19


def test_clearing_removes_it_from_grades(parent):
    _, row_id = graded(parent, 18, 20)

    assert GradeService.clear_grade(row_id)

    assert row_of(row_id).score is None
    assert row_of(row_id).points_possible is None
    assert GradeService.get_graded_rows(parent.ann) == []


@pytest.mark.parametrize(
    "score, total, expected",
    [
        (None, 20, "enter"),
        (10, None, "enter"),
        (10, 0, "total"),
        (10, -5, "total"),
        (10, 10000, "total"),
        (-1, 20, "negative"),
        (41, 20, "too high"),
    ],
)
def test_bad_grades_say_whats_wrong_and_save_nothing(parent, score, total, expected):
    _, row_id = work(parent)

    assert expected in GradeService.grade_error(score, total)
    assert GradeService.set_grade(row_id, score, total) is None
    assert row_of(row_id).score is None


def test_extra_credit_is_allowed(parent):
    assert GradeService.grade_error(22, 20) is None
    assert GradeService.grade_error(0, 20) is None


def test_zero_is_a_real_grade_and_counts(parent):
    graded(parent, 100)
    graded(parent, 0)

    rows = GradeService.get_graded_rows(parent.ann)

    assert GradeService.subject_percents(rows) == {"Math": 50}


def test_blank_scores_never_count(parent):
    graded(parent, 100)
    work(parent, "Not graded yet")

    rows = GradeService.get_graded_rows(parent.ann)

    assert GradeService.subject_percents(rows) == {"Math": 100}


def test_ungraded_assignments_cant_be_graded(parent):
    _, row_id = work(parent, graded=False)

    assert GradeService.set_grade(row_id, 18, 20) is None


# ----- What counts -----


def test_archived_assignments_still_count(parent):
    assignment, _ = graded(parent, 80)

    AssignmentService.archive_assignment(assignment.id)

    assert GradeService.subject_percents(
        GradeService.get_graded_rows(parent.ann)
    ) == {"Math": 80}


def test_turning_grading_off_stops_counting_and_keeps_the_score(parent):
    assignment, row_id = graded(parent, 80)

    def set_graded(value):
        AssignmentService.update_assignment(
            assignment_id=assignment.id,
            title="Test",
            description=None,
            due_date=YESTERDAY,
            subject_id=parent.math,
            student_ids=[parent.ann],
            assignment_type="One Time",
            recurrence_pattern=None,
            graded=value,
        )

    set_graded(False)
    assert GradeService.get_graded_rows(parent.ann) == []
    assert float(row_of(row_id).score) == 80

    set_graded(True)
    assert len(GradeService.get_graded_rows(parent.ann)) == 1


def test_editing_without_saying_keeps_it_graded(parent, fetch):
    assignment, _ = work(parent)

    AssignmentService.update_assignment(
        assignment_id=assignment.id,
        title="New title",
        description=None,
        due_date=YESTERDAY,
        subject_id=parent.math,
        student_ids=[parent.ann],
        assignment_type="One Time",
        recurrence_pattern=None,
    )

    assert fetch(Assignment, assignment.id).graded is True


def test_a_scored_lesson_doesnt_move_in_missed_day_recovery(parent):
    assignment = AssignmentService.create_assignment(
        subject_id=parent.math,
        title="Saxon Math",
        student_ids=[parent.ann],
        due_date=date(2026, 11, 2),
        assignment_type="Curriculum",
        recurrence_pattern="Mon,Tue,Wed,Thu,Fri",
        lesson_count=2,
        graded=True,
    )

    db = SessionLocal()
    try:
        first = (
            db.query(AssignmentOccurrence)
            .filter_by(assignment_id=assignment.id, lesson_number=1)
            .one()
            .id
        )
    finally:
        db.close()

    GradeService.set_grade(first, 9, 10)
    AssignmentService.shift_lessons([parent.ann], TODAY)

    assert row_of(first).occurrence_date == date(2026, 11, 2)


# ----- What's waiting for a grade -----


def test_finished_work_with_no_score_is_waiting(parent):
    _, waiting = work(parent, "Waiting", done=True)
    work(parent, "Not done", due=date(2026, 8, 1))
    graded(parent, 90, title="Already graded", done=True)
    work(parent, "Ungraded", graded=False, done=True)

    result = GradeService.get_work_to_grade(parent.ann, TODAY)

    assert [row.id for row in result["finished"]] == [waiting]
    assert result["unfinished"] == []


def test_unfinished_work_near_today_can_be_graded(parent):
    _, recent = work(parent, "Recent", due=TODAY - timedelta(days=30))
    _, soon = work(parent, "Soon", due=TODAY + timedelta(days=7))
    work(parent, "Too old", due=TODAY - timedelta(days=31))
    work(parent, "Too far", due=TODAY + timedelta(days=8))

    result = GradeService.get_work_to_grade(parent.ann, TODAY)

    assert [row.id for row in result["unfinished"]] == [recent, soon]


def test_archived_work_isnt_waiting(parent):
    assignment, _ = work(parent, done=True)
    AssignmentService.archive_assignment(assignment.id)

    assert GradeService.get_work_to_grade(parent.ann, TODAY)["finished"] == []


def test_suggested_total_comes_from_the_latest_grade(parent):
    assignment = AssignmentService.create_assignment(
        subject_id=parent.math,
        title="Quiz",
        student_ids=[parent.ann, parent.bob],
        due_date=YESTERDAY,
        graded=True,
    )

    db = SessionLocal()
    try:
        rows = db.query(AssignmentOccurrence).filter_by(
            assignment_id=assignment.id
        ).all()
        first, second = rows[0], rows[1]
    finally:
        db.close()

    assert GradeService.suggested_totals([first, second]) == {}

    GradeService.set_grade(first.id, 18, 20)

    assert GradeService.suggested_totals([second]) == {assignment.id: 20}


# ----- Periods -----


def test_periods_save_in_date_order(parent):
    GradeService.create_period("Spring", date(2027, 1, 1), date(2027, 5, 31))
    GradeService.create_period(" Fall ", date(2026, 9, 1), date(2026, 12, 31))

    assert [period.name for period in GradeService.get_periods()] == [
        "Fall",
        "Spring",
    ]


@pytest.mark.parametrize(
    "name, start, end, expected",
    [
        ("  ", date(2027, 1, 1), date(2027, 2, 1), "name"),
        ("New", None, date(2027, 2, 1), "dates"),
        ("New", date(2027, 2, 1), date(2027, 1, 1), "before"),
        ("New", date(2026, 12, 31), date(2027, 2, 1), "overlap with Fall"),
        ("New", date(2026, 8, 1), date(2026, 9, 1), "overlap with Fall"),
        ("New", date(2026, 10, 1), date(2026, 10, 2), "overlap with Fall"),
    ],
)
def test_bad_periods_say_whats_wrong(parent, name, start, end, expected):
    GradeService.create_period("Fall", date(2026, 9, 1), date(2026, 12, 31))

    assert expected in GradeService.period_error(name, start, end)
    assert GradeService.create_period(name, start, end) is None
    assert len(GradeService.get_periods()) == 1


def test_a_period_right_after_another_is_fine(parent):
    GradeService.create_period("Fall", date(2026, 9, 1), date(2026, 12, 31))

    assert GradeService.create_period("Spring", date(2027, 1, 1), date(2027, 5, 31))


def test_editing_a_period_doesnt_overlap_itself(parent, fetch):
    period = GradeService.create_period(
        "Fall", date(2026, 9, 1), date(2026, 12, 31)
    )

    assert GradeService.update_period(
        period.id, "Autumn", date(2026, 9, 15), date(2026, 12, 31)
    )
    assert fetch(GradingPeriod, period.id).name == "Autumn"


def test_archiving_a_period_keeps_grades_and_frees_its_dates(parent, fetch):
    graded(parent, 80, due=date(2026, 10, 1))
    period = GradeService.create_period(
        "Fall", date(2026, 9, 1), date(2026, 12, 31)
    )

    assert GradeService.archive_period(period.id)

    assert GradeService.get_periods() == []
    assert fetch(GradingPeriod, period.id).active is False
    assert len(GradeService.get_graded_rows(parent.ann)) == 1
    assert GradeService.create_period("New", date(2026, 9, 1), date(2026, 12, 31))


# ----- Who can do what -----


def test_a_student_sees_only_their_own_grades(parent, login):
    graded(parent, 80, student=parent.ann)
    graded(parent, 90, student=parent.bob)

    login(parent.smith, role=UserRole.STUDENT, student_id=parent.bob)

    assert GradeService.get_graded_rows(parent.ann) == []
    assert len(GradeService.get_graded_rows(parent.bob)) == 1


def test_a_student_cant_change_anything(parent, login, fetch):
    _, row_id = graded(parent, 80, student=parent.bob)
    period = GradeService.create_period(
        "Fall", date(2026, 9, 1), date(2026, 12, 31)
    )

    login(parent.smith, role=UserRole.STUDENT, student_id=parent.bob)

    assert GradeService.set_grade(row_id, 100, 100) is None
    assert GradeService.clear_grade(row_id) is None
    assert GradeService.get_work_to_grade(parent.bob, TODAY)["finished"] == []
    assert GradeService.create_period("X", date(2028, 1, 1), date(2028, 2, 1)) is None
    assert GradeService.update_period(period.id, "X", date(2028, 1, 1), date(2028, 2, 1)) is None
    assert GradeService.archive_period(period.id) is None
    assert float(row_of(row_id).score) == 80
    assert fetch(GradingPeriod, period.id).active is True

    # Students can read period names for the comparison.
    assert [p.name for p in GradeService.get_periods()] == ["Fall"]


def test_one_family_cant_see_or_change_anothers_grades(parent, login, fetch):
    assignment, row_id = graded(parent, 80)
    period = GradeService.create_period(
        "Fall", date(2026, 9, 1), date(2026, 12, 31)
    )

    login(parent.jones)

    assert GradeService.get_graded_rows(parent.ann) == []
    assert GradeService.get_work_to_grade(parent.ann, TODAY)["finished"] == []
    assert GradeService.set_grade(row_id, 100, 100) is None
    assert GradeService.clear_grade(row_id) is None
    assert GradeService.get_periods() == []
    assert GradeService.update_period(period.id, "X", date(2028, 1, 1), date(2028, 2, 1)) is None
    assert GradeService.archive_period(period.id) is None
    assert float(row_of(row_id).score) == 80
    assert fetch(GradingPeriod, period.id).active is True


def test_archived_students_grades_hide_and_come_back(parent):
    _, row_id = graded(parent, 80)

    def set_active(value):
        db = SessionLocal()
        try:
            db.get(Student, parent.ann).active = value
            db.commit()
        finally:
            db.close()

    set_active(False)
    assert GradeService.get_graded_rows(parent.ann) == []
    assert GradeService.set_grade(row_id, 90, 100) is None

    set_active(True)
    assert len(GradeService.get_graded_rows(parent.ann)) == 1


def test_admins_get_nothing(parent, login):
    graded(parent, 80)

    login(None, role=UserRole.ADMIN)

    assert GradeService.get_graded_rows(parent.ann) == []


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


def _text(at):
    return " ".join(item.value for item in at.markdown)


def _labelled(widgets, label):
    return next(widget for widget in widgets if widget.label == label)


def _setup(w, login, **kwargs):
    login(w.smith)
    with mock.patch.object(CurrentUser, "get_today", return_value=date.today()):
        result = work(w, due=date.today(), **kwargs)
    mock.patch.stopall()
    return result


def test_parent_grades_waiting_work_and_sees_the_grade(world, login, page_as):
    _, row_id = _setup(world, login, done=True, student=world.ann)

    at = page_as("Grades", "Parent").run()

    assert not at.exception
    at.selectbox(key="grades_student").set_value(world.ann).run()

    assert any("To Grade (1)" in s.value for s in at.subheader)
    assert at.number_input(key=f"total_{row_id}").value == 100

    at.number_input(key=f"score_{row_id}").set_value(18)
    at.number_input(key=f"total_{row_id}").set_value(20)
    at.button(key=f"grade_{row_id}").click().run()

    assert not at.exception
    assert float(row_of(row_id).score) == 18
    assert next(m for m in at.metric if m.label == "Overall Grade").value == "90% (A)"
    assert "| Math | 90% (A) |" in _text(at)
    assert any("To Grade (0)" in s.value for s in at.subheader)


def test_saving_with_no_score_shows_a_friendly_error(world, login, page_as):
    _, row_id = _setup(world, login, done=True, student=world.ann)

    at = page_as("Grades", "Parent").run()
    at.selectbox(key="grades_student").set_value(world.ann).run()
    at.button(key=f"grade_{row_id}").click().run()

    assert not at.exception
    assert any("enter the points" in error.value for error in at.error)
    assert row_of(row_id).score is None


def test_parent_adds_a_period_and_it_compares(world, login, page_as):
    _, row_id = _setup(world, login, done=True, student=world.ann)
    login(world.smith)
    GradeService.set_grade(row_id, 80, 100)
    mock.patch.stopall()

    at = page_as("Grades", "Parent").run()
    at.selectbox(key="grades_student").set_value(world.ann).run()

    _labelled(at.text_input, "Period Name").set_value("Fall")
    next(b for b in at.button if b.label == "Add Period").click().run()

    assert not at.exception
    assert any(s.value == "Compare Periods" for s in at.subheader)
    assert any("Periods are optional" in c.value for c in at.caption)
    assert "| Math | 80% (B) |" in _text(at)
    assert "**80% (B)**" in _text(at)


def test_student_page_is_read_only_and_only_theirs(world, login, page_as):
    _, bobs = _setup(world, login, done=True, student=world.bob, title="Bob's test")
    _, anns = _setup(world, login, done=True, student=world.ann, title="Ann's test")
    login(world.smith)
    GradeService.set_grade(bobs, 45, 50)
    GradeService.set_grade(anns, 10, 50)
    mock.patch.stopall()

    at = page_as("Grades", "Student", student_id=world.bob).run()

    assert not at.exception
    assert "Bob's test" in _text(at)
    assert "Ann's test" not in _text(at)
    assert not at.number_input
    assert "Select Student" not in [box.label for box in at.selectbox]
    assert not [
        b for b in at.button if b.label in ("Add Period", "💾 Save Grade", "✏️", "📦")
    ]


def test_new_assignment_can_be_marked_graded_from_the_form(world, page_as):
    at = page_as("Assignments", "Parent").run()

    _labelled(at.text_input, "Assignment Title").set_value("Chapter test")
    _labelled(at.checkbox, "Graded").check()
    next(b for b in at.button if b.label == "Create Assignment").click().run()

    assert not at.exception

    db = SessionLocal()
    try:
        assert db.query(Assignment).filter_by(title="Chapter test").one().graded
    finally:
        db.close()

    assert any("Graded" in caption.value for caption in at.caption)


def test_each_row_says_whether_its_completed(world, login, page_as):
    _setup(world, login, done=True, student=world.ann, title="Finished")
    _setup(world, login, student=world.ann, title="Not finished")

    at = page_as("Grades", "Parent").run()
    at.selectbox(key="grades_student").set_value(world.ann).run()

    assert not at.exception
    captions = [caption.value for caption in at.caption]
    assert any("✅ Completed" in caption for caption in captions)
    assert any("⬜ Not completed" in caption for caption in captions)
    assert any("the next 7 days" in caption for caption in captions)


def test_student_sees_completion_on_their_grades(world, login, page_as):
    _, row_id = _setup(world, login, student=world.bob)
    login(world.smith)
    GradeService.set_grade(row_id, 45, 50)
    mock.patch.stopall()

    at = page_as("Grades", "Student", student_id=world.bob).run()

    assert not at.exception
    assert any("⬜ Not completed" in caption.value for caption in at.caption)
