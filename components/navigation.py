import streamlit as st
from services.session_service import SessionService
from services.auth_service import (
    AuthService
)


class NavigationComponent:

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

            if current_user:

                st.success(
                    f"👤 {current_user.email}"
                )

                st.caption(
                    current_user.role
                )

                st.divider()

                # -----------------
                # Parent Navigation
                # -----------------

                if AuthService.is_parent():

                    st.page_link(
                        "pages/🏡_Parent_Dashboard.py",
                        label="Dashboard",
                        icon="🏡"
                    )

                    st.page_link(
                        "pages/👨‍🎓_Students.py",
                        label="Students",
                        icon="👨‍🎓"
                    )

                    st.page_link(
                        "pages/📚_Subjects.py",
                        label="Subjects",
                        icon="📚"
                    )

                    st.page_link(
                        "pages/✅_Assignments.py",
                        label="Assignments",
                        icon="✅"
                    )

                    st.page_link(
                        "pages/📅_Events.py",
                        label="Events",
                        icon="📅"
                    )

                    st.page_link(
                        "pages/📆_Calendar.py",
                        label="Calendar",
                        icon="📆"
                    )

                    st.page_link(
                        "pages/📖_Reading.py",
                        label="Reading",
                        icon="📖"
                    )

                    st.page_link(
                        "pages/📊_Grades.py",
                        label="Grades",
                        icon="📊"
                    )

                    st.page_link(
                        "pages/📢_Announcements.py",
                        label="Announcements",
                        icon="📢"
                    )

                    st.page_link(
                        "pages/🎓_Student_Dashboard.py",
                        label="Student Dashboard",
                        icon="🎓"
                    )

                # -----------------
                # Student Navigation
                # -----------------

                elif AuthService.is_student():

                    st.page_link(
                        "pages/🎓_Student_Dashboard.py",
                        label="Dashboard",
                        icon="🎓"
                    )

                    st.page_link(
                        "pages/📅_Events.py",
                        label="Events",
                        icon="📅"
                    )

                    st.page_link(
                        "pages/📆_Calendar.py",
                        label="Calendar",
                        icon="📆"
                    )

                    st.page_link(
                        "pages/📖_Reading.py",
                        label="Reading",
                        icon="📖"
                    )

                    st.page_link(
                        "pages/📊_Grades.py",
                        label="Grades",
                        icon="📊"
                    )

                # -----------------
                # Admin Navigation
                # -----------------

                elif AuthService.is_admin():

                    st.page_link(
                        "pages/📢_Announcements.py",
                        label="Announcements",
                        icon="📢"
                    )

                st.divider()

                if st.button("Logout"):

                    AuthService.logout()

                    st.rerun()

                st.caption("Version 0.4.1")
            else:

                st.page_link(
                    "pages/🏡_Landing_Page.py",
                    label="Home",
                    icon="🏡"
                )

                st.page_link(
                    "pages/🔐_Login.py",
                    label="Login",
                    icon="🔐"
                )

                st.page_link(
                    "pages/📝_Register.py",
                    label="Register",
                    icon="📝"
                )