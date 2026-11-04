"""One family can't read or change another family's data."""
from uuid import uuid4

from database.models import AssignmentOccurrence
from database.models import Assignment, Student, StudentAssignment, Subject
from services.assignment_service import AssignmentService
from services.dashboard_service import DashboardService
from services.student_service import StudentService
from services.subject_service import SubjectService
from services.user_service import UserService
from database.db import SessionLocal
from database.models import User


def test_lists_only_show_own_family(smith_parent):
    w = smith_parent

    assert {s.id for s in StudentService.get_current_family_students()} == {
        w.ann, w.bob, w.cat,
    }
    assert {s.id for s in SubjectService.get_current_family_subjects()} == {
        w.math, w.art,
    }
    assert {a.id for a in AssignmentService.get_current_family_assignments()} == {
        w.essay, w.on_old,
    }


def test_cannot_read_other_familys_rows_by_id(smith_parent):
    w = smith_parent

    assert StudentService.get_student_by_id(w.jones_kid) is None
    assert SubjectService.get_subject_by_id(w.jones_subject) is None
    assert AssignmentService.get_assignment_by_id(w.jones_work) is None
    assert StudentService.get_student_occurrences(w.jones_kid) == []
    assert SubjectService.get_subject_assignment_count(w.jones_subject) == 0


def test_can_read_own_rows_by_id(smith_parent):
    w = smith_parent

    assert StudentService.get_student_by_id(w.ann).name == "Ann"
    assert SubjectService.get_subject_by_id(w.art).name == "Art"
    assert AssignmentService.get_assignment_by_id(w.essay).title == "Essay"


def test_cannot_update_other_familys_student(smith_parent, fetch):
    w = smith_parent

    assert StudentService.update_student(w.jones_kid, name="Hacked") is None
    assert fetch(Student, w.jones_kid).name == "Jones kid"


def test_cannot_archive_other_familys_student(smith_parent, fetch):
    w = smith_parent

    assert StudentService.archive_student(w.jones_kid) is None
    assert fetch(Student, w.jones_kid).active is True


def test_cannot_update_other_familys_subject(smith_parent, fetch):
    w = smith_parent

    assert SubjectService.update_subject(w.jones_subject, name="Hacked") is None
    assert fetch(Subject, w.jones_subject).name == "Jones subject"


def test_cannot_archive_other_familys_subject(smith_parent, fetch):
    w = smith_parent

    assert SubjectService.archive_subject(w.jones_subject) is None
    assert fetch(Subject, w.jones_subject).active is True


def test_cannot_archive_other_familys_assignment(smith_parent, fetch):
    w = smith_parent

    assert AssignmentService.archive_assignment(w.jones_work) is None
    assert fetch(Assignment, w.jones_work).active is True


def test_cannot_check_off_other_familys_work(smith_parent, fetch):
    w = smith_parent

    assert StudentService.update_occurrence_status(w.jones_link_day, True) is None
    assert fetch(AssignmentOccurrence, w.jones_link_day).status == "Not Started"


def test_own_family_can_still_make_changes(smith_parent, fetch):
    w = smith_parent

    assert StudentService.update_student(w.ann, name="Annie")
    assert fetch(Student, w.ann).name == "Annie"

    assert SubjectService.update_subject(w.math, name="Maths")
    assert fetch(Subject, w.math).name == "Maths"

    assert StudentService.archive_student(w.cat)
    assert fetch(Student, w.cat).active is False

    assert SubjectService.archive_subject(w.math)
    assert fetch(Subject, w.math).active is False

    assert AssignmentService.archive_assignment(w.essay)
    assert fetch(Assignment, w.essay).active is False


def test_student_login_lookup_is_scoped(smith_parent):
    w = smith_parent

    db = SessionLocal()
    db.add(User(
        family_id=w.jones, student_id=w.jones_kid,
        email="kid@jones.test", auth_user_id=str(uuid4()), role="Student",
    ))
    db.commit()
    db.close()

    assert UserService.get_user_by_student_id(w.jones_kid, w.smith) is None
    assert UserService.get_user_by_student_id(w.jones_kid, w.jones) is not None


def test_cannot_create_login_for_other_familys_student(smith_parent):
    w = smith_parent

    assert UserService.create_student_user(w.smith, w.jones_kid, "x@x.test", uuid4()) is None
    assert UserService.get_user_by_email("x@x.test") is None


def test_cannot_create_login_for_archived_student(smith_parent):
    w = smith_parent

    assert UserService.create_student_user(w.smith, w.gone, "x@x.test", uuid4()) is None


def test_can_create_login_for_own_student(smith_parent):
    w = smith_parent

    user = UserService.create_student_user(w.smith, w.ann, "Ann@X.test ", uuid4())

    assert user.email == "ann@x.test"
    assert user.student_id == w.ann


def test_dashboard_only_counts_own_family(smith_parent):
    w = smith_parent

    data = DashboardService.get_dashboard_data()

    assert {s.id for s in data["students"]} == {w.ann, w.bob, w.cat}
    assert {a.id for a in data["assignments"]} == {w.essay, w.on_old}
