from database.db import get_session
from database.models import Family, User, UserRole


class FamilyService:

    @staticmethod
    def create_family_with_parent(
        family_name,
        email,
        auth_user_id
    ):
        """
        Saves a new family and its first parent in one commit, so a failure
        can't leave a family with nobody in it. Returns the parent's user.
        """

        with get_session() as db:

            user = User(
                family=Family(
                    family_name=family_name
                ),
                email=email.strip().lower(),
                auth_user_id=str(auth_user_id),
                role=UserRole.PARENT.value
            )

            db.add(user)

            db.commit()

            return user
