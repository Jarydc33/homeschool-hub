import streamlit as st

from services.auth_provider import AuthProvider

# Handles the links in invite and password reset emails.
#
# This page acts only on the token in the link, never on a saved login. A parent
# may open their student's link in a browser where they're logged in, and the
# form must not change the parent's password.

PAGE_TEXT = {
    "invite": {
        "title": "🔑 Complete Account Setup",
        "intro": "Choose a password for your new account.",
        "button": "Complete Setup",
        "success": (
            "Your password has been created. "
            "You can now log in with it."
        ),
    },
    "recovery": {
        "title": "🔑 Reset Your Password",
        "intro": "Choose a new password for your account.",
        "button": "Reset Password",
        "success": (
            "Your password has been reset, and any devices "
            "that were logged in have been logged out. "
            "You can now log in with your new password."
        ),
    },
}

completed_type = st.session_state.get(
    "email_link_complete"
)

if completed_type:

    st.title(
        PAGE_TEXT[completed_type]["title"]
    )

    st.success(
        PAGE_TEXT[completed_type]["success"]
    )

    st.caption(
        "If someone else is logged in on this browser, "
        "this will log them out."
    )

    if st.button(
        "Go to Login",
        use_container_width=True
    ):

        st.session_state[
            "switch_account"
        ] = True

        st.switch_page(
            "pages/🔐_Login.py"
        )

    st.stop()

token_hash = st.query_params.get(
    "token_hash"
)

link_type = st.query_params.get(
    "type"
)

if not token_hash or link_type not in PAGE_TEXT:

    st.title(
        PAGE_TEXT["invite"]["title"]
    )

    st.error(
        "This link isn't valid. "
        "Please use the link in your email, "
        "or request a new one."
    )

    st.stop()

text = PAGE_TEXT[link_type]

st.title(
    text["title"]
)

st.write(
    text["intro"]
)

# In a form so tabbing past each box's eye icon can't lose the password.

with st.form("set_password_form"):

    password = st.text_input(
        "Password",
        type="password"
    )

    confirm_password = st.text_input(
        "Confirm Password",
        type="password"
    )

    submitted = st.form_submit_button(
        text["button"],
        use_container_width=True
    )

if submitted:

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

        error_message = AuthProvider.complete_email_link(
            token_hash,
            link_type,
            password
        )

        if error_message:

            st.error(
                error_message
            )

        else:

            st.session_state[
                "email_link_complete"
            ] = link_type

            st.query_params.clear()

            st.rerun()
