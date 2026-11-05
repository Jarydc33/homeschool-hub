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

# How far back the dashboard lists completed and missed work, so a student can
# undo a mistake or catch up without the lists growing all year. Progress still
# counts everything.
RECENT_DAYS = 30

MONDAY_TO_FRIDAY = {0, 1, 2, 3, 4}

# In weekday order, so Monday is 0 like date.weekday().
SCHOOL_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

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
        end_date=None,
        lesson_count=None
    ):
        """
        Returns what's wrong with a schedule for showing to a parent, or
        None if it's fine.
        """

        if start_date is None:
            return "Please choose a date."

        if assignment_type == AssignmentType.CURRICULUM.value:

            return OccurrenceService._curriculum_error(
                recurrence_pattern,
                start_date,
                lesson_count
            )

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
    def _curriculum_error(
        school_days,
        start_date,
        lesson_count
    ):

        if not lesson_count or lesson_count < 1:
            return "Please enter how many lessons there are."

        if not OccurrenceService.parse_school_days(school_days):
            return "Please choose at least one school day."

        too_long = (
            "At this pace the lessons would run more than two years. "
            "Try more school days or fewer lessons."
        )

        if lesson_count > MAX_SCHEDULE_DAYS:
            return too_long

        last = OccurrenceService.lesson_dates(
            school_days,
            start_date,
            lesson_count
        )[-1]

        if (last - start_date).days > MAX_SCHEDULE_DAYS:
            return too_long

        return None

    @staticmethod
    def parse_school_days(school_days):
        """
        Returns the weekday numbers in a value like "Mon,Tue", leaving out
        anything that isn't a day.
        """

        return {
            SCHOOL_DAY_NAMES.index(name.strip())
            for name in (school_days or "").split(",")
            if name.strip() in SCHOOL_DAY_NAMES
        }

    @staticmethod
    def school_days_value(days):
        """
        Returns chosen day names as saved, in weekday order: "Mon,Tue".
        """

        return ",".join(
            name
            for name in SCHOOL_DAY_NAMES
            if name in days
        )

    @staticmethod
    def lesson_dates(
        school_days,
        start_date,
        count,
        taken=()
    ):
        """
        Returns the next count school days from start_date on, skipping any
        dates in taken. Needs at least one valid school day.
        """

        weekdays = OccurrenceService.parse_school_days(school_days)

        if not weekdays:
            raise ValueError("A curriculum needs school days.")

        dates = []
        day = start_date

        while len(dates) < count:

            if day.weekday() in weekdays and day not in taken:
                dates.append(day)

            day += timedelta(days=1)

        return dates

    @staticmethod
    def lesson_count(assignment):
        """
        Returns how many lessons a curriculum has. Needs its occurrences
        loaded.
        """

        return max(
            (row.lesson_number or 0 for row in assignment.occurrences),
            default=0
        )

    @staticmethod
    def last_lesson_date(assignment):
        """
        Returns when a curriculum finishes, going by whichever student
        finishes last. Needs its occurrences loaded.
        """

        return max(
            (row.occurrence_date for row in assignment.occurrences),
            default=None
        )

    @staticmethod
    def work_title(row):
        """
        Returns what to call an occurrence's work. Needs its assignment loaded.
        """

        if row.lesson_number:
            return f"{row.assignment.title}: Lesson {row.lesson_number}"

        return row.assignment.title

    @staticmethod
    def is_complete(row):

        return row.status == AssignmentStatus.COMPLETE.value

    @staticmethod
    def group_for_student(
        rows,
        today
    ):
        """
        Sorts a student's occurrences into what the dashboards show. Each
        row needs its assignment loaded.

        A past recurring date that wasn't finished is missed, not overdue,
        so a week away doesn't leave a pile of late work. Upcoming only has
        the next date of each assignment, so Every Day work doesn't fill the
        page with the rest of the year.
        """

        groups = {
            "completed": [],
            "overdue": [],
            "today": [],
            "upcoming": [],
            "missed": [],
        }

        upcoming_assignments = set()

        for row in sorted(rows, key=lambda r: r.occurrence_date):

            if OccurrenceService.is_complete(row):

                groups["completed"].append(row)

            elif row.occurrence_date == today:

                groups["today"].append(row)

            elif row.occurrence_date > today:

                if row.assignment_id not in upcoming_assignments:

                    upcoming_assignments.add(row.assignment_id)

                    groups["upcoming"].append(row)

            elif (
                row.assignment.assignment_type
                == AssignmentType.RECURRING.value
            ):

                groups["missed"].append(row)

            else:

                groups["overdue"].append(row)

        groups["completed"].reverse()
        groups["missed"].reverse()

        return groups

    @staticmethod
    def recently_completed(
        completed_rows,
        today
    ):
        """
        Returns the rows checked off in the last 30 days, newest first. It
        goes by when the work was checked off, so catching up on an old date
        still shows. A row with no completion time goes by its date.
        """

        def finished_on(row):

            if row.completed_at:
                return row.completed_at.date()

            return row.occurrence_date

        cutoff = today - timedelta(days=RECENT_DAYS)

        return sorted(
            (
                row
                for row in completed_rows
                if finished_on(row) >= cutoff
            ),
            key=finished_on,
            reverse=True
        )

    @staticmethod
    def recently_missed(
        missed_rows,
        today
    ):
        """
        Returns the missed rows dated in the last 30 days, keeping their order.
        """

        cutoff = today - timedelta(days=RECENT_DAYS)

        return [
            row
            for row in missed_rows
            if row.occurrence_date >= cutoff
        ]

    @staticmethod
    def progress(groups):
        """
        Returns a student's totals from group_for_student. Work that isn't
        due yet doesn't count until it's done, so a year of recurring dates
        doesn't make the percent look low.
        """

        completed = len(groups["completed"])

        remaining = len(groups["overdue"]) + len(groups["today"])

        total = completed + remaining + len(groups["missed"])

        return {
            "completed": completed,
            "remaining": remaining,
            "total": total,
            "percent": round(completed / total * 100) if total else 0,
        }

    @staticmethod
    def assignment_progress(
        assignment,
        today
    ):
        """
        Returns (done, total) for one assignment across its current students.
        Needs its student_assignments and occurrences loaded. One-time work
        counts students. Recurring work counts dates so far.
        """

        current_students = {
            link.student_id
            for link in assignment.student_assignments
        }

        rows = [
            row
            for row in assignment.occurrences
            if row.student_id in current_students
        ]

        if assignment.assignment_type == AssignmentType.RECURRING.value:

            rows = [
                row
                for row in rows
                if row.occurrence_date <= today
                or OccurrenceService.is_complete(row)
            ]

        done = sum(
            1
            for row in rows
            if OccurrenceService.is_complete(row)
        )

        return done, len(rows)

    @staticmethod
    def default_note_date(
        dates,
        today
    ):
        """
        Returns which of the sorted dates to offer first: the next one from
        today on, or the last one if they've all passed.
        """

        return next(
            (day for day in dates if day >= today),
            dates[-1]
        )

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
    def _is_started(row):
        """
        True if a student has worked on this lesson. A note alone doesn't
        count, since a parent's note on a lesson should move with it.
        """

        return (
            row.status != AssignmentStatus.NOT_STARTED.value
            or row.completed_at is not None
            or row.score is not None
        )

    @staticmethod
    def step_aside(
        db,
        rows
    ):
        """
        Gives rows about to move a temporary far-off date. A lesson can't take
        a date another lesson still holds, even for a moment. Adds to the
        caller's transaction without committing.
        """

        for offset, row in enumerate(rows):

            row.occurrence_date = (
                date(9000, 1, 1) + timedelta(days=offset)
            )

        db.flush()

    @staticmethod
    def recovery_moves(
        rows,
        school_days,
        resume_on
    ):
        """
        Returns [(row, new date)] for picking one student's curriculum back up
        on resume_on. Every lesson not started is laid out again in order,
        including late ones, around the lessons that stay. Rows whose date
        wouldn't change are left out.
        """

        pending = sorted(
            (
                row
                for row in rows
                if not OccurrenceService._is_started(row)
            ),
            key=lambda row: row.lesson_number
        )

        dates = OccurrenceService.lesson_dates(
            school_days,
            resume_on,
            len(pending),
            {
                row.occurrence_date
                for row in rows
                if OccurrenceService._is_started(row)
            }
        )

        return [
            (row, day)
            for row, day in zip(pending, dates)
            if row.occurrence_date != day
        ]

    @staticmethod
    def _sync_curriculum(
        db,
        assignment,
        student_ids,
        changes_from,
        lesson_count,
        reschedule
    ):
        """
        Brings a curriculum's lessons in line with its schedule, for each
        student separately. Adds to the caller's transaction without
        committing.

        Lessons a student has started never move. When reschedule is True,
        the rest from changes_from on are laid out again, in order. Otherwise
        dates stay as they are, and any new lessons go after the student's
        last one. Lowering the lesson count only removes untouched lessons.
        """

        rows_by_student = defaultdict(list)

        for row in (
            db.query(AssignmentOccurrence)
            .filter(
                AssignmentOccurrence.assignment_id == assignment.id
            )
        ):
            rows_by_student[row.student_id].append(row)

        placements = []

        for student_id, rows in rows_by_student.items():

            if student_id not in student_ids:

                for row in rows:

                    if (
                        OccurrenceService.is_untouched(row)
                        and row.occurrence_date >= changes_from
                    ):
                        db.delete(row)

        for student_id in student_ids:

            kept = []

            for row in rows_by_student[student_id]:

                if (
                    row.lesson_number > lesson_count
                    and OccurrenceService.is_untouched(row)
                ):
                    db.delete(row)

                else:
                    kept.append(row)

            moving = [
                row
                for row in kept
                if reschedule
                and not OccurrenceService._is_started(row)
                and row.occurrence_date >= changes_from
            ]

            staying = [
                row
                for row in kept
                if row not in moving
            ]

            start = max(assignment.due_date, changes_from)

            if not reschedule and kept:

                start = max(
                    start,
                    max(row.occurrence_date for row in kept)
                    + timedelta(days=1)
                )

            new_numbers = set(range(1, lesson_count + 1)) - {
                row.lesson_number
                for row in kept
            }

            lessons = sorted(
                [(row.lesson_number, row) for row in moving]
                + [(number, None) for number in new_numbers],
                key=lambda lesson: lesson[0]
            )

            dates = OccurrenceService.lesson_dates(
                assignment.recurrence_pattern,
                start,
                len(lessons),
                {row.occurrence_date for row in staying}
            )

            for (number, row), day in zip(lessons, dates):
                placements.append((student_id, number, row, day))

        OccurrenceService.step_aside(
            db,
            [row for _, _, row, _ in placements if row is not None]
        )

        for student_id, number, row, day in placements:

            if row is not None:

                row.occurrence_date = day

            else:

                db.add(
                    AssignmentOccurrence(
                        assignment_id=assignment.id,
                        student_id=student_id,
                        occurrence_date=day,
                        lesson_number=number
                    )
                )

    @staticmethod
    def sync(
        db,
        assignment,
        student_ids,
        changes_from,
        lesson_count=None,
        reschedule=False
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

        A curriculum goes by lesson instead of by date, so lesson_count and
        reschedule only apply to it. See _sync_curriculum.
        """

        if assignment.assignment_type == AssignmentType.CURRICULUM.value:

            OccurrenceService._sync_curriculum(
                db,
                assignment,
                student_ids,
                changes_from,
                lesson_count,
                reschedule
            )

            return

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
