from database.models import AssignmentOccurrence, Subject, UserRole
from services.dashboard_service import DashboardService
import pytest

from services.student_service import (
    BASIC_STUDENT_LIMIT,
    StudentLimitReached,
    StudentService,
)
from services.subject_service import SubjectService


def test_parent_can_check_off_their_students_work(smith_parent, fetch):
    w = smith_parent

    assert StudentService.update_occurrence_status(w.bob_essay_day, True)

    saved = fetch(AssignmentOccurrence, w.bob_essay_day)
    assert saved.status == "Complete"
    assert saved.completed_at is not None


def test_unchecking_clears_completion(smith_parent, fetch):
    w = smith_parent

    assert StudentService.update_occurrence_status(w.ann_essay_day, False)

    saved = fetch(AssignmentOccurrence, w.ann_essay_day)
    assert saved.status == "Not Started"
    assert saved.completed_at is None


def test_student_can_check_off_own_work(world, login, fetch):
    login(world.smith, UserRole.STUDENT, world.bob)

    assert StudentService.update_occurrence_status(world.bob_essay_day, True)
    assert fetch(AssignmentOccurrence, world.bob_essay_day).status == "Complete"


def test_student_cannot_change_siblings_work(world, login, fetch):
    login(world.smith, UserRole.STUDENT, world.bob)

    assert StudentService.update_occurrence_status(world.ann_essay_day, False) is None
    assert fetch(AssignmentOccurrence, world.ann_essay_day).status == "Complete"


def test_cannot_check_off_archived_assignment(smith_parent, fetch):
    w = smith_parent

    assert StudentService.update_occurrence_status(w.ann_archived_day, True) is None
    assert fetch(AssignmentOccurrence, w.ann_archived_day).status == "Not Started"


def test_student_list_hides_archived_assignments(smith_parent):
    w = smith_parent

    links = StudentService.get_student_occurrences(w.ann)

    assert {link.assignment_id for link in links} == {w.essay}


def test_student_list_can_read_assignment_and_subject(smith_parent):
    # The page reads these after the session closes.
    link = StudentService.get_student_occurrences(smith_parent.ann)[0]

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


# ----- The free plan's student limit -----


def _fill_to_the_limit():
    # The Smiths start with three active students.
    for number in range(BASIC_STUDENT_LIMIT - 3):
        StudentService.create_student(f"Extra {number}")


def test_a_family_can_add_students_up_to_the_limit(smith_parent):
    _fill_to_the_limit()

    assert len(StudentService.get_current_family_students()) == BASIC_STUDENT_LIMIT

    with pytest.raises(StudentLimitReached):
        StudentService.create_student("One too many")


def test_archived_students_dont_count_toward_the_limit(smith_parent):
    _fill_to_the_limit()

    StudentService.archive_student(smith_parent.ann)

    assert StudentService.create_student("Room again")


def test_restoring_a_student_cant_pass_the_limit(smith_parent):
    _fill_to_the_limit()

    with pytest.raises(StudentLimitReached):
        StudentService.restore_student(smith_parent.gone)


def test_restoring_an_active_student_at_the_limit_is_fine(smith_parent):
    _fill_to_the_limit()

    assert StudentService.restore_student(smith_parent.ann)


def test_another_familys_students_dont_count(world, login):
    login(world.smith)
    _fill_to_the_limit()

    login(world.jones)

    assert StudentService.create_student("Jones kid two")
