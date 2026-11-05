import streamlit as st

from components.navigation import (
    NavigationComponent
)
from services.achievement_service import AchievementService
from services.auth_service import AuthService
from services.navigation_service import NavigationService
from services.reading_service import (
    MAX_BOOK_PAGES,
    MAX_PAGES_PER_DAY,
    ReadingService
)
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
    "This book couldn't be saved. "
    "Please refresh the page and try again."
)

st.title("📖 Reading")

# ==================================================
# WHOSE BOOKS
# ==================================================

if AuthService.is_student():

    student_id = AuthService.get_current_student()

else:

    students = StudentService.get_current_family_students()

    if not students:

        st.warning(
            "No students found."
        )

        st.stop()

    student_id = st.selectbox(
        "Select Student",
        [student.id for student in students],
        format_func={
            student.id: student.name
            for student in students
        }.get,
        key="reading_student"
    )

today = AuthService.get_today()

books = ReadingService.get_books(student_id)

summary = ReadingService.summary(books, today)


def announce_new_badges():
    """
    Call after a change, before rerunning, to show any badge it just earned.
    """

    after = ReadingService.summary(
        ReadingService.get_books(student_id),
        today
    )

    for badge in AchievementService.newly_earned(summary, after):

        st.toast(
            f"New badge: {badge['name']}!",
            icon=badge["icon"]
        )


# ==================================================
# DIALOGS
# ==================================================

@st.dialog("✏️ Edit Book")
def edit_book_dialog(book):

    title = st.text_input(
        "Title",
        value=book.title
    )

    author = st.text_input(
        "Author",
        value=book.author or ""
    )

    total_pages = st.number_input(
        "Number of Pages",
        min_value=1,
        max_value=MAX_BOOK_PAGES,
        step=1,
        value=book.total_pages
    )

    if st.button("💾 Save Changes"):

        if not title.strip():

            st.error("Please enter a title.")

            return

        if not ReadingService.update_book(
            book.id,
            title,
            author,
            total_pages
        ):

            st.error(SAVE_ERROR)

            return

        st.toast("Book updated.")

        st.rerun()


@st.dialog("📦 Archive Book")
def archive_book_dialog(book):

    st.warning(
        f"Archive '{book.title}'?"
    )

    st.write(
        "This is for a book added by mistake. Its pages come out of the "
        "totals and streak. If it's been read, use Finished instead."
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

            if not ReadingService.archive_book(book.id):

                st.error(SAVE_ERROR)

                return

            st.toast("Book archived.")

            st.rerun()


# ==================================================
# TOTALS
# ==================================================

col1, col2, col3, col4 = st.columns(4)

with col1:

    streak = summary["streak"]

    st.metric(
        "🔥 Reading Streak",
        f"{streak} day" if streak == 1 else f"{streak} days"
    )

with col2:

    st.metric(
        "🏅 Best Streak",
        summary["best_streak"]
    )

with col3:

    st.metric(
        "📄 Pages This Week",
        summary["pages_this_week"]
    )

with col4:

    st.metric(
        "📚 Books Finished",
        summary["books_finished"]
    )

st.caption(
    "Read something every day to keep your streak alive, weekends included. "
    "Forgot a day? Pick that date below and log it."
)

st.divider()

# ==================================================
# BOOKS IN PROGRESS
# ==================================================

st.subheader("My Books")

reading_now = [
    book
    for book in books
    if not book.finished_on
]

finished_books = sorted(
    (
        book
        for book in books
        if book.finished_on
    ),
    key=lambda book: book.finished_on,
    reverse=True
)

log_date = st.date_input(
    "Reading Day",
    value=today,
    max_value=today,
    key="reading_day"
)

if not reading_now:

    st.info(
        "No books in progress. Add one below."
    )

for book in reading_now:

    with st.container():

        st.markdown(f"### 📘 {book.title}")

        if book.author:

            st.caption(f"by {book.author}")

        pages_read = ReadingService.pages_read(book)

        if book.total_pages:

            st.progress(
                min(pages_read / book.total_pages, 1.0),
                text=f"{pages_read} of {book.total_pages} pages"
            )

        else:

            st.caption(f"{pages_read} pages read")

        col1, col2 = st.columns([3, 1])

        with col1:

            pages = st.number_input(
                "Pages read today"
                if log_date == today
                else f"Pages read on {log_date:%b} {log_date.day}",
                min_value=0,
                max_value=MAX_PAGES_PER_DAY,
                step=1,
                value=ReadingService.pages_on(book, log_date),
                key=f"pages_{book.id}_{log_date}"
            )

        with col2:

            if st.button(
                "💾 Save Pages",
                key=f"save_{book.id}",
                use_container_width=True
            ):

                if ReadingService.log_pages(
                    book.id,
                    log_date,
                    pages
                ):

                    announce_new_badges()

                    st.toast("Pages saved.")

                    st.rerun()

                st.error(SAVE_ERROR)

        col1, col2, col3 = st.columns(3)

        with col1:

            if st.button(
                "✅ Finished",
                key=f"finish_{book.id}",
                use_container_width=True
            ):

                if ReadingService.set_finished(book.id, True):

                    announce_new_badges()

                    st.toast(f"You finished {book.title}!")

                    st.rerun()

                st.error(SAVE_ERROR)

        with col2:

            if st.button(
                "✏️ Edit",
                key=f"edit_{book.id}",
                use_container_width=True
            ):

                edit_book_dialog(book)

        with col3:

            if st.button(
                "📦 Archive",
                key=f"archive_{book.id}",
                use_container_width=True
            ):

                archive_book_dialog(book)

        st.divider()

# ==================================================
# ADD BOOK
# ==================================================

st.subheader("➕ Add a Book")

with st.form(
    "add_book_form",
    clear_on_submit=True
):

    new_title = st.text_input("Title")

    new_author = st.text_input("Author (optional)")

    new_total_pages = st.number_input(
        "Number of Pages (optional)",
        min_value=1,
        max_value=MAX_BOOK_PAGES,
        step=1,
        value=None
    )

    if st.form_submit_button("Add Book"):

        if not new_title.strip():

            st.error("Please enter a title.")

        elif ReadingService.add_book(
            student_id,
            new_title,
            new_author,
            new_total_pages
        ):

            st.toast("Book added.")

            st.rerun()

        else:

            st.error(SAVE_ERROR)

# ==================================================
# FINISHED BOOKS
# ==================================================

if finished_books:

    with st.expander(
        f"🎉 Finished Books ({len(finished_books)})"
    ):

        for book in finished_books:

            col1, col2 = st.columns([4, 1])

            with col1:

                by_author = (
                    f" by {book.author}"
                    if book.author
                    else ""
                )

                st.write(f"**{book.title}**{by_author}")

                st.caption(
                    f"Finished {book.finished_on}. "
                    f"{ReadingService.pages_read(book)} pages logged."
                )

            with col2:

                if st.button(
                    "↩️ Reopen",
                    key=f"reopen_{book.id}",
                    help="Put this book back in progress",
                    use_container_width=True
                ):

                    if ReadingService.set_finished(book.id, False):

                        st.rerun()

                    st.error(SAVE_ERROR)
