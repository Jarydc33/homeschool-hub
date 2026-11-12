from datetime import date, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.auth import signed_in
from api.errors import invalid
from services.calendar_service import CalendarService

router = APIRouter(prefix="/calendar", tags=["calendar"])

# A month view shows up to six weeks; this leaves room for that.
MAX_DAYS = 62


class CalendarItem(BaseModel):
    # The work's status, or "event".
    status: str
    title: str
    detail: str | None
    # Whose work it is; None for an event.
    student: str | None


class CalendarDay(BaseModel):
    date: date
    items: list[CalendarItem]


@router.get("", response_model=list[CalendarDay])
def calendar(
    first: date,
    last: date,
    student_id: int | None = None,
    user=Depends(signed_in),
):
    """
    What's scheduled from first through last, events first on each date. A
    student only ever gets their own and the whole family's; a parent gets
    everyone, or one student.
    """

    if last < first:
        raise invalid("The last date must be on or after the first.")

    if last - first > timedelta(days=MAX_DAYS):
        raise invalid(f"Please ask for {MAX_DAYS} days or fewer at a time.")

    items = CalendarService.get_items(first, last, student_id)

    return [
        CalendarDay(
            date=day,
            items=[CalendarItem(**item) for item in items.get(day, [])],
        )
        for day in sorted(items)
    ]
