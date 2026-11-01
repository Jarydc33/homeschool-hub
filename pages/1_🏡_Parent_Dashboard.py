# app.py

from datetime import date

import streamlit as st

from services.student_service import StudentService
from services.subject_service import SubjectService
from services.assignment_service import AssignmentService
from services.banner_service import BannerService

from services.startup_service import (
    initialize_database,
    database_is_empty
)

from scripts.seed_data import seed_database
from services.auth_service import (
    AuthService
)

from services.dashboard_service import (
    DashboardService
)

from services.navigation_service import (
    NavigationService
)

# --------------------------------------------------
# Startup
# --------------------------------------------------

initialize_database()

if database_is_empty():
    seed_database()

current_user = (
    AuthService.get_current_user()
)

NavigationService.require_parent()

dashboard = (
    DashboardService.get_dashboard_data()
)

active_banners = (
    BannerService.get_active_banners()
)
# --------------------------------------------------
# Page Config
# --------------------------------------------------

st.set_page_config(
    page_title="Homeschool Hub",
    page_icon="🏡",
    layout="wide"
)

# --------------------------------------------------
# Sidebar
# --------------------------------------------------

with st.sidebar:

    st.title("🏡 Homeschool Hub")

    st.caption(
        "Family Homeschool Management"
    )

    st.divider()

    st.caption("Version 1.0")
    if current_user:

        st.success(
            f"👤 {current_user.email}"
        )

        st.caption(
            f"Role: {current_user.role}"
        )

        st.divider()

        if AuthService.is_parent():

            st.caption(
                "Parent Access"
            )

        elif AuthService.is_student():

            st.caption(
                "Student Access"
            )

        if st.button("Logout"):

            AuthService.logout()

            st.rerun()

        st.divider()
    

# --------------------------------------------------
# Dashboard Header
# --------------------------------------------------

st.title("🏡 Parent Dashboard")

st.caption(
    "Homeschool Command Center"
)

st.write(
    "Welcome back! Here's an overview of your homeschool."
)

if active_banners:

    st.subheader("📢 Announcements")

    for banner in active_banners:

        st.info(
            f"**{banner.title}**\n\n"
            f"{banner.message}"
        )

    st.divider()

# --------------------------------------------------
# Data
# --------------------------------------------------

students = dashboard["students"]

subjects = dashboard["subjects"]

assignments = dashboard["assignments"]

today = dashboard["today"]

overdue_assignments = (
    dashboard["overdue_assignments"]
)

today_assignments = (
    dashboard["today_assignments"]
)


# --------------------------------------------------
# Top Metrics
# --------------------------------------------------

col1, col2, col3, col4 = st.columns(4)

with col1:

    st.metric(
        "👨‍🎓 Students",
        len(students)
    )

with col2:

    st.metric(
        "📚 Subjects",
        len(subjects)
    )

with col3:

    st.metric(
        "✅ Assignments",
        len(assignments)
    )

with col4:

    st.metric(
        "🚨 Overdue",
        len(overdue_assignments)
    )

st.divider()

# --------------------------------------------------
# Needs Attention
# --------------------------------------------------

st.subheader(
    "🚨 Needs Attention"
)

if overdue_assignments:

    for assignment in overdue_assignments:

        assigned_students = (
            ", ".join(
                [
                    sa.student.name
                    for sa in assignment.student_assignments
                    if sa.status != "Complete"
                ]
            )
        )

        st.warning(
            f"{assigned_students} still need(s) to complete "
            f"'{assignment.title}' "
            f"({assignment.subject.name})"
        )

else:

    st.success(
        "No overdue assignments."
    )

st.divider()

# --------------------------------------------------
# Due Today
# --------------------------------------------------

st.subheader(
    "📅 Due Today"
)

if today_assignments:

    for assignment in today_assignments:

        assigned_students = (
            ", ".join(
                [
                    sa.student.name
                    for sa in assignment.student_assignments
                ]
            )
        )

        st.write(
            f"📋 {assignment.title}"
        )

        st.caption(
            f"📚 {assignment.subject.name}"
        )

        st.caption(
            f"👨‍🎓 {assigned_students}"
        )

else:

    st.info(
        "No assignments due today."
    )

st.divider()

# --------------------------------------------------
# Student Progress
# --------------------------------------------------

st.subheader(
    "👨‍🎓 Student Progress"
)

if not students:

    st.info(
        "No students have been added."
    )

else:

    for student in students:
        metrics = (
            DashboardService
            .get_student_metrics(student)
        )

        student_assignments = metrics["student_assignments"]

        total = metrics["total"]

        completed = metrics["completed"]

        percent = metrics["percent"]

        overdue_count = metrics["overdue_count"]

        with st.container():

            st.markdown(
                f"### 👨‍🎓 {student.name}"
            )

            st.progress(
                percent
            )

            col1, col2, col3 = st.columns(3)

            with col1:

                st.metric(
                    "Progress",
                    f"{percent}%"
                )

            with col2:

                st.metric(
                    "Completed",
                    f"{completed}/{total}"
                )

            with col3:

                st.metric(
                    "Overdue",
                    overdue_count
                )

            st.divider()

# --------------------------------------------------
# Upcoming Events (Future)
# --------------------------------------------------

st.subheader(
    "🎉 Upcoming Events"
)

st.info(
    "Event tracking coming soon."
)

st.divider()

# --------------------------------------------------
# Recent Activity (Future)
# --------------------------------------------------

st.subheader(
    "📝 Recent Activity"
)

st.info(
    "Activity tracking coming soon."
)

