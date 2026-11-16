# services/hours_service.py
from collections import defaultdict

from sqlalchemy.orm import joinedload

from database.db import get_session
from database.models import (
    Assignment,
    AssignmentOccurrence,
    AssignmentStatus,
    Student,
)
from services.current_user import CurrentUser
from services.pe_service import PEService

# Ten hours, like P.E., so a typo can't wreck a student's totals.
MAX_MINUTES = 600

# Passed to an update to leave its minutes as they are, since None clears
# them.
KEEP = object()


class HoursService:
    """
    Hours come from the minutes saved on each day's finished work, plus P.E.
    logs. Minutes are saved when work is checked off (the assignment's time,
    else its subject's usual time), so changing a subject later doesn't
    rewrite past hours. Totals are worked out when read.

    Work counts on its scheduled date, like grades. Archived assignments and
    subjects still count, so tidying up doesn't change a past record.
    """

    # ----- Minutes -----

    @staticmethod
    def minutes_error(
        minutes,
        allow_zero=False
    ):
        """
        Returns a friendly message if minutes aren't usable, or None. Empty
        is fine wherever this is used: it means no time.
        """

        if minutes is None:
            return None

        lowest = 0 if allow_zero else 1

        if (
            not isinstance(minutes, int)
            or isinstance(minutes, bool)
            or not lowest <= minutes <= MAX_MINUTES
        ):
            return f"Minutes must be a whole number from {lowest} to {MAX_MINUTES}."

        return None

    @staticmethod
    def minutes_for(assignment):
        """
        The minutes a day of this work counts: its own, else its subject's
        usual time, else None. Needs its subject loaded.
        """

        if assignment.minutes is not None:
            return assignment.minutes

        if assignment.subject is not None:
            return assignment.subject.default_minutes

        return None

    @staticmethod
    def apply_check_off(
        occurrence,
        was_complete
    ):
        """
        Saves or clears an occurrence's minutes as it's checked on or off.
        Checking off work that was already done keeps any minutes a parent
        set. Needs its assignment and subject loaded.
        """

        complete = occurrence.status == AssignmentStatus.COMPLETE.value

        if not complete:
            occurrence.minutes = None

        elif not was_complete:
            occurrence.minutes = HoursService.minutes_for(occurrence.assignment)

    @staticmethod
    def set_minutes(
        occurrence_id,
        minutes
    ):
        """
        A parent adjusts the minutes on a day's finished work (0 for none).
        Returns the row, or None if the minutes aren't valid, the work isn't
        checked off, or it isn't available to this parent.
        """

        if minutes is None or HoursService.minutes_error(minutes, allow_zero=True):
            return None

        if not CurrentUser.is_parent():
            return None

        family_id = CurrentUser.get_family_id()

        with get_session() as db:

            row = (
                db.query(AssignmentOccurrence)
                .join(AssignmentOccurrence.assignment)
                .join(AssignmentOccurrence.student)
                .filter(
                    AssignmentOccurrence.id == occurrence_id,
                    Assignment.family_id == family_id,
                    Student.family_id == family_id,
                    Student.active.is_(True)
                )
                .first()
            )

            if not row or row.status != AssignmentStatus.COMPLETE.value:
                return None

            row.minutes = minutes

            db.commit()
            db.refresh(row)

            return row

    # ----- Reading -----

    @staticmethod
    def _can_view_student(
        db,
        student_id
    ):
        """
        True for a student's own hours, or a parent viewing an active student
        in their family.
        """

        if CurrentUser.is_student():
            return student_id == CurrentUser.get_student_id()

        if not CurrentUser.is_parent():
            return False

        return (
            db.query(Student.id)
            .filter(
                Student.id == student_id,
                Student.family_id == CurrentUser.get_family_id(),
                Student.active.is_(True)
            )
            .first()
            is not None
        )

    @staticmethod
    def get_rows(
        student_id,
        start,
        end
    ):
        """
        Returns a student's finished work with minutes, dated start to end
        (inclusive), with its assignment and subject loaded. Includes archived
        assignments. Nothing if the student isn't available to this user.
        """

        with get_session() as db:

            if not HoursService._can_view_student(db, student_id):
                return []

            return (
                db.query(AssignmentOccurrence)
                .join(AssignmentOccurrence.assignment)
                .options(
                    joinedload(
                        AssignmentOccurrence.assignment
                    ).joinedload(
                        Assignment.subject
                    )
                )
                .filter(
                    AssignmentOccurrence.student_id == student_id,
                    Assignment.family_id == CurrentUser.get_family_id(),
                    AssignmentOccurrence.status
                    == AssignmentStatus.COMPLETE.value,
                    AssignmentOccurrence.minutes.isnot(None),
                    AssignmentOccurrence.occurrence_date >= start,
                    AssignmentOccurrence.occurrence_date <= end
                )
                .order_by(
                    AssignmentOccurrence.occurrence_date.desc(),
                    AssignmentOccurrence.id
                )
                .all()
            )

    @staticmethod
    def get_pe_logs(
        student_id,
        start,
        end
    ):
        """A student's P.E. logs dated start to end (inclusive)."""

        return PEService.logs_between(
            PEService.get_logs(student_id),
            start,
            end
        )

    # ----- Totals -----

    @staticmethod
    def summary(
        rows,
        pe_logs
    ):
        """
        Totals for a stretch of days, from get_rows and get_pe_logs:
        {"total_minutes", "core_minutes", "pe_minutes", "school_days",
        "subjects": [{"subject", "minutes", "pe"}], most minutes first, with
        P.E. logs as one line with "pe" True and no subject, and "days": [{"date", "minutes", "work",
        "pe"}], newest first}. A school day is a date with any time counted.
        """

        subject_minutes = defaultdict(int)
        subjects = {}
        days = defaultdict(lambda: {"minutes": 0, "work": [], "pe": []})

        core = 0

        for row in rows:

            subject = row.assignment.subject
            key = subject.id if subject else None

            subjects[key] = subject
            subject_minutes[key] += row.minutes

            if subject is not None and subject.is_core:
                core += row.minutes

            day = days[row.occurrence_date]
            day["minutes"] += row.minutes
            day["work"].append(row)

        pe = 0

        for log in pe_logs:

            pe += log.minutes

            day = days[log.log_date]
            day["minutes"] += log.minutes
            day["pe"].append(log)

        lines = [
            {"subject": subjects[key], "minutes": minutes, "pe": False}
            for key, minutes in subject_minutes.items()
        ]

        if pe:
            lines.append({"subject": None, "minutes": pe, "pe": True})

        lines.sort(key=lambda line: -line["minutes"])

        return {
            "total_minutes": sum(day["minutes"] for day in days.values()),
            "core_minutes": core,
            "pe_minutes": pe,
            "school_days": sum(
                1 for day in days.values() if day["minutes"] > 0
            ),
            "subjects": lines,
            "days": [
                {"date": date, **days[date]}
                for date in sorted(days, reverse=True)
            ],
        }
