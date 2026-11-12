"""
What the API sends back. These are plain data, built from the ORM objects
the services return, so the app never depends on database details.
"""
from datetime import date, datetime, time
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from services.event_service import EventService
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
    birth_year: int | None = None


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


class Badge(BaseModel):
    key: str
    icon: str
    name: str
    description: str
    earned: bool


class Achievements(BaseModel):
    streak: int
    best_streak: int
    badges: list[Badge]


class ReadingSummary(BaseModel):
    streak: int
    best_streak: int
    pages_this_week: int
    total_pages: int
    books_finished: int
    badges: list[Badge]


class PESummary(BaseModel):
    minutes_this_week: int
    active_days_this_week: int
    total_minutes: int
    badges: list[Badge]


class EventOut(BaseModel):
    id: int
    title: str
    description: str | None
    start_date: date
    end_date: date | None
    start_time: time | None
    recurrence_pattern: str | None
    repeat_until: date | None
    student_ids: list[int]
    audience: str


class EventEntry(BaseModel):
    """One date of an event, as a list shows it."""

    event: EventOut
    date: date
    when: str


class Banner(BaseModel):
    id: int
    title: str
    message: str
    start_date: date | None
    end_date: date | None
    system_wide: bool


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
    recently_completed: list[WorkItem]
    recently_missed: list[WorkItem]
    achievements: Achievements
    reading: ReadingSummary
    pe: PESummary
    upcoming_events: list[EventEntry]
    banners: list[Banner]


class CheckOff(BaseModel):
    completed: bool


class CheckOffResult(BaseModel):
    work: WorkItem
    new_badges: list[Badge]


class Message(BaseModel):
    """A plain answer, such as "PIN saved."."""

    message: str


# Text people type, trimmed. A required one can't be blank.
Name = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]
Title = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
LongText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=5000),
]


def student_out(student):

    return StudentOut(
        id=student.id,
        name=student.name,
        grade_level=student.grade_level,
        birth_year=student.birth_year,
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


def event_out(event):
    """Needs the event's student links, and their students, loaded."""

    return EventOut(
        id=event.id,
        title=event.title,
        description=event.description,
        start_date=event.start_date,
        end_date=event.end_date,
        start_time=event.start_time,
        recurrence_pattern=event.recurrence_pattern,
        repeat_until=event.repeat_until,
        student_ids=sorted(link.student_id for link in event.event_students),
        audience=EventService.audience(event),
    )


def event_entry(entry):
    """An {"event", "date"} entry from EventService."""

    return EventEntry(
        event=event_out(entry["event"]),
        date=entry["date"],
        when=EventService.describe_when(entry["event"], entry["date"]),
    )


def banner(row):

    return Banner(
        id=row.id,
        title=row.title,
        message=row.message,
        start_date=row.start_date,
        end_date=row.end_date,
        system_wide=row.family_id is None,
    )
