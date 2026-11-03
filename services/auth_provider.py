import logging

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
    def sign_out(
        access_token
    ):
        """
        Ends this session in Supabase. Other devices stay logged in.
        A failure is only logged, so it can't stop someone logging out.
        """

        supabase = (
            SupabaseService.get_client()
        )

        try:

            supabase.auth.admin.sign_out(
                access_token,
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

        except Exception:

            return None

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