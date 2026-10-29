import streamlit as st

from services.assignment_service import AssignmentService
from services.student_service import StudentService
from services.subject_service import SubjectService


st.title("✅ Assignments")

students = StudentService.get_all_students()
subjects = SubjectService.get_all_subjects()

# ------------------------------------
# Create Assignment
# ------------------------------------

st.subheader("Create Assignment")

with st.form("assignment_form"):

    title = st.text_input(
        "Assignment Title"
    )

    subject = st.selectbox(
        "Subject",
        subjects,
        format_func=lambda x: x.name
    )

    selected_students = st.multiselect(
        "Assign To",
        students,
        format_func=lambda x: x.name
    )

    description = st.text_area(
        "Description"
    )

    due_date = st.date_input(
        "Due Date"
    )

    submitted = st.form_submit_button(
        "Create Assignment"
    )

    if submitted:

        AssignmentService.create_assignment(
            family_id=1,
            subject_id=subject.id,
            title=title,
            student_ids=[
                student.id
                for student in selected_students
            ],
            description=description,
            due_date=due_date
        )

        st.success(
            "Assignment created successfully."
        )

        st.rerun()

st.divider()

st.subheader("Current Assignments")

assignments = AssignmentService.get_all_assignments()

for assignment in assignments:

    with st.expander(
        f"📋 {assignment.title}"
    ):

        st.write(
            f"**Subject:** {assignment.subject.name}"
        )

        if assignment.description:
            st.write(
                f"**Description:** {assignment.description}"
            )

        st.write("**Assigned Students:**")

        for student_assignment in assignment.student_assignments:

            st.write(
                f"✅ {student_assignment.student.name}"
            )

        if assignment.due_date:
            st.write(
                f"**Due Date:** {assignment.due_date}"
            )