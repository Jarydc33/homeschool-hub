from supabase import ClientOptions, create_client
import streamlit as st
import os


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

        url = os.getenv("SUPABASE_URL")

        if not url:
            url = st.secrets["SUPABASE_URL"]

        key = os.getenv("SUPABASE_KEY")

        if not key:
            key = st.secrets["SUPABASE_KEY"]

        return SupabaseService._create(
            url,
            key
        )

    @staticmethod
    def get_admin_client():

        url = os.getenv("SUPABASE_URL")

        if not url:
            url = st.secrets["SUPABASE_URL"]

        service_key = os.getenv("SERVICE_KEY")

        if not service_key:
            service_key = st.secrets["SERVICE_KEY"]

        return SupabaseService._create(
            url,
            service_key
        )
