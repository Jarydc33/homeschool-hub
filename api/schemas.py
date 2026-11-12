"""
What the API sends back. These are plain data, built from the ORM objects
the services return, so the app never depends on database details.
"""
from datetime import date, datetime

from pydantic import BaseModel

from services.occurrence_service import OccurrenceService


class Me(BaseModel):
    role: str
    family_id: int | None
    family_name: str | None
    timezone: str | None
    student_id: int | None
    student_mode: bool
    paired_device: bool
    today: date


class StudentOut(BaseModel):
    id: int
    name: str
    grade_level: str | None


class SubjectOut(BaseModel):
    id: int
    name: str
    color: str | None


class WorkItem(BaseModel):
    """One day of one assignment for one student."""

    occurrence_id: int
    assignment_id: int
    title: str
    subject: SubjectOut | None
    date: date
    completed: bool
    completed_at: datetime | None
    notes: str | None
    lesson_number: int | None


class Progress(BaseModel):
    done: int
    total: int


class StudentDashboard(BaseModel):
    student: StudentOut
    today: date
    message: str
    progress: Progress
    overdue: list[WorkItem]
    today_work: list[WorkItem]
    completed_today: list[WorkItem]
    upcoming: list[WorkItem]
    missed: list[WorkItem]


class CheckOff(BaseModel):
    completed: bool


def student_out(student):

    return StudentOut(
        id=student.id,
        name=student.name,
        grade_level=student.grade_level,
    )


def work_item(row):
    """Needs the row's assignment and its subject loaded."""

    subject = row.assignment.subject

    return WorkItem(
        occurrence_id=row.id,
        assignment_id=row.assignment_id,
        title=OccurrenceService.work_title(row),
        subject=(
            SubjectOut(id=subject.id, name=subject.name, color=subject.color)
            if subject
            else None
        ),
        date=row.occurrence_date,
        completed=OccurrenceService.is_complete(row),
        completed_at=row.completed_at,
        notes=row.notes,
        lesson_number=row.lesson_number,
    )
