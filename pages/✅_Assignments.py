import streamlit as st

from services.assignment_service import AssignmentService
from services.student_service import StudentService
from services.subject_service import SubjectService

from database.models import (
    AssignmentType,
    RecurrencePattern
)
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

@st.dialog("✏️ Edit Assignment")
def edit_assignment_dialog(assignment_id):

    assignment = (
        AssignmentService.get_assignment_by_id(
            assignment_id
        )
    )

    if not assignment:

        st.error(
            "This assignment could not be found."
        )

        return

    subjects = (
        SubjectService.get_current_family_subjects()
    )

    students = (
        StudentService.get_current_family_students()
    )

    # Keep an archived subject selectable so saving doesn't
    # silently move the assignment to a different subject.

    current_subject_archived = (
        assignment.subject is not None
        and not assignment.subject.active
    )

    if current_subject_archived:

        subjects = [assignment.subject] + subjects

    if not subjects:

        st.warning(
            "Add a subject before editing this assignment."
        )

        return

    assigned_student_ids = [
        sa.student_id
        for sa in assignment.student_assignments
    ]

    title = st.text_input(
        "Assignment Title",
        value=assignment.title
    )

    description = st.text_area(
        "Description",
        value=assignment.description or ""
    )

    assignment_type = st.selectbox(
        "Assignment Type",
        [
            AssignmentType.ONE_TIME.value,
            AssignmentType.RECURRING.value
        ],
        index=(
            0
            if assignment.assignment_type
            == AssignmentType.ONE_TIME.value
            else 1
        )
    )

    recurrence_pattern = None

    if (
        assignment_type
        == AssignmentType.RECURRING.value
    ):

        recurrence_options = [
            RecurrencePattern.DAILY.value,
            RecurrencePattern.WEEKLY.value,
            RecurrencePattern.MONTHLY.value,
            RecurrencePattern.WEEKDAYS.value,
            RecurrencePattern.EVERY_MONDAY.value,
            RecurrencePattern.EVERY_TUESDAY.value,
            RecurrencePattern.EVERY_WEDNESDAY.value,
            RecurrencePattern.EVERY_THURSDAY.value,
            RecurrencePattern.EVERY_FRIDAY.value
        ]

        recurrence_pattern = st.selectbox(
            "Frequency",
            recurrence_options,
            index=(
                recurrence_options.index(
                    assignment.recurrence_pattern
                )
                if (
                    assignment.recurrence_pattern
                    in recurrence_options
                )
                else 0
            )
        )

    selected_subject = st.selectbox(
        "Subject",
        subjects,
        index=next(
            (
                i
                for i, subject in enumerate(subjects)
                if subject.id == assignment.subject_id
            ),
            0
        ),
        format_func=lambda x: (
            f"{x.name} (archived)"
            if not x.active
            else x.name
        )
    )

    selected_students = st.multiselect(
        "Assign To",
        students,
        default=[
            s
            for s in students
            if s.id in assigned_student_ids
        ],
        format_func=lambda x: x.name
    )

    due_date = st.date_input(
        "Due Date",
        value=assignment.due_date
    )

    if st.button("💾 Save Changes"):

        updated = AssignmentService.update_assignment(
            assignment_id=assignment.id,
            title=title,
            description=description,
            due_date=due_date,
            subject_id=selected_subject.id,
            student_ids=[
                student.id
                for student in selected_students
            ],
            assignment_type=assignment_type,
            recurrence_pattern=recurrence_pattern
        )

        if not updated:

            st.error(
                "This assignment couldn't be saved. "
                "Please refresh the page and try again."
            )

            return

        st.toast(
            "Assignment updated successfully."
        )

        st.rerun()


@st.dialog("📦 Archive Assignment")
def archive_assignment_dialog(assignment):

    st.warning(
        f"Archive '{assignment.title}'?"
    )

    st.write(
        "The assignment will be hidden from active views "
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

            archived = AssignmentService.archive_assignment(
                assignment.id
            )

            if not archived:

                st.error(
                    "This assignment couldn't be archived. "
                    "Please refresh the page and try again."
                )

                return

            st.toast(
                "Assignment archived."
            )

            st.rerun()


# ==================================================
# PAGE HEADER
# ==================================================

st.title("✅ Assignments")

students = (
    StudentService.get_current_family_students()
)

subjects = (
    SubjectService.get_current_family_subjects()
)

# ==================================================
# CREATE ASSIGNMENT
# ==================================================

st.subheader("➕ Create Assignment")

with st.form(
    "assignment_form",
    clear_on_submit=True
):

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

    assignment_type = st.selectbox(
        "Assignment Type",
        [
            AssignmentType.ONE_TIME.value,
            AssignmentType.RECURRING.value
        ]
    )

    recurrence_pattern = st.selectbox(
        "Frequency",
        [
            RecurrencePattern.DAILY.value,
            RecurrencePattern.WEEKLY.value,
            RecurrencePattern.MONTHLY.value,
            RecurrencePattern.WEEKDAYS.value,
            RecurrencePattern.EVERY_MONDAY.value,
            RecurrencePattern.EVERY_TUESDAY.value,
            RecurrencePattern.EVERY_WEDNESDAY.value,
            RecurrencePattern.EVERY_THURSDAY.value,
            RecurrencePattern.EVERY_FRIDAY.value
        ],
        disabled=(
            assignment_type
            != AssignmentType.RECURRING.value
        )
    )

    if (
        assignment_type
        == AssignmentType.ONE_TIME.value
    ):
        recurrence_pattern = None

    due_date = st.date_input(
        "Due Date"
    )

    submitted = st.form_submit_button(
        "Create Assignment"
    )

    if submitted:

        created = AssignmentService.create_assignment(
            subject_id=subject.id if subject else None,
            title=title,
            student_ids=[
                student.id
                for student in selected_students
            ],
            description=description,
            due_date=due_date,
            assignment_type=assignment_type,
            recurrence_pattern=recurrence_pattern
        )

        if created:

            st.toast(
                "Assignment created successfully."
            )

            st.rerun()

        st.error(
            "This assignment couldn't be created. Check that "
            "you've chosen an active subject and students."
        )

# ==================================================
# CURRENT ASSIGNMENTS
# ==================================================

st.divider()

st.subheader("Current Assignments")

assignments = (
    AssignmentService.get_current_family_assignments()
)

if assignments:

    for assignment in assignments:

        assigned_students = [
            sa.student.name
            for sa in assignment.student_assignments
        ]

        completed_count = len(
            [
                sa
                for sa in assignment.student_assignments
                if sa.status == "Complete"
            ]
        )

        total_students = len(
            assignment.student_assignments
        )

        with st.container():

            col1, col2, col3 = st.columns(
                [6, 1, 1]
            )

            with col1:

                st.markdown(
                    f"### 📋 {assignment.title}"
                )

                subject_color = (
                    assignment.subject.color
                    if assignment.subject.color
                    else "#2196F3"
                )

                col_subject1, col_subject2 = (
                    st.columns([1, 20])
                )

                with col_subject1:

                    st.markdown(
                        f"""
                        <div style="
                            width:15px;
                            height:15px;
                            border-radius:50%;
                            background:{subject_color};
                            margin-top:8px;
                        "></div>
                        """,
                        unsafe_allow_html=True
                    )

                with col_subject2:

                    st.caption(
                        assignment.subject.name
                    )

                st.caption(
                    "👨‍🎓 "
                    + ", ".join(
                        assigned_students
                    )
                )

                st.caption(
                    f"✅ Progress: "
                    f"{completed_count}/{total_students}"
                )

                if (
                    assignment.assignment_type
                    == AssignmentType.RECURRING.value
                ):

                    st.caption(
                        f"🔁 {assignment.recurrence_pattern}"
                    )

                else:

                    if assignment.due_date:

                        st.caption(
                            f"📅 Due: {assignment.due_date}"
                        )

                if assignment.description:

                    st.caption(
                        f"📝 {assignment.description}"
                    )

            with col2:

                if st.button(
                    "✏️",
                    key=f"edit_{assignment.id}",
                    help="Edit Assignment"
                ):

                    edit_assignment_dialog(
                        assignment.id
                    )

            with col3:

                if st.button(
                    "📦",
                    key=f"archive_{assignment.id}",
                    help="Archive Assignment"
                ):

                    archive_assignment_dialog(
                        assignment
                    )

            st.divider()

else:

    st.info(
        "No assignments have been created."
    )