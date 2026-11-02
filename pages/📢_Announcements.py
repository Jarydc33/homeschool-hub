import streamlit as st

from services.banner_service import BannerService

from services.navigation_service import NavigationService
from components.navigation import (
    NavigationComponent
)

NavigationComponent.render()
NavigationService.require_parent()

# ==================================================
# DIALOGS
# ==================================================

@st.dialog("✏️ Edit Announcement")
def edit_banner_dialog(banner_id):

    banner = (
        BannerService.get_banner_by_id(
            banner_id
        )
    )

    title = st.text_input(
        "Title",
        value=banner.title
    )

    message = st.text_area(
        "Message",
        value=banner.message
    )

    start_date = st.date_input(
        "Start Date",
        value=banner.start_date
    )

    end_date = st.date_input(
        "End Date",
        value=banner.end_date
    )

    if st.button(
        "💾 Save Changes",
        use_container_width=True
    ):

        BannerService.update_banner(
            banner_id=banner.id,
            title=title,
            message=message,
            start_date=start_date,
            end_date=end_date
        )

        st.toast(
            "Announcement updated."
        )

        st.rerun()


@st.dialog("📦 Archive Announcement")
def archive_banner_dialog(banner):

    st.warning(
        f"Archive '{banner.title}'?"
    )

    st.write(
        "The announcement will no longer display on the dashboard."
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

            BannerService.archive_banner(
                banner.id
            )

            st.toast(
                "Announcement archived."
            )

            st.rerun()


# ==================================================
# PAGE HEADER
# ==================================================

st.title("📢 Announcements")

st.write(
    "Create messages that appear on the Parent Dashboard."
)

# ==================================================
# EXISTING ANNOUNCEMENTS
# ==================================================

st.subheader(
    "Current Announcements"
)

banners = (
    BannerService.get_all_banners()
)

if banners:

    for banner in banners:

        with st.container():

            col1, col2, col3 = st.columns(
                [6, 1, 1]
            )

            with col1:

                st.markdown(
                    f"### 📢 {banner.title}"
                )

                st.caption(
                    f"Active: "
                    f"{banner.start_date} "
                    f"→ "
                    f"{banner.end_date}"
                )

                st.caption(
                    banner.message
                )

            with col2:

                if st.button(
                    "✏️",
                    key=f"edit_{banner.id}",
                    help="Edit Announcement"
                ):

                    edit_banner_dialog(
                        banner.id
                    )

            with col3:

                if st.button(
                    "📦",
                    key=f"archive_{banner.id}",
                    help="Archive Announcement"
                ):

                    archive_banner_dialog(
                        banner
                    )

            st.divider()

else:

    st.info(
        "No announcements have been created."
    )

# ==================================================
# ADD ANNOUNCEMENT
# ==================================================

st.subheader(
    "➕ Add Announcement"
)

with st.form(
    "add_announcement_form",
    clear_on_submit=True
):

    title = st.text_input(
        "Title"
    )

    message = st.text_area(
        "Message"
    )

    col1, col2 = st.columns(2)

    with col1:

        start_date = st.date_input(
            "Start Date"
        )

    with col2:

        end_date = st.date_input(
            "End Date"
        )

    submitted = st.form_submit_button(
        "Create Announcement"
    )

    if submitted:

        BannerService.create_banner(
            title=title,
            message=message,
            start_date=start_date,
            end_date=end_date
        )

        st.toast(
            "Announcement created."
        )

        st.rerun()