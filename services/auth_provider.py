import base64
import json
import logging

from supabase_auth.errors import AuthApiError, AuthWeakPasswordError

from services.supabase_service import (
    SupabaseService
)

# Streamlit and the browser session (SessionService) are imported only inside
# the Streamlit-only methods below (get_current_auth_user,
# _refresh_saved_login and complete_email_link), so the API can use the rest
# without Streamlit. Those methods go when the Streamlit app is retired.

logger = logging.getLogger(__name__)

EXPIRED_LINK_MESSAGES = {
    "invite": (
        "This invitation link has expired or has already been used. "
        "Please ask a parent to send a new one."
    ),
    "recovery": (
        "This password reset link has expired or has already been used. "
        "Please request a new one."
    ),
}


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
    def is_wrong_password(
        error
    ):
        """
        True when Supabase refused the email and password themselves, not
        for an outage, a rate limit, or an unconfirmed email.
        """

        return (
            isinstance(error, AuthApiError)
            and error.status == 400
            and error.code == "invalid_credentials"
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
        refresh_token=None,
        scope="local"
    ):
        """
        Ends this session in Supabase. Other devices stay logged in unless
        scope is "global". A failure is only logged, so it can't stop
        someone logging out.
        """

        supabase = (
            SupabaseService.get_client()
        )

        try:

            try:

                supabase.auth.admin.sign_out(
                    access_token,
                    scope
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
                    scope
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
    def new_account_id(
        auth_result
    ):
        """
        Returns the id of the account a sign-up just created, or None if the
        email was already registered. With email confirmation on, Supabase
        hides that by returning a made-up user with no identities, and its id
        doesn't belong to any account.
        """

        user = auth_result.user

        if not user or not user.identities:
            return None

        return user.id

    @staticmethod
    def register_error_message(
        error
    ):
        """
        Returns what to show someone when signing up fails, and logs the
        detail for us.
        """

        logger.warning(
            "Signing up failed: %s %s",
            type(error).__name__,
            getattr(error, "code", None)
        )

        if isinstance(error, AuthWeakPasswordError):

            return "Please choose a stronger password."

        if isinstance(error, AuthApiError):

            if error.status == 429:

                return (
                    "Too many sign-up attempts. "
                    "Please wait a few minutes and try again."
                )

            if error.status < 500:

                return (
                    "We couldn't create your account. "
                    "Please check your email and password and try again."
                )

        return (
            "We couldn't create your account right now. "
            "Please try again in a moment."
        )

    @staticmethod
    def delete_auth_user(
        auth_user_id
    ):

        SupabaseService.get_admin_client().auth.admin.delete_user(
            auth_user_id
        )

    @staticmethod
    def get_current_auth_user():

        from services.session_service import SessionService

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
    def session_id_from_token(
        access_token
    ):
        """
        Returns the session_id claim in a Supabase access token, or None.
        It stays the same when the token is refreshed and changes with each
        new login. The signature isn't checked here, so use it only once
        Supabase has accepted the token, as finding the current user does.
        """

        if not access_token:
            return None

        try:

            payload = access_token.split(".")[1]

            claims = json.loads(
                base64.urlsafe_b64decode(
                    payload + "=" * (-len(payload) % 4)
                )
            )

        except (IndexError, ValueError):

            return None

        session_id = claims.get("session_id")

        return str(session_id) if session_id else None

    @staticmethod
    def _refresh_saved_login(
        supabase
    ):
        """
        Swaps an expired saved login for a new one, then reruns so the new
        tokens reach the browser. Each refresh token only works once, so
        nothing else can happen until they're saved.
        """

        import streamlit as st

        from services.session_service import SessionService

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
                    "https://tally-homeschool.streamlit.app/Complete_Account"
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
    def get_auth_user(
        auth_user_id
    ):

        return (
            SupabaseService.get_admin_client()
            .auth.admin.get_user_by_id(auth_user_id)
            .user
        )

    @staticmethod
    def is_email_taken_error(
        error
    ):

        return (
            isinstance(error, AuthApiError)
            and error.code == "email_exists"
        )

    @staticmethod
    def set_auth_email(
        auth_user_id,
        email,
        confirmed
    ):
        """
        Changes a Supabase account's email without asking the new address
        to confirm. A finished account stays confirmed so it can still log
        in. A pending invite stays unconfirmed so it can be invited again.
        """

        attributes = {
            "email": email
        }

        if confirmed:

            attributes["email_confirm"] = True

        SupabaseService.get_admin_client().auth.admin.update_user_by_id(
            auth_user_id,
            attributes
        )

    @staticmethod
    def resend_invite_error_message(
        error
    ):
        """
        Returns what to show a parent when resending an invite fails, and
        logs the detail for us.
        """

        logger.warning(
            "Resending an invite failed: %s %s",
            type(error).__name__,
            getattr(error, "code", None)
        )

        if isinstance(error, AuthApiError):

            if error.code == "email_exists":

                return (
                    "This student has already set up their account. If "
                    "they've forgotten their password, they can use "
                    "\"Forgot your password?\" on the Login page."
                )

            if error.status == 429:

                return (
                    "An email was sent recently. "
                    "Please wait a few minutes and try again."
                )

        return (
            "We couldn't send the invitation. "
            "Please try again in a moment."
        )

    @staticmethod
    def send_password_reset(
        email
    ):
        """
        Emails a password reset link. Returns a message to show if it
        couldn't be sent, or None. Unknown emails look the same as known
        ones, so this can't be used to find out who has an account.
        """

        supabase = (
            SupabaseService.get_client()
        )

        try:

            supabase.auth.reset_password_for_email(
                email
            )

        except Exception as ex:

            logger.warning(
                "Sending a password reset failed: %s %s",
                type(ex).__name__,
                getattr(ex, "code", None)
            )

            if (
                isinstance(ex, AuthApiError)
                and ex.status == 429
            ):

                return (
                    "An email was sent recently. "
                    "Please wait a few minutes and try again."
                )

            if (
                isinstance(ex, AuthApiError)
                and ex.status < 500
            ):

                return (
                    "Please check the email address and try again."
                )

            return (
                "We couldn't send the email right now. "
                "Please try again in a moment."
            )

        return None

    @staticmethod
    def complete_email_link(
        token_hash,
        link_type,
        password
    ):
        """
        Uses the token from an invite ("invite") or password reset
        ("recovery") link to set that person's password.
        Returns a message to show if it failed, or None if it worked.

        The token only works once, so its session is kept for this browser
        session. If the password is rejected, they can try another one.
        """

        import streamlit as st

        session = st.session_state.get(
            "email_link_session"
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
                            "type": link_type
                        }
                    ).session
                )

            except AuthApiError as ex:

                logger.warning(
                    "Verifying an email link failed: %s",
                    ex.code
                )

                return EXPIRED_LINK_MESSAGES[link_type]

            except Exception as ex:

                logger.warning(
                    "Verifying an email link failed: %s",
                    type(ex).__name__
                )

                return (
                    "We couldn't finish this right now. "
                    "Please try again in a moment."
                )

            st.session_state[
                "email_link_session"
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
                    "Resuming an email link failed: %s",
                    type(ex).__name__
                )

                st.session_state.pop(
                    "email_link_session",
                    None
                )

                return EXPIRED_LINK_MESSAGES[link_type]

            st.session_state[
                "email_link_session"
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
                "Setting a password from an email link failed: %s %s",
                type(ex).__name__,
                getattr(ex, "code", None)
            )

            return (
                "We couldn't save that password. "
                "Please try again or choose a different one."
            )

        # They log in themselves, so finishing this page can't replace a
        # login already saved in this browser. End the session from the link.
        # A password reset ends every session, in case the old password was
        # stolen, so anyone using it is logged out everywhere.

        AuthProvider.sign_out(
            session.access_token,
            session.refresh_token,
            "global" if link_type == "recovery" else "local"
        )

        st.session_state.pop(
            "email_link_session",
            None
        )

        return None