from datetime import date, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.auth import require_parent, signed_in
from api.errors import invalid, not_found
from api.schemas import Message, SubjectOut
from services.current_user import CurrentUser
from services.hours_service import MAX_MINUTES, HoursService
from services.occurrence_service import OccurrenceService
from services.student_service import StudentService

router = APIRouter(tags=["hours"])

STUDENT_NOT_FOUND = "This student could not be found."

WORK_NOT_FOUND = "This work could not be found, or it isn't checked off yet."

# The longest stretch one report covers, so a typo can't ask for centuries.
MAX_DAYS = 3 * 366


class HoursLine(BaseModel):
    """One subject's time, or all P.E. logs together."""

    subject: SubjectOut | None
    # The subject's name, or "P.E." for the P.E. log.
    name: str
    is_core: bool
    pe: bool
    minutes: int


class HoursWork(BaseModel):
    occurrence_id: int
    title: str
    subject: SubjectOut | None
    minutes: int


class HoursActivity(BaseModel):
    activity: str
    minutes: int


class HoursDay(BaseModel):
    date: date
    minutes: int
    work: list[HoursWork]
    pe: list[HoursActivity]


class HoursReport(BaseModel):
    start: date
    end: date
    total_minutes: int
    # Time on subjects marked core; P.E. logs aren't core.
    core_minutes: int
    pe_minutes: int
    # Dates with any time counted.
    school_days: int
    # Most time first.
    subjects: list[HoursLine]
    # Newest first.
    days: list[HoursDay]


class MinutesIn(BaseModel):
    # 0 counts the work as no time.
    minutes: int = Field(ge=0, le=MAX_MINUTES)


def _subject_out(subject):

    if subject is None:
        return None

    return SubjectOut(id=subject.id, name=subject.name, color=subject.color)


@router.get("/students/{student_id}/hours", response_model=HoursReport)
def hours(
    student_id: int,
    start: date | None = None,
    end: date | None = None,
    user=Depends(signed_in),
):
    """
    A student's hours from start to end (both included): finished work's
    minutes and P.E. logs, by subject and by day. Leaving dates out gives
    this week so far (weeks start on Sunday). Students see their own;
    parents any of theirs.
    """

    if not StudentService.get_student_by_id(student_id):
        raise not_found(STUDENT_NOT_FOUND)

    today = CurrentUser.get_today()

    end = end or today
    start = start or today - timedelta(days=(today.weekday() + 1) % 7)

    if start > end:
        raise invalid("The start date must be on or before the end date.")

    if (end - start).days > MAX_DAYS:
        raise invalid("Choose a stretch of three years or less.")

    summary = HoursService.summary(
        HoursService.get_rows(student_id, start, end),
        HoursService.get_pe_logs(student_id, start, end),
    )

    return HoursReport(
        start=start,
        end=end,
        total_minutes=summary["total_minutes"],
        core_minutes=summary["core_minutes"],
        pe_minutes=summary["pe_minutes"],
        school_days=summary["school_days"],
        subjects=[
            HoursLine(
                subject=_subject_out(line["subject"]),
                name=(
                    "P.E."
                    if line["pe"]
                    else line["subject"].name if line["subject"] else "No subject"
                ),
                is_core=bool(line["subject"] and line["subject"].is_core),
                pe=line["pe"],
                minutes=line["minutes"],
            )
            for line in summary["subjects"]
        ],
        days=[
            HoursDay(
                date=day["date"],
                minutes=day["minutes"],
                work=[
                    HoursWork(
                        occurrence_id=row.id,
                        title=OccurrenceService.work_title(row),
                        subject=_subject_out(row.assignment.subject),
                        minutes=row.minutes,
                    )
                    for row in day["work"]
                ],
                pe=[
                    HoursActivity(activity=log.activity, minutes=log.minutes)
                    for log in day["pe"]
                ],
            )
            for day in summary["days"]
        ],
    )


@router.put("/occurrences/{occurrence_id}/minutes", response_model=Message)
def set_minutes(occurrence_id: int, body: MinutesIn, user=Depends(require_parent)):
    """
    Adjusts the minutes counted for one day of finished work. Unchecking the
    work clears them; checking it off again uses the usual time.
    """

    if not HoursService.set_minutes(occurrence_id, body.minutes):
        raise not_found(WORK_NOT_FOUND)

    return Message(message="Minutes saved.")
