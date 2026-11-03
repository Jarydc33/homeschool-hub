import streamlit as st

from services.family_service import FamilyService
from services.user_service import UserService
from services.session_service import SessionService
from services.auth_service import AuthService
from services.auth_provider import AuthProvider
from components.navigation import (
    NavigationComponent
)

NavigationComponent.render()
if AuthService.is_parent():

    st.switch_page("app.py")


st.title("📝 Create Account")

st.write(
    "Create a Homeschool Hub account and family."
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

            try:

                # -----------------------------
                # Create Supabase User
                # -----------------------------

                auth_result = (
                    AuthProvider.register(
                        email=email.strip().lower(),
                        password=password
                    )
                )

                # -----------------------------
                # Create Family
                # -----------------------------

                family = (
                    FamilyService.create_family(
                        family_name
                    )
                )

                # -----------------------------
                # Create Parent User
                # -----------------------------

                user = (
                    UserService.create_parent_user(
                        family_id=family.id,
                        email=email
                    )
                )

                # -----------------------------
                # Login
                # -----------------------------

                if auth_result.session:

                    SessionService.save_session(
                        auth_result.session.access_token
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

            except Exception as ex:

                st.error(
                    f"Registration failed: {str(ex)}"
                )