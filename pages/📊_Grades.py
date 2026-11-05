import streamlit as st

from components.navigation import (
    NavigationComponent
)
from services.auth_service import AuthService
from services.grade_service import (
    DEFAULT_POINTS,
    GradeService,
    MAX_POINTS
)
from services.navigation_service import NavigationService
from services.occurrence_service import OccurrenceService
from services.student_service import StudentService

NavigationComponent.render()
NavigationService.require_authentication()

# Admins have no family or students to view.

if AuthService.is_admin():

    st.switch_page(
        "pages/📢_Announcements.py"
    )

    st.stop()

SAVE_ERROR = (
    "This couldn't be saved. "
    "Please refresh the page and try again."
)

is_parent = AuthService.is_parent()

today = AuthService.get_today()

st.title("📊 Grades")

# ==================================================
# WHOSE GRADES, WHICH PERIOD
# ==================================================

periods = GradeService.get_periods()

period_names = {
    period.id: period.name
    for period in periods
}

col1, col2 = st.columns(2)

if is_parent:

    students = StudentService.get_current_family_students()

    if not students:

        st.warning(
            "No students found."
        )

        st.stop()

    with col1:

        student_id = st.selectbox(
            "Select Student",
            [student.id for student in students],
            format_func={
                student.id: student.name
                for student in students
            }.get,
            key="grades_student"
        )

else:

    student_id = AuthService.get_current_student()

with col2:

    period_id = st.selectbox(
        "Period",
        [None] + list(period_names),
        format_func=lambda choice: (
            "All time"
            if choice is None
            else period_names[choice]
        ),
        key="grades_period"
    )

chosen_period = next(
    (
        period
        for period in periods
        if period.id == period_id
    ),
    None
)

graded_rows = GradeService.get_graded_rows(student_id)

rows_shown = GradeService.rows_in_period(
    graded_rows,
    chosen_period
)


def status_text(row):
    """
    Says whether a piece of work is checked off.
    """

    return (
        "✅ Completed"
        if OccurrenceService.is_complete(row)
        else "⬜ Not completed"
    )


def table_text(value):
    """
    Keeps a name from breaking a Markdown table.
    """

    return str(value).replace("|", "\\|")


# ==================================================
# GRADES
# ==================================================

subject_percents = GradeService.subject_percents(rows_shown)

overall = GradeService.overall_percent(subject_percents)

if overall is None:

    st.info(
        "No grades here yet."
    )

else:

    st.metric(
        "Overall Grade",
        GradeService.describe(overall)
    )

    lines = [
        "| Subject | Grade |",
        "| --- | --- |",
    ]

    lines += [
        f"| {table_text(name)} | {GradeService.describe(percent)} |"
        for name, percent in subject_percents.items()
    ]

    st.markdown("\n".join(lines))

# ==================================================
# COMPARE PERIODS
# ==================================================

comparison = GradeService.comparison(
    graded_rows,
    periods
)

if comparison["overall"]:

    st.subheader("Compare Periods")

    shown_periods = [
        period
        for period in periods
        if period.id in comparison["overall"]
    ]

    lines = [
        "| Subject | "
        + " | ".join(table_text(period.name) for period in shown_periods)
        + " |",
        "| --- |" + " --- |" * len(shown_periods),
    ]

    for name, percents in comparison["subjects"].items():

        cells = [
            GradeService.describe(percents[period.id])
            if period.id in percents
            else "–"
            for period in shown_periods
        ]

        lines.append(
            f"| {table_text(name)} | " + " | ".join(cells) + " |"
        )

    overall_cells = [
        f"**{GradeService.describe(comparison['overall'][period.id])}**"
        for period in shown_periods
    ]

    lines.append(
        "| **Overall** | " + " | ".join(overall_cells) + " |"
    )

    st.markdown("\n".join(lines))

st.divider()

# ==================================================
# ENTERING GRADES
# ==================================================


def render_row(
    row,
    suggested_total
):
    """
    Shows one piece of work with boxes to grade it.
    """

    is_graded = row.score is not None

    title = OccurrenceService.work_title(row)

    if not row.assignment.active:
        title += " (archived)"

    st.write(f"**{title}**")

    st.caption(
        f"{row.assignment.subject.name} · {row.occurrence_date} · "
        f"{status_text(row)}"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        score = st.number_input(
            "Points Earned",
            min_value=0.0,
            max_value=float(MAX_POINTS),
            step=1.0,
            format="%g",
            value=float(row.score) if is_graded else None,
            key=f"score_{row.id}"
        )

    with col2:

        total = st.number_input(
            "Out Of",
            min_value=1.0,
            max_value=float(MAX_POINTS),
            step=1.0,
            format="%g",
            value=(
                float(row.points_possible)
                if is_graded
                else suggested_total
            ),
            key=f"total_{row.id}"
        )

    with col3:

        if st.button(
            "💾 Save Grade",
            key=f"grade_{row.id}",
            use_container_width=True
        ):

            error = GradeService.grade_error(score, total)

            if error:

                st.error(error)

            elif GradeService.set_grade(row.id, score, total):

                st.toast("Grade saved.")

                st.rerun()

            else:

                st.error(SAVE_ERROR)

        if is_graded and st.button(
            "🗑️ Clear Grade",
            key=f"clear_{row.id}",
            use_container_width=True
        ):

            if GradeService.clear_grade(row.id):

                st.toast("Grade cleared.")

                st.rerun()

            st.error(SAVE_ERROR)

    st.divider()


if is_parent:

    work = GradeService.get_work_to_grade(
        student_id,
        today
    )

    totals = GradeService.suggested_totals(
        work["finished"] + work["unfinished"]
    )

    def suggested(row):

        return totals.get(
            row.assignment_id,
            float(DEFAULT_POINTS)
        )

    st.subheader(
        f"📝 To Grade ({len(work['finished'])})"
    )

    if work["finished"]:

        st.caption(
            "Finished work on graded assignments. For a plain percentage, "
            "use a total of 100."
        )

        for row in work["finished"]:

            render_row(row, suggested(row))

    else:

        st.caption(
            "Nothing is waiting for a grade. Mark an assignment as Graded "
            "on the Assignments page to see its finished work here."
        )

    if work["unfinished"]:

        with st.expander(
            f"Grade Work Not Checked Off ({len(work['unfinished'])})"
        ):

            st.caption(
                "This shows work from the last 30 days and the next 7 days, "
                "so you can grade something early. Grading doesn't check it "
                "off, and blank scores never count."
            )

            for row in work["unfinished"]:

                render_row(row, suggested(row))

# ==================================================
# GRADED WORK
# ==================================================

if rows_shown:

    with st.expander(
        f"Graded Work ({len(rows_shown)})"
    ):

        for row in rows_shown:

            if is_parent:

                render_row(row, float(DEFAULT_POINTS))

            else:

                st.write(
                    f"**{OccurrenceService.work_title(row)}**: "
                    f"{GradeService.describe(GradeService.percent(row))}"
                )

                st.caption(
                    f"{row.assignment.subject.name} · "
                    f"{row.occurrence_date} · "
                    f"{status_text(row)} · "
                    f"{float(row.score):g} out of "
                    f"{float(row.points_possible):g}"
                )

# ==================================================
# MANAGING PERIODS
# ==================================================


@st.dialog("✏️ Edit Period")
def edit_period_dialog(period):

    name = st.text_input(
        "Name",
        value=period.name
    )

    start_date = st.date_input(
        "Start Date",
        value=period.start_date
    )

    end_date = st.date_input(
        "End Date",
        value=period.end_date
    )

    if st.button("💾 Save Changes"):

        error = GradeService.period_error(
            name,
            start_date,
            end_date,
            period.id
        )

        if error:

            st.error(error)

            return

        if not GradeService.update_period(
            period.id,
            name,
            start_date,
            end_date
        ):

            st.error(SAVE_ERROR)

            return

        st.toast("Period updated.")

        st.rerun()


@st.dialog("📦 Archive Period")
def archive_period_dialog(period):

    st.warning(
        f"Archive '{period.name}'?"
    )

    st.write(
        "It will no longer be offered or compared. Grades aren't changed."
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

            if not GradeService.archive_period(period.id):

                st.error(SAVE_ERROR)

                return

            st.toast("Period archived.")

            st.rerun()


if is_parent:

    st.subheader("🗓️ Grading Periods")

    st.caption(
        "Name them whatever fits your school year, like Fall 2026. A grade "
        "belongs to the period its date falls in."
    )

    for period in periods:

        col1, col2, col3 = st.columns([6, 1, 1])

        with col1:

            st.write(
                f"**{period.name}**: "
                f"{period.start_date} to {period.end_date}"
            )

        with col2:

            if st.button(
                "✏️",
                key=f"edit_period_{period.id}",
                help="Edit Period"
            ):

                edit_period_dialog(period)

        with col3:

            if st.button(
                "📦",
                key=f"archive_period_{period.id}",
                help="Archive Period"
            ):

                archive_period_dialog(period)

    with st.form(
        "add_period_form",
        clear_on_submit=True
    ):

        new_name = st.text_input("Period Name")

        col1, col2 = st.columns(2)

        with col1:

            new_start = st.date_input(
                "Start Date",
                value=today
            )

        with col2:

            new_end = st.date_input(
                "End Date",
                value=today
            )

        if st.form_submit_button("Add Period"):

            error = GradeService.period_error(
                new_name,
                new_start,
                new_end
            )

            if error:

                st.error(error)

            elif GradeService.create_period(
                new_name,
                new_start,
                new_end
            ):

                st.toast("Period added.")

                st.rerun()

            else:

                st.error(SAVE_ERROR)
