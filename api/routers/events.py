from datetime import date, time

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.auth import require_parent, signed_in
from api.errors import could_not_save, invalid, not_found
from api.schemas import EventEntry, EventOut, LongText, Title, event_entry, event_out
from services.current_user import CurrentUser
from services.event_service import EventService

router = APIRouter(prefix="/events", tags=["events"])

NOT_FOUND_MESSAGE = "This event could not be found."

SAVE_FAILED_MESSAGE = (
    "This event couldn't be saved. Check its students, then try again."
)


class EventList(BaseModel):
    # The next date of each upcoming event, soonest first.
    upcoming: list[EventEntry]
    # Events that are over, newest first.
    past: list[EventOut]


class EventIn(BaseModel):
    title: Title
    start_date: date
    description: LongText | None = None
    end_date: date | None = None
    start_time: time | None = None
    # "Weekly", "Every Day", ... or none for a one-off.
    recurrence_pattern: str | None = Field(default=None, max_length=50)
    repeat_until: date | None = None
    # None or empty means the whole family, including students added later.
    student_ids: list[int] = Field(default_factory=list, max_length=100)


def _schedule_error(body):

    return EventService.schedule_error(
        body.start_date,
        body.end_date,
        body.recurrence_pattern,
        body.repeat_until,
    )


def _fields(body):

    return dict(
        title=body.title,
        start_date=body.start_date,
        description=body.description or None,
        end_date=body.end_date,
        start_time=body.start_time,
        recurrence_pattern=body.recurrence_pattern or None,
        repeat_until=body.repeat_until,
        student_ids=body.student_ids,
    )


def _saved(event_id):
    """Reads a saved event back with its students loaded."""

    event = EventService.get_event_by_id(event_id)

    if not event:
        raise not_found(NOT_FOUND_MESSAGE)

    return event_out(event)


@router.get("", response_model=EventList)
def list_events(student_id: int | None = None, user=Depends(signed_in)):
    """
    The events the current user can see. A student only ever gets their
    own and the whole family's; a parent can narrow to one student.
    """

    upcoming, past = EventService.split_by_date(
        EventService.get_visible_events(student_id),
        CurrentUser.get_today(),
    )

    return EventList(
        upcoming=[event_entry(entry) for entry in upcoming],
        past=[event_out(event) for event in past],
    )


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: int, user=Depends(require_parent)):

    return _saved(event_id)


@router.post("", response_model=EventOut, status_code=201)
def create_event(body: EventIn, user=Depends(require_parent)):

    error = _schedule_error(body)

    if error:
        raise invalid(error)

    event = EventService.create_event(**_fields(body))

    if not event:
        raise could_not_save(SAVE_FAILED_MESSAGE)

    return _saved(event.id)


@router.put("/{event_id}", response_model=EventOut)
def update_event(event_id: int, body: EventIn, user=Depends(require_parent)):
    """Changes apply to every date of a repeating event."""

    error = _schedule_error(body)

    if error:
        raise invalid(error)

    event = EventService.update_event(event_id=event_id, **_fields(body))

    if not event:
        raise could_not_save(SAVE_FAILED_MESSAGE)

    return _saved(event_id)


@router.post("/{event_id}/archive", response_model=EventOut)
def archive_event(event_id: int, user=Depends(require_parent)):

    event = EventService.get_event_by_id(event_id)

    if not event or not EventService.archive_event(event_id):
        raise not_found(NOT_FOUND_MESSAGE)

    return event_out(event)
