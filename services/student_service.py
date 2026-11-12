from database.db import get_session
from database.models import (
    Assignment,
    AssignmentOccurrence,
    AssignmentStatus,
    Student,
    StudentAssignment,
)
from sqlalchemy import and_
from sqlalchemy.orm import joinedload
from datetime import datetime
from services.current_user import CurrentUser


class StudentService:

    @staticmethod
    def update_occurrence_status(
        occurrence_id,
        completed
    ):
        """
        Checks one date of an assignment on or off. Returns the row, with its
        assignment and subject loaded, or None if it isn't available to the
        current user.
        """

        with get_session() as db:

            query = (
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
                    AssignmentOccurrence.id == occurrence_id,
                    Assignment.family_id
                    == CurrentUser.get_family_id(),
                    Assignment.active.is_(True)
                )
            )

            # Students can only check off their own work.

            if CurrentUser.is_student():

                query = query.filter(
                    AssignmentOccurrence.student_id
                    == CurrentUser.get_student_id()
                )

            occurrence = query.first()

            if not occurrence:
                return None

            if completed:

                occurrence.status = (
                    AssignmentStatus.COMPLETE.value
                )

                occurrence.completed_at = (
                    datetime.utcnow()
                )

            else:

                occurrence.status = (
                    AssignmentStatus.NOT_STARTED.value
                )

                occurrence.completed_at = None

            db.commit()

            return occurrence

    @staticmethod
    def get_student_occurrences(student_id):
        """
        Returns a student's occurrences on active assignments they're still
        assigned to. Rows kept after a student comes off an assignment stay
        in the database as history, but aren't shown as their work. A student
        can only read their own.
        """

        if (
            CurrentUser.is_student()
            and student_id != CurrentUser.get_student_id()
        ):
            return []

        with get_session() as db:

            return (
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
                    Assignment.family_id
                    == CurrentUser.get_family_id(),
                    Assignment.active.is_(True)
                )
                .all()
            )

    @staticmethod
    def get_student_by_id(student_id):
        """
        Returns a single student. A student can only get their own.
        """

        if (
            CurrentUser.is_student()
            and student_id != CurrentUser.get_student_id()
        ):
            return None

        with get_session() as db:
            student = (
                db.query(Student)
                .filter(
                    Student.id == student_id,
                    Student.family_id
                    == CurrentUser.get_family_id()
                )
                .first()
            )

            return student

    @staticmethod
    def get_current_family_students():

        family_id = (
            CurrentUser.get_family_id()
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

        # Only parents change this, even if a page guard is ever missed.

        if not CurrentUser.is_parent():
            return []

        with get_session() as db:

            return (
                db.query(Student)
                .filter(
                    Student.family_id
                    == CurrentUser.get_family_id(),
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

        # Only parents change this, even if a page guard is ever missed.

        if not CurrentUser.is_parent():
            return None

        with get_session() as db:

            student = (
                db.query(Student)
                .filter(
                    Student.id == student_id,
                    Student.family_id
                    == CurrentUser.get_family_id()
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

        # Only parents change this, even if a page guard is ever missed.

        if not CurrentUser.is_parent():
            return None

        with get_session() as db:

            student = Student(
                family_id=CurrentUser.get_family_id(),
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

        # Only parents change this, even if a page guard is ever missed.

        if not CurrentUser.is_parent():
            return None

        with get_session() as db:

            student = (
                db.query(Student)
                .filter(
                    Student.id == student_id,
                    Student.family_id
                    == CurrentUser.get_family_id()
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

        # Only parents change this, even if a page guard is ever missed.

        if not CurrentUser.is_parent():
            return None

        with get_session() as db:

            student = (
                db.query(Student)
                .filter(
                    Student.id == student_id,
                    Student.family_id
                    == CurrentUser.get_family_id()
                )
                .first()
            )

            if not student:
                return None

            student.active = False

            db.commit()

            return student
