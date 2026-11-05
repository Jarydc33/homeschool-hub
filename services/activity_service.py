# services/activity_service.py
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import and_
from sqlalchemy.orm import joinedload

from database.db import get_session
from database.models import (
    Assignment,
    AssignmentOccurrence,
    AssignmentStatus,
    Book,
    ReadingLog,
    Student,
    StudentAssignment,
)
from services.auth_service import AuthService
from services.occurrence_service import OccurrenceService

RECENT_DAYS = 7

MOST_ITEMS = 20


class ActivityService:
    """
    Recent activity is worked out from what's already saved, when read.
    """

    @staticmethod
    def _finished_work(
        db,
        family_id,
        first_day,
        zone
    ):
        """
        Returns (day, time checked off, text) for work finished since
        first_day. Completion times are saved in UTC, so the day is worked
        out in the family's time zone.
        """

        cutoff = (
            datetime.combine(first_day, time.min, zone)
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )

        rows = (
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
                joinedload(AssignmentOccurrence.assignment),
                joinedload(AssignmentOccurrence.student)
            )
            .filter(
                AssignmentOccurrence.status
                == AssignmentStatus.COMPLETE.value,
                AssignmentOccurrence.completed_at >= cutoff,
                Assignment.family_id == family_id,
                Assignment.active.is_(True),
                Student.family_id == family_id,
                Student.active.is_(True)
            )
            .all()
        )

        return [
            (
                row.completed_at
                .replace(tzinfo=timezone.utc)
                .astimezone(zone)
                .date(),
                row.completed_at.isoformat(),
                f"✅ {row.student.name} finished "
                f"**{OccurrenceService.work_title(row)}**"
            )
            for row in rows
        ]

    @staticmethod
    def _reading(
        db,
        family_id,
        first_day
    ):
        """
        Returns (day, "", text) for pages logged and books finished since
        first_day. Reading has a date but no time.
        """

        logs = (
            db.query(ReadingLog)
            .join(ReadingLog.book)
            .join(Book.student)
            .options(
                joinedload(ReadingLog.book).joinedload(Book.student)
            )
            .filter(
                ReadingLog.log_date >= first_day,
                Book.family_id == family_id,
                Book.active.is_(True),
                Student.active.is_(True)
            )
            .all()
        )

        finished = (
            db.query(Book)
            .join(Book.student)
            .options(
                joinedload(Book.student)
            )
            .filter(
                Book.finished_on >= first_day,
                Book.family_id == family_id,
                Book.active.is_(True),
                Student.active.is_(True)
            )
            .all()
        )

        entries = []

        for log in logs:

            pages = (
                "1 page"
                if log.pages == 1
                else f"{log.pages} pages"
            )

            entries.append(
                (
                    log.log_date,
                    "",
                    f"📖 {log.book.student.name} read {pages} of "
                    f"**{log.book.title}**"
                )
            )

        for book in finished:

            entries.append(
                (
                    book.finished_on,
                    "",
                    f"🎉 {book.student.name} finished the book "
                    f"**{book.title}**"
                )
            )

        return entries

    @staticmethod
    def get_recent(today):
        """
        Returns [(day, [text])] for what this family's students did in the
        last 7 days, newest day first, with at most 20 items in all. Within a
        day, check-offs come first, newest first, then reading. Only for
        parents.
        """

        if not AuthService.is_parent():
            return []

        family_id = AuthService.get_current_family()

        first_day = today - timedelta(days=RECENT_DAYS - 1)

        with get_session() as db:

            entries = (
                ActivityService._finished_work(
                    db,
                    family_id,
                    first_day,
                    AuthService.get_zone()
                )
                + ActivityService._reading(
                    db,
                    family_id,
                    first_day
                )
            )

        # Text first ascending, then the rest descending, keeps reading in a
        # steady order within a day.
        entries.sort(key=lambda entry: entry[2])
        entries.sort(key=lambda entry: entry[:2], reverse=True)

        grouped = []

        for day, _, text in entries[:MOST_ITEMS]:

            if not grouped or grouped[-1][0] != day:
                grouped.append((day, []))

            grouped[-1][1].append(text)

        return grouped

    @staticmethod
    def day_label(
        day,
        today
    ):
        """
        Returns a day for reading, such as "Today" or "Mon, Nov 2".
        """

        if day == today:
            return "Today"

        if day == today - timedelta(days=1):
            return "Yesterday"

        return f"{day:%a, %b} {day.day}"
