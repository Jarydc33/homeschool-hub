# services/grade_service.py
from datetime import timedelta
from statistics import fmean

from sqlalchemy import and_
from sqlalchemy.orm import joinedload

from database.db import get_session
from database.models import (
    Assignment,
    AssignmentOccurrence,
    GradingPeriod,
    Student,
    StudentAssignment,
)
from services.current_user import CurrentUser
from services.occurrence_service import OccurrenceService

# Fits the database column.
MAX_POINTS = 9999

# Extra credit is fine, but a score this far over the total is a typo.
MAX_SCORE_MULTIPLE = 2

DEFAULT_POINTS = 100

# How far around today to offer work that isn't checked off for grading.
UNFINISHED_DAYS_BACK = 30
UNFINISHED_DAYS_AHEAD = 7

LETTER_MINIMUMS = [
    (90, "A"),
    (80, "B"),
    (70, "C"),
    (60, "D"),
]


class GradeService:
    """
    Percentages and letters are worked out when read, never stored. Work with
    no score never counts, not even as zero.

    Archived assignments and subjects still count, so tidying up finished work
    doesn't change a past semester's grade. That's a deliberate exception to
    leaving archived rows out.
    """

    # ----- Working out grades -----

    @staticmethod
    def percent(row):
        """
        Returns a scored row's percentage.
        """

        return float(row.score) / float(row.points_possible) * 100

    @staticmethod
    def letter(percent):
        """
        Returns the letter for a percentage, going by the rounded number so
        that a grade shown as 90% is always an A.
        """

        for minimum, letter in LETTER_MINIMUMS:

            if round(percent) >= minimum:
                return letter

        return "F"

    @staticmethod
    def describe(percent):
        """
        Returns a grade for reading, such as "92% (A)".
        """

        return f"{round(percent)}% ({GradeService.letter(percent)})"

    @staticmethod
    def rows_in_period(
        rows,
        period
    ):
        """
        Returns the rows dated within a period. No period means all of them.
        """

        if period is None:
            return list(rows)

        return [
            row
            for row in rows
            if period.start_date <= row.occurrence_date <= period.end_date
        ]

    @staticmethod
    def subject_percents(rows):
        """
        Returns {subject name: average percent}. Each item counts equally, so
        18/20 and 45/50 weigh the same. Rows need their assignment and subject
        loaded.
        """

        by_subject = {}

        for row in rows:

            by_subject.setdefault(
                row.assignment.subject.name,
                []
            ).append(GradeService.percent(row))

        return {
            name: fmean(percents)
            for name, percents in sorted(by_subject.items())
        }

    @staticmethod
    def overall_percent(subject_percents):
        """
        Returns the average across subjects, so a subject with lots of work
        doesn't outweigh the others. None if there's nothing to average.
        """

        if not subject_percents:
            return None

        return fmean(subject_percents.values())

    @staticmethod
    def comparison(
        rows,
        periods
    ):
        """
        Returns {"subjects": {name: {period id: percent}}, "overall": {period
        id: percent}} across periods. A period with no grades is left out.
        """

        subjects = {}
        overall = {}

        for period in periods:

            percents = GradeService.subject_percents(
                GradeService.rows_in_period(rows, period)
            )

            for name, percent in percents.items():

                subjects.setdefault(name, {})[period.id] = percent

            if percents:

                overall[period.id] = GradeService.overall_percent(percents)

        return {
            "subjects": dict(sorted(subjects.items())),
            "overall": overall,
        }

    # ----- Reading grades -----

    @staticmethod
    def _can_view_student(
        db,
        student_id
    ):
        """
        True for a student's own grades, or a parent viewing an active student
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
    def get_graded_rows(student_id):
        """
        Returns a student's scored work on graded assignments, newest first,
        including archived assignments. Nothing if they aren't available to
        the current user.
        """

        with get_session() as db:

            if not GradeService._can_view_student(db, student_id):
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
                    AssignmentOccurrence.score.isnot(None),
                    AssignmentOccurrence.points_possible.isnot(None),
                    Assignment.family_id == CurrentUser.get_family_id(),
                    Assignment.graded.is_(True)
                )
                .order_by(
                    AssignmentOccurrence.occurrence_date.desc(),
                    AssignmentOccurrence.id.desc()
                )
                .all()
            )

    @staticmethod
    def get_work_to_grade(
        student_id,
        today
    ):
        """
        Returns what a parent can grade for a student, on active graded
        assignments they're still assigned to: {"finished": rows with no
        score, oldest first, "unfinished": rows not checked off, from the
        last 30 days through the next 7}. Empty for anyone but a parent.
        """

        empty = {"finished": [], "unfinished": []}

        if not CurrentUser.is_parent():
            return empty

        with get_session() as db:

            if not GradeService._can_view_student(db, student_id):
                return empty

            rows = (
                db.query(AssignmentOccurrence)
                .join(AssignmentOccurrence.assignment)
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
                    )
                )
                .filter(
                    AssignmentOccurrence.student_id == student_id,
                    AssignmentOccurrence.score.is_(None),
                    Assignment.family_id == CurrentUser.get_family_id(),
                    Assignment.active.is_(True),
                    Assignment.graded.is_(True)
                )
                .order_by(
                    AssignmentOccurrence.occurrence_date,
                    AssignmentOccurrence.id
                )
                .all()
            )

        first = today - timedelta(days=UNFINISHED_DAYS_BACK)
        last = today + timedelta(days=UNFINISHED_DAYS_AHEAD)

        return {
            "finished": [
                row
                for row in rows
                if OccurrenceService.is_complete(row)
            ],
            "unfinished": [
                row
                for row in rows
                if not OccurrenceService.is_complete(row)
                and first <= row.occurrence_date <= last
            ],
        }

    @staticmethod
    def suggested_totals(rows):
        """
        Returns {assignment id: points} to suggest for these rows: the total
        from the assignment's latest grade for anyone in the family. An
        assignment with no grades isn't included.
        """

        assignment_ids = {
            row.assignment_id
            for row in rows
        }

        if not assignment_ids:
            return {}

        with get_session() as db:

            totals = (
                db.query(
                    AssignmentOccurrence.assignment_id,
                    AssignmentOccurrence.points_possible
                )
                .join(AssignmentOccurrence.assignment)
                .filter(
                    AssignmentOccurrence.assignment_id.in_(assignment_ids),
                    AssignmentOccurrence.points_possible.isnot(None),
                    Assignment.family_id == CurrentUser.get_family_id()
                )
                .order_by(
                    AssignmentOccurrence.occurrence_date,
                    AssignmentOccurrence.id
                )
                .all()
            )

        return {
            assignment_id: float(points)
            for assignment_id, points in totals
        }

    # ----- Entering grades -----

    @staticmethod
    def grade_error(
        score,
        points_possible
    ):
        """
        Returns what's wrong with a grade for showing to a parent, or None.
        """

        if score is None or points_possible is None:
            return "Please enter the points earned and the total."

        if not 0 < points_possible <= MAX_POINTS:
            return f"The total must be between 1 and {MAX_POINTS}."

        if score < 0:
            return "The points earned can't be negative."

        if score > points_possible * MAX_SCORE_MULTIPLE or score > MAX_POINTS:
            return "That score looks too high for this total."

        return None

    @staticmethod
    def _find_row(
        db,
        occurrence_id
    ):
        """
        Returns a row this parent can grade, or None.
        """

        if not CurrentUser.is_parent():
            return None

        family_id = CurrentUser.get_family_id()

        return (
            db.query(AssignmentOccurrence)
            .join(AssignmentOccurrence.assignment)
            .join(AssignmentOccurrence.student)
            .filter(
                AssignmentOccurrence.id == occurrence_id,
                Assignment.family_id == family_id,
                Assignment.graded.is_(True),
                Student.family_id == family_id,
                Student.active.is_(True)
            )
            .first()
        )

    @staticmethod
    def set_grade(
        occurrence_id,
        score,
        points_possible
    ):
        """
        Saves a grade. It doesn't check the work off. Returns the row, or None
        if the grade isn't valid or this row isn't available to this parent.
        """

        if GradeService.grade_error(score, points_possible):
            return None

        with get_session() as db:

            row = GradeService._find_row(db, occurrence_id)

            if not row:
                return None

            row.score = score
            row.points_possible = points_possible

            db.commit()
            db.refresh(row)

            return row

    @staticmethod
    def clear_grade(occurrence_id):
        """
        Removes a grade, so the work stops counting. Returns the row, or None
        if it isn't available to this parent.
        """

        with get_session() as db:

            row = GradeService._find_row(db, occurrence_id)

            if not row:
                return None

            row.score = None
            row.points_possible = None

            db.commit()
            db.refresh(row)

            return row

    # ----- Grading periods -----

    @staticmethod
    def get_periods():
        """
        Returns this family's active periods, earliest first.
        """

        with get_session() as db:

            return (
                db.query(GradingPeriod)
                .filter(
                    GradingPeriod.family_id
                    == CurrentUser.get_family_id(),
                    GradingPeriod.active.is_(True)
                )
                .order_by(GradingPeriod.start_date)
                .all()
            )

    @staticmethod
    def period_error(
        name,
        start_date,
        end_date,
        period_id=None
    ):
        """
        Returns what's wrong with a period for showing to a parent, or None.
        Periods can't overlap, so each grade lands in exactly one.
        """

        if not (name or "").strip():
            return "Please enter a name."

        if start_date is None or end_date is None:
            return "Please choose the start and end dates."

        if end_date < start_date:
            return "The end date can't be before the start date."

        for other in GradeService.get_periods():

            if (
                other.id != period_id
                and start_date <= other.end_date
                and end_date >= other.start_date
            ):
                return f"Those dates overlap with {other.name}."

        return None

    @staticmethod
    def create_period(
        name,
        start_date,
        end_date
    ):
        """
        Returns the new period, or None if a parent can't make it.
        """

        if (
            not CurrentUser.is_parent()
            or GradeService.period_error(name, start_date, end_date)
        ):
            return None

        with get_session() as db:

            period = GradingPeriod(
                family_id=CurrentUser.get_family_id(),
                name=name.strip(),
                start_date=start_date,
                end_date=end_date
            )

            db.add(period)
            db.commit()
            db.refresh(period)

            return period

    @staticmethod
    def _find_period(
        db,
        period_id
    ):

        if not CurrentUser.is_parent():
            return None

        return (
            db.query(GradingPeriod)
            .filter(
                GradingPeriod.id == period_id,
                GradingPeriod.family_id == CurrentUser.get_family_id(),
                GradingPeriod.active.is_(True)
            )
            .first()
        )

    @staticmethod
    def update_period(
        period_id,
        name,
        start_date,
        end_date
    ):
        """
        Returns the updated period, or None if it can't be saved.
        """

        if (
            not CurrentUser.is_parent()
            or GradeService.period_error(
                name,
                start_date,
                end_date,
                period_id
            )
        ):
            return None

        with get_session() as db:

            period = GradeService._find_period(db, period_id)

            if not period:
                return None

            period.name = name.strip()
            period.start_date = start_date
            period.end_date = end_date

            db.commit()
            db.refresh(period)

            return period

    @staticmethod
    def archive_period(period_id):
        """
        Removes a period. Grades aren't touched, since they go by date.
        Returns it, or None if it isn't available to this parent.
        """

        with get_session() as db:

            period = GradeService._find_period(db, period_id)

            if not period:
                return None

            period.active = False

            db.commit()

            return period
