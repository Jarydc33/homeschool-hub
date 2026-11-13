import threading

from supabase import ClientOptions, create_client

from config import get_setting

_token_client = None
_token_client_lock = threading.Lock()


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
    def get_token_client():
        """
        One client shared by every API request, only for checking access
        tokens with auth.get_user(token). That call is given the token and
        stores nothing on the client, so sharing it is safe, and reusing its
        connection saves a new encrypted handshake with Supabase on every
        request. Never sign in, refresh or set a session on it: use
        get_client() for anything that does.
        """

        global _token_client

        with _token_client_lock:

            if _token_client is None:

                _token_client = SupabaseService._create(
                    get_setting("SUPABASE_URL"),
                    get_setting("SUPABASE_KEY")
                )

            return _token_client

    @staticmethod
    def get_admin_client():

        url = get_setting("SUPABASE_URL")

        service_key = get_setting("SERVICE_KEY")

        return SupabaseService._create(
            url,
            service_key
        )
