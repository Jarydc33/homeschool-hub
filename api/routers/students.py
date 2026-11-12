from datetime import datetime

from fastapi import APIRouter, Depends
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from api.auth import require_parent, signed_in
from api.errors import could_not_save, invalid, not_found
from api.schemas import (
    Achievements,
    Message,
    Name,
    PESummary,
    Progress,
    ReadingSummary,
    StudentDashboard,
    StudentOut,
    banner,
    event_entry,
    student_out,
    work_item,
)
from services.account_service import AccountService
from services.achievement_service import AchievementService
from services.banner_service import BannerService
from services.current_user import CurrentUser
from services.daily_message_service import DailyMessageService
from services.event_service import EventService
from services.occurrence_service import OccurrenceService
from services.pairing_service import PairingService
from services.pe_service import PEService
from services.reading_service import ReadingService
from services.student_service import StudentService
from services.user_service import UserService

router = APIRouter(prefix="/students", tags=["students"])

NOT_FOUND_MESSAGE = "This student could not be found."


class StudentIn(BaseModel):
    name: Name
    grade_level: str | None = Field(default=None, max_length=50)
    birth_year: int | None = Field(default=None, ge=1990, le=2100)


class StudentLogin(BaseModel):
    """A student's login email, or None if they don't have one."""

    email: str | None


class EmailIn(BaseModel):
    # AccountService checks that it looks like an email.
    email: Annotated[str, StringConstraints(strip_whitespace=True, max_length=254)]


class PairingCodeOut(BaseModel):
    code: str
    expires_at: datetime


# ----- Listing -----


@router.get("", response_model=list[StudentOut])
def list_students(user=Depends(signed_in)):
    """
    A parent gets the family's active students; a student gets only
    themselves.
    """

    if CurrentUser.is_student():

        # The service lists the whole family, which the Streamlit pages
        # never show a student.

        student = StudentService.get_student_by_id(
            CurrentUser.get_student_id()
        )

        return [student_out(student)] if student else []

    return [
        student_out(student)
        for student in StudentService.get_current_family_students()
    ]


@router.get("/archived", response_model=list[StudentOut])
def list_archived(user=Depends(require_parent)):

    return [
        student_out(student)
        for student in StudentService.get_archived_students()
    ]


# ----- Changing students (parents) -----


@router.post("", response_model=StudentOut, status_code=201)
def create_student(body: StudentIn, user=Depends(require_parent)):

    student = StudentService.create_student(
        name=body.name,
        grade_level=body.grade_level,
        birth_year=body.birth_year,
    )

    if not student:
        raise could_not_save()

    return student_out(student)


@router.put("/{student_id}", response_model=StudentOut)
def update_student(student_id: int, body: StudentIn, user=Depends(require_parent)):

    student = StudentService.update_student(
        student_id=student_id,
        name=body.name,
        grade_level=body.grade_level,
        birth_year=body.birth_year,
    )

    if not student:
        raise not_found(NOT_FOUND_MESSAGE)

    return student_out(student)


@router.post("/{student_id}/archive", response_model=StudentOut)
def archive_student(student_id: int, user=Depends(require_parent)):
    """
    Hides a student and blocks their login and paired devices. Their work
    and grades are kept, and restoring brings everything back.
    """

    student = StudentService.archive_student(student_id)

    if not student:
        raise not_found(NOT_FOUND_MESSAGE)

    return student_out(student)


@router.post("/{student_id}/restore", response_model=StudentOut)
def restore_student(student_id: int, user=Depends(require_parent)):

    student = StudentService.restore_student(student_id)

    if not student:
        raise not_found(NOT_FOUND_MESSAGE)

    return student_out(student)


# ----- Student logins (parents) -----


def _active_student(student_id):

    student = StudentService.get_student_by_id(student_id)

    if not student or not student.active:
        raise not_found(NOT_FOUND_MESSAGE)

    return student


@router.get("/{student_id}/login", response_model=StudentLogin)
def get_login(student_id: int, user=Depends(require_parent)):

    _active_student(student_id)

    login = UserService.get_user_by_student_id(
        student_id,
        CurrentUser.get_family_id(),
    )

    return StudentLogin(email=login.email if login else None)


@router.post("/{student_id}/login", response_model=Message)
def invite_student(student_id: int, body: EmailIn, user=Depends(require_parent)):
    """Emails the student an invitation to set a password."""

    _active_student(student_id)

    invited, message = AccountService.invite_student(student_id, body.email)

    if not invited:
        raise invalid(message)

    return Message(message=message)


@router.put("/{student_id}/login", response_model=Message)
def change_login_email(student_id: int, body: EmailIn, user=Depends(require_parent)):

    _active_student(student_id)

    updated, message = AccountService.update_student_email(student_id, body.email)

    if not updated:
        raise invalid(message)

    return Message(message=message)


@router.post("/{student_id}/pairing-code", response_model=PairingCodeOut)
def create_pairing_code(student_id: int, user=Depends(require_parent)):
    """
    A one-time 6-digit code that pairs a student's own device. It works
    for 10 minutes.
    """

    code, expires_at, message = PairingService.create_code(student_id)

    if not code:
        raise invalid(message)

    return PairingCodeOut(code=code, expires_at=expires_at)


# ----- The student dashboard -----


@router.get("/{student_id}/dashboard", response_model=StudentDashboard)
def student_dashboard(student_id: int, user=Depends(signed_in)):
    """
    Everything the Student Dashboard shows: work grouped by when it's due,
    today's progress, streaks and badges, reading, P.E., events and
    announcements. Parents can open any of their students; a student only
    their own.
    """

    student = StudentService.get_student_by_id(student_id)

    if not student or not student.active:
        raise not_found(NOT_FOUND_MESSAGE)

    today = CurrentUser.get_today()

    rows = StudentService.get_student_occurrences(student_id)

    groups = OccurrenceService.group_for_student(rows, today)

    done, total = OccurrenceService.today_progress(groups, today)

    achievements = AchievementService.summary(rows, today)

    reading = ReadingService.summary(ReadingService.get_books(student_id), today)

    pe = PEService.summary(PEService.get_logs(student_id), today)

    return StudentDashboard(
        student=student_out(student),
        today=today,
        message=DailyMessageService.get_message(today),
        progress=Progress(done=done, total=total),
        overdue=[work_item(row) for row in groups["overdue"]],
        today_work=[work_item(row) for row in groups["today"]],
        completed_today=[
            work_item(row)
            for row in groups["completed"]
            if row.occurrence_date == today
        ],
        upcoming=[work_item(row) for row in groups["upcoming"]],
        missed=[work_item(row) for row in groups["missed"]],
        recently_completed=[
            work_item(row)
            for row in OccurrenceService.recently_completed(groups["completed"], today)
        ],
        recently_missed=[
            work_item(row)
            for row in OccurrenceService.recently_missed(groups["missed"], today)
        ],
        achievements=Achievements(**achievements),
        reading=ReadingSummary(**reading),
        pe=PESummary(**pe),
        upcoming_events=[
            event_entry(entry)
            for entry in EventService.get_upcoming(today, student_id)
        ],
        banners=[banner(row) for row in BannerService.get_active_banners()],
    )
