# services/assignment_service.py
from sqlalchemy.orm import joinedload
from database.db import SessionLocal
from database.models import (
    Assignment,
    Student,
    StudentAssignment,
    AssignmentType,
    RecurrencePattern
)


class AssignmentService:

    @staticmethod
    def get_all_assignments():

        db = SessionLocal()

        try:

            assignments = (
                db.query(Assignment)
                .options(
                    joinedload(Assignment.subject),
                    joinedload(
                        Assignment.student_assignments
                    ).joinedload(
                        StudentAssignment.student
                    )
                )
                .all()
            )

            return assignments

        finally:
            db.close()

    @staticmethod
    def get_active_assignments():

        db = SessionLocal()

        try:

            assignments = (
                db.query(Assignment)
                .options(
                    joinedload(
                        Assignment.subject
                    ),
                    joinedload(
                        Assignment.student_assignments
                    ).joinedload(
                        StudentAssignment.student
                    )
                )
                .filter(
                    Assignment.active.is_(True)
                )
                .all()
            )

            return assignments

        finally:
            db.close()

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
                        Assignment.student_assignments
                    )
                )
                .filter(
                    Assignment.id == assignment_id
                )
                .first()
            )

        finally:
            db.close()

    @staticmethod
    def create_assignment(
        family_id,
        subject_id,
        title,
        student_ids,
        description=None,
        due_date=None,
        assignment_type=AssignmentType.ONE_TIME.value,
        recurrence_pattern=None
    ):

        db = SessionLocal()

        try:

            assignment = Assignment(
                family_id=family_id,
                subject_id=subject_id,
                title=title,
                description=description,
                due_date=due_date,
                assignment_type=assignment_type,
                recurrence_pattern=recurrence_pattern
            )

            db.add(assignment)
            db.commit()
            db.refresh(assignment)

            # Create student assignment records

            for student_id in student_ids:

                student_assignment = StudentAssignment(
                    assignment_id=assignment.id,
                    student_id=student_id
                )

                db.add(student_assignment)

            db.commit()

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

        db = SessionLocal()

        try:

            assignment = (
                db.query(Assignment)
                .filter(
                    Assignment.id == assignment_id
                )
                .first()
            )

            if not assignment:
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
            # Replace Student Mappings
            # -------------------------

            db.query(StudentAssignment).filter(
                StudentAssignment.assignment_id
                == assignment_id
            ).delete()

            for student_id in student_ids:

                db.add(
                    StudentAssignment(
                        assignment_id=assignment_id,
                        student_id=student_id
                    )
                )

            db.commit()

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
                    Assignment.id == assignment_id
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