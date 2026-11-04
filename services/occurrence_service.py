from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta

from database.models import (
    AssignmentOccurrence,
    AssignmentStatus,
    AssignmentType,
    RecurrencePattern,
)

# About two years, so a mistyped year can't create thousands of rows.
MAX_SCHEDULE_DAYS = 731

MONDAY_TO_FRIDAY = {0, 1, 2, 3, 4}

WEEKDAY_OF_PATTERN = {
    RecurrencePattern.EVERY_MONDAY.value: 0,
    RecurrencePattern.EVERY_TUESDAY.value: 1,
    RecurrencePattern.EVERY_WEDNESDAY.value: 2,
    RecurrencePattern.EVERY_THURSDAY.value: 3,
    RecurrencePattern.EVERY_FRIDAY.value: 4,
}


class OccurrenceService:

    @staticmethod
    def default_end_date(today):
        """
        Returns the date recurring work ends unless a parent changes it.
        """

        return date(today.year, 12, 31)

    @staticmethod
    def schedule_error(
        assignment_type,
        recurrence_pattern,
        start_date,
        end_date=None
    ):
        """
        Returns what's wrong with a schedule for showing to a parent, or
        None if it's fine.
        """

        if start_date is None:
            return "Please choose a date."

        if assignment_type != AssignmentType.RECURRING.value:
            return None

        if end_date is None:
            return "Please choose when this ends."

        if end_date < start_date:
            return "The end date can't be before the start date."

        if (end_date - start_date).days > MAX_SCHEDULE_DAYS:
            return "The end date can be at most two years after the start date."

        try:

            dates = OccurrenceService.dates_for(
                assignment_type,
                recurrence_pattern,
                start_date,
                end_date
            )

        except ValueError:

            return "Please choose a frequency."

        if not dates:
            return "This frequency doesn't fall on any date in that range."

        return None

    @staticmethod
    def is_untouched(row):
        """
        True if nobody has done anything with this occurrence yet.
        """

        return (
            row.status == AssignmentStatus.NOT_STARTED.value
            and row.completed_at is None
            and not row.notes
            and row.score is None
        )

    @staticmethod
    def sync(
        db,
        assignment,
        student_ids,
        changes_from
    ):
        """
        Brings an assignment's occurrences in line with its schedule and
        students. Adds to the caller's transaction without committing.

        Recurring work only changes from changes_from on, which is today for
        an edit, and untouched rows are the only ones removed, so history and
        anyone's work are kept. A new assignment passes date.min, so a start
        date in the past gets its past dates.

        One-time work has a single date, so a changed due date moves its row,
        keeping any progress. Work that was recurring may have several rows,
        and only touched ones stay, since unfinished one-time work stays
        overdue and old dates would all look late.
        """

        one_time = (
            assignment.assignment_type
            != AssignmentType.RECURRING.value
        )

        dates = set(
            OccurrenceService.dates_for(
                assignment.assignment_type,
                assignment.recurrence_pattern,
                assignment.due_date,
                assignment.end_date
            )
        )

        rows_by_student = defaultdict(list)

        for row in (
            db.query(AssignmentOccurrence)
            .filter(
                AssignmentOccurrence.assignment_id == assignment.id
            )
        ):
            rows_by_student[row.student_id].append(row)

        for student_id, rows in rows_by_student.items():

            for row in rows:

                untouched = OccurrenceService.is_untouched(row)

                if student_id not in student_ids:

                    if untouched and row.occurrence_date >= changes_from:
                        db.delete(row)

                elif one_time and len(rows) == 1:

                    row.occurrence_date = assignment.due_date

                elif (
                    row.occurrence_date not in dates
                    and untouched
                    and (one_time or row.occurrence_date >= changes_from)
                ):

                    db.delete(row)

        for student_id in student_ids:

            existing = {
                row.occurrence_date
                for row in rows_by_student[student_id]
            }

            for day in dates - existing:

                if one_time or day >= changes_from:

                    db.add(
                        AssignmentOccurrence(
                            assignment_id=assignment.id,
                            student_id=student_id,
                            occurrence_date=day
                        )
                    )

    @staticmethod
    def dates_for(
        assignment_type,
        recurrence_pattern,
        start_date,
        end_date=None
    ):
        """
        Returns the dates an assignment happens on, in order.

        One-time work happens once, on start_date. Recurring work runs from
        start_date through end_date, including both. Raises ValueError if a
        recurring assignment has no end date or an unknown pattern.
        """

        if assignment_type != AssignmentType.RECURRING.value:
            return [start_date]

        if end_date is None:
            raise ValueError("Recurring work needs an end date.")

        if recurrence_pattern == RecurrencePattern.MONTHLY.value:
            return OccurrenceService._monthly(start_date, end_date)

        matches = OccurrenceService._day_matcher(
            recurrence_pattern,
            start_date
        )

        return [
            start_date + timedelta(days=offset)
            for offset in range((end_date - start_date).days + 1)
            if matches(start_date + timedelta(days=offset))
        ]

    @staticmethod
    def _day_matcher(
        recurrence_pattern,
        start_date
    ):

        if recurrence_pattern == RecurrencePattern.DAILY.value:
            return lambda day: True

        if recurrence_pattern == RecurrencePattern.WEEKDAYS.value:
            return lambda day: day.weekday() in MONDAY_TO_FRIDAY

        if recurrence_pattern == RecurrencePattern.WEEKLY.value:
            weekday = start_date.weekday()

        elif recurrence_pattern in WEEKDAY_OF_PATTERN:
            weekday = WEEKDAY_OF_PATTERN[recurrence_pattern]

        else:
            raise ValueError(
                f"Unknown recurrence pattern: {recurrence_pattern}"
            )

        return lambda day: day.weekday() == weekday

    @staticmethod
    def _monthly(
        start_date,
        end_date
    ):
        """
        Keeps to start_date's day of the month, or the month's last day when
        it's shorter. Work starting on the 31st goes Jan 31, Feb 28, Mar 31.
        """

        dates = []
        year = start_date.year
        month = start_date.month

        while True:

            last_day = monthrange(year, month)[1]

            day = date(
                year,
                month,
                min(start_date.day, last_day)
            )

            if day > end_date:
                return dates

            dates.append(day)

            month += 1

            if month > 12:
                month = 1
                year += 1
