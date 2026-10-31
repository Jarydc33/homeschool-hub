from services.supabase_service import (
    SupabaseService
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

        return (
            supabase.auth.sign_in_with_password(
                {
                    "email": email,
                    "password": password
                }
            )
        )
