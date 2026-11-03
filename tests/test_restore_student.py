from datetime import date, timedelta

from database.db import SessionLocal
from database.models import Assignment, Student, StudentAssignment
from services.assignment_service import AssignmentService
from services.dashboard_service import DashboardService
from services.student_service import StudentService


def roster(assignment_id):
    assignment = next(
        a
        for a in AssignmentService.get_current_family_assignments()
        if a.id == assignment_id
    )
    return {sa.student.name for sa in assignment.student_assignments}


def test_archived_list_shows_only_own_familys_archived_students(smith_parent):
    names = [s.name for s in StudentService.get_archived_students()]

    assert names == ["Gone", "Other gone"]


def test_archived_list_is_empty_for_a_family_with_none(world, login):
    login(world.jones)

    assert StudentService.get_archived_students() == []


def test_restore_makes_student_active_again(smith_parent, fetch):
    w = smith_parent

    assert StudentService.restore_student(w.gone)

    assert fetch(Student, w.gone).active is True
    assert w.gone in {s.id for s in StudentService.get_current_family_students()}
    assert w.gone not in {s.id for s in StudentService.get_archived_students()}


def test_cannot_restore_other_familys_student(world, login, fetch):
    db = SessionLocal()
    db.get(Student, world.jones_kid).active = False
    db.commit()
    db.close()
    login(world.smith)

    assert StudentService.restore_student(world.jones_kid) is None
    assert fetch(Student, world.jones_kid).active is False


def test_cannot_see_other_familys_archived_students(world, login):
    db = SessionLocal()
    db.get(Student, world.jones_kid).active = False
    db.commit()
    db.close()
    login(world.smith)

    assert world.jones_kid not in {
        s.id for s in StudentService.get_archived_students()
    }


def test_restoring_a_missing_student_returns_none(smith_parent):
    assert StudentService.restore_student(999999) is None


def test_restoring_an_active_student_changes_nothing(smith_parent, fetch):
    w = smith_parent

    assert StudentService.restore_student(w.ann)
    assert fetch(Student, w.ann).active is True


def test_restore_brings_back_roster_and_history(smith_parent, fetch):
    w = smith_parent
    assert roster(w.essay) == {"Ann", "Bob"}

    StudentService.restore_student(w.gone)

    assert roster(w.essay) == {"Ann", "Bob", "Gone"}
    link = fetch(StudentAssignment, w.gone_essay)
    assert link.status == "Complete"
    assert link.completed_at == w.done_at


def test_archive_and_restore_round_trip_keeps_progress(smith_parent, fetch):
    w = smith_parent

    StudentService.archive_student(w.ann)
    assert "Ann" not in roster(w.essay)

    StudentService.restore_student(w.ann)

    assert "Ann" in roster(w.essay)
    link = fetch(StudentAssignment, w.ann_essay)
    assert link.status == "Complete"
    assert link.notes == "Well done"


def test_restore_brings_back_overdue_warning(smith_parent):
    w = smith_parent
    db = SessionLocal()
    late = Assignment(
        family_id=w.smith,
        subject_id=w.art,
        title="Late",
        due_date=date.today() - timedelta(days=1),
    )
    db.add(late)
    db.flush()
    db.add(StudentAssignment(assignment_id=late.id, student_id=w.gone))
    db.commit()
    db.close()

    def overdue():
        return {
            a.title
            for a in DashboardService.get_dashboard_data()["overdue_assignments"]
        }

    assert "Late" not in overdue()

    StudentService.restore_student(w.gone)

    assert "Late" in overdue()
