# app.py

from datetime import date

import streamlit as st

from services.student_service import StudentService
from services.subject_service import SubjectService
from services.assignment_service import AssignmentService
from services.activity_service import ActivityService
from services.banner_service import BannerService
from services.daily_message_service import DailyMessageService
from services.event_service import EventService
from services.student_mode_service import StudentModeService

from services.auth_service import (
    AuthService
)

from services.dashboard_service import (
    DashboardService
)

from services.navigation_service import (
    NavigationService
)
from components.navigation import (
    NavigationComponent
)

NavigationComponent.render()

current_user = (
    AuthService.get_current_user()
)

NavigationService.require_parent()

dashboard = (
    DashboardService.get_dashboard_data()
)


@st.dialog("🤒 Missed a Day?")
def missed_day_dialog():

    today = AuthService.get_today()

    st.write(
        "Unfinished curriculum lessons pick up on the day you choose, "
        "and the rest follow in order on their school days. Other "
        "assignments stay as they are."
    )

    students = dashboard["students"]

    behind = AssignmentService.get_students_behind(today)

    chosen = st.multiselect(
        "Who missed?",
        students,
        default=[
            student
            for student in students
            if student.id in behind
        ],
        format_func=lambda student: student.name,
        key="missed_day_students"
    )

    resume_on = st.date_input(
        "Pick Up On",
        value=today,
        min_value=today,
        key="missed_day_resume"
    )

    student_ids = [
        student.id
        for student in chosen
    ]

    plan = AssignmentService.get_recovery_plan(
        student_ids,
        resume_on
    )

    if not plan:

        st.info(
            "Nothing needs to move for that choice."
        )

        return

    for change in plan:

        st.write(
            f"**{change['student_name']}: {change['title']}**"
        )

        st.caption(
            f"Lesson {change['next_lesson']} moves to "
            f"{change['next_date']:%a, %b} {change['next_date'].day}. "
            f"Finish: {change['old_finish']} → {change['new_finish']}"
        )

    if st.button(
        "Shift Schedule",
        type="primary"
    ):

        moved = AssignmentService.shift_lessons(
            student_ids,
            resume_on
        )

        if moved is None:

            st.error(
                "The schedule couldn't be shifted. "
                "Please refresh the page and try again."
            )

            return

        st.toast(
            "Schedule shifted."
        )

        st.rerun()


@st.dialog("🔒 Start Student Mode")
def student_mode_dialog():

    st.write(
        "This device switches to one student's view. They can see and check "
        "off their own work, but can't open parent pages or log out. "
        "Leaving Student Mode needs the family PIN."
    )

    if not StudentModeService.has_pin():

        st.info(
            "First, set a family PIN in Settings."
        )

        st.page_link(
            "pages/⚙️_Settings.py",
            label="Go to Settings",
            icon="⚙️"
        )

        return

    students = dashboard["students"]

    if not students:

        st.info(
            "Add a student first."
        )

        return

    student = st.selectbox(
        "Student",
        students,
        format_func=lambda student: student.name,
        key="student_mode_student"
    )

    if st.button(
        "Start Student Mode",
        type="primary"
    ):

        started, message = StudentModeService.start(
            student.id
        )

        if not started:

            st.error(message)

            return

        st.switch_page(
            "pages/🎓_Student_Dashboard.py"
        )


active_banners = (
    BannerService.get_active_banners()
)
# --------------------------------------------------
# Page Config
# --------------------------------------------------

st.set_page_config(
    page_title="Tally",
    page_icon="🏡",
    layout="wide"
)

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

st.info(
    DailyMessageService.get_message(dashboard["today"]),
    icon="💬"
)

if st.button(
    "🔒 Start Student Mode",
    help="Hand this device to a student"
):

    student_mode_dialog()

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

if AssignmentService.has_curriculum():

    if st.button(
        "🤒 Missed a Day?",
        help="Move unfinished curriculum lessons forward"
    ):

        missed_day_dialog()

if overdue_assignments:

    for entry in overdue_assignments:

        assignment = entry["assignment"]

        assigned_students = ", ".join(
            entry["student_names"]
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

    for entry in today_assignments:

        assignment = entry["assignment"]

        assigned_students = ", ".join(
            entry["student_names"]
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
# Upcoming Events
# --------------------------------------------------

st.subheader(
    "🎉 Upcoming Events"
)

upcoming_events = EventService.get_upcoming(
    dashboard["today"]
)

if upcoming_events:

    for entry in upcoming_events:

        event = entry["event"]

        st.write(
            f"🎉 **{event.title}**: "
            f"{EventService.describe_when(event, entry['date'])}"
        )

        st.caption(
            f"👨‍🎓 {EventService.audience(event)}"
        )

else:

    st.info(
        "No events in the next 30 days."
    )

st.divider()

# --------------------------------------------------
# Recent Activity
# --------------------------------------------------

st.subheader(
    "📝 Recent Activity"
)

recent_activity = ActivityService.get_recent(
    dashboard["today"]
)

if recent_activity:

    for day, entries in recent_activity:

        st.markdown(
            f"**{ActivityService.day_label(day, dashboard['today'])}**"
        )

        for entry in entries:

            st.write(entry)

else:

    st.info(
        "Nothing has been finished in the last 7 days yet."
    )

