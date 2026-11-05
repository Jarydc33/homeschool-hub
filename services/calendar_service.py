# services/calendar_service.py
from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import and_
from sqlalchemy.orm import joinedload

from database.db import get_session
from database.models import (
    Assignment,
    AssignmentOccurrence,
    AssignmentType,
    Student,
    StudentAssignment,
)
from services.auth_service import AuthService
from services.event_service import EventService
from services.occurrence_service import OccurrenceService

DONE = "done"
OVERDUE = "overdue"
MISSED = "missed"
TO_DO = "to_do"
EVENT = "event"

STATUS_ICONS = {
    DONE: "✅",
    OVERDUE: "⚠️",
    MISSED: "🕓",
    TO_DO: "📋",
    EVENT: "🎉",
}


class CalendarService:

    @staticmethod
    def week_days(day):
        """
        Returns the seven dates of day's week, Sunday first.
        """

        sunday = day - timedelta(days=(day.weekday() + 1) % 7)

        return [
            sunday + timedelta(days=offset)
            for offset in range(7)
        ]

    @staticmethod
    def month_weeks(day):
        """
        Returns the weeks that show day's month, as lists of seven dates.
        The first and last can include days from the months around it.
        """

        last = date(
            day.year,
            day.month,
            monthrange(day.year, day.month)[1]
        )

        weeks = []
        current = day.replace(day=1)

        while current <= last:

            weeks.append(CalendarService.week_days(current))

            current = weeks[-1][-1] + timedelta(days=1)

        return weeks

    @staticmethod
    def shift(
        day,
        view_months,
        step
    ):
        """
        Returns the date to show after moving step weeks, or step months if
        view_months. Moving by month lands on the 1st, since not every month
        has a 31st.
        """

        if not view_months:
            return day + timedelta(days=7 * step)

        months = day.year * 12 + day.month - 1 + step

        return date(months // 12, months % 12 + 1, 1)

    @staticmethod
    def _status(
        row,
        today
    ):

        if OccurrenceService.is_complete(row):
            return DONE

        if row.occurrence_date >= today:
            return TO_DO

        if (
            row.assignment.assignment_type
            == AssignmentType.RECURRING.value
        ):
            return MISSED

        return OVERDUE

    @staticmethod
    def _work_rows(
        first,
        last,
        student_id
    ):
        """
        Returns the family's occurrences in the range, on active assignments
        and for active students still assigned to them.
        """

        family_id = AuthService.get_current_family()

        with get_session() as db:

            query = (
                db.query(AssignmentOccurrence)
                .join(AssignmentOccurrence.assignment)
                .join(AssignmentOccurrence.student)
                .join(
                    StudentAssignment,
                    and_(
                        StudentAssignment.assignment_id
                        == AssignmentOccurrence.assignment_id,
                        StudentAssignment.student_id
                        == AssignmentOccurrence.student_id
                    )
                )
                .options(
                    joinedload(
                        AssignmentOccurrence.assignment
                    ).joinedload(
                        Assignment.subject
                    ),
                    joinedload(AssignmentOccurrence.student)
                )
                .filter(
                    AssignmentOccurrence.occurrence_date >= first,
                    AssignmentOccurrence.occurrence_date <= last,
                    Assignment.family_id == family_id,
                    Assignment.active.is_(True),
                    Student.family_id == family_id,
                    Student.active.is_(True)
                )
            )

            if student_id is not None:

                query = query.filter(
                    AssignmentOccurrence.student_id == student_id
                )

            return query.all()

    @staticmethod
    def get_items(
        first,
        last,
        student_id=None
    ):
        """
        Returns {date: items} for what's scheduled from first through last,
        with events first on each date. A student only ever gets their own
        and the whole family's, whatever is asked for. A parent gets everyone,
        or one student if student_id is given.

        Each item is {"status", "title", "detail", "student"}. Student is who
        the work belongs to, and None for an event.
        """

        if AuthService.is_student():

            student_id = AuthService.get_current_student()

        elif not AuthService.is_parent():

            return {}

        today = AuthService.get_today()

        items = defaultdict(list)

        for event in EventService.get_visible_events(student_id):

            detail = (
                EventService.clock(event.start_time)
                if event.start_time
                else "All day"
            )

            for day in EventService.dates_in_range(event, first, last):

                items[day].append(
                    {
                        "status": EVENT,
                        "title": event.title,
                        "detail": detail,
                        "student": None,
                        "_order": (
                            0,
                            (
                                event.start_time.isoformat()
                                if event.start_time
                                else ""
                            ),
                            event.title,
                        ),
                    }
                )

        for row in CalendarService._work_rows(first, last, student_id):

            title = OccurrenceService.work_title(row)

            items[row.occurrence_date].append(
                {
                    "status": CalendarService._status(row, today),
                    "title": title,
                    "detail": row.assignment.subject.name,
                    "student": row.student.name,
                    "_order": (1, row.student.name, title),
                }
            )

        for day_items in items.values():

            day_items.sort(key=lambda item: item["_order"])

            for item in day_items:
                del item["_order"]

        return dict(items)

    @staticmethod
    def label(
        item,
        show_student
    ):
        """
        Returns an item for reading, such as "📋 Saxon Math: Lesson 47 (Ann)".
        """

        text = f"{STATUS_ICONS[item['status']]} {item['title']}"

        if show_student and item["student"]:
            text += f" ({item['student']})"

        return text
