# services/assignment_service.py
from collections import defaultdict
from datetime import date
import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_
from sqlalchemy.orm import joinedload, selectinload
from database.db import get_session
from database.models import (
    Assignment,
    AssignmentOccurrence,
    AssignmentStatus,
    Student,
    StudentAssignment,
    Subject,
    AssignmentType
)

from services.current_user import CurrentUser
from services.occurrence_service import OccurrenceService

logger = logging.getLogger(__name__)


class AssignmentService:

    @staticmethod
    def _schedule_fields(
        assignment_type,
        recurrence_pattern,
        end_date
    ):
        """
        Returns the recurrence_pattern and end_date to save for this type.
        """

        if assignment_type == AssignmentType.RECURRING.value:
            return recurrence_pattern, end_date

        if assignment_type == AssignmentType.CURRICULUM.value:

            return (
                OccurrenceService.school_days_value(
                    recurrence_pattern.split(",")
                ),
                None
            )

        return None, None

    @staticmethod
    def get_assignment_by_id(
        assignment_id
    ):

        with get_session() as db:

            return (
                db.query(Assignment)
                .options(
                    joinedload(
                        Assignment.subject
                    ),
                    joinedload(
                        Assignment.student_assignments
                    ),
                    selectinload(
                        Assignment.occurrences
                    )
                )
                .filter(
                    Assignment.id == assignment_id,
                    Assignment.family_id
                    == CurrentUser.get_family_id()
                )
                .first()
            )

    @staticmethod
    def get_assignments_by_family(
        family_id
    ):
        """
        Returns active assignments. Their student_assignments and
        occurrences leave out archived students, so rosters, progress, and
        overdue warnings don't count them. The rows themselves are kept as
        history.
        """

        with get_session() as db:

            return (
                db.query(Assignment)
                .options(
                    joinedload(
                        Assignment.subject
                    ),

                    joinedload(
                        Assignment.student_assignments.and_(
                            StudentAssignment.student.has(
                                Student.active.is_(True)
                            )
                        )
                    ).joinedload(
                        StudentAssignment.student
                    ),

                    selectinload(
                        Assignment.occurrences.and_(
                            AssignmentOccurrence.student.has(
                                Student.active.is_(True)
                            )
                        )
                    )
                )
                .filter(
                    Assignment.family_id == family_id
                )
                .filter(
                    Assignment.active.is_(True)
                )
                .all()
            )

    @staticmethod
    def get_current_family_assignments():

        family_id = (
            CurrentUser.get_family_id()
        )

        return (
            AssignmentService.get_assignments_by_family(
                family_id
            )
        )

    @staticmethod
    def create_assignment(
        subject_id,
        title,
        student_ids,
        description=None,
        due_date=None,
        assignment_type=AssignmentType.ONE_TIME.value,
        recurrence_pattern=None,
        end_date=None,
        lesson_count=None,
        graded=False
    ):
        """
        Returns the new assignment, or None if its schedule isn't valid or
        the subject or any student is not an active part of this family.
        Its student links and occurrences are saved in the same commit.

        A curriculum passes lesson_count, with its school days as
        recurrence_pattern and its first day as due_date.
        """

        # Only parents change this, even if a page guard is ever missed.

        if not CurrentUser.is_parent():
            return None

        if OccurrenceService.schedule_error(
            assignment_type,
            recurrence_pattern,
            due_date,
            end_date,
            lesson_count
        ):
            return None

        recurrence_pattern, end_date = (
            AssignmentService._schedule_fields(
                assignment_type,
                recurrence_pattern,
                end_date
            )
        )

        family_id = (
            CurrentUser.get_family_id()
        )

        with get_session() as db:

            subject = (
                db.query(Subject)
                .filter(
                    Subject.id == subject_id,
                    Subject.family_id == family_id,
                    Subject.active.is_(True)
                )
                .first()
            )

            if not subject:
                return None

            requested_ids = set(student_ids)

            active_ids = {
                student_id
                for (student_id,) in (
                    db.query(Student.id)
                    .filter(
                        Student.family_id == family_id,
                        Student.active.is_(True)
                    )
                )
            }

            if not requested_ids <= active_ids:
                return None

            assignment = Assignment(
                family_id=family_id,
                subject_id=subject_id,
                title=title,
                description=description,
                due_date=due_date,
                assignment_type=assignment_type,
                recurrence_pattern=recurrence_pattern,
                end_date=end_date,
                graded=graded,
                student_assignments=[
                    StudentAssignment(
                        student_id=student_id
                    )
                    for student_id in requested_ids
                ]
            )

            db.add(assignment)
            db.flush()

            OccurrenceService.sync(
                db,
                assignment,
                requested_ids,
                date.min,
                lesson_count
            )

            db.commit()
            db.refresh(assignment)

            return assignment

    @staticmethod
    def update_assignment(
        assignment_id,
        title,
        description,
        due_date,
        subject_id,
        student_ids,
        assignment_type,
        recurrence_pattern,
        end_date=None,
        lesson_count=None,
        graded=None
    ):
        """
        Returns the updated assignment, or None if its schedule isn't valid
        or the assignment, subject, or any student is not available to this
        family. Other work can't become a curriculum, or the reverse.

        A curriculum's lessons only get new dates if its start date or school
        days changed, so saving a new title leaves any moved lessons alone.

        Only student links that changed are added or removed, so
        everyone else keeps their status, completion date, and notes.
        Links to archived students are left alone, since archived
        students aren't offered as choices on the edit form.
        """

        # Only parents change this, even if a page guard is ever missed.

        if not CurrentUser.is_parent():
            return None

        if OccurrenceService.schedule_error(
            assignment_type,
            recurrence_pattern,
            due_date,
            end_date,
            lesson_count
        ):
            return None

        recurrence_pattern, end_date = (
            AssignmentService._schedule_fields(
                assignment_type,
                recurrence_pattern,
                end_date
            )
        )

        family_id = (
            CurrentUser.get_family_id()
        )

        with get_session() as db:

            assignment = (
                db.query(Assignment)
                .filter(
                    Assignment.id == assignment_id,
                    Assignment.family_id == family_id
                )
                .first()
            )

            if not assignment:
                return None

            curriculum = AssignmentType.CURRICULUM.value

            if (
                (assignment.assignment_type == curriculum)
                != (assignment_type == curriculum)
            ):
                return None

            reschedule = (
                due_date != assignment.due_date
                or recurrence_pattern != assignment.recurrence_pattern
            )

            # -------------------------
            # Validate Subject
            # -------------------------

            # An archived subject may stay on an assignment that
            # already has it, but can't be newly chosen.

            if subject_id != assignment.subject_id:

                subject = (
                    db.query(Subject)
                    .filter(
                        Subject.id == subject_id,
                        Subject.family_id == family_id,
                        Subject.active.is_(True)
                    )
                    .first()
                )

                if not subject:
                    return None

            # -------------------------
            # Validate Students
            # -------------------------

            requested_ids = set(student_ids)

            active_ids = {
                student_id
                for (student_id,) in (
                    db.query(Student.id)
                    .filter(
                        Student.family_id == family_id,
                        Student.active.is_(True)
                    )
                )
            }

            links = (
                db.query(StudentAssignment)
                .filter(
                    StudentAssignment.assignment_id
                    == assignment_id
                )
                .all()
            )

            linked_ids = {
                link.student_id
                for link in links
            }

            if not (requested_ids - linked_ids) <= active_ids:
                return None

            # -------------------------
            # Update Assignment Fields
            # -------------------------

            assignment.title = title
            assignment.description = description
            assignment.due_date = due_date
            assignment.subject_id = subject_id
            assignment.assignment_type = (
                assignment_type
            )

            assignment.recurrence_pattern = (
                recurrence_pattern
            )

            assignment.end_date = end_date

            # Leaving this out keeps it as it was. Turning it off stops scores
            # counting but keeps them, in case it's turned back on.
            if graded is not None:
                assignment.graded = graded

            # -------------------------
            # Apply Student Changes
            # -------------------------

            kept_ids = set(requested_ids)

            for link in links:

                if (
                    link.student_id in active_ids
                    and link.student_id not in requested_ids
                ):
                    db.delete(link)

                else:
                    kept_ids.add(link.student_id)

            for student_id in requested_ids - linked_ids:

                db.add(
                    StudentAssignment(
                        assignment_id=assignment_id,
                        student_id=student_id
                    )
                )

            OccurrenceService.sync(
                db,
                assignment,
                kept_ids,
                CurrentUser.get_today(),
                lesson_count,
                reschedule
            )

            # Another tab may have just linked the same student.
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                logger.warning(
                    "Assignment %s changed while saving",
                    assignment_id
                )
                return None

            db.refresh(assignment)

            return assignment

    @staticmethod
    def get_note_rows(
        assignment_id
    ):
        """
        Returns the occurrences a parent can add notes to on this assignment,
        with their students: dates for active students still assigned to it.
        """

        if not CurrentUser.is_parent():
            return []

        with get_session() as db:

            return (
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
                    joinedload(AssignmentOccurrence.student)
                )
                .filter(
                    AssignmentOccurrence.assignment_id == assignment_id,
                    Assignment.family_id
                    == CurrentUser.get_family_id(),
                    Assignment.active.is_(True),
                    Student.active.is_(True)
                )
                .order_by(
                    AssignmentOccurrence.occurrence_date,
                    Student.name
                )
                .all()
            )

    @staticmethod
    def set_occurrence_note(
        assignment_id,
        occurrence_date,
        student_ids,
        note
    ):
        """
        Saves a note on one date for the chosen students, in one commit. A
        blank note removes it. Returns how many rows changed, or None if
        there's nothing here this parent can change.
        """

        rows = [
            row
            for row in AssignmentService.get_note_rows(assignment_id)
            if row.occurrence_date == occurrence_date
            and row.student_id in set(student_ids)
        ]

        if not rows:
            return None

        note = (note or "").strip() or None

        with get_session() as db:

            saved = (
                db.query(AssignmentOccurrence)
                .filter(
                    AssignmentOccurrence.id.in_(
                        [row.id for row in rows]
                    )
                )
                .all()
            )

            for row in saved:
                row.notes = note

            db.commit()

            return len(saved)

    @staticmethod
    def _recovery_moves(
        db,
        family_id,
        student_ids,
        resume_on
    ):
        """
        Returns what shifting these students would do, as a list with one
        {"student", "assignment", "rows", "moves"} per curriculum that would
        change. Leaves out archived work and students, students no longer
        assigned, and any other family's. A curriculum that hasn't reached
        its start date keeps it.
        """

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
                AssignmentOccurrence.student_id.in_(student_ids),
                Assignment.family_id == family_id,
                Assignment.active.is_(True),
                Assignment.assignment_type
                == AssignmentType.CURRICULUM.value,
                Student.family_id == family_id,
                Student.active.is_(True)
            )
            .all()
        )

        grouped = defaultdict(list)

        for row in rows:
            grouped[(row.student_id, row.assignment_id)].append(row)

        changes = []

        for group in grouped.values():

            assignment = group[0].assignment

            moves = OccurrenceService.recovery_moves(
                group,
                assignment.recurrence_pattern,
                max(resume_on, assignment.due_date)
            )

            if moves:

                changes.append(
                    {
                        "student": group[0].student,
                        "assignment": assignment,
                        "rows": group,
                        "moves": moves,
                    }
                )

        return sorted(
            changes,
            key=lambda change: (
                change["student"].name,
                change["assignment"].title
            )
        )

    @staticmethod
    def get_recovery_plan(
        student_ids,
        resume_on
    ):
        """
        Returns what shift_lessons would do, without changing anything: one
        {"student_name", "title", "next_lesson", "next_date", "old_finish",
        "new_finish"} per curriculum that would change.
        """

        if not CurrentUser.is_parent():
            return []

        family_id = (
            CurrentUser.get_family_id()
        )

        with get_session() as db:

            plan = []

            for change in AssignmentService._recovery_moves(
                db,
                family_id,
                student_ids,
                resume_on
            ):

                moved = dict(change["moves"])

                first, first_date = min(
                    change["moves"],
                    key=lambda move: move[0].lesson_number
                )

                plan.append(
                    {
                        "student_name": change["student"].name,
                        "title": change["assignment"].title,
                        "next_lesson": first.lesson_number,
                        "next_date": first_date,
                        "old_finish": max(
                            row.occurrence_date
                            for row in change["rows"]
                        ),
                        "new_finish": max(
                            moved.get(row, row.occurrence_date)
                            for row in change["rows"]
                        ),
                    }
                )

            return plan

    @staticmethod
    def get_students_behind(
        today
    ):
        """
        Returns the ids of this family's students with a curriculum lesson
        dated before today that isn't done.
        """

        if not CurrentUser.is_parent():
            return set()

        family_id = (
            CurrentUser.get_family_id()
        )

        with get_session() as db:

            return {
                student_id
                for (student_id,) in (
                    db.query(AssignmentOccurrence.student_id)
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
                    .filter(
                        AssignmentOccurrence.occurrence_date < today,
                        AssignmentOccurrence.status
                        != AssignmentStatus.COMPLETE.value,
                        Assignment.family_id == family_id,
                        Assignment.active.is_(True),
                        Assignment.assignment_type
                        == AssignmentType.CURRICULUM.value,
                        Student.active.is_(True)
                    )
                )
            }

    @staticmethod
    def has_curriculum():
        """
        True if this family has any active curriculum.
        """

        with get_session() as db:

            return (
                db.query(Assignment.id)
                .filter(
                    Assignment.family_id
                    == CurrentUser.get_family_id(),
                    Assignment.active.is_(True),
                    Assignment.assignment_type
                    == AssignmentType.CURRICULUM.value
                )
                .first()
                is not None
            )

    @staticmethod
    def shift_lessons(
        student_ids,
        resume_on
    ):
        """
        Picks the chosen students' curricula back up on resume_on, in one
        commit. Each student only moves their own lessons, and lessons
        they've started stay where they are. Returns how many lessons moved,
        or None if a parent can't do this or the date has already passed.
        """

        if not CurrentUser.is_parent():
            return None

        if resume_on < CurrentUser.get_today():
            return None

        family_id = (
            CurrentUser.get_family_id()
        )

        with get_session() as db:

            moves = [
                move
                for change in AssignmentService._recovery_moves(
                    db,
                    family_id,
                    student_ids,
                    resume_on
                )
                for move in change["moves"]
            ]

            OccurrenceService.step_aside(
                db,
                [row for row, _ in moves]
            )

            for row, day in moves:
                row.occurrence_date = day

            db.commit()

            return len(moves)

    @staticmethod
    def get_archived_assignments():
        """
        Returns the current family's archived assignments with their
        subjects, by title, for a parent.
        """

        if not CurrentUser.is_parent():
            return []

        with get_session() as db:

            return (
                db.query(Assignment)
                .options(
                    joinedload(Assignment.subject)
                )
                .filter(
                    Assignment.family_id == CurrentUser.get_family_id(),
                    Assignment.active.is_(False)
                )
                .order_by(Assignment.title)
                .all()
            )

    @staticmethod
    def restore_assignment(assignment_id):
        """
        Unarchives an assignment. Its dates, students, check-offs, notes and
        grades come back as they were. Returns it, or None if it isn't
        available to this parent.
        """

        if not CurrentUser.is_parent():
            return None

        with get_session() as db:

            assignment = (
                db.query(Assignment)
                .filter(
                    Assignment.id == assignment_id,
                    Assignment.family_id == CurrentUser.get_family_id()
                )
                .first()
            )

            if not assignment:
                return None

            assignment.active = True

            db.commit()

            return assignment

    @staticmethod
    def archive_assignment(
        assignment_id
    ):

        # Only parents change this, even if a page guard is ever missed.

        if not CurrentUser.is_parent():
            return None

        with get_session() as db:

            assignment = (
                db.query(Assignment)
                .filter(
                    Assignment.id == assignment_id,
                    Assignment.family_id
                    == CurrentUser.get_family_id()
                )
                .first()
            )

            if not assignment:
                return None

            assignment.active = False

            db.commit()

            return assignment
