import streamlit as st

from services.auth_provider import AuthProvider
from components.navigation import (
    NavigationComponent
)

NavigationComponent.render()

st.title("🔑 Forgot Your Password?")

st.write(
    "Enter your email address and we'll send you "
    "a link to choose a new password."
)

email = st.text_input(
    "Email"
)

if st.button(
    "Send Reset Link",
    use_container_width=True
):

    email = email.strip().lower()

    if not email:

        st.error(
            "Please enter your email address."
        )

    else:

        error_message = AuthProvider.send_password_reset(
            email
        )

        if error_message:

            st.error(
                error_message
            )

        else:

            st.success(
                "If that email has an account, a reset link is on its way. "
                "It may take a few minutes to arrive."
            )

st.page_link(
    "pages/🔐_Login.py",
    label="Back to Login",
    icon="🔐"
)
