import streamlit as st

from components.navigation import (
    NavigationComponent
)
from services.auth_service import AuthService
from services.event_service import (
    EventService,
    REPEAT_OPTIONS
)
from services.navigation_service import NavigationService
from services.occurrence_service import OccurrenceService
from services.student_service import StudentService

NavigationComponent.render()
NavigationService.require_authentication()

# Admins have no family or events to view.

if AuthService.is_admin():

    st.switch_page(
        "pages/📢_Announcements.py"
    )

    st.stop()

NO_REPEAT = "Does not repeat"

SAVE_ERROR = (
    "This event couldn't be saved. "
    "Please refresh the page and try again."
)


# ==================================================
# DIALOGS
# ==================================================

@st.dialog("✏️ Edit Event")
def edit_event_dialog(event_id):

    event = EventService.get_event_by_id(
        event_id
    )

    if not event:

        st.error(
            "This event could not be found."
        )

        return

    title = st.text_input(
        "Title",
        value=event.title
    )

    description = st.text_area(
        "Details",
        value=event.description or "",
        help="Where to go, what to bring, anything else."
    )

    students = StudentService.get_current_family_students()

    linked_ids = {
        link.student_id
        for link in event.event_students
    }

    chosen = st.multiselect(
        "Who's It For?",
        students,
        default=[
            student
            for student in students
            if student.id in linked_ids
        ],
        format_func=lambda student: student.name,
        placeholder="Whole family"
    )

    options = [NO_REPEAT] + REPEAT_OPTIONS

    repeat = st.selectbox(
        "Repeats",
        options,
        index=(
            options.index(event.recurrence_pattern)
            if event.recurrence_pattern in options
            else 0
        )
    )

    start_date = st.date_input(
        "Date" if repeat == NO_REPEAT else "First Date",
        value=event.start_date
    )

    end_date = None
    repeat_until = None

    if repeat == NO_REPEAT:

        end_date = st.date_input(
            "Last Day (for a multi-day event)",
            value=event.end_date
        )

    else:

        repeat_until = st.date_input(
            "Repeats Until",
            value=(
                event.repeat_until
                or OccurrenceService.default_end_date(
                    AuthService.get_today()
                )
            )
        )

    start_time = st.time_input(
        "Start Time (leave empty for all day)",
        value=event.start_time
    )

    if st.button("💾 Save Changes"):

        recurrence_pattern = (
            None
            if repeat == NO_REPEAT
            else repeat
        )

        schedule_error = EventService.schedule_error(
            start_date,
            end_date,
            recurrence_pattern,
            repeat_until
        )

        if schedule_error:

            st.error(schedule_error)

            return

        if not title.strip():

            st.error("Please enter a title.")

            return

        updated = EventService.update_event(
            event_id=event.id,
            title=title,
            start_date=start_date,
            description=description,
            end_date=end_date,
            start_time=start_time,
            recurrence_pattern=recurrence_pattern,
            repeat_until=repeat_until,
            student_ids=[
                student.id
                for student in chosen
            ]
        )

        if not updated:

            st.error(SAVE_ERROR)

            return

        st.toast("Event updated.")

        st.rerun()


@st.dialog("📦 Archive Event")
def archive_event_dialog(event):

    st.warning(
        f"Archive '{event.title}'?"
    )

    st.write(
        "It will no longer show for anyone. "
        "For a repeating event, that's every date."
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

            if not EventService.archive_event(event.id):

                st.error(SAVE_ERROR)

                return

            st.toast("Event archived.")

            st.rerun()


# ==================================================
# EVENT LIST
# ==================================================

is_parent = AuthService.is_parent()


def render_event(
    event,
    day=None
):

    col1, col2, col3 = st.columns([6, 1, 1])

    with col1:

        st.markdown(f"### 🎉 {event.title}")

        if day:

            st.caption(
                f"📅 {EventService.describe_when(event, day)}"
            )

        if event.recurrence_pattern:

            st.caption(
                f"🔁 {event.recurrence_pattern}, "
                f"until {event.repeat_until}"
            )

        st.caption(
            f"👨‍🎓 {EventService.audience(event)}"
        )

        if event.description:

            st.caption(
                f"📝 {event.description}"
            )

    if is_parent:

        with col2:

            if st.button(
                "✏️",
                key=f"edit_{event.id}",
                help="Edit Event"
            ):

                edit_event_dialog(event.id)

        with col3:

            if st.button(
                "📦",
                key=f"archive_{event.id}",
                help="Archive Event"
            ):

                archive_event_dialog(event)

    st.divider()


st.title("📅 Events")

today = AuthService.get_today()

upcoming, past = EventService.split_by_date(
    EventService.get_visible_events(),
    today
)

st.subheader("Upcoming")

if upcoming:

    for entry in upcoming:

        render_event(
            entry["event"],
            entry["date"]
        )

else:

    st.info(
        "No upcoming events."
    )

if past:

    with st.expander(
        f"Past Events ({len(past)})"
    ):

        for event in past:

            render_event(event)

# ==================================================
# ADD EVENT
# ==================================================

if is_parent:

    st.subheader("➕ Add Event")

    # Outside the form so that changing it reruns the page and shows the
    # right date fields.

    repeat = st.selectbox(
        "Repeats",
        [NO_REPEAT] + REPEAT_OPTIONS,
        key="create_event_repeat"
    )

    with st.form(
        "add_event_form",
        clear_on_submit=True
    ):

        title = st.text_input("Title")

        description = st.text_area(
            "Details",
            help="Where to go, what to bring, anything else."
        )

        chosen = st.multiselect(
            "Who's It For?",
            StudentService.get_current_family_students(),
            format_func=lambda student: student.name,
            placeholder="Whole family"
        )

        start_date = st.date_input(
            "Date" if repeat == NO_REPEAT else "First Date",
            value=today
        )

        end_date = None
        repeat_until = None

        if repeat == NO_REPEAT:

            end_date = st.date_input(
                "Last Day (for a multi-day event)",
                value=None
            )

        else:

            repeat_until = st.date_input(
                "Repeats Until",
                value=OccurrenceService.default_end_date(today)
            )

        start_time = st.time_input(
            "Start Time (leave empty for all day)",
            value=None
        )

        submitted = st.form_submit_button(
            "Create Event"
        )

        if submitted:

            recurrence_pattern = (
                None
                if repeat == NO_REPEAT
                else repeat
            )

            schedule_error = EventService.schedule_error(
                start_date,
                end_date,
                recurrence_pattern,
                repeat_until
            )

            if schedule_error:

                st.error(schedule_error)

            elif not title.strip():

                st.error("Please enter a title.")

            elif EventService.create_event(
                title=title,
                start_date=start_date,
                description=description,
                end_date=end_date,
                start_time=start_time,
                recurrence_pattern=recurrence_pattern,
                repeat_until=repeat_until,
                student_ids=[
                    student.id
                    for student in chosen
                ]
            ):

                st.toast("Event created.")

                st.rerun()

            else:

                st.error(
                    "This event couldn't be created. "
                    "Please refresh the page and try again."
                )
