import streamlit as st

from services.user_service import UserService
from services.auth_service import AuthService
from services.auth_provider import AuthProvider
from config import DEV_MODE
from services.session_service import SessionService

if DEV_MODE:

        st.divider()

        st.subheader(
            "🛠 Developer Tools"
        )

        if st.button(
            "Parent"
        ):
            AuthService.set_current_user(1)
            st.rerun()

        if st.button(
            "Emma"
        ):
            AuthService.set_current_user(2)
            st.rerun()

        if st.button(
            "Noah"
        ):
            AuthService.set_current_user(3)
            st.rerun()

if AuthService.is_authenticated():

    if AuthService.is_parent():

        st.switch_page("app.py")

    else:

        st.switch_page(
            "pages/5_🎓_Student_Dashboard.py"
        )


st.title("🔐 Login")

st.write(
    "Sign in to Homeschool Hub."
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
                email,
                password
            )
        )

        user = (
            UserService.get_user_by_email(
                email
            )
        )

        if not user:

            st.error(
                "User authenticated but no matching Homeschool Hub user exists."
            )

        else:

            AuthService.set_current_user(
                user.id
            )

            st.success(
                f"Welcome {user.email}"
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

if AuthService.is_authenticated():

    current_user = (
        AuthService.get_current_user()
    )

    st.divider()

    st.success(
        f"Logged in as "
        f"{current_user.email}"
    )

    if st.button(
        "Logout",
        use_container_width=True
    ):

        AuthService.logout()

        st.rerun()