import streamlit as st

from services.student_service import StudentService

st.title("👨‍🎓 Students")

students = StudentService.get_all_students()

# ------------------------------
# Existing Students
# ------------------------------

st.subheader("Current Students")

if students:

    for student in students:

        st.write(
            f"✅ {student.name} ({student.grade_level})"
        )

else:
    st.info("No students found.")

st.divider()

# ------------------------------
# Add Student
# ------------------------------

st.subheader("Add Student")

with st.form("add_student_form"):

    name = st.text_input("Student Name")

    grade_level = st.text_input("Grade Level")

    birth_year = st.number_input(
        "Birth Year",
        min_value=1900,
        max_value=2100,
        value=2015
    )

    submitted = st.form_submit_button(
        "Add Student"
    )

    if submitted:

        StudentService.create_student(
            family_id=1,
            name=name,
            grade_level=grade_level,
            birth_year=birth_year
        )
        st.session_state.name = ""
        st.session_state.grade_level = ""
        st.session_state.birth_year = 2015

        st.success(
            f"{name} added successfully."
        )

        st.toast("Student added successfully.")