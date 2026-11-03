import logging

import streamlit as st
from supabase_auth.errors import AuthApiError, AuthWeakPasswordError

from services.supabase_service import (
    SupabaseService
)

from services.session_service import (
    SessionService
)

logger = logging.getLogger(__name__)


class AuthProvider:

    @staticmethod
    def login(
        email,
        password
    ):

        supabase = (
            SupabaseService.get_client()
        )

        return (
            supabase.auth.sign_in_with_password(
                {
                    "email": email,
                    "password": password
                }
            )
        )

    @staticmethod
    def login_error_message(
        error
    ):
        """
        Returns what to show someone when logging in fails, and logs the
        detail for us.
        """

        logger.warning(
            "Login failed: %s %s",
            type(error).__name__,
            getattr(error, "code", None)
        )

        if isinstance(error, AuthApiError):

            if error.code == "email_not_confirmed":

                return (
                    "Please confirm your email address, "
                    "then try logging in again."
                )

            if error.status == 429:

                return (
                    "Too many login attempts. "
                    "Please wait a few minutes and try again."
                )

            if error.status < 500:

                return "Incorrect email or password."

        return (
            "We couldn't log you in right now. "
            "Please try again in a moment."
        )

    @staticmethod
    def sign_out(
        access_token,
        refresh_token=None
    ):
        """
        Ends this session in Supabase. Other devices stay logged in.
        A failure is only logged, so it can't stop someone logging out.
        """

        supabase = (
            SupabaseService.get_client()
        )

        try:

            try:

                supabase.auth.admin.sign_out(
                    access_token,
                    "local"
                )

            except AuthApiError:

                # An expired access token can't end its own session, but
                # the refresh token could still be used. Get a new one first.

                if not refresh_token:
                    raise

                session = (
                    supabase.auth.refresh_session(
                        refresh_token
                    ).session
                )

                supabase.auth.admin.sign_out(
                    session.access_token,
                    "local"
                )

        except Exception as ex:

            logger.warning(
                "Supabase sign out failed: %s",
                type(ex).__name__
            )

    @staticmethod
    def register(
        email,
        password
    ):

        supabase = (
            SupabaseService.get_client()
        )

        return (
            supabase.auth.sign_up(
                {
                    "email": email,
                    "password": password
                }
            )
        )

    @staticmethod
    def get_current_auth_user():

        access_token = (
            SessionService.get_access_token()
        )

        if not access_token:
            return None

        supabase = (
            SupabaseService.get_client()
        )

        try:

            user = (
                supabase.auth.get_user(
                    access_token
                )
            )

            return user

        except AuthApiError:

            # Supabase rejected the token, which usually means it expired.

            return AuthProvider._refresh_saved_login(
                supabase
            )

        except Exception:

            # Probably a network problem, so keep the login for next time.

            return None

    @staticmethod
    def _refresh_saved_login(
        supabase
    ):
        """
        Swaps an expired saved login for a new one, then reruns so the new
        tokens reach the browser. Each refresh token only works once, so
        nothing else can happen until they're saved.
        """

        refresh_token = (
            SessionService.get_known_refresh_token()
        )

        if not refresh_token:

            SessionService.forget_session()

            return None

        try:

            session = (
                supabase.auth.refresh_session(
                    refresh_token
                ).session
            )

        except AuthApiError:

            # The login has ended, so they'll need to log in again.

            SessionService.forget_session()

            return None

        except Exception as ex:

            logger.warning(
                "Refreshing a saved login failed: %s",
                type(ex).__name__
            )

            return None

        SessionService.save_session(
            session.access_token,
            session.refresh_token
        )

        st.rerun()

    @staticmethod
    def create_student_account(
        email
    ):

        supabase = (
            SupabaseService.get_admin_client()
        )

        return (
            supabase.auth.admin.invite_user_by_email(
                email,
                {
                    "redirect_to":
                    "https://homeschool-app.streamlit.app/Complete_Account"
                }
            )
        )

    @staticmethod
    def invite_send_error_message(
        error
    ):
        """
        Returns what to show a parent when sending an invite fails, and
        logs the detail for us.
        """

        logger.warning(
            "Sending an invite failed: %s %s",
            type(error).__name__,
            getattr(error, "code", None)
        )

        if (
            isinstance(error, AuthApiError)
            and error.code == "email_exists"
        ):

            return (
                "This email already has an account. "
                "Please use a different email."
            )

        return (
            "We couldn't send the invitation. "
            "Please check the email address and try again."
        )

    @staticmethod
    def complete_invite(
        token_hash,
        password
    ):
        """
        Uses the token from an invite link to set that person's password.
        Returns a message to show if it failed, or None if it worked.

        The token only works once, so its session is kept for this browser
        session. If the password is rejected, they can try another one.
        """

        session = st.session_state.get(
            "invite_session"
        )

        supabase = (
            SupabaseService.get_client()
        )

        if not session:

            try:

                session = (
                    supabase.auth.verify_otp(
                        {
                            "token_hash": token_hash,
                            "type": "invite"
                        }
                    ).session
                )

            except AuthApiError as ex:

                logger.warning(
                    "Verifying an invite failed: %s",
                    ex.code
                )

                return (
                    "This invitation link has expired or has already "
                    "been used. Please ask a parent to send a new one."
                )

            except Exception as ex:

                logger.warning(
                    "Verifying an invite failed: %s",
                    type(ex).__name__
                )

                return (
                    "We couldn't set up your account right now. "
                    "Please try again in a moment."
                )

            st.session_state[
                "invite_session"
            ] = session

        else:

            try:

                session = (
                    supabase.auth.set_session(
                        session.access_token,
                        session.refresh_token
                    ).session
                )

            except Exception as ex:

                logger.warning(
                    "Resuming an invite failed: %s",
                    type(ex).__name__
                )

                st.session_state.pop(
                    "invite_session",
                    None
                )

                return (
                    "This invitation link has expired or has already "
                    "been used. Please ask a parent to send a new one."
                )

            st.session_state[
                "invite_session"
            ] = session

        try:

            supabase.auth.update_user(
                {
                    "password": password
                }
            )

        except AuthWeakPasswordError:

            return (
                "That password is too easy to guess. "
                "Please choose a stronger one."
            )

        except Exception as ex:

            logger.warning(
                "Setting an invited password failed: %s %s",
                type(ex).__name__,
                getattr(ex, "code", None)
            )

            return (
                "We couldn't save that password. "
                "Please try again or choose a different one."
            )

        # They log in themselves, so finishing this page can't replace a
        # login already saved in this browser. End the setup session.

        AuthProvider.sign_out(
            session.access_token,
            session.refresh_token
        )

        st.session_state.pop(
            "invite_session",
            None
        )

        return None