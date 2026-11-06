"""Dashboards and check-offs work per date."""
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from database.db import SessionLocal
from database.models import AssignmentOccurrence, User, UserRole
from services.assignment_service import AssignmentService
from services.auth_service import AuthService
from services.dashboard_service import DashboardService
from services.occurrence_service import OccurrenceService
from services.session_service import SessionService
from services.student_service import StudentService

TODAY = date(2026, 11, 4)
YESTERDAY = TODAY - timedelta(days=1)
LAST_WEEK = TODAY - timedelta(days=7)
TOMORROW = TODAY + timedelta(days=1)
NEXT_WEEK = TODAY + timedelta(days=7)
ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def parent(smith_parent):
    with mock.patch.object(AuthService, "get_today", return_value=TODAY):
        yield smith_parent


def daily(w, title="Math", start=LAST_WEEK, end=NEXT_WEEK, students=None):
    return AssignmentService.create_assignment(
        subject_id=w.art,
        title=title,
        student_ids=[w.ann] if students is None else students,
        due_date=start,
        assignment_type="Recurring",
        recurrence_pattern="Every Day",
        end_date=end,
    )


def one_time(w, title="Essay 2", due=TODAY, students=None):
    return AssignmentService.create_assignment(
        subject_id=w.art,
        title=title,
        student_ids=[w.ann] if students is None else students,
        due_date=due,
    )


def groups_for(student_id):
    return OccurrenceService.group_for_student(
        StudentService.get_student_occurrences(student_id), TODAY
    )


def row_on(rows, assignment, day):
    return next(
        row
        for row in rows
        if row.assignment_id == assignment.id and row.occurrence_date == day
    )


def titles(rows):
    return [row.assignment.title for row in rows]


# ----- Grouping -----


def test_a_past_recurring_date_is_missed_not_overdue(parent):
    w = parent
    work = daily(w, end=YESTERDAY)

    groups = groups_for(w.ann)

    assert len([r for r in groups["missed"] if r.assignment_id == work.id]) == 7
    assert "Math" not in titles(groups["overdue"])


def test_past_one_time_work_is_overdue_not_missed(parent):
    w = parent
    one_time(w, "Late", YESTERDAY)

    groups = groups_for(w.ann)

    assert "Late" in titles(groups["overdue"])
    assert "Late" not in titles(groups["missed"])


def test_todays_date_is_in_today(parent):
    w = parent
    daily(w)
    one_time(w, "Quiz")

    assert sorted(titles(groups_for(w.ann)["today"])) == ["Math", "Quiz"]


def test_upcoming_only_has_the_next_date_of_recurring_work(parent):
    w = parent
    work = daily(w)

    rows = [r for r in groups_for(w.ann)["upcoming"] if r.assignment_id == work.id]

    assert [row.occurrence_date for row in rows] == [TOMORROW]


def test_finishing_a_future_date_moves_upcoming_to_the_next_one(parent):
    w = parent
    work = daily(w)
    rows = StudentService.get_student_occurrences(w.ann)
    StudentService.update_occurrence_status(row_on(rows, work, TOMORROW).id, True)

    upcoming = [r for r in groups_for(w.ann)["upcoming"] if r.assignment_id == work.id]

    assert [row.occurrence_date for row in upcoming] == [TOMORROW + timedelta(days=1)]


def test_every_future_one_time_assignment_is_upcoming(parent):
    w = parent
    one_time(w, "First", TOMORROW)
    one_time(w, "Second", NEXT_WEEK)

    upcoming = titles(groups_for(w.ann)["upcoming"])

    assert "First" in upcoming and "Second" in upcoming


def test_a_missed_day_doesnt_affect_future_dates(parent):
    w = parent
    work = daily(w)

    groups = groups_for(w.ann)

    assert work.id in {r.assignment_id for r in groups["today"]}
    assert work.id in {r.assignment_id for r in groups["upcoming"]}
    assert work.id in {r.assignment_id for r in groups["missed"]}


# ----- Progress -----


def test_progress_leaves_out_work_not_due_yet():
    groups = {
        "completed": [object()],
        "overdue": [object()],
        "today": [object()],
        "upcoming": [object(), object()],
        "missed": [object()],
    }

    assert OccurrenceService.progress(groups) == {
        "completed": 1,
        "remaining": 2,
        "total": 4,
        "percent": 25,
    }


def test_progress_with_nothing_due_is_zero():
    empty = dict(completed=[], overdue=[], today=[], upcoming=[], missed=[])

    assert OccurrenceService.progress(empty)["percent"] == 0


def _row(day):
    return SimpleNamespace(occurrence_date=day)


def test_today_progress_counts_only_work_dated_today():
    groups = {
        "completed": [_row(TODAY), _row(YESTERDAY), _row(TOMORROW)],
        "overdue": [_row(LAST_WEEK)],
        "today": [_row(TODAY), _row(TODAY)],
        "upcoming": [_row(TOMORROW)],
        "missed": [_row(YESTERDAY)],
    }

    assert OccurrenceService.today_progress(groups, TODAY) == (1, 3)


def test_today_progress_with_nothing_today_is_zero():
    empty = dict(completed=[], overdue=[], today=[], upcoming=[], missed=[])

    assert OccurrenceService.today_progress(empty, TODAY) == (0, 0)


def test_assignment_progress_counts_recurring_dates_so_far(parent):
    w = parent
    work = daily(w, start=YESTERDAY, end=NEXT_WEEK)
    rows = StudentService.get_student_occurrences(w.ann)
    StudentService.update_occurrence_status(row_on(rows, work, TODAY).id, True)

    listed = next(
        a for a in AssignmentService.get_current_family_assignments() if a.id == work.id
    )

    assert OccurrenceService.assignment_progress(listed, TODAY) == (1, 2)


def test_student_metrics_use_occurrences(parent):
    w = parent
    daily(w, title="Math", start=YESTERDAY, end=TODAY, students=[w.cat])
    one_time(w, "Late", YESTERDAY, students=[w.cat])

    metrics = DashboardService.get_student_metrics(StudentService.get_student_by_id(w.cat))

    assert metrics == {"total": 3, "completed": 0, "percent": 0, "overdue_count": 1}


# ----- Recently completed -----


def _done(day, completed_at=None):
    return SimpleNamespace(occurrence_date=day, completed_at=completed_at)


def test_recently_completed_keeps_only_the_last_30_days():
    on_the_edge = _done(TODAY - timedelta(days=30), datetime(2026, 10, 5, 9, 0))
    too_old = _done(TODAY - timedelta(days=31), datetime(2026, 10, 4, 9, 0))

    assert OccurrenceService.recently_completed([on_the_edge, too_old], TODAY) == [on_the_edge]


def test_recently_completed_goes_by_when_it_was_checked_off():
    caught_up_today = _done(date(2026, 8, 1), datetime(2026, 11, 4, 9, 0))

    assert OccurrenceService.recently_completed([caught_up_today], TODAY) == [caught_up_today]


def test_recently_completed_uses_the_date_when_there_is_no_completion_time():
    recent = _done(YESTERDAY)
    old = _done(date(2026, 8, 1))

    assert OccurrenceService.recently_completed([recent, old], TODAY) == [recent]


def test_recently_completed_lists_the_newest_first():
    older = _done(LAST_WEEK, datetime(2026, 10, 28, 9, 0))
    newer = _done(LAST_WEEK, datetime(2026, 11, 3, 9, 0))

    assert OccurrenceService.recently_completed([older, newer], TODAY) == [newer, older]


def test_recently_missed_keeps_only_the_last_30_days():
    on_the_edge = _done(TODAY - timedelta(days=30))
    too_old = _done(TODAY - timedelta(days=31))

    assert OccurrenceService.recently_missed([on_the_edge, too_old], TODAY) == [on_the_edge]


def test_old_missed_dates_still_count_in_progress():
    groups = dict(
        completed=[],
        overdue=[],
        today=[],
        upcoming=[],
        missed=[_done(date(2026, 1, 1)), _done(YESTERDAY)],
    )

    assert OccurrenceService.progress(groups)["total"] == 2


def test_old_completed_work_still_counts_in_progress():
    groups = dict(
        completed=[_done(date(2026, 1, 1)), _done(YESTERDAY)],
        overdue=[],
        today=[],
        upcoming=[],
        missed=[],
    )

    assert OccurrenceService.progress(groups)["completed"] == 2


# ----- Check-offs -----


def test_checking_off_one_date_leaves_the_others_alone(parent):
    w = parent
    work = daily(w)
    rows = StudentService.get_student_occurrences(w.ann)

    assert StudentService.update_occurrence_status(row_on(rows, work, TODAY).id, True)

    rows = StudentService.get_student_occurrences(w.ann)
    done = [row for row in rows if row.assignment_id == work.id and row.status == "Complete"]
    assert [row.occurrence_date for row in done] == [TODAY]
    assert done[0].completed_at is not None


def test_a_missed_date_can_still_be_checked_off(parent):
    w = parent
    work = daily(w)
    rows = StudentService.get_student_occurrences(w.ann)

    StudentService.update_occurrence_status(row_on(rows, work, YESTERDAY).id, True)

    groups = groups_for(w.ann)
    assert YESTERDAY not in [r.occurrence_date for r in groups["missed"]]
    assert YESTERDAY in [r.occurrence_date for r in groups["completed"]]


def test_unchecking_clears_completion(parent):
    w = parent
    work = one_time(w)
    rows = StudentService.get_student_occurrences(w.ann)
    row = row_on(rows, work, TODAY)

    StudentService.update_occurrence_status(row.id, True)
    saved = StudentService.update_occurrence_status(row.id, False)

    assert saved.status == "Not Started"
    assert saved.completed_at is None


def test_student_cant_read_a_siblings_work(world, login):
    login(world.smith, UserRole.STUDENT, world.bob)

    assert StudentService.get_student_occurrences(world.ann) == []
    assert StudentService.get_student_occurrences(world.bob) != []


def test_parent_cant_read_another_familys_work(parent):
    assert StudentService.get_student_occurrences(parent.jones_kid) == []


def test_rows_kept_after_coming_off_an_assignment_arent_shown(parent):
    w = parent
    work = daily(w, students=[w.ann, w.bob])
    rows = StudentService.get_student_occurrences(w.bob)
    StudentService.update_occurrence_status(row_on(rows, work, YESTERDAY).id, True)

    AssignmentService.update_assignment(
        assignment_id=work.id,
        title="Math",
        description=None,
        due_date=LAST_WEEK,
        subject_id=w.art,
        student_ids=[w.ann],
        assignment_type="Recurring",
        recurrence_pattern="Every Day",
        end_date=NEXT_WEEK,
    )

    assert work.id not in {
        row.assignment_id for row in StudentService.get_student_occurrences(w.bob)
    }
    db = SessionLocal()
    try:
        kept = (
            db.query(AssignmentOccurrence)
            .filter_by(assignment_id=work.id, student_id=w.bob, status="Complete")
            .count()
        )
    finally:
        db.close()
    assert kept == 1


# ----- Parent dashboard data -----


def _entry(entries, work):
    return next((e for e in entries if e["assignment"].id == work.id), None)


def test_parent_dashboard_doesnt_call_missed_days_overdue(parent):
    w = parent
    work = daily(w)

    data = DashboardService.get_dashboard_data()

    assert _entry(data["overdue_assignments"], work) is None
    assert _entry(data["today_assignments"], work)["student_names"] == ["Ann"]


def test_parent_dashboard_drops_today_once_everyone_is_done(parent):
    w = parent
    work = daily(w)
    rows = StudentService.get_student_occurrences(w.ann)
    StudentService.update_occurrence_status(row_on(rows, work, TODAY).id, True)

    assert _entry(DashboardService.get_dashboard_data()["today_assignments"], work) is None


def test_parent_dashboard_names_only_who_still_owes_overdue_work(parent):
    w = parent
    work = one_time(w, "Late", YESTERDAY, students=[w.ann, w.bob])
    rows = StudentService.get_student_occurrences(w.ann)
    StudentService.update_occurrence_status(row_on(rows, work, YESTERDAY).id, True)

    entry = _entry(DashboardService.get_dashboard_data()["overdue_assignments"], work)

    assert entry["student_names"] == ["Bob"]


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


def _add_work(w, today):
    """Real dates, since the pages use the real clock."""
    with mock.patch.object(AuthService, "get_today", return_value=today):
        work = AssignmentService.create_assignment(
            subject_id=w.art,
            title="Math",
            student_ids=[w.bob],
            due_date=today - timedelta(days=2),
            assignment_type="Recurring",
            recurrence_pattern="Every Day",
            end_date=today + timedelta(days=5),
        )
    return work


def test_student_page_shows_todays_date_and_checks_it_off(smith_parent, page_as, login):
    w = smith_parent
    today = date.today()
    _add_work(w, today)
    mock.patch.stopall()

    at = page_as("Student_Dashboard", w.smith, "Student", w.bob).run()

    assert not at.exception
    subheaders = [s.value for s in at.subheader]
    assert "📅 Today's Work (1)" in subheaders
    assert any("Missed (2)" in e.label for e in at.expander)
    math = [c for c in at.checkbox if c.label.startswith("Math")]
    # Today, the next upcoming date, and two missed dates.
    assert len(math) == 4

    next(c for c in math if not c.value).check().run()

    assert not at.exception
    assert any(c.label.startswith("Math") and c.value for c in at.checkbox)


def test_student_page_only_lists_recent_completed_work(smith_parent, page_as):
    w = smith_parent
    today = date.today()
    work = _add_work(w, today)
    db = SessionLocal()
    try:
        rows = (
            db.query(AssignmentOccurrence)
            .filter_by(assignment_id=work.id, student_id=w.bob)
            .order_by(AssignmentOccurrence.occurrence_date)
            .all()
        )
        rows[0].status = "Complete"
        rows[0].completed_at = datetime.combine(today - timedelta(days=40), datetime.min.time())
        rows[1].status = "Complete"
        rows[1].completed_at = datetime.combine(today, datetime.min.time())
        db.commit()
    finally:
        db.close()
    mock.patch.stopall()

    at = page_as("Student_Dashboard", w.smith, "Student", w.bob).run()

    assert not at.exception
    assert any("Completed in the Last 30 Days (1)" in e.label for e in at.expander)
    assert len([c for c in at.checkbox if c.label.startswith("Math") and c.value]) == 1


def test_student_page_only_lists_recent_missed_dates(smith_parent, page_as):
    w = smith_parent
    today = date.today()
    with mock.patch.object(AuthService, "get_today", return_value=today):
        AssignmentService.create_assignment(
            subject_id=w.art,
            title="Math",
            student_ids=[w.bob],
            due_date=today - timedelta(days=35),
            assignment_type="Recurring",
            recurrence_pattern="Every Day",
            end_date=today,
        )
    mock.patch.stopall()

    at = page_as("Student_Dashboard", w.smith, "Student", w.bob).run()

    assert not at.exception
    assert any("Missed (30)" in e.label for e in at.expander)


def test_parent_dashboard_page_runs_with_recurring_work(smith_parent, page_as):
    w = smith_parent
    _add_work(w, date.today())
    mock.patch.stopall()

    at = page_as("Parent_Dashboard", w.smith, "Parent").run()

    assert not at.exception


def test_assignments_page_shows_recurring_dates_and_progress(smith_parent, page_as):
    w = smith_parent
    _add_work(w, date.today())
    mock.patch.stopall()

    at = page_as("Assignments", w.smith, "Parent").run()

    assert not at.exception
    captions = " ".join(c.value for c in at.caption)
    assert "Every Day" in captions
    assert "Progress: 0/3" in captions


def test_student_page_puts_work_first_and_tucks_away_the_parents_login_tools(
    smith_parent, page_as
):
    w = smith_parent
    _add_work(w, date.today())
    mock.patch.stopall()

    at = page_as("Student_Dashboard", w.smith, "Parent").run()

    assert not at.exception
    assert any("Student Login" in e.label for e in at.expander)
    subheaders = [s.value for s in at.subheader]
    assert subheaders.index("🔥 Streaks") > max(
        i for i, s in enumerate(subheaders) if "Today's Work" in s
    )
