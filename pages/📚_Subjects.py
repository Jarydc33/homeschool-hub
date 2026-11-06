import streamlit as st

from services.subject_service import SubjectService
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

@st.dialog("✏️ Edit Subject")
def edit_subject_dialog(subject_id):

    subject = (
        SubjectService.get_subject_by_id(
            subject_id
        )
    )

    if not subject:

        st.error(
            "This subject could not be found."
        )

        return

    name = st.text_input(
        "Subject Name",
        value=subject.name
    )

    color = st.color_picker(
        "Subject Color",
        value=subject.color
        if subject.color
        else "#2196F3"
    )

    if st.button("💾 Save Changes"):

        updated = SubjectService.update_subject(
            subject_id=subject.id,
            name=name,
            color=color
        )

        if not updated:

            st.error(
                "This subject couldn't be saved. "
                "Please refresh the page and try again."
            )

            return

        st.toast(
            f"{name} updated successfully."
        )

        st.rerun()


@st.dialog("📦 Archive Subject")
def archive_subject_dialog(subject):

    st.warning(
        f"Archive {subject.name}?"
    )

    st.write(
        "The subject will be hidden from active views but will remain in the database."
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

            archived = SubjectService.archive_subject(
                subject.id
            )

            if not archived:

                st.error(
                    "This subject couldn't be archived. "
                    "Please refresh the page and try again."
                )

                return

            st.toast(
                f"{subject.name} archived."
            )

            st.rerun()


# ==================================================
# PAGE HEADER
# ==================================================

st.title("📚 Subjects")

st.write(
    "Manage homeschool subjects."
)

subjects = (
    SubjectService.get_current_family_subjects()
)

# ==================================================
# CURRENT SUBJECTS
# ==================================================

st.subheader("Current Subjects")

if subjects:

    for subject in subjects:
        # Using service call instead of subject.assignments
        # to avoid SQLAlchemy session/loading issues.
        assignment_count = (
            SubjectService.get_subject_assignment_count(
                subject.id
            )
        )

        with st.container():

            col1, col2, col3 = st.columns(
                [6, 1, 1]
            )

            # ------------------------------
            # Subject Info
            # ------------------------------

            with col1:

                color = SubjectService.display_color(
                    subject.color
                )

                st.markdown(
                    f"### {subject.name}"
                )

                st.caption(
                    f"🎯 {assignment_count} assignment(s)"
                )

                st.markdown(
                    f"""
                    <div
                        style="
                        width:40px;
                        height:8px;
                        background:{color};
                        border-radius:10px;
                        margin-top:-5px;
                        ">
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            # ------------------------------
            # Edit Button
            # ------------------------------

            with col2:

                if st.button(
                    "✏️",
                    key=f"edit_{subject.id}",
                    help="Edit Subject"
                ):

                    edit_subject_dialog(
                        subject.id
                    )

            # ------------------------------
            # Archive Button
            # ------------------------------

            with col3:

                if st.button(
                    "📦",
                    key=f"archive_{subject.id}",
                    help="Archive Subject"
                ):

                    archive_subject_dialog(
                        subject
                    )

            st.divider()

else:

    st.info(
        "No subjects have been created."
    )

# ==================================================
# ARCHIVED SUBJECTS
# ==================================================

archived_subjects = SubjectService.get_archived_subjects()

if archived_subjects:

    with st.expander(
        f"📦 Archived Subjects ({len(archived_subjects)})"
    ):

        st.caption(
            "Restoring a subject lets you choose it for new work again. "
            "Its assignments and grades were never removed."
        )

        for subject in archived_subjects:

            col1, col2 = st.columns(
                [5, 2]
            )

            with col1:

                st.write(
                    subject.name
                )

            with col2:

                if st.button(
                    "Restore",
                    key=f"restore_subject_{subject.id}",
                    use_container_width=True
                ):

                    if SubjectService.restore_subject(
                        subject.id
                    ):

                        st.toast(
                            f"{subject.name} restored."
                        )

                        st.rerun()

                    st.error(
                        "This subject couldn't be restored. "
                        "Please refresh the page and try again."
                    )

# ==================================================
# ADD SUBJECT
# ==================================================

st.subheader("➕ Add Subject")

with st.form(
    "add_subject_form",
    clear_on_submit=True
):

    name = st.text_input(
        "Subject Name"
    )

    color = st.color_picker(
        "Subject Color",
        "#2196F3"
    )

    submitted = st.form_submit_button(
        "Add Subject"
    )

    if submitted:

        SubjectService.create_subject(
            name=name,
            color=color
        )

        st.toast(
            f"{name} added successfully."
        )

        st.rerun()