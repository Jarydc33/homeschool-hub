# services/achievement_service.py
from collections import defaultdict
from datetime import timedelta

from database.models import AssignmentType
from services.occurrence_service import OccurrenceService

# Weeks with fewer scheduled days than this are too light to count as perfect.
PERFECT_WEEK_MIN_DAYS = 3

COMPLETED_BADGES = [
    (1, "👣", "First Step", "Finish your first piece of work"),
    (10, "🌱", "Getting Going", "Finish 10 pieces of work"),
    (50, "💪", "Hard Worker", "Finish 50 pieces of work"),
    (100, "💯", "Century Club", "Finish 100 pieces of work"),
    (250, "🏔️", "Mountain Climber", "Finish 250 pieces of work"),
]

STREAK_BADGES = [
    (3, "🔥", "On a Roll", "Reach a 3-day streak"),
    (5, "🖐️", "High Five", "Reach a 5-day streak"),
    (10, "🎯", "Perfect Ten", "Reach a 10-day streak"),
    (30, "🚀", "Unstoppable", "Reach a 30-day streak"),
]


class AchievementService:
    """
    Streaks and badges are worked out from a student's occurrences when read,
    never stored, so they stay right when a date moves or work gets caught up.
    """

    @staticmethod
    def summary(
        rows,
        today
    ):
        """
        Returns a student's {"streak", "best_streak", "badges"}. Each row
        needs its assignment loaded. Each badge is {"key", "icon", "name",
        "description", "earned"}.
        """

        current, best = AchievementService._streaks(rows, today)

        return {
            "streak": current,
            "best_streak": best,
            "badges": AchievementService._badges(rows, today, best),
        }

    @staticmethod
    def newly_earned(
        before,
        after
    ):
        """
        Returns the badges earned in the summary after that weren't in before.
        """

        earned_before = {
            badge["key"]
            for badge in before["badges"]
            if badge["earned"]
        }

        return [
            badge
            for badge in after["badges"]
            if badge["earned"] and badge["key"] not in earned_before
        ]

    @staticmethod
    def _days_done(
        rows,
        today
    ):
        """
        Returns {date: everything dated that day is complete}, up to today.
        """

        days = defaultdict(lambda: True)

        for row in rows:

            if row.occurrence_date <= today:

                days[row.occurrence_date] = (
                    days[row.occurrence_date]
                    and OccurrenceService.is_complete(row)
                )

        return dict(days)

    @staticmethod
    def _streaks(
        rows,
        today
    ):
        """
        Returns (current streak, best streak), in days with work on them.

        A day counts once all its work is done, whenever that happens, so
        catching up repairs a streak. Days with no work don't count or break
        it, including a day cleared by shifting the schedule. Today can only
        add to a streak, since there's still time to finish.
        """

        days = AchievementService._days_done(rows, today)

        if not days.get(today, True):
            del days[today]

        current = 0
        best = 0

        for day in sorted(days):

            current = current + 1 if days[day] else 0

            best = max(best, current)

        return current, best

    @staticmethod
    def _has_perfect_week(
        rows,
        today
    ):
        """
        True if every day of a finished Monday-to-Sunday week was done, with
        enough scheduled days for it to mean something.
        """

        weeks = defaultdict(list)

        for day, done in AchievementService._days_done(rows, today).items():

            monday = day - timedelta(days=day.weekday())

            weeks[monday].append(done)

        return any(
            monday + timedelta(days=6) < today
            and len(days) >= PERFECT_WEEK_MIN_DAYS
            and all(days)
            for monday, days in weeks.items()
        )

    @staticmethod
    def _curriculum_progress(rows):
        """
        Returns the highest share of lessons done on any one curriculum, from
        0 to 1.
        """

        lessons = defaultdict(list)

        for row in rows:

            if (
                row.assignment.assignment_type
                == AssignmentType.CURRICULUM.value
            ):

                lessons[row.assignment_id].append(
                    OccurrenceService.is_complete(row)
                )

        return max(
            (sum(done) / len(done) for done in lessons.values()),
            default=0
        )

    @staticmethod
    def _badges(
        rows,
        today,
        best_streak
    ):

        completed = sum(
            1
            for row in rows
            if OccurrenceService.is_complete(row)
        )

        curriculum = AchievementService._curriculum_progress(rows)

        badges = [
            (f"completed_{goal}", icon, name, description, completed >= goal)
            for goal, icon, name, description in COMPLETED_BADGES
        ]

        badges += [
            (f"streak_{goal}", icon, name, description, best_streak >= goal)
            for goal, icon, name, description in STREAK_BADGES
        ]

        badges += [
            (
                "perfect_week",
                "🌟",
                "Perfect Week",
                "Finish everything in a full week of school",
                AchievementService._has_perfect_week(rows, today),
            ),
            (
                "halfway",
                "⛰️",
                "Halfway There",
                "Finish half the lessons in a curriculum",
                curriculum >= 0.5,
            ),
            (
                "finisher",
                "🎓",
                "Book Finished",
                "Finish every lesson in a curriculum",
                curriculum == 1,
            ),
        ]

        return [
            {
                "key": key,
                "icon": icon,
                "name": name,
                "description": description,
                "earned": earned,
            }
            for key, icon, name, description, earned in badges
        ]
