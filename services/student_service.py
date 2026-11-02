from database.db import SessionLocal
from database.models import Student, StudentAssignment, Assignment, AssignmentStatus
from sqlalchemy.orm import joinedload
from datetime import datetime
from services.auth_service import AuthService


class StudentService:

    @staticmethod
    def update_assignment_status(
        student_assignment_id,
        completed
    ):

        db = SessionLocal()

        try:

            student_assignment = (
                db.query(StudentAssignment)
                .filter(
                    StudentAssignment.id
                    == student_assignment_id
                )
                .first()
            )

            if not student_assignment:
                return None

            if completed:

                student_assignment.status = (
                    AssignmentStatus.COMPLETE.value
                )

                student_assignment.completed_at = (
                    datetime.utcnow()
                )

            else:

                student_assignment.status = (
                    AssignmentStatus.NOT_STARTED.value
                )

                student_assignment.completed_at = None

            db.commit()

            return student_assignment

        finally:
            db.close()

    @staticmethod
    def get_student_assignments(student_id):

        db = SessionLocal()

        try:

            student_assignments = (
                db.query(StudentAssignment)
                .options(
                    joinedload(
                        StudentAssignment.assignment
                    ).joinedload(
                        Assignment.subject
                    )
                )
                .filter(
                    StudentAssignment.student_id == student_id
                )
                .all()
            )

            return student_assignments

        finally:
            db.close()

    @staticmethod
    def get_student_by_id(student_id):
        """
        Returns a single student.
        """

        db = SessionLocal()

        try:
            student = (
                db.query(Student)
                .filter(Student.id == student_id)
                .first()
            )

            return student

        finally:
            db.close()

    @staticmethod
    def get_current_family_students():

        family_id = (
            AuthService.get_current_family()
        )

        return (
            StudentService.get_students_by_family(
                family_id
            )
        )

    @staticmethod
    def get_students_by_family(family_id):
        """
        Returns all students for a family.
        """

        db = SessionLocal()

        try:
            students = (
                db.query(Student)
                .filter(Student.family_id == family_id)
                .filter(
                    Student.active.is_(True)
                )
                .all()
            )

            return students

        finally:
            db.close()

    @staticmethod
    def create_student(
        name,
        grade_level=None,
        birth_year=None
    ):
        """
        Creates a new student.
        """

        db = SessionLocal()

        try:

            student = Student(
                family_id=AuthService.get_current_family(),
                name=name,
                grade_level=grade_level,
                birth_year=birth_year
            )

            db.add(student)
            db.commit()
            db.refresh(student)

            return student

        finally:
            db.close()

    @staticmethod
    def update_student(
        student_id,
        name=None,
        grade_level=None,
        birth_year=None
    ):
        """
        Updates an existing student.
        """

        db = SessionLocal()

        try:

            student = (
                db.query(Student)
                .filter(Student.id == student_id)
                .first()
            )

            if not student:
                return None

            if name is not None:
                student.name = name

            if grade_level is not None:
                student.grade_level = grade_level

            if birth_year is not None:
                student.birth_year = birth_year

            db.commit()

            return student

        finally:
            db.close()

    @staticmethod
    def archive_student(student_id):
        """
        Soft delete.
        Student remains in database.
        """

        db = SessionLocal()

        try:

            student = (
                db.query(Student)
                .filter(Student.id == student_id)
                .first()
            )

            if not student:
                return None

            student.active = False

            db.commit()

            return student

        finally:
            db.close()