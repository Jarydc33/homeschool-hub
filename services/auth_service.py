import logging
import re

import streamlit as st

from services.family_service import FamilyService
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

REGISTERED_EMAIL_MESSAGE = (
    "This email already has an account. Please log in instead."
)

REGISTRATION_FAILED_MESSAGE = (
    "We couldn't finish creating your account, so nothing was saved. "
    "Please try again in a moment."
)


class AuthService:

    @staticmethod
    def register_parent(
        family_name,
        email,
        password
    ):
        """
        Creates a Supabase account, then the family and parent that go with
        it. Returns (user, session, None), or (None, None, message) when
        nothing was created.

        Supabase can't share a transaction with our database, so if saving
        fails, the account made here is removed. Otherwise the email could
        never sign up again, and it would have no app user to log in as.
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

        try:

            user = FamilyService.create_family_with_parent(
                family_name,
                email,
                auth_user_id
            )

        except Exception as ex:

            logger.warning(
                "Saving a new family failed: %s",
                type(ex).__name__
            )

            AuthService._remove_new_account(
                auth_user_id
            )

            return None, None, REGISTRATION_FAILED_MESSAGE

        return user, auth_result.session, None

    @staticmethod
    def _remove_new_account(
        auth_user_id
    ):
        """
        Removes the Supabase account from a sign-up that couldn't be saved.
        """

        try:

            AuthProvider.delete_auth_user(
                auth_user_id
            )

        except Exception as ex:

            # That email can't sign up again until someone removes the
            # account by hand.

            logger.error(
                "Removing a new account failed, leaving auth user %s with no "
                "app user: %s",
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
