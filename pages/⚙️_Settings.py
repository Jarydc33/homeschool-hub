import streamlit as st

from components.navigation import (
    NavigationComponent
)
from services.auth_service import AuthService
from services.family_service import FamilyService
from services.navigation_service import NavigationService
from services.student_mode_service import StudentModeService

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

# ------------------------------------------------------------------
# Family PIN
# ------------------------------------------------------------------

st.divider()

st.subheader("🔒 Family PIN")

has_pin = StudentModeService.has_pin()

st.caption(
    "The 4-digit PIN that ends Student Mode. Any parent in your family can "
    "use it. Keep it secret from the kids."
)

if has_pin:

    st.write("✅ A PIN is set.")

with st.form("family_pin_form", clear_on_submit=True):

    pin = st.text_input(
        "New PIN" if has_pin else "PIN",
        type="password",
        max_chars=4
    )

    confirm_pin = st.text_input(
        "Type it again",
        type="password",
        max_chars=4
    )

    if st.form_submit_button(
        "💾 Change PIN" if has_pin else "💾 Set PIN"
    ):

        saved, message = StudentModeService.set_pin(
            pin,
            confirm_pin
        )

        if saved:

            st.toast(message)

            st.rerun()

        st.error(message)

# ------------------------------------------------------------------
# Devices in Student Mode
# ------------------------------------------------------------------

st.divider()

st.subheader("📱 Devices in Student Mode")

device_sessions = StudentModeService.list_sessions()

if device_sessions:

    zone = AuthService.get_zone()

    for device in device_sessions:

        col1, col2 = st.columns([4, 1])

        with col1:

            st.write(
                f"**{device.student.name}**"
            )

            st.caption(
                "Started "
                f"{StudentModeService.describe_time(device.created_at, zone)}"
                " · Last used "
                f"{StudentModeService.describe_time(device.last_seen_at, zone)}"
            )

        with col2:

            if st.button(
                "End",
                key=f"end_device_{device.id}",
                help="End Student Mode on this device"
            ):

                if StudentModeService.end_session(device.id):

                    st.toast(
                        f"Student Mode ended for {device.student.name}."
                    )

                    st.rerun()

                st.error(
                    "This device couldn't be updated. "
                    "Please refresh the page and try again."
                )

else:

    st.caption(
        "No devices are in Student Mode. Start it from the Dashboard."
    )
