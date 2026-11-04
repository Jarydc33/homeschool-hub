from database.db import get_session
from database.models import Family


class FamilyService:

    @staticmethod
    def create_family(
        family_name
    ):

        with get_session() as db:

            family = Family(
                family_name=family_name
            )

            db.add(family)

            db.commit()

            db.refresh(family)

            return family
