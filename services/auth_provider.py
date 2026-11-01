from services.supabase_service import (
    SupabaseService
)

from services.session_service import (
    SessionService
)

class AuthProvider:

    @staticmethod
    def login(
        email,
        password
    ):

        supabase = (
            SupabaseService.get_client()
        )

        result = (
            supabase.auth.sign_in_with_password(
                {
                    "email": email,
                    "password": password
                }
            )
        )

        if result.session:

            SessionService.save_session(
                result.session.access_token,
                None
            )

        return result

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

        session = (
            SessionService.get_session()
        )

        if not session:
            return None

        access_token = (
            session.get(
                "access_token"
            )
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
    def logout():
        SessionService.clear_session()