# services/event_service.py
from datetime import timedelta

from sqlalchemy.orm import selectinload

from database.db import get_session
from database.models import (
    AssignmentType,
    Event,
    EventStudent,
    RecurrencePattern,
    Student,
)
from services.auth_service import AuthService
from services.occurrence_service import (
    MAX_SCHEDULE_DAYS,
    OccurrenceService,
)

# How far ahead the dashboards look.
UPCOMING_DAYS = 30

REPEAT_OPTIONS = [
    RecurrencePattern.DAILY.value,
    RecurrencePattern.WEEKLY.value,
    RecurrencePattern.MONTHLY.value,
    RecurrencePattern.WEEKDAYS.value,
    RecurrencePattern.EVERY_MONDAY.value,
    RecurrencePattern.EVERY_TUESDAY.value,
    RecurrencePattern.EVERY_WEDNESDAY.value,
    RecurrencePattern.EVERY_THURSDAY.value,
    RecurrencePattern.EVERY_FRIDAY.value,
]


class EventService:
    """
    A repeating event's dates are worked out when read. An event with no
    student links is for the whole family, including students added later.
    """

    @staticmethod
    def schedule_error(
        start_date,
        end_date=None,
        recurrence_pattern=None,
        repeat_until=None
    ):
        """
        Returns what's wrong with an event's dates for showing to a parent,
        or None if they're fine.
        """

        if start_date is None:
            return "Please choose a date."

        if not recurrence_pattern:

            if end_date is not None and end_date < start_date:
                return "The last day can't be before the first day."

            if (
                end_date is not None
                and (end_date - start_date).days > MAX_SCHEDULE_DAYS
            ):
                return "An event can be at most two years long."

            return None

        if recurrence_pattern not in REPEAT_OPTIONS:
            return "Please choose how often this repeats."

        if repeat_until is None:
            return "Please choose when this stops repeating."

        if repeat_until < start_date:
            return "It can't stop repeating before its first date."

        if (repeat_until - start_date).days > MAX_SCHEDULE_DAYS:
            return "An event can repeat for at most two years."

        if not EventService._repeat_dates(
            start_date,
            recurrence_pattern,
            repeat_until
        ):
            return "That repeat doesn't fall on any date in that range."

        return None

    @staticmethod
    def _repeat_dates(
        start_date,
        recurrence_pattern,
        repeat_until
    ):

        return OccurrenceService.dates_for(
            AssignmentType.RECURRING.value,
            recurrence_pattern,
            start_date,
            repeat_until
        )

    @staticmethod
    def next_date(
        event,
        today
    ):
        """
        Returns the date to show an event under: its next repeat, or its
        first day if it hasn't finished. None once it's over.
        """

        if event.recurrence_pattern:

            return next(
                (
                    day
                    for day in EventService._repeat_dates(
                        event.start_date,
                        event.recurrence_pattern,
                        event.repeat_until
                    )
                    if day >= today
                ),
                None
            )

        if (event.end_date or event.start_date) >= today:
            return event.start_date

        return None

    @staticmethod
    def describe_when(
        event,
        day
    ):
        """
        Returns an event's date for reading, such as "Tue, Nov 10 at 2:00 PM"
        or "Mon, Nov 9 to Fri, Nov 13".
        """

        def short(value):
            return f"{value:%a, %b} {value.day}"

        text = short(day)

        if event.end_date and event.end_date != day:
            text += f" to {short(event.end_date)}"

        if event.start_time:

            text += f" at {EventService.clock(event.start_time)}"

        return text

    @staticmethod
    def clock(value):
        """
        Returns a time for reading, such as "2:00 PM".
        """

        return f"{value:%I:%M %p}".lstrip("0")

    @staticmethod
    def dates_in_range(
        event,
        first,
        last
    ):
        """
        Returns every date an event happens on from first through last.
        """

        if event.recurrence_pattern:

            return [
                day
                for day in EventService._repeat_dates(
                    event.start_date,
                    event.recurrence_pattern,
                    event.repeat_until
                )
                if first <= day <= last
            ]

        start = max(event.start_date, first)
        end = min(event.end_date or event.start_date, last)

        return [
            start + timedelta(days=offset)
            for offset in range((end - start).days + 1)
        ]

    @staticmethod
    def audience(event):
        """
        Returns who an event is for, for reading. Needs its student links
        loaded.
        """

        if not event.event_students:
            return "Whole family"

        names = sorted(
            link.student.name
            for link in event.event_students
            if link.student.active
        )

        return ", ".join(names) or "Archived students only"

    @staticmethod
    def _active_family_student_ids(
        db,
        family_id
    ):

        return {
            student_id
            for (student_id,) in (
                db.query(Student.id)
                .filter(
                    Student.family_id == family_id,
                    Student.active.is_(True)
                )
            )
        }

    @staticmethod
    def create_event(
        title,
        start_date,
        description=None,
        end_date=None,
        start_time=None,
        recurrence_pattern=None,
        repeat_until=None,
        student_ids=()
    ):
        """
        Returns the new event, or None if a parent can't make it: its details
        aren't valid, or a student isn't an active part of this family. No
        students means the whole family. Saved in one commit.
        """

        if not AuthService.is_parent():
            return None

        title = (title or "").strip()

        if (
            not title
            or EventService.schedule_error(
                start_date,
                end_date,
                recurrence_pattern,
                repeat_until
            )
        ):
            return None

        family_id = (
            AuthService.get_current_family()
        )

        with get_session() as db:

            requested_ids = set(student_ids)

            if not requested_ids <= (
                EventService._active_family_student_ids(db, family_id)
            ):
                return None

            event = Event(
                family_id=family_id,
                title=title,
                description=(description or "").strip() or None,
                start_date=start_date,
                end_date=None if recurrence_pattern else end_date,
                start_time=start_time,
                recurrence_pattern=recurrence_pattern or None,
                repeat_until=repeat_until if recurrence_pattern else None,
                event_students=[
                    EventStudent(student_id=student_id)
                    for student_id in requested_ids
                ]
            )

            db.add(event)
            db.commit()
            db.refresh(event)

            return event

    @staticmethod
    def update_event(
        event_id,
        title,
        start_date,
        description=None,
        end_date=None,
        start_time=None,
        recurrence_pattern=None,
        repeat_until=None,
        student_ids=()
    ):
        """
        Returns the updated event, or None if it can't be saved. Only student
        links that changed are added or removed. Links to archived students
        stay, since they aren't offered as choices, unless the event becomes
        for the whole family.
        """

        if not AuthService.is_parent():
            return None

        title = (title or "").strip()

        if (
            not title
            or EventService.schedule_error(
                start_date,
                end_date,
                recurrence_pattern,
                repeat_until
            )
        ):
            return None

        family_id = (
            AuthService.get_current_family()
        )

        with get_session() as db:

            event = (
                db.query(Event)
                .options(
                    selectinload(Event.event_students)
                )
                .filter(
                    Event.id == event_id,
                    Event.family_id == family_id
                )
                .first()
            )

            if not event:
                return None

            requested_ids = set(student_ids)

            active_ids = EventService._active_family_student_ids(
                db,
                family_id
            )

            linked_ids = {
                link.student_id
                for link in event.event_students
            }

            if not (requested_ids - linked_ids) <= active_ids:
                return None

            event.title = title
            event.description = (description or "").strip() or None
            event.start_date = start_date
            event.end_date = None if recurrence_pattern else end_date
            event.start_time = start_time
            event.recurrence_pattern = recurrence_pattern or None
            event.repeat_until = (
                repeat_until if recurrence_pattern else None
            )

            for link in list(event.event_students):

                if not requested_ids or (
                    link.student_id in active_ids
                    and link.student_id not in requested_ids
                ):
                    event.event_students.remove(link)

            for student_id in requested_ids - linked_ids:

                event.event_students.append(
                    EventStudent(student_id=student_id)
                )

            db.commit()
            db.refresh(event)

            return event

    @staticmethod
    def archive_event(event_id):
        """
        Hides an event everywhere. Returns it, or None if it isn't available
        to this parent.
        """

        if not AuthService.is_parent():
            return None

        with get_session() as db:

            event = (
                db.query(Event)
                .filter(
                    Event.id == event_id,
                    Event.family_id == AuthService.get_current_family()
                )
                .first()
            )

            if not event:
                return None

            event.active = False

            db.commit()

            return event

    @staticmethod
    def get_event_by_id(event_id):
        """
        Returns one of this family's active events, for a parent to edit.
        """

        if not AuthService.is_parent():
            return None

        with get_session() as db:

            return (
                EventService._active_events(db)
                .filter(Event.id == event_id)
                .first()
            )

    @staticmethod
    def _active_events(db):

        return (
            db.query(Event)
            .options(
                selectinload(Event.event_students)
                .joinedload(EventStudent.student)
            )
            .filter(
                Event.family_id == AuthService.get_current_family(),
                Event.active.is_(True)
            )
        )

    @staticmethod
    def get_visible_events(student_id=None):
        """
        Returns the active events the current user can see. A student only
        ever gets their own and the whole family's, whatever is asked for.
        A parent gets them all, or one student's if student_id is given.
        """

        if AuthService.is_student():

            student_id = AuthService.get_current_student()

        elif not AuthService.is_parent():

            return []

        with get_session() as db:

            events = EventService._active_events(db).all()

        if student_id is None:
            return events

        return [
            event
            for event in events
            if not event.event_students
            or any(
                link.student_id == student_id
                for link in event.event_students
            )
        ]

    @staticmethod
    def split_by_date(
        events,
        today
    ):
        """
        Returns (upcoming, past). Upcoming is {"event", "date"}, soonest
        first, and has only the next date of a repeating event, so a daily
        event doesn't fill the page. Past is events that are over, newest
        first.
        """

        upcoming = []
        past = []

        for event in events:

            day = EventService.next_date(event, today)

            if day is None:
                past.append(event)

            else:
                upcoming.append({"event": event, "date": day})

        # All-day events first on a date, then by time.
        upcoming.sort(
            key=lambda entry: (
                entry["date"],
                (
                    entry["event"].start_time.isoformat()
                    if entry["event"].start_time
                    else ""
                ),
                entry["event"].title
            )
        )

        past.sort(
            key=lambda event: (
                event.repeat_until
                or event.end_date
                or event.start_date
            ),
            reverse=True
        )

        return upcoming, past

    @staticmethod
    def get_upcoming(
        today,
        student_id=None
    ):
        """
        Returns the {"event", "date"} entries a dashboard shows: what's
        visible to the current user, in the next 30 days.
        """

        cutoff = today + timedelta(days=UPCOMING_DAYS)

        upcoming, _ = EventService.split_by_date(
            EventService.get_visible_events(student_id),
            today
        )

        return [
            entry
            for entry in upcoming
            if entry["date"] <= cutoff
        ]
