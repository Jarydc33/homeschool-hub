from services.auth_service import (
    AuthService
)
import streamlit as st

if AuthService.is_authenticated():

    if AuthService.is_student():

        st.switch_page(
            "pages/🎓_Student_Dashboard.py"
        )

    else:

        st.switch_page(
            "pages/🏡_Parent_Dashboard.py"
        )
else:
    st.switch_page(
        "pages/🏡_Landing_Page.py"
    )