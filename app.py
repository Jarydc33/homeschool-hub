from services.auth_service import (
    AuthService
)
import streamlit as st

if AuthService.is_authenticated():

    if AuthService.is_student():

        st.switch_page(
            "pages/5_🎓_Student_Dashboard.py"
        )

    else:

        st.switch_page(
            "pages/1_🏡_Parent_Dashboard.py"
        )
else:
    st.switch_page(
        "pages/0_🏡_Landing_Page.py"
    )