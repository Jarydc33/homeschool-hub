from database.db import SessionLocal
from database.models import Student, User

class UserService:

    @staticmethod
    def get_user_by_email(email):

        db = SessionLocal()

        try:

            return (
                db.query(User)
                .filter(
                    User.email == email.strip().lower()
                )
                .first()
            )

        finally:
            db.close()

    @staticmethod
    def get_user_by_student_id(
        student_id,
        family_id
    ):

        db = SessionLocal()

        try:

            return (
                db.query(User)
                .filter(
                    User.student_id == student_id,
                    User.family_id == family_id
                )
                .first()
            )

        finally:
            db.close()

    @staticmethod
    def get_user_by_id(user_id):

        db = SessionLocal()

        try:

            return (
                db.query(User)
                .filter(
                    User.id == user_id
                )
                .first()
            )

        finally:
            db.close()

    @staticmethod
    def create_parent_user(
        family_id,
        email
    ):
        email = email.strip().lower()
        db = SessionLocal()

        try:

            user = User(
                family_id=family_id,
                email=email,
                role="Parent"
            )

            db.add(user)

            db.commit()

            db.refresh(user)

            return user

        finally:
            db.close()

    @staticmethod
    def create_student_user(
        family_id,
        student_id,
        email
    ):
        """
        Returns the new user, or None if the student is not an
        active part of this family.
        """

        db = SessionLocal()

        try:

            student = (
                db.query(Student)
                .filter(
                    Student.id == student_id,
                    Student.family_id == family_id,
                    Student.active.is_(True)
                )
                .first()
            )

            if not student:
                return None

            user = User(
                family_id=family_id,
                student_id=student_id,
                email=email.strip().lower(),
                role="Student"
            )

            db.add(user)

            db.commit()

            db.refresh(user)

            return user

        finally:
            db.close()
