import streamlit as st

from services.auth_service import AuthService

# --------------------------------------------------
# Redirect Authenticated Users
# --------------------------------------------------

if AuthService.is_authenticated():

    if AuthService.is_student():

        st.switch_page(
            "pages/5_🎓_Student_Dashboard.py"
        )

    else:

        st.switch_page(
            "pages/🏡_Parent_Dashboard.py"
        )

# --------------------------------------------------
# Page Config
# --------------------------------------------------

st.set_page_config(
    page_title="Homeschool Hub",
    page_icon="🏡",
    layout="wide"
)

# --------------------------------------------------
# Hero Section
# --------------------------------------------------

st.title("🏡 Homeschool Hub")

st.subheader(
    "The simplest way to manage your homeschool."
)

st.write(
    """
    Homeschool Hub helps parents organize students,
    assignments, schedules, and educational progress
    while giving students a simple daily dashboard
    focused on completing their work.
    """
)

st.divider()

# --------------------------------------------------
# Key Features
# --------------------------------------------------

st.header("Why Families Use Homeschool Hub")

col1, col2, col3 = st.columns(3)

with col1:

    st.markdown("### ✅ Assignment Tracking")

    st.write(
        """
        Create assignments,
        assign work to multiple students,
        and track completion progress.
        """
    )

with col2:

    st.markdown("### 🎓 Student Dashboard")

    st.write(
        """
        Give students a clear view of
        today's work, overdue tasks,
        and progress toward completion.
        """
    )

with col3:

    st.markdown("### 📈 Parent Oversight")

    st.write(
        """
        Monitor student progress,
        overdue assignments,
        announcements, and daily workload
        from a single dashboard.
        """
    )

st.divider()

# --------------------------------------------------
# How It Works
# --------------------------------------------------

st.header("How It Works")

st.write(
    """
    1. Create your family account.
    2. Add students.
    3. Create subjects.
    4. Assign daily work.
    5. Let students track their progress.
    """
)

st.divider()

# --------------------------------------------------
# Call To Action
# --------------------------------------------------

st.header("Get Started")

col1, col2 = st.columns(2)

with col1:

    if st.button(
        "🔐 Login",
        use_container_width=True
    ):

        st.switch_page(
            "pages/0_🔐_Login.py"
        )

with col2:

    if st.button(
        "📝 Create Account",
        use_container_width=True
    ):

        st.switch_page(
            "pages/0_📝_Register.py"
        )

st.divider()

# --------------------------------------------------
# Footer
# --------------------------------------------------

st.caption(
    "Built specifically for homeschooling families."
)