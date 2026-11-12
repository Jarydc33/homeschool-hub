"""
Who is making the current request, without depending on any web framework.

Services ask CurrentUser for the role, family, student and today's date.
Where those come from depends on what's running:

- An API request (FastAPI) works out the user from its login token and wraps
  the request in CurrentUser.acting_as(...).
- The Streamlit app registers AuthService as the fallback, which finds the
  user from Streamlit's session as before.

With neither, there is no user, so every check fails closed.
"""
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from database.models import UserRole

logger = logging.getLogger(__name__)

_NOT_LOADED = object()


@dataclass
class RequestIdentity:
    """
    One request's user. auth_session_id is the Supabase session behind the
    login, which ties a parent's login to Student Mode. The Student Mode row
    is looked up when first needed, and again after forget_student_mode().
    """

    user: object
    auth_session_id: str = None
    student_mode: object = field(default=_NOT_LOADED, repr=False)


_current = ContextVar("tally_current_user", default=None)


class CurrentUser:

    # Answers when no request identity is set: the Streamlit AuthService.
    # It needs get_current_user, get_student_mode, get_auth_session_id and
    # forget_student_mode.
    _fallback = None

    @staticmethod
    def set_fallback(source):

        CurrentUser._fallback = source

    @staticmethod
    @contextmanager
    def acting_as(user, auth_session_id=None):
        """
        Runs the block as this user. Ends when the block does, even after an
        error, so one request's user never leaks into the next.
        """

        token = _current.set(
            RequestIdentity(user=user, auth_session_id=auth_session_id)
        )

        try:
            yield
        finally:
            _current.reset(token)

    # ----- the user and their login -----

    @staticmethod
    def get():
        """
        Returns the user making this request, or None. It's a users row, or
        a PairedUser on a student's paired device.
        """

        identity = _current.get()

        if identity is not None:
            return identity.user

        if CurrentUser._fallback is not None:
            return CurrentUser._fallback.get_current_user()

        return None

    @staticmethod
    def get_auth_session_id():
        """
        Returns the Supabase session behind this login, or None.
        """

        identity = _current.get()

        if identity is not None:
            return identity.auth_session_id

        if CurrentUser._fallback is not None:
            return CurrentUser._fallback.get_auth_session_id()

        return None

    @staticmethod
    def get_student_mode():
        """
        Returns this login's active Student Mode row, with its student, or
        None. Only a parent's login can be in Student Mode.
        """

        identity = _current.get()

        if identity is None:

            if CurrentUser._fallback is not None:
                return CurrentUser._fallback.get_student_mode()

            return None

        if identity.student_mode is _NOT_LOADED:

            identity.student_mode = CurrentUser.load_student_mode(
                identity.user,
                identity.auth_session_id
            )

        return identity.student_mode

    @staticmethod
    def forget_student_mode():
        """
        Makes the next check look up Student Mode fresh, after it starts or
        ends.
        """

        identity = _current.get()

        if identity is not None:
            identity.student_mode = _NOT_LOADED

        elif CurrentUser._fallback is not None:
            CurrentUser._fallback.forget_student_mode()

    @staticmethod
    def load_student_mode(user, auth_session_id):
        """
        Looks up the active Student Mode row for a user's login, or None.
        """

        from services.student_mode_service import StudentModeService

        if not user or user.role != UserRole.PARENT.value:
            return None

        return StudentModeService.find_active(
            user.family_id,
            auth_session_id
        )

    # ----- roles -----

    @staticmethod
    def is_authenticated():

        return CurrentUser.get() is not None

    @staticmethod
    def is_parent():
        """
        True for a parent, but not while their login is in Student Mode.
        """

        user = CurrentUser.get()

        if not user:
            return False

        return (
            user.role == UserRole.PARENT.value
            and not CurrentUser.get_student_mode()
        )

    @staticmethod
    def is_student():
        """
        True for a student, including a parent's login in Student Mode.
        """

        user = CurrentUser.get()

        if not user:
            return False

        if user.role == UserRole.STUDENT.value:
            return True

        return (
            user.role == UserRole.PARENT.value
            and CurrentUser.get_student_mode() is not None
        )

    @staticmethod
    def is_admin():

        user = CurrentUser.get()

        if not user:
            return False

        return user.role == UserRole.ADMIN.value

    # ----- family, student and dates -----

    @staticmethod
    def get_family_id():

        user = CurrentUser.get()

        if not user:
            return None

        return user.family_id

    @staticmethod
    def get_student_id():
        """
        Returns the student this login acts as, or None. For a parent that's
        the Student Mode student, if any.
        """

        user = CurrentUser.get()

        if not user:
            return None

        if user.role == UserRole.PARENT.value:

            mode = CurrentUser.get_student_mode()

            return mode.student_id if mode else None

        return user.student_id

    @staticmethod
    def get_today():
        """
        Returns today's date for the current family. Admins and anyone
        logged out have no family, so they get UTC's date.
        """

        return datetime.now(CurrentUser.get_zone()).date()

    @staticmethod
    def get_zone():
        """
        Returns the current family's time zone, or UTC if there isn't one.
        """

        user = CurrentUser.get()

        name = (
            user.family.timezone
            if user and user.family
            else "UTC"
        )

        try:

            zone = ZoneInfo(name)

        except (ZoneInfoNotFoundError, ValueError):

            logger.warning("Unknown family time zone: %s", name)

            zone = ZoneInfo("UTC")

        return zone
