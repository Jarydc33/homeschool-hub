from services.auth_service import (
    AuthService
)
import streamlit as st

from components.navigation import NavigationComponent

# Once the new app takes over, every page only says where it went.
NavigationComponent.show_moved_notice()

AuthService.start_page_run()

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