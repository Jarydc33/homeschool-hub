import logging
import re

import streamlit as st

from services.user_service import UserService
from database.models import UserRole

from services.auth_provider import AuthProvider
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


class AuthService:

    @staticmethod
    def update_student_email(
        student_id,
        new_email
    ):
        """
        Changes a student's login email. Returns (True, message) or
        (False, message), and a failure leaves the old email in place.

        The email lives in both Supabase and our users table, and they're
        linked by it, so both must change together. Supabase goes first
        because it's the more likely to refuse. If our table then fails,
        Supabase is changed back.

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

            accounts = AuthProvider.find_auth_users(
                old_email,
                new_email
            )

        except Exception as ex:

            logger.warning(
                "Looking up accounts for an email change failed: %s",
                type(ex).__name__
            )

            return False, EMAIL_UPDATE_FAILED_MESSAGE

        if new_email in accounts:

            return False, EMAIL_TAKEN_MESSAGE

        account = accounts.get(old_email)

        finished = bool(
            account and account.email_confirmed_at
        )

        try:

            if account:

                AuthProvider.set_auth_email(
                    account.id,
                    new_email,
                    finished
                )

            if not finished:

                AuthProvider.create_student_account(
                    new_email
                )

        except Exception as ex:

            logger.warning(
                "Changing an account's email failed: %s %s",
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

        if not account:
            return

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
    def set_current_user(user_id):

        st.session_state[
            "current_user_id"
        ] = user_id

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

        email = (
            auth_user.user.email
        )

        user = AuthService._allow_login(
            UserService.get_user_by_email(
                email
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
        )

    @staticmethod
    def is_student():

        user = (
            AuthService.get_current_user()
        )

        if not user:
            return False

        return (
            user.role
            == UserRole.STUDENT.value
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
    def get_current_student():

        user = (
            AuthService.get_current_user()
        )

        if not user:
            return None

        return user.student_id

    @staticmethod
    def logout():
        """
        Ends the session in Supabase and here, and queues removing the token
        from the browser. Follow this with st.rerun().
        """

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
