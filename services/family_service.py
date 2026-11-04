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
