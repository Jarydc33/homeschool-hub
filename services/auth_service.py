import streamlit as st

from services.user_service import UserService
from database.models import UserRole

from services.auth_provider import AuthProvider
from services.session_service import (
    SessionService
)

class AuthService:

    @staticmethod
    def set_current_user(user_id):

        st.session_state[
            "current_user_id"
        ] = user_id

    @staticmethod
    def get_current_user():

        user_id = (
            st.session_state.get(
                "current_user_id"
            )
        )

        if user_id:

            return (
                UserService.get_user_by_id(
                    user_id
                )
            )

        auth_user = (
            AuthProvider.get_current_auth_user()
        )

        if not auth_user:
            return None

        email = (
            auth_user.user.email
        )

        user = (
            UserService.get_user_by_email(
                email
            )
        )

        if user:

            AuthService.set_current_user(
                user.id
            )

        return user

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
    def is_admin():

        user = (
            AuthService.get_current_user()
        )

        if not user:
            return False

        return (
            user.role
            == UserRole.ADMIN.value
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

        pass
