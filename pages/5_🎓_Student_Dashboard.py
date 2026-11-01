# pages/student_view.py

from datetime import date

import streamlit as st

from services.student_service import StudentService
from services.auth_service import (
    AuthService
)

from services.navigation_service import (
    NavigationService
)

NavigationService.require_authentication()

st.title("🎓 Student View")

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

    st.info(
        "Student Mode"
    )

else:

    students = (
        StudentService.get_all_students()
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

        StudentService.update_assignment_status(
            student_assignment.id,
            checked
        )

        st.rerun()

    if assignment.due_date:

        st.caption(
            f"Due: {assignment.due_date}"
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