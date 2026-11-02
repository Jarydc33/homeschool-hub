import streamlit as st

from services.auth_service import AuthService


class NavigationService:

    @staticmethod
    def require_authentication():

        if not AuthService.is_authenticated():

            st.warning(
                "Please login."
            )

            st.switch_page(
                "pages/🔐_Login.py"
            )

            st.stop()

    @staticmethod
    def require_parent():

        NavigationService.require_authentication()

        if AuthService.is_parent():
            return

        if AuthService.is_student():

            st.switch_page(
                "pages/🎓_Student_Dashboard.py"
            )

            st.stop()

        st.error(
            "You do not have access to this page."
        )

        st.stop()

    @staticmethod
    def require_student():

        NavigationService.require_authentication()

        if not AuthService.is_student():

            st.error(
                "You do not have access to this page."
            )

            st.stop()