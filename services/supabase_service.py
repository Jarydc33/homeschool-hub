from supabase import create_client
import streamlit as st
import os


class SupabaseService:

    @staticmethod
    def get_client():

        url = os.getenv("SUPABASE_URL")

        if not url:
            url = st.secrets["SUPABASE_URL"]

        key = os.getenv("SUPABASE_KEY")

        if not key:
            key = st.secrets["SUPABASE_KEY"]

        return create_client(
            url,
            key
        )