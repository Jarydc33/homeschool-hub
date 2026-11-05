import streamlit as st

from components.navigation import (
    NavigationComponent
)
from services.achievement_service import AchievementService
from services.auth_service import AuthService
from services.grade_service import GradeService
from services.navigation_service import NavigationService
from services.pe_service import (
    MAX_MINUTES,
    PEService
)
from services.student_service import StudentService

NavigationComponent.render()
NavigationService.require_authentication()

# Admins have no family or students to view.

if AuthService.is_admin():

    st.switch_page(
        "pages/📢_Announcements.py"
    )

    st.stop()

SAVE_ERROR = (
    "This couldn't be saved. "
    "Please refresh the page and try again."
)

is_parent = AuthService.is_parent()

today = AuthService.get_today()

st.title("🏃 P.E.")

# ==================================================
# WHOSE ACTIVITIES
# ==================================================

if is_parent:

    students = StudentService.get_current_family_students()

    if not students:

        st.warning(
            "No students found."
        )

        st.stop()

    student_names = {
        student.id: student.name
        for student in students
    }

    student_id = st.selectbox(
        "Select Student",
        list(student_names),
        format_func=student_names.get,
        key="pe_student"
    )

else:

    student_id = AuthService.get_current_student()

logs = PEService.get_logs(student_id)

summary = PEService.summary(logs, today)

# ==================================================
# TOTALS
# ==================================================

col1, col2, col3 = st.columns(3)

with col1:

    st.metric(
        "⏱️ This Week",
        PEService.describe_minutes(summary["minutes_this_week"])
    )

with col2:

    st.metric(
        "📅 Active Days This Week",
        f"{summary['active_days_this_week']} of 7"
    )

with col3:

    st.metric(
        "🏅 All Time",
        PEService.describe_minutes(summary["total_minutes"])
    )

periods = GradeService.get_periods()

if periods:

    st.caption("Totals by grading period")

    for period in periods:

        minutes = sum(
            log.minutes
            for log in PEService.logs_between(
                logs,
                period.start_date,
                period.end_date
            )
        )

        st.write(
            f"**{period.name}**: {PEService.describe_minutes(minutes)}"
        )

st.divider()

# ==================================================
# LOG AN ACTIVITY
# ==================================================

st.subheader("➕ Log an Activity")

with st.form(
    "log_activity_form",
    clear_on_submit=True
):

    if is_parent:

        who = st.multiselect(
            "Who Did It?",
            list(student_names),
            default=[student_id],
            format_func=student_names.get,
            help="Pick more than one for something you did together."
        )

    else:

        who = [student_id]

    activity = st.selectbox(
        "Activity",
        PEService.known_activities(logs),
        index=None,
        accept_new_options=True,
        placeholder="Type a new one, or pick one you've done before"
    )

    col1, col2 = st.columns(2)

    with col1:

        log_date = st.date_input(
            "Date",
            value=today,
            max_value=today
        )

    with col2:

        minutes = st.number_input(
            "Minutes",
            min_value=1,
            max_value=MAX_MINUTES,
            step=5,
            value=None
        )

    if st.form_submit_button("Save Activity"):

        error = PEService.log_error(
            log_date,
            activity,
            minutes
        )

        if not who:

            st.error("Please choose who did it.")

        elif error:

            st.error(error)

        elif PEService.log_activity(
            who,
            log_date,
            activity,
            minutes
        ):

            after = PEService.summary(
                PEService.get_logs(student_id),
                today
            )

            for badge in AchievementService.newly_earned(summary, after):

                st.toast(
                    f"New badge: {badge['name']}!",
                    icon=badge["icon"]
                )

            st.toast("Activity saved.")

            st.rerun()

        else:

            st.error(SAVE_ERROR)

# ==================================================
# RECENT ENTRIES
# ==================================================

st.subheader("Recent Activities")

recent = logs[:30]

if not recent:

    st.info(
        "Nothing logged yet."
    )

for log in recent:

    col1, col2 = st.columns([5, 1])

    with col1:

        st.write(
            f"**{log.activity}**: "
            f"{PEService.describe_minutes(log.minutes)}"
        )

        st.caption(
            f"{log.log_date:%a, %b} {log.log_date.day}, {log.log_date.year}"
        )

    with col2:

        if st.button(
            "🗑️",
            key=f"delete_{log.id}",
            help="Delete this entry"
        ):

            if PEService.delete_log(log.id):

                st.toast("Entry deleted.")

                st.rerun()

            st.error(SAVE_ERROR)

if len(logs) > len(recent):

    st.caption(
        f"Showing the latest {len(recent)} of {len(logs)} entries. "
        "Every entry still counts towards the totals."
    )
