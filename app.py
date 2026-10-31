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

# --------------------------------------------------
# Startup
# --------------------------------------------------

initialize_database()

if database_is_empty():
    seed_database()

current_user = (
    AuthService.get_current_user()
)

if not AuthService.is_authenticated():

    st.warning(
        "Please login."
    )

    st.stop()

if (
    AuthService.is_authenticated()
    and
    not AuthService.is_parent()
):

    st.info(
        "Redirecting to Student Dashboard..."
    )

    st.switch_page(
        "pages/5_🎓_Student_Dashboard.py"
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

    st.caption("Version 0.1 MVP")
    if current_user:

        st.success(
            f"👤 {current_user.email}"
        )

        st.caption(
            f"Role: {current_user.role}"
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

students = StudentService.get_all_students()
subjects = SubjectService.get_all_subjects()
assignments = AssignmentService.get_all_assignments()

today = date.today()

overdue_assignments = []
today_assignments = []

for assignment in assignments:

    if not assignment.due_date:
        continue

    incomplete_students = [
        sa
        for sa in assignment.student_assignments
        if sa.status != "Complete"
    ]

    # If everyone is finished,
    # don't include it in dashboard alerts
    if not incomplete_students:
        continue

    if assignment.due_date < today:

        overdue_assignments.append(
            assignment
        )

    elif assignment.due_date == today:

        today_assignments.append(
            assignment
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

        student_assignments = (
            StudentService.get_student_assignments(
                student.id
            )
        )

        total = len(
            student_assignments
        )

        completed = len(
            [
                assignment
                for assignment
                in student_assignments
                if assignment.status == "Complete"
            ]
        )

        percent = 0

        if total > 0:

            percent = round(
                (completed / total) * 100
            )

        overdue_count = len(
            [
                assignment
                for assignment
                in student_assignments
                if (
                    assignment.assignment.due_date
                    and assignment.assignment.due_date < today
                    and assignment.status != "Complete"
                )
            ]
        )

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

