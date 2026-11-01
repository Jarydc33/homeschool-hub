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

    @staticmethod
    def get_family_by_id(
        family_id
    ):

        db = SessionLocal()

        try:

            return (
                db.query(Family)
                .filter(
                    Family.id == family_id
                )
                .first()
            )

        finally:
            db.close()

    @staticmethod
    def get_family_by_name(
        family_name
    ):

        db = SessionLocal()

        try:

            return (
                db.query(Family)
                .filter(
                    Family.family_name
                    == family_name
                )
                .first()
            )

        finally:
            db.close()

    @staticmethod
    def get_all_families():

        db = SessionLocal()

        try:

            return (
                db.query(Family)
                .all()
            )

        finally:
            db.close()

    @staticmethod
    def update_family(
        family_id,
        family_name
    ):

        db = SessionLocal()

        try:

            family = (
                db.query(Family)
                .filter(
                    Family.id == family_id
                )
                .first()
            )

            if not family:
                return None

            family.family_name = (
                family_name
            )

            db.commit()

            return family

        finally:
            db.close()