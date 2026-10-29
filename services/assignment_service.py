# services/assignment_service.py
from sqlalchemy.orm import joinedload
from database.db import SessionLocal
from database.models import (
    Assignment,
    Student,
    StudentAssignment
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
    def create_assignment(
        family_id,
        subject_id,
        title,
        student_ids,
        description=None,
        due_date=None
    ):

        db = SessionLocal()

        try:

            assignment = Assignment(
                family_id=family_id,
                subject_id=subject_id,
                title=title,
                description=description,
                due_date=due_date
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