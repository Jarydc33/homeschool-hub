from sqlalchemy.orm import joinedload

from database.db import get_session
from database.models import Student, User

class UserService:

    @staticmethod
    def get_user_by_email(email):

        with get_session() as db:

            return (
                db.query(User)
                .options(
                    joinedload(User.student)
                )
                .filter(
                    User.email == email.strip().lower()
                )
                .first()
            )

    @staticmethod
    def get_user_by_auth_id(auth_user_id):

        with get_session() as db:

            return (
                db.query(User)
                .options(
                    joinedload(User.student)
                )
                .filter(
                    User.auth_user_id == str(auth_user_id)
                )
                .first()
            )

    @staticmethod
    def get_user_by_student_id(
        student_id,
        family_id
    ):

        with get_session() as db:

            return (
                db.query(User)
                .filter(
                    User.student_id == student_id,
                    User.family_id == family_id
                )
                .first()
            )

    @staticmethod
    def get_user_by_id(user_id):

        with get_session() as db:

            return (
                db.query(User)
                .options(
                    joinedload(User.student)
                )
                .filter(
                    User.id == user_id
                )
                .first()
            )

    @staticmethod
    def update_user_email(
        user_id,
        family_id,
        email
    ):
        """
        Changes a user's email within their family. Returns the user, or
        None if they aren't in this family. Use
        AuthService.update_student_email, which also updates Supabase.
        """

        with get_session() as db:

            user = (
                db.query(User)
                .filter(
                    User.id == user_id,
                    User.family_id == family_id
                )
                .first()
            )

            if not user:
                return None

            user.email = email.strip().lower()

            db.commit()

            return user

    @staticmethod
    def create_parent_user(
        family_id,
        email,
        auth_user_id
    ):
        email = email.strip().lower()
        with get_session() as db:

            user = User(
                family_id=family_id,
                email=email,
                auth_user_id=str(auth_user_id),
                role="Parent"
            )

            db.add(user)

            db.commit()

            db.refresh(user)

            return user

    @staticmethod
    def create_student_user(
        family_id,
        student_id,
        email,
        auth_user_id
    ):
        """
        Returns the new user, or None if the student is not an
        active part of this family.
        """

        with get_session() as db:

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
                auth_user_id=str(auth_user_id),
                role="Student"
            )

            db.add(user)

            db.commit()

            db.refresh(user)

            return user
