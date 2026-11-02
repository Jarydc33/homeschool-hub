from streamlit_local_storage import LocalStorage
import streamlit as st

class SessionService:

    ACCESS_TOKEN_KEY = (
        "homeschoolhub_access_token"
    )

    REFRESH_TOKEN_KEY = (
        "homeschoolhub_refresh_token"
    )

    @staticmethod
    def get_storage():

        if "local_storage" not in st.session_state:

            st.session_state["local_storage"] = (
                LocalStorage()
            )

        return st.session_state["local_storage"]

    @staticmethod
    def save_session(
        access_token,
        refresh_token
    ):
        
        storage = (
            SessionService.get_storage()
        )

        storage.setItem(
            SessionService.ACCESS_TOKEN_KEY,
            access_token
        )

        #storage.setItem(
        #    SessionService.REFRESH_TOKEN_KEY,
        #    refresh_token
        #)

    @staticmethod
    def get_access_token():

        storage = (
            SessionService.get_storage()
        )

        return storage.getItem(
            SessionService.ACCESS_TOKEN_KEY
        )

    @staticmethod
    def get_refresh_token():

        storage = (
            SessionService.get_storage()
        )

        return storage.getItem(
            SessionService.REFRESH_TOKEN_KEY
        )

    @staticmethod
    def get_session():

        access_token = (
            SessionService.get_access_token()
        )

        refresh_token = (
            SessionService.get_refresh_token()
        )

        if not access_token:
            return None

        return {
            "access_token": access_token,
            "refresh_token": refresh_token
        }