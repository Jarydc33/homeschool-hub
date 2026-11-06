import streamlit as st

from services.user_service import UserService
from services.auth_service import AuthService
from services.auth_provider import AuthProvider
from services.session_service import SessionService
from services.login_limit_service import (
    LOCKED_MESSAGE as LOGIN_LOCKED_MESSAGE,
    LoginLimitService
)
from services.pairing_service import PairingService
from components.navigation import (
    NavigationComponent
)

NavigationComponent.render()

# Coming from an email link, whoever's saved in this browser logs out first,
# so the person who just set a password can log in.

if (
    st.session_state.pop("switch_account", False)
    and AuthService.is_authenticated()
    and not AuthService.is_paired_device()
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
    "Sign in to tally."
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

if st.session_state.pop(
    "device_unpaired",
    False
):

    st.success(
        "This device is unpaired."
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

if submitted and LoginLimitService.is_locked(email):

    st.error(
        LOGIN_LOCKED_MESSAGE
    )

elif submitted:

    try:

        result = (
            AuthProvider.login(
                email.strip().lower(),
                password
            )
        )

        LoginLimitService.record_success(email)

        user = (
            UserService.get_user_by_auth_id(
                result.user.id
            )
        )

        if not user:

            st.error(
                "We couldn't find a tally account for this email."
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

        if AuthProvider.is_wrong_password(ex):

            LoginLimitService.record_failure(email)

        st.error(
            AuthProvider.login_error_message(ex)
        )

st.page_link(
    "pages/Forgot_Password.py",
    label="Forgot your password?"
)

# ------------------------------------------------------------------
# Pairing a student's own device
# ------------------------------------------------------------------

st.divider()

st.subheader("📱 Have a Pairing Code?")

st.caption(
    "For a student's own device, with no email needed. A parent makes the "
    "code in Settings, under Devices."
)

with st.form("pairing_form", clear_on_submit=True):

    code = st.text_input(
        "Pairing Code",
        max_chars=7,
        placeholder="123456"
    )

    if st.form_submit_button(
        "Pair This Device",
        use_container_width=True
    ):

        device_token, message = PairingService.redeem(code)

        if device_token:

            # Saved like a login, then the rerun finishes the browser write
            # and sends them to their dashboard.

            SessionService.save_device_token(device_token)

            AuthService.start_page_run()

            st.rerun()

        st.error(message)
