import streamlit as st

from services.user_service import UserService
from services.auth_service import AuthService
from services.auth_provider import AuthProvider
from services.session_service import SessionService
from config import DEV_MODE
from components.navigation import (
    NavigationComponent
)

NavigationComponent.render()

if AuthService.is_authenticated():

    if AuthService.is_student():

        st.switch_page(
            "pages/🎓_Student_Dashboard.py"
        )

    else:

        st.switch_page("app.py")


st.title("🔐 Login")

st.write(
    "Sign in to Homeschool Hub."
)

INACTIVE_MESSAGE = (
    "This account is inactive. "
    "Please ask a parent to reactivate it."
)

if st.session_state.pop(
    "account_inactive",
    False
):

    st.error(
        INACTIVE_MESSAGE
    )

if st.session_state.pop(
    "logged_out",
    False
):

    st.success(
        "You have been logged out."
    )

email = st.text_input(
    "Email"
)

password = st.text_input(
    "Password",
    type="password"
)

if st.button(
    "Login",
    use_container_width=True
):

    try:

        result = (
            AuthProvider.login(
                email.strip().lower(),
                password
            )
        )

        user = (
            UserService.get_user_by_email(
                email.strip().lower()
            )
        )

        if not user:

            st.error(
                "User authenticated but no matching Homeschool Hub user exists."
            )

        elif AuthService.is_archived_student(user):

            st.error(
                INACTIVE_MESSAGE
            )

        else:

            if result.session:

                SessionService.save_session(
                    result.session.access_token
                )

            AuthService.set_current_user(
                user.id
            )

            st.rerun()

    #/except Exception as ex:

        #st.error(
         #   "Invalid email or password."
        #)
    except Exception as ex:

        st.error(
            f"ERROR: {str(ex)}"
        )