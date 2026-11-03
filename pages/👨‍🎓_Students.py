import streamlit as st

from services.student_service import StudentService
from services.auth_service import (
    AuthService
)

from services.navigation_service import NavigationService
from components.navigation import (
    NavigationComponent
)

NavigationComponent.render()
NavigationService.require_parent()

# ==================================================
# DIALOGS
# ==================================================

@st.dialog("✏️ Edit Student")
def edit_student_dialog(student_id):

    student = (
        StudentService.get_student_by_id(
            student_id
        )
    )

    if not student:

        st.error(
            "This student could not be found."
        )

        return

    name = st.text_input(
        "Student Name",
        value=student.name
    )

    grade_level = st.text_input(
        "Grade Level",
        value=student.grade_level or ""
    )

    birth_year = st.number_input(
        "Birth Year",
        min_value=1900,
        max_value=2100,
        value=(
            student.birth_year
            if student.birth_year
            else 2015
        )
    )

    if st.button("💾 Save Changes"):

        updated = StudentService.update_student(
            student_id=student.id,
            name=name,
            grade_level=grade_level,
            birth_year=birth_year
        )

        if not updated:

            st.error(
                "This student couldn't be saved. "
                "Please refresh the page and try again."
            )

            return

        st.toast(
            f"{name} updated successfully."
        )

        st.rerun()


@st.dialog("📦 Archive Student")
def archive_student_dialog(student):

    st.warning(
        f"Archive {student.name}?"
    )

    st.write(
        "The student will be hidden from active views "
        "but will remain in the database."
    )

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "Cancel",
            use_container_width=True
        ):
            st.rerun()

    with col2:

        if st.button(
            "Archive",
            type="primary",
            use_container_width=True
        ):
            archived = StudentService.archive_student(
                student.id
            )

            if not archived:

                st.error(
                    "This student couldn't be archived. "
                    "Please refresh the page and try again."
                )

                return

            st.toast(
                f"{student.name} archived."
            )

            st.rerun()


# ==================================================
# PAGE HEADER
# ==================================================

st.title("👨‍🎓 Students")

st.write(
    "Manage students within your homeschool."
)

students = StudentService.get_current_family_students()

# ==================================================
# ACTIVE STUDENTS
# ==================================================

st.subheader("Current Students")

if students:

    for student in students:

        with st.container():

            col1, col2, col3 = st.columns(
                [5, 1, 1]
            )

            with col1:

                st.markdown(
                    f"### 👨‍🎓 {student.name}"
                )

                st.caption(
                    student.grade_level
                    if student.grade_level
                    else "No grade level assigned"
                )

            with col2:

                if st.button(
                    "✏️",
                    key=f"edit_{student.id}",
                    help="Edit Student"
                ):
                    edit_student_dialog(
                        student.id
                    )

            with col3:

                if st.button(
                    "📦",
                    key=f"archive_{student.id}",
                    help="Archive Student"
                ):
                    archive_student_dialog(
                        student
                    )

            st.divider()

else:

    st.info(
        "No students found."
    )

# ==================================================
# ADD STUDENT
# ==================================================

st.subheader("➕ Add Student")

with st.form(
    "add_student_form",
    clear_on_submit=True
):

    name = st.text_input(
        "Student Name"
    )

    grade_level = st.text_input(
        "Grade Level"
    )

    birth_year = st.number_input(
        "Birth Year",
        min_value=1900,
        max_value=2100,
        value=2015
    )

    submitted = (
        st.form_submit_button(
            "Add Student"
        )
    )

    if submitted:

        StudentService.create_student(
            name=name,
            grade_level=grade_level,
            birth_year=birth_year
        )

        st.toast(
            f"{name} added successfully."
        )

        st.rerun()