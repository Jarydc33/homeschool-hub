from calendar import monthrange
from datetime import date, timedelta

from database.models import AssignmentType, RecurrencePattern

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
