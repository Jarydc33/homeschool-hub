# services/pe_service.py
from collections import Counter
from datetime import timedelta

from database.db import get_session
from database.models import (
    ActivityLog,
    Student,
)
from services.auth_service import AuthService

# Ten hours, so a typo can't wreck a student's totals.
MAX_MINUTES = 600

MAX_ACTIVITY_LENGTH = 100

HOUR_BADGES = [
    (10, "🏃", "On the Move", "Log 10 hours of P.E."),
    (50, "🚴", "Going the Distance", "Log 50 hours of P.E."),
    (100, "🥇", "100 Hours Strong", "Log 100 hours of P.E."),
]


class PEService:
    """
    Totals and badges are worked out from the logs when read. A log entered
    by mistake is deleted, not archived: it's a correction, not a record
    anyone needs to keep.
    """

    @staticmethod
    def _usable_student_ids(
        db,
        student_ids
    ):
        """
        Returns which of these students the current user can log for: a
        student only themselves, and a parent any active student in their
        family.
        """

        requested = set(student_ids)

        if AuthService.is_student():

            return requested & {AuthService.get_current_student()}

        if not AuthService.is_parent() or not requested:
            return set()

        return {
            student_id
            for (student_id,) in (
                db.query(Student.id)
                .filter(
                    Student.id.in_(requested),
                    Student.family_id == AuthService.get_current_family(),
                    Student.active.is_(True)
                )
            )
        }

    @staticmethod
    def log_error(
        log_date,
        activity,
        minutes
    ):
        """
        Returns what's wrong with an activity for showing, or None.
        """

        if log_date is None:
            return "Please choose a date."

        if log_date > AuthService.get_today():
            return "You can't log an activity for a future date."

        if not (activity or "").strip():
            return "Please enter an activity."

        if len(activity.strip()) > MAX_ACTIVITY_LENGTH:
            return "Please use a shorter activity name."

        if minutes is None or not 1 <= minutes <= MAX_MINUTES:
            return f"Please enter between 1 and {MAX_MINUTES} minutes."

        return None

    @staticmethod
    def log_activity(
        student_ids,
        log_date,
        activity,
        minutes
    ):
        """
        Saves the activity once for each student, in one commit. Returns how
        many were saved, or None if it isn't valid or any student isn't
        available to the current user.
        """

        if not student_ids or PEService.log_error(
            log_date,
            activity,
            minutes
        ):
            return None

        with get_session() as db:

            usable = PEService._usable_student_ids(db, student_ids)

            if usable != set(student_ids):
                return None

            for student_id in usable:

                db.add(
                    ActivityLog(
                        family_id=AuthService.get_current_family(),
                        student_id=student_id,
                        log_date=log_date,
                        activity=activity.strip(),
                        minutes=minutes
                    )
                )

            db.commit()

            return len(usable)

    @staticmethod
    def get_logs(student_id):
        """
        Returns a student's activities, newest first. Nothing if they aren't
        available to the current user.
        """

        with get_session() as db:

            if not PEService._usable_student_ids(db, [student_id]):
                return []

            return (
                db.query(ActivityLog)
                .filter(
                    ActivityLog.student_id == student_id,
                    ActivityLog.family_id == AuthService.get_current_family()
                )
                .order_by(
                    ActivityLog.log_date.desc(),
                    ActivityLog.id.desc()
                )
                .all()
            )

    @staticmethod
    def delete_log(log_id):
        """
        Deletes a mistaken entry. Returns True, or False if it isn't available
        to the current user.
        """

        with get_session() as db:

            log = (
                db.query(ActivityLog)
                .filter(
                    ActivityLog.id == log_id,
                    ActivityLog.family_id == AuthService.get_current_family()
                )
                .first()
            )

            if not log or not PEService._usable_student_ids(
                db,
                [log.student_id]
            ):
                return False

            db.delete(log)
            db.commit()

            return True

    @staticmethod
    def known_activities(logs):
        """
        Returns the activity names already used, most used first, so they can
        be picked again. Names differing only in capitals count as one.
        """

        counts = Counter()
        spelling = {}

        for log in logs:

            key = log.activity.lower()

            counts[key] += 1

            spelling.setdefault(key, log.activity)

        return [
            spelling[key]
            for key, _ in sorted(
                counts.items(),
                key=lambda item: (-item[1], item[0])
            )
        ]

    @staticmethod
    def describe_minutes(minutes):
        """
        Returns a length of time for reading, such as "1 hr 30 min".
        """

        hours, rest = divmod(minutes, 60)

        if not hours:
            return f"{rest} min"

        if not rest:
            return f"{hours} hr"

        return f"{hours} hr {rest} min"

    @staticmethod
    def logs_between(
        logs,
        first,
        last
    ):
        """
        Returns the logs dated from first through last.
        """

        return [
            log
            for log in logs
            if first <= log.log_date <= last
        ]

    @staticmethod
    def summary(
        logs,
        today
    ):
        """
        Returns a student's {"minutes_this_week", "active_days_this_week",
        "total_minutes", "badges"}. Weeks start on Sunday, like the calendar.
        """

        week_start = today - timedelta(days=(today.weekday() + 1) % 7)

        this_week = PEService.logs_between(logs, week_start, today)

        total = sum(log.minutes for log in logs)

        return {
            "minutes_this_week": sum(log.minutes for log in this_week),
            "active_days_this_week": len(
                {log.log_date for log in this_week}
            ),
            "total_minutes": total,
            "badges": [
                {
                    "key": f"pe_hours_{goal}",
                    "icon": icon,
                    "name": name,
                    "description": description,
                    "earned": total >= goal * 60,
                }
                for goal, icon, name, description in HOUR_BADGES
            ],
        }
