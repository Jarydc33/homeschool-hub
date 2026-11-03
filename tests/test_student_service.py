from database.models import StudentAssignment, Subject, UserRole
from services.dashboard_service import DashboardService
from services.student_service import StudentService
from services.subject_service import SubjectService


def test_parent_can_check_off_their_students_work(smith_parent, fetch):
    w = smith_parent

    assert StudentService.update_assignment_status(w.bob_essay, True)

    saved = fetch(StudentAssignment, w.bob_essay)
    assert saved.status == "Complete"
    assert saved.completed_at is not None


def test_unchecking_clears_completion(smith_parent, fetch):
    w = smith_parent

    assert StudentService.update_assignment_status(w.ann_essay, False)

    saved = fetch(StudentAssignment, w.ann_essay)
    assert saved.status == "Not Started"
    assert saved.completed_at is None


def test_student_can_check_off_own_work(world, login, fetch):
    login(world.smith, UserRole.STUDENT, world.bob)

    assert StudentService.update_assignment_status(world.bob_essay, True)
    assert fetch(StudentAssignment, world.bob_essay).status == "Complete"


def test_student_cannot_change_siblings_work(world, login, fetch):
    login(world.smith, UserRole.STUDENT, world.bob)

    assert StudentService.update_assignment_status(world.ann_essay, False) is None
    assert fetch(StudentAssignment, world.ann_essay).status == "Complete"


def test_cannot_check_off_archived_assignment(smith_parent, fetch):
    w = smith_parent

    assert StudentService.update_assignment_status(w.ann_archived, True) is None
    assert fetch(StudentAssignment, w.ann_archived).status == "Not Started"


def test_student_list_hides_archived_assignments(smith_parent):
    w = smith_parent

    links = StudentService.get_student_assignments(w.ann)

    assert {link.assignment_id for link in links} == {w.essay}


def test_student_list_can_read_assignment_and_subject(smith_parent):
    # The page reads these after the session closes.
    link = StudentService.get_student_assignments(smith_parent.ann)[0]

    assert link.assignment.title == "Essay"
    assert link.assignment.subject.name == "Art"


def test_metrics_ignore_archived_assignments(smith_parent):
    w = smith_parent

    metrics = DashboardService.get_student_metrics(
        StudentService.get_student_by_id(w.ann)
    )

    assert metrics["total"] == 1
    assert metrics["completed"] == 1
    assert metrics["percent"] == 100


def test_subject_count_ignores_archived_assignments(smith_parent):
    # Art has one active assignment and one archived.
    assert SubjectService.get_subject_assignment_count(smith_parent.art) == 1


def test_archiving_keeps_the_row(smith_parent, fetch):
    w = smith_parent

    SubjectService.archive_subject(w.math)

    assert fetch(Subject, w.math) is not None
