import logging
from zoneinfo import available_timezones

from database.db import get_session
from database.models import DEFAULT_TIMEZONE, Family, User, UserRole

logger = logging.getLogger(__name__)

COMMON_TIMEZONES = {
    "America/New_York": "US Eastern",
    "America/Chicago": "US Central",
    "America/Denver": "US Mountain",
    "America/Phoenix": "US Arizona",
    "America/Los_Angeles": "US Pacific",
    "America/Anchorage": "US Alaska",
    "Pacific/Honolulu": "US Hawaii",
}


MAX_FAMILY_NAME_LENGTH = 100


class FamilyService:

    @staticmethod
    def timezone_choices():
        """
        Returns time zone names for a dropdown, with common ones first.
        """

        others = sorted(
            name
            for name in available_timezones()
            if "/" in name
            and name not in COMMON_TIMEZONES
            and not name.startswith(("Etc/", "SystemV/", "posix/", "right/"))
        )

        return list(COMMON_TIMEZONES) + others

    @staticmethod
    def timezone_label(name):

        common = COMMON_TIMEZONES.get(name)

        return f"{common} ({name})" if common else name

    @staticmethod
    def preferred_timezone(browser_timezone):
        """
        Returns the choice to preselect: the browser's zone if we know it.
        """

        if browser_timezone in FamilyService.timezone_choices():
            return browser_timezone

        return DEFAULT_TIMEZONE

    @staticmethod
    def settings_error(
        family_name,
        timezone
    ):
        """
        Returns what's wrong with a family's settings for showing, or None.
        """

        if not (family_name or "").strip():
            return "Please enter a family name."

        if len(family_name.strip()) > MAX_FAMILY_NAME_LENGTH:
            return "Please use a shorter family name."

        if timezone not in available_timezones():
            return "Please choose a time zone from the list."

        return None

    @staticmethod
    def update_settings(
        family_name,
        timezone
    ):
        """
        Saves the current family's name and time zone. Returns the family, or
        None if they aren't valid or the current user isn't a parent. Saved
        dates don't change; only what counts as today does.
        """

        # Imported here because AuthService imports this module.
        from services.current_user import CurrentUser

        if (
            not CurrentUser.is_parent()
            or FamilyService.settings_error(family_name, timezone)
        ):
            return None

        with get_session() as db:

            family = db.get(
                Family,
                CurrentUser.get_family_id()
            )

            if not family:
                return None

            family.family_name = family_name.strip()
            family.timezone = timezone

            db.commit()
            db.refresh(family)

            return family

    @staticmethod
    def create_family_with_parent(
        family_name,
        email,
        auth_user_id,
        timezone=DEFAULT_TIMEZONE
    ):
        """
        Saves a new family and its first parent in one commit, so a failure
        can't leave a family with nobody in it. Returns the parent's user.
        """

        if timezone not in available_timezones():

            logger.warning("Ignoring an unknown time zone at sign-up")

            timezone = DEFAULT_TIMEZONE

        with get_session() as db:

            user = User(
                family=Family(
                    family_name=family_name,
                    timezone=timezone
                ),
                email=email.strip().lower(),
                auth_user_id=str(auth_user_id),
                role=UserRole.PARENT.value
            )

            db.add(user)

            db.commit()

            return user
