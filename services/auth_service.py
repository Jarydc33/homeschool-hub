import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st

from services.family_service import FamilyService
from services.user_service import UserService
from database.models import DEFAULT_TIMEZONE, UserRole

from services.auth_provider import AuthProvider
from services.student_mode_service import StudentModeService
from services.session_service import (
    SessionService
)

logger = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

EMAIL_TAKEN_MESSAGE = (
    "This email already has an account. Please use a different email."
)

EMAIL_UPDATE_FAILED_MESSAGE = (
    "We couldn't update the email, so nothing was changed. "
    "Please try again in a moment."
)

REGISTERED_EMAIL_MESSAGE = (
    "This email already has an account. Please log in instead."
)

REGISTRATION_FAILED_MESSAGE = (
    "We couldn't finish creating your account, so nothing was saved. "
    "Please try again in a moment."
)

INVITE_FAILED_MESSAGE = (
    "We couldn't finish creating this login, so nothing was saved. "
    "Please try again in a moment."
)

# Holds the current user for one page run. Having no user is saved too, since
# looking that up can mean a call to Supabase.
USER_THIS_RUN = "current_user_this_run"

# Holds this login's Student Mode row, or None, for one page run.
MODE_THIS_RUN = "student_mode_this_run"


class AuthService:

    @staticmethod
    def register_parent(
        family_name,
        email,
        password,
        timezone=DEFAULT_TIMEZONE
    ):
        """
        Creates a Supabase account, then the family and parent that go with
        it. Returns (user, session, None), or (None, None, message) when
        nothing was created.

        Supabase can't share a transaction with our database, so if saving
        fails, an account nothing uses is removed. Otherwise the email could
        be stuck with no app user to log in as.
        """

        email = email.strip().lower()

        try:

            auth_result = AuthProvider.register(
                email=email,
                password=password
            )

        except Exception as ex:

            return None, None, AuthProvider.register_error_message(ex)

        auth_user_id = AuthProvider.new_account_id(
            auth_result
        )

        if not auth_user_id:

            return None, None, REGISTERED_EMAIL_MESSAGE

        # Supabase hands back the existing account for an email that hasn't
        # been confirmed yet, which may already belong to someone here.

        if UserService.get_user_by_auth_id(auth_user_id):

            return None, None, REGISTERED_EMAIL_MESSAGE

        try:

            user = FamilyService.create_family_with_parent(
                family_name,
                email,
                auth_user_id,
                timezone
            )

        except Exception as ex:

            logger.warning(
                "Saving a new family failed: %s",
                type(ex).__name__
            )

            AuthService._remove_unused_account(
                auth_user_id
            )

            return None, None, REGISTRATION_FAILED_MESSAGE

        return user, auth_result.session, None

    @staticmethod
    def invite_student(
        student_id,
        email
    ):
        """
        Invites a student by email and saves their login. Returns
        (True, message) or (False, message).

        The invite goes first because it needs the new account's id. If
        saving then fails, an account nothing uses is removed, so the parent
        can simply try again.
        """

        family_id = AuthService.get_current_family()

        if not AuthService.is_parent() or family_id is None:

            return False, "You do not have access to do this."

        email = (email or "").strip().lower()

        if not EMAIL_PATTERN.match(email):

            return False, "Please enter a valid email address."

        if UserService.get_user_by_student_id(
            student_id,
            family_id
        ):

            return False, "Student already has a login."

        if UserService.get_user_by_email(email):

            return False, EMAIL_TAKEN_MESSAGE

        try:

            invite = AuthProvider.create_student_account(
                email
            )

        except Exception as ex:

            return False, AuthProvider.invite_send_error_message(ex)

        auth_user_id = invite.user.id

        try:

            user = UserService.create_student_user(
                family_id=family_id,
                student_id=student_id,
                email=email,
                auth_user_id=auth_user_id
            )

        except Exception as ex:

            logger.warning(
                "Saving a student login failed: %s",
                type(ex).__name__
            )

            AuthService._remove_unused_account(
                auth_user_id
            )

            return False, INVITE_FAILED_MESSAGE

        if not user:

            AuthService._remove_unused_account(
                auth_user_id
            )

            return False, "This student could not be found."

        return True, f"Invitation sent to {email}."

    @staticmethod
    def _remove_unused_account(
        auth_user_id
    ):
        """
        Removes a Supabase account after its login couldn't be saved. An
        account a users row points to belongs to someone else, because
        Supabase returns the existing account for an unconfirmed email, so
        it stays. So does any account we can't check: deleting can't be
        undone, and an unconfirmed email can still try again.
        """

        try:

            if UserService.get_user_by_auth_id(auth_user_id):

                return

            AuthProvider.delete_auth_user(
                auth_user_id
            )

        except Exception as ex:

            logger.error(
                "Removing an unused account failed, leaving auth user %s "
                "with no app user: %s",
                auth_user_id,
                type(ex).__name__
            )

    @staticmethod
    def update_student_email(
        student_id,
        new_email
    ):
        """
        Changes a student's login email. Returns (True, message) or
        (False, message), and a failure leaves the old email in place.

        The email lives in both Supabase and our users table, and people
        sign in with Supabase's, so both must change together. Supabase goes
        first because it's the more likely to refuse, and it refuses an email
        that another account already has. If our table then fails, Supabase
        is changed back.

        Someone who has finished setting up keeps their password. Someone
        who hasn't gets a new invitation at the new address, which also
        replaces the link sent to the old one.
        """

        family_id = AuthService.get_current_family()

        if not AuthService.is_parent() or family_id is None:

            return False, "You do not have access to do this."

        new_email = (new_email or "").strip().lower()

        if not EMAIL_PATTERN.match(new_email):

            return False, "Please enter a valid email address."

        user = UserService.get_user_by_student_id(
            student_id,
            family_id
        )

        if not user:

            return False, "This student doesn't have a login yet."

        old_email = user.email

        if new_email == old_email:

            return False, "That's already this student's email."

        if UserService.get_user_by_email(new_email):

            return False, EMAIL_TAKEN_MESSAGE

        try:

            account = AuthProvider.get_auth_user(
                user.auth_user_id
            )

        except Exception as ex:

            logger.warning(
                "Looking up an account for an email change failed: %s",
                type(ex).__name__
            )

            return False, EMAIL_UPDATE_FAILED_MESSAGE

        finished = bool(
            account.email_confirmed_at
        )

        try:

            AuthProvider.set_auth_email(
                account.id,
                new_email,
                finished
            )

        except Exception as ex:

            logger.warning(
                "Changing an account's email failed: %s %s",
                type(ex).__name__,
                getattr(ex, "code", None)
            )

            if AuthProvider.is_email_taken_error(ex):

                return False, EMAIL_TAKEN_MESSAGE

            return False, EMAIL_UPDATE_FAILED_MESSAGE

        if not finished:

            try:

                AuthProvider.create_student_account(
                    new_email
                )

            except Exception as ex:

                logger.warning(
                    "Inviting a changed email failed: %s %s",
                    type(ex).__name__,
                    getattr(ex, "code", None)
                )

                AuthService._restore_auth_email(
                    account,
                    old_email,
                    finished
                )

                return False, EMAIL_UPDATE_FAILED_MESSAGE

        try:

            updated = UserService.update_user_email(
                user.id,
                family_id,
                new_email
            )

        except Exception as ex:

            logger.warning(
                "Saving a changed email failed: %s",
                type(ex).__name__
            )

            updated = None

        if not updated:

            AuthService._restore_auth_email(
                account,
                old_email,
                finished
            )

            return False, EMAIL_UPDATE_FAILED_MESSAGE

        if finished:

            return True, (
                f"Email updated. They can now log in with {new_email} "
                "and the same password."
            )

        return True, (
            f"Email updated. A new invitation was sent to {new_email}."
        )

    @staticmethod
    def _restore_auth_email(
        account,
        old_email,
        finished
    ):
        """
        Puts a Supabase account's email back after a later step failed.
        """

        try:

            AuthProvider.set_auth_email(
                account.id,
                old_email,
                finished
            )

        except Exception as ex:

            # The two now disagree, and that student can't log in until
            # someone fixes it by hand.

            logger.error(
                "Restoring an account's email failed, leaving Supabase and "
                "the users table out of step for auth user %s: %s",
                account.id,
                type(ex).__name__
            )

    @staticmethod
    def start_page_run():
        """
        Forgets the saved user, so this page run looks them up fresh. Run it
        before anything reads the current user. NavigationComponent.render()
        does, and so does app.py.

        A button in an open dialog reruns only the dialog, so it keeps the
        user from when the page last ran.
        """

        st.session_state.pop(
            USER_THIS_RUN,
            None
        )

        AuthService.forget_student_mode()

    @staticmethod
    def forget_student_mode():
        """
        Makes the next check look up Student Mode fresh, after it starts or
        ends.
        """

        st.session_state.pop(
            MODE_THIS_RUN,
            None
        )

    @staticmethod
    def get_auth_session_id():
        """
        Returns the Supabase session behind this login, or None.
        """

        return AuthProvider.session_id_from_token(
            SessionService.get_known_token()
        )

    @staticmethod
    def get_student_mode():
        """
        Returns this login's Student Mode row, with its student, or None.
        Only a parent's login can be in Student Mode. Looked up once per
        page run.
        """

        if MODE_THIS_RUN not in st.session_state:

            st.session_state[
                MODE_THIS_RUN
            ] = AuthService._load_student_mode()

        return st.session_state[
            MODE_THIS_RUN
        ]

    @staticmethod
    def _load_student_mode():

        user = AuthService.get_current_user()

        if not user or user.role != UserRole.PARENT.value:
            return None

        return StudentModeService.find_active(
            user.family_id,
            AuthService.get_auth_session_id()
        )

    @staticmethod
    def set_current_user(user_id):

        st.session_state[
            "current_user_id"
        ] = user_id

        AuthService.start_page_run()

    @staticmethod
    def is_archived_student(user):
        """
        True for a student login whose student has been archived.
        They can't sign in until the student is unarchived.
        """

        if user.role != UserRole.STUDENT.value:
            return False

        return not (
            user.student
            and user.student.active
        )

    @staticmethod
    def _allow_login(user):
        """
        Returns the user, or None if their account can't be used.
        The flag lets the Login page explain why.
        """

        if user and AuthService.is_archived_student(user):

            st.session_state[
                "account_inactive"
            ] = True

            return None

        return user

    @staticmethod
    def get_current_user():
        """
        Returns the signed-in user, looking them up once per page run.
        """

        if USER_THIS_RUN not in st.session_state:

            st.session_state[
                USER_THIS_RUN
            ] = AuthService._load_current_user()

        return st.session_state[
            USER_THIS_RUN
        ]

    @staticmethod
    def _load_current_user():

        user_id = (
            st.session_state.get(
                "current_user_id"
            )
        )

        if user_id:

            return AuthService._allow_login(
                UserService.get_user_by_id(
                    user_id
                )
            )

        auth_user = (
            AuthProvider.get_current_auth_user()
        )

        if not auth_user:
            return None

        user = AuthService._allow_login(
            UserService.get_user_by_auth_id(
                auth_user.user.id
            )
        )

        if user:

            AuthService.set_current_user(
                user.id
            )

        return user

    @staticmethod
    def is_authenticated():

        return (
            AuthService.get_current_user()
            is not None
        )

    @staticmethod
    def is_parent():

        user = (
            AuthService.get_current_user()
        )

        if not user:
            return False

        return (
            user.role
            == UserRole.PARENT.value
            and not AuthService.get_student_mode()
        )

    @staticmethod
    def is_student():

        user = (
            AuthService.get_current_user()
        )

        if not user:
            return False

        if user.role == UserRole.STUDENT.value:
            return True

        # A parent's login in Student Mode counts as that student.

        return (
            user.role == UserRole.PARENT.value
            and AuthService.get_student_mode() is not None
        )

    @staticmethod
    def is_admin():

        user = (
            AuthService.get_current_user()
        )

        if not user:
            return False

        return (
            user.role
            == UserRole.ADMIN.value
        )

    @staticmethod
    def get_current_family():

        user = (
            AuthService.get_current_user()
        )

        if not user:
            return None

        return user.family_id

    @staticmethod
    def get_today():
        """
        Returns today's date for the current family. Admins and anyone
        logged out have no family, so they get UTC's date.
        """

        return datetime.now(AuthService.get_zone()).date()

    @staticmethod
    def get_zone():
        """
        Returns the current family's time zone, or UTC if there isn't one.
        """

        user = AuthService.get_current_user()

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

    @staticmethod
    def get_current_student():

        user = (
            AuthService.get_current_user()
        )

        if not user:
            return None

        if user.role == UserRole.PARENT.value:

            mode = AuthService.get_student_mode()

            return mode.student_id if mode else None

        return user.student_id

    @staticmethod
    def logout():
        """
        Ends the session in Supabase and here, and queues removing the token
        from the browser. Follow this with st.rerun().
        """

        # Logging out of Student Mode is allowed without the PIN, since
        # getting back in needs the parent's password.

        StudentModeService.end_current_for_logout()

        access_token = (
            SessionService.get_known_token()
        )

        if access_token:

            AuthProvider.sign_out(
                access_token,
                SessionService.get_known_refresh_token()
            )

        SessionService.clear_session()

        st.session_state.pop(
            "current_user_id",
            None
        )

        AuthService.start_page_run()
