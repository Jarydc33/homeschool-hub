import streamlit as st
from services.session_service import SessionService
from services.auth_service import (
    AuthService
)
from services.student_mode_service import StudentModeService

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
    def render():

        AuthService.start_page_run()

        # Finish any login or logout write before drawing the page.

        if SessionService.sync_browser() == "clear":

            st.session_state["logged_out"] = True

            st.switch_page(
                "pages/🔐_Login.py"
            )

        with st.sidebar:

            st.title("🏡 Tally")

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

                st.caption("Version 0.4.1")

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

                if st.button("Logout"):

                    AuthService.logout()

                    st.rerun()

                st.caption("Version 0.4.1")
            else:

                NavigationComponent._render_links(LOGGED_OUT_LINKS)
