import streamlit as st

from components.navigation import (
    NavigationComponent
)
from services.auth_service import AuthService
from services.calendar_service import CalendarService
from services.navigation_service import NavigationService
from services.student_service import StudentService

st.set_page_config(
    page_title="Calendar",
    page_icon="📆",
    layout="wide"
)

NavigationComponent.render()
NavigationService.require_authentication()

# Admins have no family or schedule to view.

if AuthService.is_admin():

    st.switch_page(
        "pages/📢_Announcements.py"
    )

    st.stop()

# How many items a month's day shows before "+3 more".
MONTH_DAY_ITEMS = 3

today = AuthService.get_today()

st.title("📆 Calendar")

# ==================================================
# WHAT TO SHOW
# ==================================================

student_id = None

col1, col2 = st.columns(2)

with col1:

    view = st.radio(
        "View",
        ["Week", "Month"],
        horizontal=True,
        key="calendar_view"
    )

show_months = view == "Month"

if AuthService.is_parent():

    students = {
        student.id: student.name
        for student in StudentService.get_current_family_students()
    }

    with col2:

        student_id = st.selectbox(
            "Whose Schedule?",
            [None] + list(students),
            format_func=lambda choice: (
                "Whole family"
                if choice is None
                else students[choice]
            ),
            key="calendar_student"
        )

show_student = (
    AuthService.is_parent()
    and student_id is None
)


# ==================================================
# MOVING AROUND
# ==================================================

if "calendar_day" not in st.session_state:

    st.session_state["calendar_day"] = today


def move(step):

    st.session_state["calendar_day"] = CalendarService.shift(
        st.session_state["calendar_day"],
        show_months,
        step
    )


def go_to_today():

    st.session_state["calendar_day"] = today


col1, col2, col3 = st.columns(3)

with col1:

    st.button(
        "◀ Previous",
        key="calendar_previous",
        on_click=move,
        args=(-1,),
        use_container_width=True
    )

with col2:

    st.button(
        "Today",
        key="calendar_today",
        on_click=go_to_today,
        use_container_width=True
    )

with col3:

    st.button(
        "Next ▶",
        key="calendar_next",
        on_click=move,
        args=(1,),
        use_container_width=True
    )

shown_day = st.session_state["calendar_day"]

weeks = (
    CalendarService.month_weeks(shown_day)
    if show_months
    else [CalendarService.week_days(shown_day)]
)

first = weeks[0][0]
last = weeks[-1][-1]

if show_months:

    st.subheader(f"{shown_day:%B %Y}")

else:

    st.subheader(
        f"{first:%b} {first.day} to {last:%b} {last.day}, {last.year}"
    )

st.caption(
    "🎉 Event  ·  📋 To do  ·  ✅ Done  ·  ⚠️ Overdue  ·  🕓 Missed"
)

# ==================================================
# THE CALENDAR
# ==================================================

items = CalendarService.get_items(
    first,
    last,
    student_id
)


def render_day(day):

    heading = f"{day:%a} {day.day}"

    if day == today:

        st.markdown(f":blue[**{heading} (Today)**]")

    elif show_months and day.month != shown_day.month:

        st.caption(heading)

    else:

        st.markdown(f"**{heading}**")

    day_items = items.get(day, [])

    shown = (
        day_items[:MONTH_DAY_ITEMS]
        if show_months
        else day_items
    )

    for item in shown:

        st.write(
            CalendarService.label(
                item,
                show_student
            )
        )

        if not show_months:

            st.caption(item["detail"])

    hidden = len(day_items) - len(shown)

    if hidden:

        st.caption(f"+{hidden} more")


for week in weeks:

    for column, day in zip(st.columns(7), week):

        with column:

            render_day(day)

    st.divider()

if not items:

    st.info(
        "Nothing is scheduled here."
    )
