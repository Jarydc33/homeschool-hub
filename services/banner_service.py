from datetime import date

from database.db import SessionLocal
from database.models import BannerMessage


class BannerService:

    @staticmethod
    def get_all_banners():
        """
        Returns all banner messages.
        """

        db = SessionLocal()

        try:

            return (
                db.query(BannerMessage)
                .order_by(
                    BannerMessage.start_date.desc()
                )
                .all()
            )

        finally:
            db.close()

    @staticmethod
    def get_active_banners():
        """
        Returns banners that should currently display.
        """

        db = SessionLocal()

        try:

            today = date.today()

            return (
                db.query(BannerMessage)
                .filter(
                    BannerMessage.active.is_(True),
                    BannerMessage.start_date <= today,
                    BannerMessage.end_date >= today
                )
                .order_by(
                    BannerMessage.start_date.asc()
                )
                .all()
            )

        finally:
            db.close()

    @staticmethod
    def get_banner_by_id(
        banner_id
    ):
        """
        Returns a single banner.
        """

        db = SessionLocal()

        try:

            return (
                db.query(BannerMessage)
                .filter(
                    BannerMessage.id == banner_id
                )
                .first()
            )

        finally:
            db.close()

    @staticmethod
    def create_banner(
        title,
        message,
        start_date,
        end_date
    ):
        """
        Creates a new banner.
        """

        db = SessionLocal()

        try:

            banner = BannerMessage(
                title=title,
                message=message,
                start_date=start_date,
                end_date=end_date
            )

            db.add(banner)

            db.commit()

            db.refresh(banner)

            return banner

        finally:
            db.close()

    @staticmethod
    def update_banner(
        banner_id,
        title,
        message,
        start_date,
        end_date
    ):
        """
        Updates an existing banner.
        """

        db = SessionLocal()

        try:

            banner = (
                db.query(BannerMessage)
                .filter(
                    BannerMessage.id == banner_id
                )
                .first()
            )

            if not banner:
                return None

            banner.title = title
            banner.message = message
            banner.start_date = start_date
            banner.end_date = end_date

            db.commit()

            return banner

        finally:
            db.close()

    @staticmethod
    def archive_banner(
        banner_id
    ):
        """
        Soft delete banner.
        """

        db = SessionLocal()

        try:

            banner = (
                db.query(BannerMessage)
                .filter(
                    BannerMessage.id == banner_id
                )
                .first()
            )

            if not banner:
                return None

            banner.active = False

            db.commit()

            return banner

        finally:
            db.close()