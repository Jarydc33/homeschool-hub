import streamlit as st

from services.family_service import FamilyService
from services.session_service import SessionService
from services.auth_service import AuthService
from components.navigation import (
    NavigationComponent
)

NavigationComponent.render()
if AuthService.is_parent():

    st.switch_page("app.py")


st.title("📝 Create Account")

st.write(
    "Create a tally account and family."
)

with st.form(
    "register_form"
):

    family_name = st.text_input(
        "Family Name"
    )

    email = st.text_input(
        "Parent Email"
    )

    password = st.text_input(
        "Password",
        type="password"
    )

    confirm_password = st.text_input(
        "Confirm Password",
        type="password"
    )

    timezone_choices = FamilyService.timezone_choices()

    timezone = st.selectbox(
        "Time Zone",
        timezone_choices,
        index=timezone_choices.index(
            FamilyService.preferred_timezone(
                st.context.timezone
            )
        ),
        format_func=FamilyService.timezone_label,
        help="Used to work out what's due today for your family."
    )

    submitted = st.form_submit_button(
        "Create Account"
    )

    if submitted:

        # -----------------------------
        # Validation
        # -----------------------------

        if not family_name:

            st.error(
                "Family name is required."
            )

        elif not email:

            st.error(
                "Email is required."
            )

        elif password != confirm_password:

            st.error(
                "Passwords do not match."
            )

        elif len(password) < 8:

            st.error(
                "Password must be at least 8 characters."
            )

        else:

            user, session, error = (
                AuthService.register_parent(
                    family_name,
                    email,
                    password,
                    timezone
                )
            )

            if error:

                st.error(error)

            elif session:

                SessionService.save_session(
                    session.access_token,
                    session.refresh_token
                )

                AuthService.set_current_user(
                    user.id
                )

                st.success(
                    "Account created successfully!"
                )

                st.switch_page(
                    "app.py"
                )

            else:

                # With email confirmation on, Supabase gives no session
                # until the email is confirmed.

                st.success(
                    "Check your email to confirm your account, then log in."
                )
