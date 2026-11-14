import streamlit as st

from config import get_optional_setting
from services.session_service import SessionService
from services.auth_service import (
    AuthService
)
from services.pairing_service import PairingService
from services.student_mode_service import StudentModeService

# The square logo for browser tabs, and the mark without its background for
# the navy sidebar.
FAVICON = "assets/tally-logo.png"
SIDEBAR_LOGO = "assets/tally-mark.png"

# Where parents' comments and suggestions go. The link opens their email
# app; the address is shown too, for computers without one set up.
FEEDBACK_EMAIL = "hello@tallyhomeschool.com"
FEEDBACK_LINK = f"mailto:{FEEDBACK_EMAIL}?subject=tally%20feedback"

# Each group is (heading, [(page, label, icon)]). A heading of None means the
# links sit above the groups.

PARENT_LINKS = [
    (
        None,
        [
            ("pages/🏡_Parent_Dashboard.py", "Dashboard", "🏡"),
            ("pages/🎓_Student_Dashboard.py", "Student View", "🎓"),
        ],
    ),
    (
        "Plan",
        [
            ("pages/📆_Calendar.py", "Calendar", "📆"),
            ("pages/✅_Assignments.py", "Assignments", "✅"),
            ("pages/📅_Events.py", "Events", "📅"),
            ("pages/📚_Subjects.py", "Subjects", "📚"),
        ],
    ),
    (
        "Track",
        [
            ("pages/📊_Grades.py", "Grades", "📊"),
            ("pages/📖_Reading.py", "Reading", "📖"),
            ("pages/🏃_PE.py", "P.E.", "🏃"),
        ],
    ),
    (
        "Family",
        [
            ("pages/👨‍🎓_Students.py", "Students", "👨‍🎓"),
            ("pages/📢_Announcements.py", "Announcements", "📢"),
            ("pages/⚙️_Settings.py", "Settings", "⚙️"),
        ],
    ),
]

STUDENT_LINKS = [
    (
        None,
        [
            ("pages/🎓_Student_Dashboard.py", "Dashboard", "🎓"),
        ],
    ),
    (
        "Plan",
        [
            ("pages/📆_Calendar.py", "Calendar", "📆"),
            ("pages/📅_Events.py", "Events", "📅"),
        ],
    ),
    (
        "Track",
        [
            ("pages/📊_Grades.py", "Grades", "📊"),
            ("pages/📖_Reading.py", "Reading", "📖"),
            ("pages/🏃_PE.py", "P.E.", "🏃"),
        ],
    ),
]

ADMIN_LINKS = [
    (
        None,
        [
            ("pages/📢_Announcements.py", "Announcements", "📢"),
        ],
    ),
]

LOGGED_OUT_LINKS = [
    (
        None,
        [
            ("pages/🏡_Landing_Page.py", "Home", "🏡"),
            ("pages/🔐_Login.py", "Login", "🔐"),
            ("pages/📝_Register.py", "Register", "📝"),
        ],
    ),
]


@st.dialog("🔒 Exit Student Mode")
def exit_student_mode_dialog():

    # A password box outside a form can lose its value; see CLAUDE.md.

    with st.form("exit_student_mode_form"):

        pin = st.text_input(
            "Parent PIN",
            type="password",
            max_chars=4
        )

        if st.form_submit_button("🔓 Exit Student Mode"):

            exited, message = StudentModeService.exit(pin)

            if exited:

                st.switch_page(
                    "pages/🏡_Parent_Dashboard.py"
                )

            st.error(message)

    st.caption(
        "Forgot the PIN? Log out, then sign back in with the parent "
        "password. You can set a new PIN in Settings."
    )

    if st.button("Log out instead"):

        AuthService.logout()

        st.rerun()


@st.dialog("🔒 Unpair This Device")
def unpair_device_dialog():

    st.write(
        "Unpairing signs this device out. Pairing it again needs a new code "
        "from a parent."
    )

    with st.form("unpair_device_form"):

        pin = st.text_input(
            "Parent PIN",
            type="password",
            max_chars=4
        )

        if st.form_submit_button("🔓 Unpair"):

            unpaired, message = PairingService.unpair(pin)

            if unpaired:

                st.session_state["device_unpaired"] = True

                st.rerun()

            st.error(message)

    st.caption(
        "Forgot the PIN? A parent can end this device from Settings, "
        "under Devices, on their own phone or computer."
    )


class NavigationComponent:

    @staticmethod
    def _render_links(groups):

        for heading, links in groups:

            if heading:

                st.caption(heading.upper())

            for page, label, icon in links:

                st.page_link(
                    page,
                    label=label,
                    icon=icon
                )

    @staticmethod
    def show_moved_notice():
        """
        Once the new app takes over, APP_MOVED_TO (Streamlit secrets) is its
        address, and every page shows only a "tally has moved" notice.
        Complete_Account doesn't call this, so invite and reset links sent
        before the move still work. Remove the setting to bring the old app
        back.
        """

        moved_to = get_optional_setting("APP_MOVED_TO")

        if not moved_to:
            return

        st.set_page_config(page_title="tally has moved", page_icon=FAVICON)

        st.title("tally has moved")

        st.write(
            "tally has a new home, with a fresh look and apps on the way. "
            "Log in there with the same email and password: your students, "
            "work and history are all there."
        )

        st.link_button(
            "Go to the new tally",
            moved_to,
            type="primary",
            use_container_width=True
        )

        st.caption(
            f"Update your bookmark to {moved_to}"
        )

        st.stop()

    @staticmethod
    def render():

        NavigationComponent.show_moved_notice()

        AuthService.start_page_run()

        # Calls to set_page_config add up, so this only sets the tab icon
        # and leaves each page's own title and layout alone.

        st.set_page_config(page_icon=FAVICON)

        # Collapsed, the sidebar's icon sits on the white page, so it uses
        # the square logo with its own navy background.

        st.logo(
            SIDEBAR_LOGO,
            size="large",
            icon_image=FAVICON
        )

        # Finish any login or logout write before drawing the page.

        if SessionService.sync_browser() == "clear":

            st.session_state["logged_out"] = True

            st.switch_page(
                "pages/🔐_Login.py"
            )

        with st.sidebar:

            st.title("tally")

            st.caption("Less logging, more learning")

            current_user = (
                AuthService.get_current_user()
            )

            student_mode = (
                AuthService.get_student_mode()
                if current_user
                else None
            )

            if student_mode:

                # No Logout button here: leaving Student Mode needs the PIN,
                # and the exit dialog offers logging out instead.

                st.success(
                    f"🎓 {student_mode.student.name}"
                )

                st.caption("Student Mode")

                st.divider()

                NavigationComponent._render_links(STUDENT_LINKS)

                st.divider()

                if st.button("🔒 Exit Student Mode"):

                    exit_student_mode_dialog()

                st.caption("Version 1.0.0")

            elif AuthService.is_paired_device():

                # No Logout: a paired device stays this student's until a
                # parent unpairs it with the PIN or ends it from Settings.

                st.success(
                    f"🎓 {current_user.student.name}"
                )

                st.caption("Paired device")

                st.divider()

                NavigationComponent._render_links(STUDENT_LINKS)

                st.divider()

                if st.button("🔒 Unpair This Device"):

                    unpair_device_dialog()

                st.caption("Version 1.0.0")

            elif current_user:

                st.success(
                    f"👤 {current_user.email}"
                )

                st.caption(
                    current_user.role
                )

                st.divider()

                if AuthService.is_parent():

                    NavigationComponent._render_links(PARENT_LINKS)

                elif AuthService.is_student():

                    NavigationComponent._render_links(STUDENT_LINKS)

                elif AuthService.is_admin():

                    NavigationComponent._render_links(ADMIN_LINKS)

                st.divider()

                if AuthService.is_parent():

                    st.markdown(
                        f"💬 [Send feedback]({FEEDBACK_LINK})"
                    )

                    st.caption(
                        f"Comments and ideas are welcome at {FEEDBACK_EMAIL}"
                    )

                if st.button("Logout"):

                    AuthService.logout()

                    st.rerun()

                st.caption("Version 1.0.0")

            else:

                NavigationComponent._render_links(LOGGED_OUT_LINKS)
