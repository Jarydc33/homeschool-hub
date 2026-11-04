from database.db import get_session
from database.models import (
    Assignment,
    AssignmentOccurrence,
    AssignmentStatus,
    AssignmentType,
    Student,
    StudentAssignment,
)
from sqlalchemy.orm import joinedload
from datetime import datetime
from services.auth_service import AuthService


class StudentService:

    @staticmethod
    def update_assignment_status(
        student_assignment_id,
        completed
    ):

        with get_session() as db:

            query = (
                db.query(StudentAssignment)
                .join(StudentAssignment.assignment)
                .filter(
                    StudentAssignment.id
                    == student_assignment_id,
                    Assignment.family_id
                    == AuthService.get_current_family(),
                    Assignment.active.is_(True)
                )
            )

            # Students can only check off their own work.

            if AuthService.is_student():

                query = query.filter(
                    StudentAssignment.student_id
                    == AuthService.get_current_student()
                )

            student_assignment = query.first()

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

            # Pages still read the link, but occurrences take over soon, so
            # keep one-time work matching. Recurring work has no single date
            # to update until check-offs are made per date.

            assignment = student_assignment.assignment

            if assignment.assignment_type != AssignmentType.RECURRING.value:

                occurrence = (
                    db.query(AssignmentOccurrence)
                    .filter(
                        AssignmentOccurrence.assignment_id == assignment.id,
                        AssignmentOccurrence.student_id
                        == student_assignment.student_id,
                        AssignmentOccurrence.occurrence_date
                        == assignment.due_date
                    )
                    .first()
                )

                if occurrence:

                    occurrence.status = student_assignment.status

                    occurrence.completed_at = (
                        student_assignment.completed_at
                    )

            db.commit()

            return student_assignment

    @staticmethod
    def get_student_assignments(student_id):

        with get_session() as db:

            student_assignments = (
                db.query(StudentAssignment)
                .join(StudentAssignment.assignment)
                .options(
                    joinedload(
                        StudentAssignment.assignment
                    ).joinedload(
                        Assignment.subject
                    )
                )
                .filter(
                    StudentAssignment.student_id == student_id,
                    Assignment.family_id
                    == AuthService.get_current_family(),
                    Assignment.active.is_(True)
                )
                .all()
            )

            return student_assignments

    @staticmethod
    def get_student_by_id(student_id):
        """
        Returns a single student.
        """

        with get_session() as db:
            student = (
                db.query(Student)
                .filter(
                    Student.id == student_id,
                    Student.family_id
                    == AuthService.get_current_family()
                )
                .first()
            )

            return student

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

        with get_session() as db:
            students = (
                db.query(Student)
                .filter(Student.family_id == family_id)
                .filter(
                    Student.active.is_(True)
                )
                .all()
            )

            return students

    @staticmethod
    def get_archived_students():
        """
        Returns the current family's archived students.
        """

        with get_session() as db:

            return (
                db.query(Student)
                .filter(
                    Student.family_id
                    == AuthService.get_current_family(),
                    Student.active.is_(False)
                )
                .order_by(Student.name)
                .all()
            )

    @staticmethod
    def restore_student(student_id):
        """
        Unarchives a student. Their assignments, progress, and login
        return as they were.
        """

        with get_session() as db:

            student = (
                db.query(Student)
                .filter(
                    Student.id == student_id,
                    Student.family_id
                    == AuthService.get_current_family()
                )
                .first()
            )

            if not student:
                return None

            student.active = True

            db.commit()

            return student

    @staticmethod
    def create_student(
        name,
        grade_level=None,
        birth_year=None
    ):
        """
        Creates a new student.
        """

        with get_session() as db:

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

        with get_session() as db:

            student = (
                db.query(Student)
                .filter(
                    Student.id == student_id,
                    Student.family_id
                    == AuthService.get_current_family()
                )
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

    @staticmethod
    def archive_student(student_id):
        """
        Soft delete.
        Student remains in database.
        """

        with get_session() as db:

            student = (
                db.query(Student)
                .filter(
                    Student.id == student_id,
                    Student.family_id
                    == AuthService.get_current_family()
                )
                .first()
            )

            if not student:
                return None

            student.active = False

            db.commit()

            return student
