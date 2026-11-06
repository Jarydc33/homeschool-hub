# pages/🎓_Student_Dashboard.py

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
from services.pe_service import PEService
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

    greeting = f"Hi, {selected_student.name}!"

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

    greeting = selected_student.name

    # Login management is for parents only, so it stays tucked away
    # instead of pushing the student's work down the page.

    student_user = UserService.get_user_by_student_id(
        selected_student.id,
        AuthService.get_current_family()
    )

    with st.expander(
        "🔐 Student Login"
    ):

        if student_user:

            st.write(
                f"✅ Login enabled for {student_user.email}"
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

            st.write(
                f"{selected_student.name} doesn't have a login yet."
            )

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

pe = PEService.summary(
    PEService.get_logs(selected_student.id),
    today
)

overdue = groups["overdue"]
today_assignments = groups["today"]
upcoming = groups["upcoming"]
missed = OccurrenceService.recently_missed(
    groups["missed"],
    today
)
recently_completed = OccurrenceService.recently_completed(
    groups["completed"],
    today
)

# ------------------------------------------------------------------
# Header and Today's Progress
# ------------------------------------------------------------------

st.header(greeting)

if selected_student.grade_level:

    st.caption(
        selected_student.grade_level
    )

st.info(
    DailyMessageService.get_message(today),
    icon="💬"
)

done_today, total_today = OccurrenceService.today_progress(
    groups,
    today
)

if total_today:

    if done_today == total_today:

        progress_text = (
            f"Today: all {total_today} done! 🎉"
        )

    else:

        progress_text = (
            f"Today: {done_today} of {total_today} done"
        )

    st.progress(
        done_today / total_today,
        text=progress_text
    )

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

    st.subheader(f"⚠ Overdue ({len(overdue)})")

    for occurrence in overdue:

        render_occurrence(
            occurrence
        )

# ------------------------------------------------------------------
# Today's Work
# ------------------------------------------------------------------

if today_assignments:

    st.subheader(f"📅 Today's Work ({len(today_assignments)})")

    for occurrence in today_assignments:

        render_occurrence(
            occurrence
        )

else:

    st.subheader("📅 Today's Work")

    st.success(
        "Nothing left for today!"
        if done_today
        else "Nothing due today!"
    )

# ------------------------------------------------------------------
# Upcoming Assignments
# ------------------------------------------------------------------

if upcoming:

    st.subheader(f"📚 Coming Up ({len(upcoming)})")

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

st.divider()

# ------------------------------------------------------------------
# Streaks
# ------------------------------------------------------------------

st.subheader("🔥 Streaks")

streak = achievements["streak"]

col1, col2, col3 = st.columns(3)

with col1:

    st.metric(
        "🔥 Streak",
        f"{streak} day" if streak == 1 else f"{streak} days"
    )

    st.caption(
        f"Personal best: {achievements['best_streak']}"
    )

with col2:

    reading_streak = reading["streak"]

    st.metric(
        "📖 Reading Streak",
        f"{reading_streak} day"
        if reading_streak == 1
        else f"{reading_streak} days"
    )

    st.caption(
        f"{reading['pages_this_week']} pages this week"
    )

with col3:

    st.metric(
        "🏃 P.E. This Week",
        PEService.describe_minutes(pe["minutes_this_week"])
    )

    st.caption(
        f"{pe['active_days_this_week']} of 7 days active"
    )

st.caption(
    "Days with no work don't break a streak, and catching up repairs it."
)

# ------------------------------------------------------------------
# Badges
# ------------------------------------------------------------------

all_badges = (
    achievements["badges"]
    + reading["badges"]
    + pe["badges"]
)

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

# ------------------------------------------------------------------
# Completed Assignments
# ------------------------------------------------------------------

if recently_completed:

    st.divider()

    with st.expander(
        f"✅ Completed in the Last 30 Days ({len(recently_completed)})"
    ):

        for occurrence in recently_completed:

            render_occurrence(
                occurrence
            )
