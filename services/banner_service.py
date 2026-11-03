from datetime import date

from sqlalchemy import false, or_

from database.db import SessionLocal
from database.models import BannerMessage
from services.auth_service import AuthService


class BannerService:

    @staticmethod
    def _manageable_filter():
        """
        Limits a query to the banners the current user can manage:
        system-wide ones for an Admin, their own family's for a Parent.
        """

        if AuthService.is_admin():

            return BannerMessage.family_id.is_(None)

        family_id = AuthService.get_current_family()

        # Without the family check, a NULL family_id would match
        # the system-wide banners.

        if AuthService.is_parent() and family_id is not None:

            return BannerMessage.family_id == family_id

        return false()

    @staticmethod
    def get_manageable_banners():
        """
        Returns the banners listed on the Announcements page.
        """

        db = SessionLocal()

        try:

            return (
                db.query(BannerMessage)
                .filter(
                    BannerService._manageable_filter(),
                    BannerMessage.active.is_(True)
                )
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
        Returns banners that should currently display: the current
        family's, plus system-wide ones.
        """

        family_id = AuthService.get_current_family()

        db = SessionLocal()

        try:

            today = date.today()

            return (
                db.query(BannerMessage)
                .filter(
                    or_(
                        BannerMessage.family_id.is_(None),
                        BannerMessage.family_id == family_id
                    ),
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
        Returns a single banner the current user can manage.
        """

        db = SessionLocal()

        try:

            return (
                db.query(BannerMessage)
                .filter(
                    BannerMessage.id == banner_id,
                    BannerService._manageable_filter()
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
        Creates a system-wide banner for an Admin, or a family banner
        for a Parent. Returns None for anyone else.
        """

        if AuthService.is_admin():

            family_id = None

        else:

            family_id = AuthService.get_current_family()

            if not AuthService.is_parent() or family_id is None:
                return None

        db = SessionLocal()

        try:

            banner = BannerMessage(
                family_id=family_id,
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
        Updates a banner the current user can manage.
        """

        db = SessionLocal()

        try:

            banner = (
                db.query(BannerMessage)
                .filter(
                    BannerMessage.id == banner_id,
                    BannerService._manageable_filter()
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
        Soft deletes a banner the current user can manage.
        """

        db = SessionLocal()

        try:

            banner = (
                db.query(BannerMessage)
                .filter(
                    BannerMessage.id == banner_id,
                    BannerService._manageable_filter()
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
