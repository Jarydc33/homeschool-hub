import streamlit as st

from services.subject_service import SubjectService

st.title("📚 Subjects")

subjects = SubjectService.get_all_subjects()

# -----------------------------
# Existing Subjects
# -----------------------------

st.subheader("Current Subjects")

if subjects:

    for subject in subjects:

        st.write(
            f"📘 {subject.name}"
        )

else:
    st.info("No subjects have been created.")

st.divider()

# -----------------------------
# Add Subject
# -----------------------------

st.subheader("Add Subject")

with st.form("add_subject_form"):

    name = st.text_input("Subject Name")

    color = st.color_picker(
        "Subject Color",
        "#2196F3"
    )

    submitted = st.form_submit_button(
        "Add Subject"
    )

    if submitted:

        SubjectService.create_subject(
            family_id=1,
            name=name,
            color=color
        )

        st.success(
            f"{name} added successfully."
        )

        st.rerun()