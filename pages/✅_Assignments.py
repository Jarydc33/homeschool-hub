import streamlit as st

from services.assignment_service import AssignmentService
from services.student_service import StudentService
from services.subject_service import SubjectService

from database.models import (
    AssignmentType,
    RecurrencePattern
)
from services.auth_service import (
    AuthService
)

from services.navigation_service import NavigationService
from services.occurrence_service import (
    OccurrenceService,
    SCHOOL_DAY_NAMES
)
from components.navigation import (
    NavigationComponent
)

NavigationComponent.render()
NavigationService.require_parent()

# ==================================================
# DIALOGS
# ==================================================

@st.dialog("✏️ Edit Assignment")
def edit_assignment_dialog(assignment_id):

    assignment = (
        AssignmentService.get_assignment_by_id(
            assignment_id
        )
    )

    if not assignment:

        st.error(
            "This assignment could not be found."
        )

        return

    subjects = (
        SubjectService.get_current_family_subjects()
    )

    students = (
        StudentService.get_current_family_students()
    )

    # Keep an archived subject selectable so saving doesn't
    # silently move the assignment to a different subject.

    current_subject_archived = (
        assignment.subject is not None
        and not assignment.subject.active
    )

    if current_subject_archived:

        subjects = [assignment.subject] + subjects

    if not subjects:

        st.warning(
            "Add a subject before editing this assignment."
        )

        return

    assigned_student_ids = [
        sa.student_id
        for sa in assignment.student_assignments
    ]

    title = st.text_input(
        "Assignment Title",
        value=assignment.title
    )

    description = st.text_area(
        "Description",
        value=assignment.description or ""
    )

    is_curriculum = (
        assignment.assignment_type
        == AssignmentType.CURRICULUM.value
    )

    # A curriculum's lessons can't become other work, or the reverse.

    if is_curriculum:

        assignment_type = assignment.assignment_type

    else:

        assignment_type = st.selectbox(
            "Assignment Type",
            [
                AssignmentType.ONE_TIME.value,
                AssignmentType.RECURRING.value
            ],
            index=(
                0
                if assignment.assignment_type
                == AssignmentType.ONE_TIME.value
                else 1
            )
        )

    recurrence_pattern = None

    if (
        assignment_type
        == AssignmentType.RECURRING.value
    ):

        recurrence_options = [
            RecurrencePattern.DAILY.value,
            RecurrencePattern.WEEKLY.value,
            RecurrencePattern.MONTHLY.value,
            RecurrencePattern.WEEKDAYS.value,
            RecurrencePattern.EVERY_MONDAY.value,
            RecurrencePattern.EVERY_TUESDAY.value,
            RecurrencePattern.EVERY_WEDNESDAY.value,
            RecurrencePattern.EVERY_THURSDAY.value,
            RecurrencePattern.EVERY_FRIDAY.value
        ]

        recurrence_pattern = st.selectbox(
            "Frequency",
            recurrence_options,
            index=(
                recurrence_options.index(
                    assignment.recurrence_pattern
                )
                if (
                    assignment.recurrence_pattern
                    in recurrence_options
                )
                else 0
            )
        )

    selected_subject = st.selectbox(
        "Subject",
        subjects,
        index=next(
            (
                i
                for i, subject in enumerate(subjects)
                if subject.id == assignment.subject_id
            ),
            0
        ),
        format_func=lambda x: (
            f"{x.name} (archived)"
            if not x.active
            else x.name
        )
    )

    selected_students = st.multiselect(
        "Assign To",
        students,
        default=[
            s
            for s in students
            if s.id in assigned_student_ids
        ],
        format_func=lambda x: x.name
    )

    is_recurring = (
        assignment_type
        == AssignmentType.RECURRING.value
    )

    due_date = st.date_input(
        "Starts On" if is_recurring or is_curriculum else "Due Date",
        value=assignment.due_date
    )

    lesson_count = None

    if is_curriculum:

        lesson_count = st.number_input(
            "Number of Lessons",
            min_value=1,
            step=1,
            value=max(
                OccurrenceService.lesson_count(assignment),
                1
            )
        )

        recurrence_pattern = OccurrenceService.school_days_value(
            st.multiselect(
                "School Days",
                SCHOOL_DAY_NAMES,
                default=(assignment.recurrence_pattern or "").split(",")
            )
        )

        st.caption(
            "Changing the start date or school days gives every lesson "
            "that hasn't been started a new date, from today on."
        )

    end_date = None

    if is_recurring:

        end_date = st.date_input(
            "Ends On",
            value=(
                assignment.end_date
                or OccurrenceService.default_end_date(
                    AuthService.get_today()
                )
            )
        )

    graded = st.checkbox(
        "Graded",
        value=bool(assignment.graded),
        help="Its scores count towards grades on the Grades page."
    )

    if st.button("💾 Save Changes"):

        schedule_error = OccurrenceService.schedule_error(
            assignment_type,
            recurrence_pattern,
            due_date,
            end_date,
            lesson_count
        )

        if schedule_error:

            st.error(schedule_error)

            return

        updated = AssignmentService.update_assignment(
            assignment_id=assignment.id,
            title=title,
            description=description,
            due_date=due_date,
            subject_id=selected_subject.id,
            student_ids=[
                student.id
                for student in selected_students
            ],
            assignment_type=assignment_type,
            recurrence_pattern=recurrence_pattern,
            end_date=end_date,
            lesson_count=lesson_count,
            graded=graded
        )

        if not updated:

            st.error(
                "This assignment couldn't be saved. "
                "Please refresh the page and try again."
            )

            return

        st.toast(
            "Assignment updated successfully."
        )

        st.rerun()


@st.dialog("📝 Note for a Date")
def note_dialog(assignment_id):

    rows = AssignmentService.get_note_rows(
        assignment_id
    )

    if not rows:

        st.warning(
            "This assignment has no students to add a note for."
        )

        return

    dates = sorted(
        {row.occurrence_date for row in rows}
    )

    day = st.selectbox(
        "Date",
        dates,
        index=dates.index(
            OccurrenceService.default_note_date(
                dates,
                AuthService.get_today()
            )
        ),
        format_func=lambda d: d.strftime("%a, %b %d, %Y")
    )

    rows_on_day = [
        row
        for row in rows
        if row.occurrence_date == day
    ]

    names = {
        row.student_id: row.student.name
        for row in rows_on_day
    }

    selected_students = st.multiselect(
        "For",
        list(names),
        default=list(names),
        format_func=names.get,
        key=f"note_students_{day}"
    )

    existing_notes = {
        row.notes or ""
        for row in rows_on_day
        if row.student_id in selected_students
    }

    if len(existing_notes) > 1:

        st.caption(
            "These students have different notes. "
            "Saving replaces them all."
        )

    note = st.text_area(
        "Note",
        value=min(existing_notes, default=""),
        key=f"note_text_{day}",
        help="Students see this on that date. Leave it blank to remove it."
    )

    if st.button("💾 Save Note"):

        if not selected_students:

            st.error(
                "Please choose at least one student."
            )

            return

        saved = AssignmentService.set_occurrence_note(
            assignment_id,
            day,
            selected_students,
            note
        )

        if not saved:

            st.error(
                "This note couldn't be saved. "
                "Please refresh the page and try again."
            )

            return

        st.toast(
            "Note saved."
        )

        st.rerun()


@st.dialog("📦 Archive Assignment")
def archive_assignment_dialog(assignment):

    st.warning(
        f"Archive '{assignment.title}'?"
    )

    st.write(
        "The assignment will be hidden from active views "
        "but will remain in the database."
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

            archived = AssignmentService.archive_assignment(
                assignment.id
            )

            if not archived:

                st.error(
                    "This assignment couldn't be archived. "
                    "Please refresh the page and try again."
                )

                return

            st.toast(
                "Assignment archived."
            )

            st.rerun()


# ==================================================
# PAGE HEADER
# ==================================================

st.title("✅ Assignments")

students = (
    StudentService.get_current_family_students()
)

subjects = (
    SubjectService.get_current_family_subjects()
)

# ==================================================
# CREATE ASSIGNMENT
# ==================================================

st.subheader("➕ Create Assignment")

# Outside the form so that changing it reruns the page and shows Frequency.

assignment_type = st.selectbox(
    "Assignment Type",
    [
        AssignmentType.ONE_TIME.value,
        AssignmentType.RECURRING.value,
        AssignmentType.CURRICULUM.value
    ],
    key="create_assignment_type"
)

is_curriculum = (
    assignment_type
    == AssignmentType.CURRICULUM.value
)

today = AuthService.get_today()

lesson_count = None
school_days = None

# Also outside the form, so the finish date updates as these change.

if is_curriculum:

    lesson_count = st.number_input(
        "Number of Lessons",
        min_value=1,
        step=1,
        value=None,
        placeholder="For example, 120",
        key="create_lesson_count"
    )

    school_days = OccurrenceService.school_days_value(
        st.multiselect(
            "School Days",
            SCHOOL_DAY_NAMES,
            default=SCHOOL_DAY_NAMES[:5],
            key="create_school_days"
        )
    )

    curriculum_start = st.date_input(
        "Starts On",
        value=today,
        key="create_curriculum_start"
    )

    if lesson_count and school_days:

        curriculum_error = OccurrenceService.schedule_error(
            assignment_type,
            school_days,
            curriculum_start,
            lesson_count=lesson_count
        )

        if curriculum_error:

            st.warning(curriculum_error)

        else:

            last_lesson = OccurrenceService.lesson_dates(
                school_days,
                curriculum_start,
                lesson_count
            )[-1]

            st.info(
                f"Lesson {lesson_count} lands on "
                f"{last_lesson:%A, %B} {last_lesson.day}, {last_lesson.year}."
            )

with st.form(
    "assignment_form",
    clear_on_submit=True
):

    title = st.text_input(
        "Assignment Title"
    )

    subject = st.selectbox(
        "Subject",
        subjects,
        format_func=lambda x: x.name
    )

    selected_students = st.multiselect(
        "Assign To",
        students,
        format_func=lambda x: x.name
    )

    description = st.text_area(
        "Description"
    )

    recurrence_pattern = None

    if (
        assignment_type
        == AssignmentType.RECURRING.value
    ):

        recurrence_pattern = st.selectbox(
            "Frequency",
            [
                RecurrencePattern.DAILY.value,
                RecurrencePattern.WEEKLY.value,
                RecurrencePattern.MONTHLY.value,
                RecurrencePattern.WEEKDAYS.value,
                RecurrencePattern.EVERY_MONDAY.value,
                RecurrencePattern.EVERY_TUESDAY.value,
                RecurrencePattern.EVERY_WEDNESDAY.value,
                RecurrencePattern.EVERY_THURSDAY.value,
                RecurrencePattern.EVERY_FRIDAY.value
            ]
        )

    is_recurring = (
        assignment_type
        == AssignmentType.RECURRING.value
    )

    if is_curriculum:

        recurrence_pattern = school_days
        due_date = curriculum_start

    else:

        due_date = st.date_input(
            "Starts On" if is_recurring else "Due Date",
            value=today
        )

    end_date = None

    if is_recurring:

        end_date = st.date_input(
            "Ends On",
            value=OccurrenceService.default_end_date(today)
        )

    graded = st.checkbox(
        "Graded",
        help="Its scores count towards grades on the Grades page."
    )

    submitted = st.form_submit_button(
        "Create Assignment"
    )

    schedule_error = (
        OccurrenceService.schedule_error(
            assignment_type,
            recurrence_pattern,
            due_date,
            end_date,
            lesson_count
        )
        if submitted
        else None
    )

    if schedule_error:

        st.error(schedule_error)

    elif submitted:

        created = AssignmentService.create_assignment(
            subject_id=subject.id if subject else None,
            title=title,
            student_ids=[
                student.id
                for student in selected_students
            ],
            description=description,
            due_date=due_date,
            assignment_type=assignment_type,
            recurrence_pattern=recurrence_pattern,
            end_date=end_date,
            lesson_count=lesson_count,
            graded=graded
        )

        if created:

            st.toast(
                "Assignment created successfully."
            )

            st.rerun()

        st.error(
            "This assignment couldn't be created. Check that "
            "you've chosen an active subject and students."
        )

# ==================================================
# CURRENT ASSIGNMENTS
# ==================================================

st.divider()

st.subheader("Current Assignments")

assignments = (
    AssignmentService.get_current_family_assignments()
)

if assignments:

    for assignment in assignments:

        assigned_students = [
            sa.student.name
            for sa in assignment.student_assignments
        ]

        completed_count, total_count = (
            OccurrenceService.assignment_progress(
                assignment,
                AuthService.get_today()
            )
        )

        with st.container():

            col1, col2, col3, col4 = st.columns(
                [6, 1, 1, 1]
            )

            with col1:

                st.markdown(
                    f"### 📋 {assignment.title}"
                )

                subject_color = SubjectService.display_color(
                    assignment.subject.color
                )

                col_subject1, col_subject2 = (
                    st.columns([1, 20])
                )

                with col_subject1:

                    st.markdown(
                        f"""
                        <div style="
                            width:15px;
                            height:15px;
                            border-radius:50%;
                            background:{subject_color};
                            margin-top:8px;
                        "></div>
                        """,
                        unsafe_allow_html=True
                    )

                with col_subject2:

                    st.caption(
                        assignment.subject.name
                    )

                st.caption(
                    "👨‍🎓 "
                    + ", ".join(
                        assigned_students
                    )
                )

                st.caption(
                    f"✅ Progress: "
                    f"{completed_count}/{total_count}"
                )

                if (
                    assignment.assignment_type
                    == AssignmentType.RECURRING.value
                ):

                    st.caption(
                        f"🔁 {assignment.recurrence_pattern}, "
                        f"{assignment.due_date} to {assignment.end_date}"
                    )

                elif (
                    assignment.assignment_type
                    == AssignmentType.CURRICULUM.value
                ):

                    school_days_shown = (
                        assignment.recurrence_pattern.replace(",", ", ")
                    )

                    st.caption(
                        f"📖 {OccurrenceService.lesson_count(assignment)} "
                        f"lessons, {school_days_shown}, "
                        f"{assignment.due_date} to "
                        f"{OccurrenceService.last_lesson_date(assignment)}"
                    )

                else:

                    if assignment.due_date:

                        st.caption(
                            f"📅 Due: {assignment.due_date}"
                        )

                if assignment.graded:

                    st.caption(
                        "📊 Graded"
                    )

                if assignment.description:

                    st.caption(
                        f"📝 {assignment.description}"
                    )

            with col2:

                if st.button(
                    "✏️",
                    key=f"edit_{assignment.id}",
                    help="Edit Assignment"
                ):

                    edit_assignment_dialog(
                        assignment.id
                    )

            with col4:

                if st.button(
                    "📝",
                    key=f"note_{assignment.id}",
                    help="Add a Note for a Date"
                ):

                    note_dialog(
                        assignment.id
                    )

            with col3:

                if st.button(
                    "📦",
                    key=f"archive_{assignment.id}",
                    help="Archive Assignment"
                ):

                    archive_assignment_dialog(
                        assignment
                    )

            st.divider()

else:

    st.info(
        "No assignments have been created."
    )

# ==================================================
# ARCHIVED ASSIGNMENTS
# ==================================================

archived_assignments = AssignmentService.get_archived_assignments()

if archived_assignments:

    with st.expander(
        f"📦 Archived Assignments ({len(archived_assignments)})"
    ):

        st.caption(
            "Restoring an assignment brings back its dates, students, "
            "check-offs, notes and grades. Dates that passed while it was "
            "archived show as overdue or missed, and Missed a Day? on the "
            "dashboard can move curriculum lessons forward."
        )

        for assignment in archived_assignments:

            col1, col2 = st.columns(
                [5, 2]
            )

            with col1:

                subject_name = assignment.subject.name

                if not assignment.subject.active:
                    subject_name += " (archived)"

                st.write(
                    f"**{assignment.title}**"
                )

                st.caption(
                    f"{subject_name} · {assignment.assignment_type}"
                )

            with col2:

                if st.button(
                    "Restore",
                    key=f"restore_assignment_{assignment.id}",
                    use_container_width=True
                ):

                    if AssignmentService.restore_assignment(
                        assignment.id
                    ):

                        st.toast(
                            f"{assignment.title} restored."
                        )

                        st.rerun()

                    st.error(
                        "This assignment couldn't be restored. "
                        "Please refresh the page and try again."
                    )
