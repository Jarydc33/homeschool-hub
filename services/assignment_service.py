# services/assignment_service.py
from sqlalchemy.orm import joinedload
from database.db import SessionLocal
from database.models import (
    Assignment,
    Student,
    StudentAssignment,
    Subject,
    AssignmentType
)

from services.auth_service import AuthService

class AssignmentService:

    @staticmethod
    def get_assignment_by_id(
        assignment_id
    ):

        db = SessionLocal()

        try:

            return (
                db.query(Assignment)
                .options(
                    joinedload(
                        Assignment.subject
                    ),
                    joinedload(
                        Assignment.student_assignments
                    )
                )
                .filter(
                    Assignment.id == assignment_id,
                    Assignment.family_id
                    == AuthService.get_current_family()
                )
                .first()
            )

        finally:
            db.close()

    @staticmethod
    def get_assignments_by_family(
        family_id
    ):
        """
        Returns active assignments. Their student_assignments leave out
        archived students, so rosters, progress, and overdue warnings
        don't count them. The rows themselves are kept as history.
        """

        db = SessionLocal()

        try:

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

        finally:
            db.close()

    @staticmethod
    def get_current_family_assignments():

        family_id = (
            AuthService.get_current_family()
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
        recurrence_pattern=None
    ):
        """
        Returns the new assignment, or None if the subject or any
        student is not an active part of this family.
        """

        family_id = (
            AuthService.get_current_family()
        )

        db = SessionLocal()

        try:

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
                student_assignments=[
                    StudentAssignment(
                        student_id=student_id
                    )
                    for student_id in requested_ids
                ]
            )

            db.add(assignment)
            db.commit()
            db.refresh(assignment)

            return assignment

        finally:
            db.close()

    @staticmethod
    def update_assignment(
        assignment_id,
        title,
        description,
        due_date,
        subject_id,
        student_ids,
        assignment_type,
        recurrence_pattern
    ):
        """
        Returns the updated assignment, or None if the assignment,
        subject, or any student is not available to this family.

        Only student links that changed are added or removed, so
        everyone else keeps their status, completion date, and notes.
        Links to archived students are left alone, since archived
        students aren't offered as choices on the edit form.
        """

        family_id = (
            AuthService.get_current_family()
        )

        db = SessionLocal()

        try:

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

            # -------------------------
            # Apply Student Changes
            # -------------------------

            for link in links:

                if (
                    link.student_id in active_ids
                    and link.student_id not in requested_ids
                ):
                    db.delete(link)

            for student_id in requested_ids - linked_ids:

                db.add(
                    StudentAssignment(
                        assignment_id=assignment_id,
                        student_id=student_id
                    )
                )

            db.commit()
            db.refresh(assignment)

            return assignment

        finally:
            db.close()

    @staticmethod
    def archive_assignment(
        assignment_id
    ):

        db = SessionLocal()

        try:

            assignment = (
                db.query(Assignment)
                .filter(
                    Assignment.id == assignment_id,
                    Assignment.family_id
                    == AuthService.get_current_family()
                )
                .first()
            )

            if not assignment:
                return None

            assignment.active = False

            db.commit()

            return assignment

        finally:
            db.close()