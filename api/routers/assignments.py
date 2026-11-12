from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from api.auth import require_parent
from api.errors import could_not_save, invalid, not_found
from api.schemas import LongText, Message, Progress, StudentOut, SubjectOut, Title, student_out
from database.models import AssignmentType
from services.assignment_service import AssignmentService
from services.current_user import CurrentUser
from services.occurrence_service import OccurrenceService
from services.student_service import StudentService

# Assignments are a parent's tools. Students see their work through their
# dashboard and the calendar.
router = APIRouter(
    prefix="/assignments",
    tags=["assignments"],
    dependencies=[Depends(require_parent)],
)

NOT_FOUND_MESSAGE = "This assignment could not be found."

SAVE_FAILED_MESSAGE = (
    "This assignment couldn't be saved. Check its subject and students, "
    "then try again."
)


class AssignmentOut(BaseModel):
    id: int
    title: str
    description: str | None
    subject: SubjectOut | None
    assignment_type: str
    # Recurring: how often ("Every Day", "Weekly", ...). Curriculum: its
    # school days ("Mon,Wed,Fri").
    recurrence_pattern: str | None
    # One-time: due. Recurring: the first date. Curriculum: the first lesson.
    due_date: date
    end_date: date | None
    graded: bool
    active: bool
    students: list[StudentOut]
    progress: Progress | None
    lesson_count: int | None
    finish_date: date | None


class AssignmentIn(BaseModel):
    title: Title
    subject_id: int
    student_ids: list[int] = Field(default_factory=list, max_length=100)
    description: LongText | None = None
    assignment_type: Literal["One Time", "Recurring", "Curriculum"] = "One Time"
    recurrence_pattern: str | None = Field(default=None, max_length=100)
    due_date: date
    end_date: date | None = None
    lesson_count: int | None = Field(default=None, ge=1, le=1000)
    graded: bool = False


class NoteRow(BaseModel):
    occurrence_id: int
    student: StudentOut
    date: date
    notes: str | None


class NoteIn(BaseModel):
    date: date
    student_ids: list[int] = Field(min_length=1, max_length=100)
    # Blank removes the note.
    note: LongText = ""


class RecoveryIn(BaseModel):
    student_ids: list[int] = Field(min_length=1, max_length=100)
    resume_on: date


class RecoveryStep(BaseModel):
    student_name: str
    title: str
    next_lesson: int | None
    next_date: date | None
    old_finish: date | None
    new_finish: date | None


class RecoveryInfo(BaseModel):
    has_curriculum: bool
    students_behind: list[int]


class Moved(BaseModel):
    lessons_moved: int


def _assignment_out(assignment, students_by_id, full=True):
    """
    The assignment's students come from students_by_id (the family's active
    students), so archived students aren't listed. Without full, only what
    the archived list loads is read: no students, progress or lessons.
    """

    subject = assignment.subject

    is_curriculum = (
        full and assignment.assignment_type == AssignmentType.CURRICULUM.value
    )

    done_total = (
        OccurrenceService.assignment_progress(assignment, CurrentUser.get_today())
        if full
        else None
    )

    return AssignmentOut(
        id=assignment.id,
        title=assignment.title,
        description=assignment.description,
        subject=(
            SubjectOut(id=subject.id, name=subject.name, color=subject.color)
            if subject
            else None
        ),
        assignment_type=assignment.assignment_type,
        recurrence_pattern=assignment.recurrence_pattern,
        due_date=assignment.due_date,
        end_date=assignment.end_date,
        graded=bool(assignment.graded),
        active=bool(assignment.active),
        students=[
            student_out(students_by_id[link.student_id])
            for link in (assignment.student_assignments if full else [])
            if link.student_id in students_by_id
        ],
        progress=(
            Progress(done=done_total[0], total=done_total[1])
            if done_total
            else None
        ),
        lesson_count=(
            OccurrenceService.lesson_count(assignment) if is_curriculum else None
        ),
        finish_date=(
            OccurrenceService.last_lesson_date(assignment) if is_curriculum else None
        ),
    )


def _students_by_id():

    return {
        student.id: student
        for student in StudentService.get_current_family_students()
    }


def _find_active(assignment_id):

    for assignment in AssignmentService.get_current_family_assignments():
        if assignment.id == assignment_id:
            return assignment

    raise not_found(NOT_FOUND_MESSAGE)


def _schedule_error(body):

    return OccurrenceService.schedule_error(
        body.assignment_type,
        body.recurrence_pattern,
        body.due_date,
        body.end_date,
        body.lesson_count,
    )


def _fields(body):

    return dict(
        title=body.title,
        description=body.description or None,
        due_date=body.due_date,
        subject_id=body.subject_id,
        student_ids=body.student_ids,
        assignment_type=body.assignment_type,
        recurrence_pattern=body.recurrence_pattern,
        end_date=body.end_date,
        lesson_count=body.lesson_count,
        graded=body.graded,
    )


# ----- Listing -----


@router.get("", response_model=list[AssignmentOut])
def list_assignments():
    """Active assignments, with their students and progress so far."""

    students = _students_by_id()

    return [
        _assignment_out(assignment, students)
        for assignment in AssignmentService.get_current_family_assignments()
    ]


@router.get("/archived", response_model=list[AssignmentOut])
def list_archived():

    students = _students_by_id()

    return [
        _assignment_out(assignment, students, full=False)
        for assignment in AssignmentService.get_archived_assignments()
    ]


@router.get("/missed-day", response_model=RecoveryInfo)
def missed_day_info():
    """
    Whether "Missed a Day?" applies: the family has a curriculum, and which
    students have a lesson before today that isn't done.
    """

    return RecoveryInfo(
        has_curriculum=AssignmentService.has_curriculum(),
        students_behind=sorted(
            AssignmentService.get_students_behind(CurrentUser.get_today())
        ),
    )


@router.get("/missed-day/plan", response_model=list[RecoveryStep])
def missed_day_plan(
    resume_on: date,
    student_ids: list[int] = Query(min_length=1),
):
    """What picking up on resume_on would move, without changing anything."""

    return [
        RecoveryStep(**step)
        for step in AssignmentService.get_recovery_plan(student_ids, resume_on)
    ]


@router.post("/missed-day", response_model=Moved)
def missed_day_shift(body: RecoveryIn):
    """
    Picks the chosen students' curricula back up on resume_on. Only
    unfinished lessons move; other kinds of work don't shift.
    """

    if body.resume_on < CurrentUser.get_today():
        raise invalid("Please choose today or a later date.")

    moved = AssignmentService.shift_lessons(body.student_ids, body.resume_on)

    if moved is None:
        raise could_not_save()

    return Moved(lessons_moved=moved)


@router.get("/{assignment_id}", response_model=AssignmentOut)
def get_assignment(assignment_id: int):

    return _assignment_out(_find_active(assignment_id), _students_by_id())


# ----- Changing assignments -----


@router.post("", response_model=AssignmentOut, status_code=201)
def create_assignment(body: AssignmentIn):
    """
    Creates the assignment and every date it happens on for its students.
    A curriculum passes lesson_count, its school days as
    recurrence_pattern ("Mon,Wed,Fri") and its first day as due_date.
    """

    error = _schedule_error(body)

    if error:
        raise invalid(error)

    fields = _fields(body)

    assignment = AssignmentService.create_assignment(
        subject_id=fields.pop("subject_id"),
        title=fields.pop("title"),
        student_ids=fields.pop("student_ids"),
        **fields,
    )

    if not assignment:
        raise could_not_save(SAVE_FAILED_MESSAGE)

    return _assignment_out(_find_active(assignment.id), _students_by_id())


@router.put("/{assignment_id}", response_model=AssignmentOut)
def update_assignment(assignment_id: int, body: AssignmentIn):
    """
    Saves changes. Students who stay keep their check-offs, notes and
    grades. Other work can't become a curriculum, or the reverse.
    """

    error = _schedule_error(body)

    if error:
        raise invalid(error)

    assignment = AssignmentService.update_assignment(
        assignment_id=assignment_id,
        **_fields(body),
    )

    if not assignment:
        raise could_not_save(SAVE_FAILED_MESSAGE)

    return _assignment_out(_find_active(assignment_id), _students_by_id())


@router.post("/{assignment_id}/archive", response_model=Message)
def archive_assignment(assignment_id: int):
    """Hides it everywhere. Check-offs, notes and grades are kept."""

    if not AssignmentService.archive_assignment(assignment_id):
        raise not_found(NOT_FOUND_MESSAGE)

    return Message(message="Assignment archived.")


@router.post("/{assignment_id}/restore", response_model=AssignmentOut)
def restore_assignment(assignment_id: int):

    if not AssignmentService.restore_assignment(assignment_id):
        raise not_found(NOT_FOUND_MESSAGE)

    return _assignment_out(_find_active(assignment_id), _students_by_id())


# ----- Notes for a date -----


@router.get("/{assignment_id}/notes", response_model=list[NoteRow])
def list_notes(assignment_id: int):
    """Every date of this assignment for its active students, with any note."""

    return [
        NoteRow(
            occurrence_id=row.id,
            student=student_out(row.student),
            date=row.occurrence_date,
            notes=row.notes,
        )
        for row in AssignmentService.get_note_rows(assignment_id)
    ]


@router.put("/{assignment_id}/notes", response_model=Message)
def set_note(assignment_id: int, body: NoteIn):
    """Saves one date's note for the chosen students. Blank removes it."""

    changed = AssignmentService.set_occurrence_note(
        assignment_id,
        body.date,
        body.student_ids,
        body.note,
    )

    if changed is None:
        raise not_found(NOT_FOUND_MESSAGE)

    return Message(message="Note saved." if body.note else "Note removed.")
