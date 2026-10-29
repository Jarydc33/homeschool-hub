import streamlit as st

from services.student_service import StudentService
from services.subject_service import SubjectService

st.title("🏡 Homeschool Hub")

st.subheader("Parent Dashboard")

students = StudentService.get_all_students()
subjects = SubjectService.get_all_subjects()

col1, col2 = st.columns(2)

with col1:
    st.metric(
        "Students",
        len(students)
    )

with col2:
    st.metric(
        "Subjects",
        len(subjects)
    )
