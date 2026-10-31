from database.db import SessionLocal
from database.models import User

class UserService:

    @staticmethod
    def get_user_by_email(email):

        db = SessionLocal()

        try:

            return (
                db.query(User)
                .filter(
                    User.email == email
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
    def get_family_users(family_id):

        db = SessionLocal()

        try:

            return (
                db.query(User)
                .filter(
                    User.family_id == family_id
                )
                .all()
            )

        finally:
            db.close()

    @staticmethod
    def create_parent_user(
        family_id,
        email,
        password_hash
    ):

        db = SessionLocal()

        try:

            user = User(
                family_id=family_id,
                email=email,
                password_hash=password_hash,
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
        email,
        password_hash
    ):

        db = SessionLocal()

        try:

            user = User(
                family_id=family_id,
                student_id=student_id,
                email=email,
                password_hash=password_hash,
                role="Student"
            )

            db.add(user)

            db.commit()

            db.refresh(user)

            return user

        finally:
            db.close()

    @staticmethod
    def deactivate_user(user_id):

        db = SessionLocal()

        try:

            user = (
                db.query(User)
                .filter(
                    User.id == user_id
                )
                .first()
            )

            if not user:
                return None

            user.is_active = False

            db.commit()

            return user

        finally:
            db.close()