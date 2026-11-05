# pages/student_view.py

import streamlit as st

from services.achievement_service import AchievementService
from services.auth_provider import AuthProvider
from services.banner_service import BannerService
from services.daily_message_service import DailyMessageService
from services.event_service import EventService
from services.student_service import StudentService
from services.auth_service import (
    AuthService
)

from services.navigation_service import (
    NavigationService
)
from services.occurrence_service import OccurrenceService
from services.reading_service import ReadingService
from components.navigation import (
    NavigationComponent
)
from services.user_service import UserService

NavigationComponent.render()
NavigationService.require_authentication()

# Admins have no family or students to view.

if AuthService.is_admin():

    st.switch_page(
        "pages/📢_Announcements.py"
    )

@st.dialog("🔐 Create Student Login")
def create_student_login_dialog(
    student
):

    st.write(
        f"Create a login for {student.name}"
    )

    email = st.text_input(
        "Student Email"
    )

    if st.button(
        "Create Login"
    ):

        invited, message = AuthService.invite_student(
            student.id,
            email
        )

        if not invited:

            st.error(message)

            return

        st.toast(message)

        st.rerun()

@st.dialog("✏️ Update Student Login")
def update_student_login_dialog(
    student
):

    user = (
        UserService.get_user_by_student_id(
            student.id,
            AuthService.get_current_family()
        )
    )

    if not user:

        st.error(
            "This student doesn't have a login yet."
        )

        return

    st.write(
        f"Change the email {student.name} uses to log in."
    )

    st.caption(
        "If they've already set a password, it stays the same. "
        "If they haven't, we'll send a new invitation to the new "
        "email, and the old invitation stops working."
    )

    email = st.text_input(
        "New Email",
        value=user.email
    )

    if st.button(
        "Save"
    ):

        updated, message = AuthService.update_student_email(
            student.id,
            email
        )

        if not updated:

            st.error(
                message
            )

            return

        st.toast(
            message
        )

        st.rerun()

st.title("🎓 Student View")

# ------------------------------------------------------------------
# Announcements
# ------------------------------------------------------------------

for banner in BannerService.get_active_banners():

    st.info(
        f"**{banner.title}**\n\n"
        f"{banner.message}"
    )

# ------------------------------------------------------------------
# Student Selection
# ------------------------------------------------------------------
    
if AuthService.is_student():

    student_id = (
        AuthService
        .get_current_student()
    )

    selected_student = (
        StudentService.get_student_by_id(
            student_id
        )
    )

    if not selected_student:

        st.error(
            "We couldn't find your student profile. "
            "Please ask a parent for help."
        )

        st.stop()

    st.success(
        f"Welcome back, {selected_student.name}!"
    )

else:

    students = (
        StudentService.get_current_family_students()
    )

    if not students:

        st.warning(
            "No students found."
        )

        st.stop()

    selected_student = st.selectbox(
        "Select Student",
        students,
        format_func=lambda x: x.name
    )

    st.info(
        "Parent Viewing Student Dashboard"
    )

    student_user = UserService.get_user_by_student_id(
        selected_student.id,
        AuthService.get_current_family()
    )

    if student_user:

        st.success(
            "✅ Student Login Enabled"
        )

        st.caption(
            f"Email: {student_user.email}"
        )

        if st.button(
            "📧 Resend Invitation"
        ):

            try:

                AuthProvider.create_student_account(
                    student_user.email
                )

                st.success(
                    f"Invitation sent to {student_user.email}."
                )

            except Exception as ex:

                st.error(
                    AuthProvider.resend_invite_error_message(ex)
                )

        if st.button(
            "✏️ Update Email"
        ):

            update_student_login_dialog(
                selected_student
            )

    else:

        if st.button(
            "🔐 Create Student Login"
        ):

            create_student_login_dialog(
                selected_student
            )


today = AuthService.get_today()

occurrence_rows = StudentService.get_student_occurrences(
    selected_student.id
)

groups = OccurrenceService.group_for_student(
    occurrence_rows,
    today
)

achievements = AchievementService.summary(
    occurrence_rows,
    today
)

reading = ReadingService.summary(
    ReadingService.get_books(selected_student.id),
    today
)

overdue = groups["overdue"]
today_assignments = groups["today"]
upcoming = groups["upcoming"]
missed = OccurrenceService.recently_missed(
    groups["missed"],
    today
)
completed_assignments = groups["completed"]

progress = OccurrenceService.progress(groups)

# ------------------------------------------------------------------
# Student Header
# ------------------------------------------------------------------

st.header(selected_student.name)

st.info(
    DailyMessageService.get_message(today),
    icon="💬"
)

streak = achievements["streak"]

st.metric(
    "🔥 Streak",
    f"{streak} day" if streak == 1 else f"{streak} days"
)

st.caption(
    f"Personal best: {achievements['best_streak']}. "
    "Days with no work don't break a streak, and catching up repairs it."
)

st.write(
    f"📖 {reading['streak']}-day reading streak · "
    f"{reading['pages_this_week']} pages this week"
)

col1, col2, col3 = st.columns(3)

with col1:

    st.metric(
        "✅ Complete",
        progress["completed"]
    )

with col2:

    st.metric(
        "📚 Remaining",
        progress["remaining"]
    )

with col3:

    st.metric(
        "🎯 Progress",
        f"{progress['percent']}%"
    )

if selected_student.grade_level:
    st.caption(
        selected_student.grade_level
    )

# ------------------------------------------------------------------
# Progress Area
# ------------------------------------------------------------------

st.subheader("Progress")

st.progress(progress["percent"])

st.metric(
    "Completion Rate",
    f"{progress['percent']}%"
)

st.write(
    f"{progress['completed']} of "
    f"{progress['total']} assignments complete so far"
)

st.divider()

# ------------------------------------------------------------------
# Upcoming Events
# ------------------------------------------------------------------

st.subheader("🎉 Upcoming Events")

upcoming_events = EventService.get_upcoming(
    today,
    selected_student.id
)

if upcoming_events:

    for entry in upcoming_events:

        event = entry["event"]

        st.write(
            f"**{event.title}**: "
            f"{EventService.describe_when(event, entry['date'])}"
        )

        if event.description:

            st.caption(event.description)

else:

    st.caption(
        "No events in the next 30 days."
    )

st.divider()

# ------------------------------------------------------------------
# Badges
# ------------------------------------------------------------------

all_badges = achievements["badges"] + reading["badges"]

earned_badges = [
    badge
    for badge in all_badges
    if badge["earned"]
]

unearned_badges = [
    badge
    for badge in all_badges
    if not badge["earned"]
]

st.subheader(
    f"🏅 Badges ({len(earned_badges)} of "
    f"{len(all_badges)})"
)

if earned_badges:

    for badge in earned_badges:

        st.write(
            f"{badge['icon']} **{badge['name']}**: "
            f"{badge['description']}"
        )

else:

    st.caption(
        "Finish your first piece of work to earn your first badge."
    )

if unearned_badges:

    with st.expander(
        "Badges to earn"
    ):

        for badge in unearned_badges:

            st.write(
                f"{badge['icon']} {badge['name']}: "
                f"{badge['description']}"
            )

st.divider()

# ------------------------------------------------------------------
# Hide Completed Toggle
# ------------------------------------------------------------------

hide_completed = st.checkbox(
    "Hide Completed Assignments",
    value=False
)

# ------------------------------------------------------------------
# Dashboard Metrics
# ------------------------------------------------------------------

st.subheader("🎯 Today's Focus")

if overdue:

    next_assignment = overdue[0]

elif today_assignments:

    next_assignment = today_assignments[0]

elif upcoming:

    next_assignment = upcoming[0]

else:

    next_assignment = None

if next_assignment:

    st.info(
        f"Next Task: {OccurrenceService.work_title(next_assignment)}"
    )

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "⚠ Overdue",
        len(overdue)
    )

with col2:
    st.metric(
        "📅 Due Today",
        len(today_assignments)
    )

with col3:
    st.metric(
        "📚 Upcoming",
        len(upcoming)
    )

st.divider()

# ------------------------------------------------------------------
# Assignment Renderer
# ------------------------------------------------------------------

def render_occurrence(
    occurrence
):

    assignment = (
        occurrence.assignment
    )

    completed = OccurrenceService.is_complete(
        occurrence
    )

    checked = st.checkbox(
        f"{OccurrenceService.work_title(occurrence)} "
        f"({assignment.subject.name})",
        value=completed,
        key=f"occurrence_{occurrence.id}"
    )

    if checked != completed:

        updated = StudentService.update_occurrence_status(
            occurrence.id,
            checked
        )

        if updated:

            for badge in AchievementService.newly_earned(
                achievements,
                AchievementService.summary(
                    StudentService.get_student_occurrences(
                        selected_student.id
                    ),
                    today
                )
            ):

                st.toast(
                    f"New badge: {badge['name']}!",
                    icon=badge["icon"]
                )

            st.rerun()

        st.error(
            "This assignment couldn't be updated. "
            "Please refresh the page and try again."
        )

    if assignment.description:

        st.caption(
            f"📝 {assignment.description}"
        )

    if occurrence.notes:

        st.info(
            occurrence.notes,
            icon="📝"
        )

    st.caption(
        f"Due: {occurrence.occurrence_date}"
    )

    if assignment.assignment_type == "Recurring":

        st.caption(
            f"🔁 {assignment.recurrence_pattern}"
        )

# ------------------------------------------------------------------
# Overdue Assignments
# ------------------------------------------------------------------

if overdue:

    st.subheader("⚠ Overdue")

    for occurrence in overdue:

        render_occurrence(
            occurrence
        )

# ------------------------------------------------------------------
# Today's Work
# ------------------------------------------------------------------

st.subheader("📅 Today's Work")

if today_assignments:

    for occurrence in today_assignments:

        render_occurrence(
            occurrence
        )

else:

    st.success(
        "Nothing due today!"
    )

# ------------------------------------------------------------------
# Upcoming Assignments
# ------------------------------------------------------------------

if upcoming:

    st.subheader("📚 Upcoming")

    for occurrence in upcoming:

        render_occurrence(
            occurrence
        )

# ------------------------------------------------------------------
# Missed Dates
# ------------------------------------------------------------------

if missed:

    with st.expander(
        f"🕓 Missed ({len(missed)})"
    ):

        st.caption(
            "Recurring work from the last 30 days. "
            "You can still check these off if they got done."
        )

        for occurrence in missed:

            render_occurrence(
                occurrence
            )

# ------------------------------------------------------------------
# Completed Assignments
# ------------------------------------------------------------------

recently_completed = OccurrenceService.recently_completed(
    completed_assignments,
    today
)

if (
    recently_completed and
    not hide_completed
):

    st.subheader("✅ Completed in the Last 30 Days")

    for occurrence in recently_completed:

        render_occurrence(
            occurrence
        )
