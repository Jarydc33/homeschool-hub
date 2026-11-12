from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.auth import signed_in
from api.errors import could_not_save, invalid, not_found
from api.schemas import Message, Name, PESummary
from services.current_user import CurrentUser
from services.pe_service import PEService

# Students log their own activity; parents any of their students'.
router = APIRouter(tags=["pe"], dependencies=[Depends(signed_in)])


class ActivityOut(BaseModel):
    id: int
    student_id: int
    date: date
    activity: str
    minutes: int


class PELog(BaseModel):
    logs: list[ActivityOut]
    summary: PESummary
    # Activity names already used, most used first, to suggest.
    known_activities: list[str]


class ActivityIn(BaseModel):
    student_ids: list[int] = Field(min_length=1, max_length=100)
    date: date
    activity: Name
    minutes: int


class Saved(BaseModel):
    saved: int


@router.get("/students/{student_id}/pe", response_model=PELog)
def pe_log(student_id: int):
    """A student's activities, newest first, with this week's totals and badges."""

    logs = PEService.get_logs(student_id)

    return PELog(
        logs=[
            ActivityOut(
                id=log.id,
                student_id=log.student_id,
                date=log.log_date,
                activity=log.activity,
                minutes=log.minutes,
            )
            for log in logs
        ],
        summary=PESummary(**PEService.summary(logs, CurrentUser.get_today())),
        known_activities=PEService.known_activities(logs),
    )


@router.post("/pe", response_model=Saved, status_code=201)
def log_activity(body: ActivityIn):
    """Saves one activity for each chosen student, all at once."""

    error = PEService.log_error(body.date, body.activity, body.minutes)

    if error:
        raise invalid(error)

    saved = PEService.log_activity(
        body.student_ids,
        body.date,
        body.activity,
        body.minutes,
    )

    if saved is None:
        raise could_not_save()

    return Saved(saved=saved)


@router.delete("/pe/{log_id}", response_model=Message)
def delete_activity(log_id: int):
    """
    Deletes a mistaken entry. Deleted, not archived, since it's a
    correction rather than a record.
    """

    if not PEService.delete_log(log_id):
        raise not_found("This activity could not be found.")

    return Message(message="Activity deleted.")
