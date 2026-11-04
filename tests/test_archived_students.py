"""Archived students drop out of rosters, totals and warnings, but keep history."""
from datetime import date, timedelta

import pytest

from database.db import SessionLocal
from database.models import Assignment, StudentAssignment
from services.assignment_service import AssignmentService
from services.dashboard_service import DashboardService
from services.student_service import StudentService

YESTERDAY = date.today() - timedelta(days=1)
TODAY = date.today()


def add_assignment(world, title, due_date, student_ids):
    db = SessionLocal()
    try:
        assignment = Assignment(
            family_id=world.smith,
            subject_id=world.art,
            title=title,
            due_date=due_date,
        )
        db.add(assignment)
        db.flush()
        db.add_all(
            StudentAssignment(assignment_id=assignment.id, student_id=student_id)
            for student_id in student_ids
        )
        db.commit()
        return assignment.id
    finally:
        db.close()


def listed(assignment_id):
    return next(
        a
        for a in AssignmentService.get_current_family_assignments()
        if a.id == assignment_id
    )


def overdue_titles():
    return {a.title for a in DashboardService.get_dashboard_data()["overdue_assignments"]}


def today_titles():
    return {a.title for a in DashboardService.get_dashboard_data()["today_assignments"]}


@pytest.fixture
def parent(smith_parent):
    return smith_parent


def test_roster_leaves_out_archived_students(parent):
    names = {sa.student.name for sa in listed(parent.essay).student_assignments}

    assert names == {"Ann", "Bob"}


def test_progress_total_leaves_out_archived_students(parent):
    # Ann is complete and Bob isn't. Gone is complete but archived.
    links = listed(parent.essay).student_assignments

    assert len(links) == 2
    assert len([sa for sa in links if sa.status == "Complete"]) == 1


def test_assignment_with_only_archived_students_stays_listed(parent):
    w = parent
    only_gone = add_assignment(w, "Only gone", TODAY, [w.gone])

    assert listed(only_gone).student_assignments == []


def test_archived_student_alone_does_not_trigger_overdue(parent):
    w = parent
    add_assignment(w, "Only gone", YESTERDAY, [w.gone])

    assert "Only gone" not in overdue_titles()


def test_active_student_still_triggers_overdue(parent):
    w = parent
    add_assignment(w, "Late", YESTERDAY, [w.bob, w.gone])

    assert "Late" in overdue_titles()


def test_overdue_warning_names_only_active_students(parent):
    w = parent
    add_assignment(w, "Late", YESTERDAY, [w.bob, w.gone])

    late = next(
        a
        for a in DashboardService.get_dashboard_data()["overdue_assignments"]
        if a.title == "Late"
    )

    assert [sa.student.name for sa in late.student_assignments] == ["Bob"]


def test_archived_student_alone_does_not_show_as_due_today(parent):
    w = parent
    add_assignment(w, "Only gone", TODAY, [w.gone])

    assert "Only gone" not in today_titles()


def test_archiving_a_student_clears_their_overdue_warning(parent):
    w = parent
    add_assignment(w, "Late", YESTERDAY, [w.cat])
    assert "Late" in overdue_titles()

    StudentService.archive_student(w.cat)

    assert "Late" not in overdue_titles()


def test_archived_students_history_is_kept(parent, fetch):
    w = parent

    AssignmentService.get_current_family_assignments()

    saved = fetch(StudentAssignment, w.gone_essay)
    assert saved.status == "Complete"
    assert saved.completed_at == w.done_at


def test_editing_after_listing_keeps_archived_students_link(parent, fetch):
    w = parent
    AssignmentService.get_current_family_assignments()

    assert AssignmentService.update_assignment(
        assignment_id=w.essay,
        title="Edited",
        description=None,
        due_date=date(2026, 12, 1),
        subject_id=w.art,
        student_ids=[w.ann, w.bob],
        assignment_type="One Time",
        recurrence_pattern=None,
    )

    assert fetch(StudentAssignment, w.gone_essay).status == "Complete"
