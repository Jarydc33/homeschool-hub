import streamlit as st

from services.auth_provider import AuthProvider
from services.auth_service import AuthService

st.title("🔑 Complete Account Setup")

auth_user = (
    AuthProvider.get_current_auth_user()
)

if not auth_user:

    st.error(
        "No active invitation found."
    )

    st.stop()

st.success(
    f"Account invitation verified for {auth_user.user.email}"
)

password = st.text_input(
    "Password",
    type="password"
)

confirm_password = st.text_input(
    "Confirm Password",
    type="password"
)

if st.button(
    "Complete Setup",
    use_container_width=True
):

    if password != confirm_password:

        st.error(
            "Passwords do not match."
        )

    elif len(password) < 8:

        st.error(
            "Password must be at least 8 characters."
        )

    else:

        try:

            AuthProvider.set_password(
                password
            )

            st.success(
                "Password created successfully."
            )

            st.switch_page(
                "app.py"
            )

        except Exception as ex:

            st.error(
                str(ex)
            )