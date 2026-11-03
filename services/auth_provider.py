import logging

import streamlit as st
from supabase_auth.errors import AuthApiError

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
    def set_password(
        password
    ):

        supabase = (
            SupabaseService.get_client()
        )

        return (
            supabase.auth.update_user(
                {
                    "password": password
                }
            )
        )