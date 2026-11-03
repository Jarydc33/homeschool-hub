from database.db import SessionLocal
from database.models import Family


class FamilyService:

    @staticmethod
    def create_family(
        family_name
    ):

        db = SessionLocal()

        try:

            family = Family(
                family_name=family_name
            )

            db.add(family)

            db.commit()

            db.refresh(family)

            return family

        finally:
            db.close()
