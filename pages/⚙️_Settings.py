from datetime import datetime

import streamlit as st

from components.navigation import (
    NavigationComponent
)
from services.auth_service import AuthService
from services.family_service import FamilyService
from services.navigation_service import NavigationService
from services.pairing_service import PairingService
from services.student_mode_service import StudentModeService
from services.student_service import StudentService
from database.models import DeviceMode

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
# Devices
# ------------------------------------------------------------------

@st.dialog("📱 Pair a Device")
def pair_device_dialog():

    st.write(
        "Pair a student's own phone, tablet or computer. It will show only "
        "their view, with no email or password on it."
    )

    if not StudentModeService.has_pin():

        st.info(
            "First, set a family PIN above. It's what unpairs a device."
        )

        return

    students = StudentService.get_current_family_students()

    if not students:

        st.info("Add a student first.")

        return

    code = st.session_state.get("pairing_code")

    if code:

        st.write(f"Pairing code for **{code['name']}**:")

        st.markdown(f"## {code['code'][:3]} {code['code'][3:]}")

        st.caption(
            "On their device, open tally and enter this code on the Login "
            "page, under Have a Pairing Code. It works once and expires at "
            f"{StudentModeService.describe_time(code['expires_at'], AuthService.get_zone())}."
        )

        if st.button("Done"):

            st.session_state.pop("pairing_code", None)

            st.rerun()

        return

    student = st.selectbox(
        "Student",
        students,
        format_func=lambda student: student.name,
        key="pairing_student"
    )

    if st.button(
        "Make a Code",
        type="primary"
    ):

        new_code, expires_at, message = PairingService.create_code(
            student.id
        )

        if not new_code:

            st.error(message)

            return

        # Kept for this dialog only, so closing it and reopening shows the
        # same code instead of making another.

        st.session_state["pairing_code"] = {
            "code": new_code,
            "expires_at": expires_at,
            "name": student.name,
        }

        st.rerun(scope="fragment")


st.divider()

st.subheader("📱 Devices")

st.caption(
    "Devices showing a student's view: paired devices, and parent devices "
    "in Student Mode. Ending one sends it back to the Login page."
)

# A code from an earlier visit is only shown while it can still be used.

shown_code = st.session_state.get("pairing_code")

if shown_code and shown_code["expires_at"] <= datetime.utcnow():

    st.session_state.pop("pairing_code", None)

if st.button("➕ Pair a Device"):

    pair_device_dialog()

device_sessions = StudentModeService.list_sessions()

if device_sessions:

    zone = AuthService.get_zone()

    for device in device_sessions:

        kind = (
            "Paired device"
            if device.mode == DeviceMode.PAIRED.value
            else "Student Mode"
        )

        col1, col2 = st.columns([4, 1])

        with col1:

            st.write(
                f"**{device.student.name}** · {kind}"
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
                help="Send this device back to the Login page"
            ):

                if StudentModeService.end_session(device.id):

                    st.toast(
                        f"{kind} ended for {device.student.name}."
                    )

                    st.rerun()

                st.error(
                    "This device couldn't be updated. "
                    "Please refresh the page and try again."
                )

else:

    st.caption(
        "No devices yet. Pair one above, or start Student Mode from the "
        "Dashboard."
    )
