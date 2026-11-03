import streamlit as st

from services.user_service import UserService
from services.auth_service import AuthService
from services.auth_provider import AuthProvider
from services.session_service import SessionService
from components.navigation import (
    NavigationComponent
)

NavigationComponent.render()

# Coming from an email link, whoever's saved in this browser logs out first,
# so the person who just set a password can log in.

if (
    st.session_state.pop("switch_account", False)
    and AuthService.is_authenticated()
):

    AuthService.logout()

    st.rerun()

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

# In a form so tabbing past the password box's eye icon can't lose the password.

with st.form("login_form"):

    email = st.text_input(
        "Email"
    )

    password = st.text_input(
        "Password",
        type="password"
    )

    submitted = st.form_submit_button(
        "Login",
        use_container_width=True
    )

if submitted:

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
                "We couldn't find a Homeschool Hub account for this email."
            )

        elif AuthService.is_archived_student(user):

            st.error(
                INACTIVE_MESSAGE
            )

        else:

            if result.session:

                SessionService.save_session(
                    result.session.access_token,
                    result.session.refresh_token
                )

            AuthService.set_current_user(
                user.id
            )

            st.rerun()

    except Exception as ex:

        st.error(
            AuthProvider.login_error_message(ex)
        )

st.page_link(
    "pages/Forgot_Password.py",
    label="Forgot your password?"
)
