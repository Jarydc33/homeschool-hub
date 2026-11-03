# pages/student_view.py

from datetime import date

import streamlit as st

from services.auth_provider import AuthProvider
from services.banner_service import BannerService
from services.student_service import StudentService
from services.auth_service import (
    AuthService
)

from services.navigation_service import (
    NavigationService
)
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

        email = (
            email.strip().lower()
        )

        existing_user = (
            UserService.get_user_by_student_id(
                student.id,
                AuthService.get_current_family()
            )
        )

        if existing_user:

            st.error(
                "Student already has a login."
            )

            return

        existing_email = (
            UserService.get_user_by_email(
                email
            )
        )

        if existing_email:

            st.error(
                "Email already exists."
            )

            return

        if not email:

            st.error(
                "Please enter an email address."
            )

            return

        # Send the invite first. If it fails, no login row is left behind
        # to block trying again.

        try:

            AuthProvider.create_student_account(
                email
            )

        except Exception as ex:

            st.error(
                AuthProvider.invite_send_error_message(ex)
            )

            return

        student_user = UserService.create_student_user(
            family_id=AuthService.get_current_family(),
            student_id=student.id,
            email=email
        )

        if not student_user:

            st.error(
                "This student could not be found."
            )

            return

        st.toast(
            f"Invitation sent to {email}."
        )

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

    email = st.text_input(
        "Email",
        value=user.email
    )

    if st.button(
        "Save"
    ):

        UserService.update_user_email(
            user.id,
            email.strip().lower()
        )

        st.success(
            "Email updated."
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
            "✏️ Update Email"
        ):

            #update_student_login_dialog(
            #    selected_student
            #)
            st.error("This feature coming soon")

    else:

        if st.button(
            "🔐 Create Student Login"
        ):

            create_student_login_dialog(
                selected_student
            )


student_assignments = (
    StudentService.get_student_assignments(
        selected_student.id
    )
)

# ------------------------------------------------------------------
# Progress Calculation
# ------------------------------------------------------------------

total_assignments = len(student_assignments)

completed_assignments = len(
    [
        assignment
        for assignment in student_assignments
        if assignment.status == "Complete"
    ]
)

progress = 0

if total_assignments:
    progress = (
        completed_assignments
        / total_assignments
    ) * 100

# ------------------------------------------------------------------
# Student Header
# ------------------------------------------------------------------

st.header(selected_student.name)

st.metric(
    "🔥 Streak",
    "Coming Soon"
)

col1, col2, col3 = st.columns(3)

with col1:

    st.metric(
        "✅ Complete",
        completed_assignments
    )

with col2:

    st.metric(
        "📚 Remaining",
        total_assignments - completed_assignments
    )

with col3:

    st.metric(
        "🎯 Progress",
        f"{int(progress)}%"
    )

if selected_student.grade_level:
    st.caption(
        selected_student.grade_level
    )

# ------------------------------------------------------------------
# Progress Area
# ------------------------------------------------------------------

st.subheader("Today's Progress")

st.progress(int(progress))

st.metric(
    "Completion Rate",
    f"{int(progress)}%"
)

st.write(
    f"{completed_assignments} of "
    f"{total_assignments} assignments complete"
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
# Assignment Categorization
# ------------------------------------------------------------------

today = date.today()

completed_assignments = []

overdue = []
today_assignments = []
upcoming = []
no_due_date = []

for student_assignment in student_assignments:

    if student_assignment.status == "Complete":

        completed_assignments.append(
            student_assignment
        )

        continue

    due_date = (
        student_assignment.assignment.due_date
    )

    if due_date is None:

        no_due_date.append(
            student_assignment
        )

    elif due_date < today:

        overdue.append(
            student_assignment
        )

    elif due_date == today:

        today_assignments.append(
            student_assignment
        )

    else:

        upcoming.append(
            student_assignment
        )

# ------------------------------------------------------------------
# Sort Buckets
# ------------------------------------------------------------------

overdue.sort(
    key=lambda x: x.assignment.due_date
)

today_assignments.sort(
    key=lambda x: x.assignment.due_date
)

upcoming.sort(
    key=lambda x: x.assignment.due_date
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
        f"Next Task: {next_assignment.assignment.title}"
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

def render_assignment(
    student_assignment
):

    assignment = (
        student_assignment.assignment
    )

    completed = (
        student_assignment.status
        == "Complete"
    )

    checked = st.checkbox(
        f"{assignment.title} "
        f"({assignment.subject.name})",
        value=completed,
        key=f"assignment_"
        f"{student_assignment.id}"
    )

    if checked != completed:

        updated = StudentService.update_assignment_status(
            student_assignment.id,
            checked
        )

        if updated:

            st.rerun()

        st.error(
            "This assignment couldn't be updated. "
            "Please refresh the page and try again."
        )

    if assignment.due_date:

        st.caption(
            f"Due: {assignment.due_date}"
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

    for assignment in overdue:

        render_assignment(
            assignment
        )

# ------------------------------------------------------------------
# Today's Work
# ------------------------------------------------------------------

st.subheader("📅 Today's Work")

if today_assignments:

    for assignment in today_assignments:

        render_assignment(
            assignment
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

    for assignment in upcoming:

        render_assignment(
            assignment
        )

# ------------------------------------------------------------------
# No Due Date Assignments
# ------------------------------------------------------------------

if no_due_date:

    st.subheader("📝 Other Assignments")

    for assignment in no_due_date:

        render_assignment(
            assignment
        )
        
# ------------------------------------------------------------------
# Completed Assignments
# ------------------------------------------------------------------

if (
    completed_assignments and
    not hide_completed
):

    st.subheader("✅ Completed")

    for assignment in completed_assignments:

        render_assignment(
            assignment
        )