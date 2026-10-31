import streamlit as st

from services.user_service import UserService
from services.auth_service import AuthService

st.title("🔐 Authentication Test")

email = st.text_input(
    "User Email"
)

if st.button("Login"):

    user = (
        UserService.get_user_by_email(
            email
        )
    )

    if not user:

        st.error(
            "User not found."
        )

    else:

        st.session_state[
            "current_user_id"
        ] = user.id

        st.success(
            f"Logged in as {user.email}"
        )

if st.button("Logout"):

    AuthService.logout()

    st.rerun()

st.divider()

st.subheader("Current User")

current_user = (
    AuthService.get_current_user()
)

if current_user:

    st.sidebar.success(
        f"Logged in as: "
        f"{current_user.email}"
    )

    st.sidebar.write(
        f"Role: {current_user.role}"
    )

    if st.sidebar.button(
        "Logout"
    ):

        AuthService.logout()

        st.rerun()

    st.write(
        "Email:",
        current_user.email
    )

    st.write(
        "Role:",
        current_user.role
    )

    st.write(
        "Family ID:",
        current_user.family_id
    )

    st.write(
        "Student ID:",
        current_user.student_id
    )

    st.write(
        "Authenticated:",
        AuthService.is_authenticated()
    )

    st.write(
        "Parent:",
        AuthService.is_parent()
    )

    st.write(
        "Student:",
        AuthService.is_student()
    )

else:

    st.info(
        "No user logged in."
    )