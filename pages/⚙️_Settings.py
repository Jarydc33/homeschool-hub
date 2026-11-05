import streamlit as st

from components.navigation import (
    NavigationComponent
)
from services.auth_service import AuthService
from services.family_service import FamilyService
from services.navigation_service import NavigationService

NavigationComponent.render()
NavigationService.require_parent()

st.title("⚙️ Family Settings")

family = AuthService.get_current_user().family

timezone_choices = FamilyService.timezone_choices()

with st.form("family_settings_form"):

    family_name = st.text_input(
        "Family Name",
        value=family.family_name or ""
    )

    timezone = st.selectbox(
        "Time Zone",
        timezone_choices,
        index=(
            timezone_choices.index(family.timezone)
            if family.timezone in timezone_choices
            else 0
        ),
        format_func=FamilyService.timezone_label,
        help="Used to work out what's due today for your family."
    )

    st.caption(
        "Changing the time zone changes what counts as today for your whole "
        "family. Saved dates don't move: a lesson on Nov 5 stays on Nov 5."
    )

    if st.form_submit_button("💾 Save Settings"):

        error = FamilyService.settings_error(
            family_name,
            timezone
        )

        if error:

            st.error(error)

        elif FamilyService.update_settings(
            family_name,
            timezone
        ):

            st.toast("Settings saved.")

            st.rerun()

        else:

            st.error(
                "These settings couldn't be saved. "
                "Please refresh the page and try again."
            )
