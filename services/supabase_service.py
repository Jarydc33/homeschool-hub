from supabase import ClientOptions, create_client

from config import get_setting


class SupabaseService:

    @staticmethod
    def _create(url, key):
        """
        Each call gets its own client, so one person's session can't reach
        another's. Auto refresh stays off because it would use up refresh
        tokens on a background timer, and each one only works once. The
        browser holds the login, and AuthProvider refreshes it when needed.
        """

        return create_client(
            url,
            key,
            options=ClientOptions(
                auto_refresh_token=False,
                persist_session=False
            )
        )

    @staticmethod
    def get_client():

        url = get_setting("SUPABASE_URL")

        key = get_setting("SUPABASE_KEY")

        return SupabaseService._create(
            url,
            key
        )

    @staticmethod
    def get_admin_client():

        url = get_setting("SUPABASE_URL")

        service_key = get_setting("SERVICE_KEY")

        return SupabaseService._create(
            url,
            service_key
        )
