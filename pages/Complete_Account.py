import streamlit as st

from services.auth_provider import AuthProvider

# This page acts only on the token in the invite link, never on a saved login.
# A parent may open their student's link in a browser where they're logged in,
# and the form must not change the parent's password.

st.title("🔑 Complete Account Setup")

if st.session_state.get("invite_complete"):

    st.success(
        "Your password has been created. "
        "You can now log in with it."
    )

    st.page_link(
        "pages/🔐_Login.py",
        label="Go to Login",
        icon="🔐"
    )

    st.stop()

token_hash = st.query_params.get(
    "token_hash"
)

if not token_hash or st.query_params.get("type") != "invite":

    st.error(
        "This invitation link isn't valid. "
        "Please use the link in your invitation email, "
        "or ask a parent to send a new one."
    )

    st.stop()

st.write(
    "Choose a password for your new account."
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

        # The token is only used here, not on page load, because it works
        # once and email security scanners can open links before people do.

        error_message = AuthProvider.complete_invite(
            token_hash,
            password
        )

        if error_message:

            st.error(
                error_message
            )

        else:

            st.session_state[
                "invite_complete"
            ] = True

            st.query_params.clear()

            st.rerun()
