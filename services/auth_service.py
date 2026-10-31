import streamlit as st

from services.user_service import UserService
from database.models import UserRole


class AuthService:

    @staticmethod
    def get_current_user():

        user_id = (
            st.session_state.get(
                "current_user_id"
            )
        )

        if not user_id:
            return None

        return (
            UserService.get_user_by_id(
                user_id
            )
        )

    @staticmethod
    def is_authenticated():

        return (
            AuthService.get_current_user()
            is not None
        )

    @staticmethod
    def is_parent():

        user = (
            AuthService.get_current_user()
        )

        if not user:
            return False

        return (
            user.role
            == UserRole.PARENT.value
        )

    @staticmethod
    def is_student():

        user = (
            AuthService.get_current_user()
        )

        if not user:
            return False

        return (
            user.role
            == UserRole.STUDENT.value
        )

    @staticmethod
    def get_current_family():

        user = (
            AuthService.get_current_user()
        )

        if not user:
            return None

        return user.family_id

    @staticmethod
    def get_current_student():

        user = (
            AuthService.get_current_user()
        )

        if not user:
            return None

        return user.student_id

    @staticmethod
    def logout():

        st.session_state.pop(
            "current_user_id",
            None
        )
    @staticmethod
    def set_current_user(user_id):
        """
        Developer shortcut for logging in as a user.
        """

        st.session_state[
            "current_user_id"
        ] = user_id