# services/reading_service.py
from datetime import timedelta

from sqlalchemy.orm import selectinload

from database.db import get_session
from database.models import (
    Book,
    ReadingLog,
    Student,
)
from services.current_user import CurrentUser

# Enough for any real day, so a typo can't wreck a student's totals.
MAX_PAGES_PER_DAY = 5000

MAX_BOOK_PAGES = 50000

FINISHED_BADGES = [
    (1, "📕", "First Book", "Finish your first book"),
    (5, "📚", "Bookworm", "Finish 5 books"),
]

PAGE_BADGES = [
    (1000, "📖", "1,000 Pages", "Read 1,000 pages"),
]

READING_STREAK_BADGES = [
    (7, "🔖", "Week of Reading", "Read 7 days in a row"),
    (30, "🏆", "Month of Reading", "Read 30 days in a row"),
]


class ReadingService:
    """
    Each student has their own books. Streaks, totals and badges are worked
    out from the logs when read, never stored.
    """

    @staticmethod
    def _can_use_student(
        db,
        student_id
    ):
        """
        True if the current user can see and change this student's books: a
        student their own, and a parent any active student in their family.
        """

        if CurrentUser.is_student():

            return student_id == CurrentUser.get_student_id()

        if not CurrentUser.is_parent():
            return False

        return (
            db.query(Student.id)
            .filter(
                Student.id == student_id,
                Student.family_id == CurrentUser.get_family_id(),
                Student.active.is_(True)
            )
            .first()
            is not None
        )

    @staticmethod
    def _find_book(
        db,
        book_id
    ):
        """
        Returns an active book the current user can change, or None.
        """

        book = (
            db.query(Book)
            .filter(
                Book.id == book_id,
                Book.family_id == CurrentUser.get_family_id(),
                Book.active.is_(True)
            )
            .first()
        )

        if (
            not book
            or not ReadingService._can_use_student(db, book.student_id)
        ):
            return None

        return book

    @staticmethod
    def _valid_details(
        title,
        total_pages
    ):

        return (
            bool((title or "").strip())
            and (
                total_pages is None
                or 1 <= total_pages <= MAX_BOOK_PAGES
            )
        )

    @staticmethod
    def add_book(
        student_id,
        title,
        author=None,
        total_pages=None
    ):
        """
        Returns the new book, or None if its details aren't valid or this
        student isn't available to the current user.
        """

        if not ReadingService._valid_details(title, total_pages):
            return None

        with get_session() as db:

            if not ReadingService._can_use_student(db, student_id):
                return None

            book = Book(
                family_id=CurrentUser.get_family_id(),
                student_id=student_id,
                title=title.strip(),
                author=(author or "").strip() or None,
                total_pages=total_pages
            )

            db.add(book)
            db.commit()
            db.refresh(book)

            return book

    @staticmethod
    def update_book(
        book_id,
        title,
        author=None,
        total_pages=None
    ):
        """
        Returns the updated book, or None if it can't be saved.
        """

        if not ReadingService._valid_details(title, total_pages):
            return None

        with get_session() as db:

            book = ReadingService._find_book(db, book_id)

            if not book:
                return None

            book.title = title.strip()
            book.author = (author or "").strip() or None
            book.total_pages = total_pages

            db.commit()
            db.refresh(book)

            return book

    @staticmethod
    def archive_book(book_id):
        """
        Hides a book added by mistake, and takes its pages out of the totals.
        Returns it, or None if it isn't available.
        """

        with get_session() as db:

            book = ReadingService._find_book(db, book_id)

            if not book:
                return None

            book.active = False

            db.commit()

            return book

    @staticmethod
    def set_finished(
        book_id,
        finished
    ):
        """
        Marks a book finished today, or back to still reading. Returns it, or
        None if it isn't available.
        """

        with get_session() as db:

            book = ReadingService._find_book(db, book_id)

            if not book:
                return None

            book.finished_on = (
                CurrentUser.get_today()
                if finished
                else None
            )

            db.commit()
            db.refresh(book)

            return book

    @staticmethod
    def log_pages(
        book_id,
        log_date,
        pages
    ):
        """
        Saves how many pages were read on one date, replacing what was there.
        Zero removes that date. Returns True, or False if it can't be saved:
        a future date, a number out of range, or a book that's finished or
        isn't available.
        """

        if (
            log_date > CurrentUser.get_today()
            or pages < 0
            or pages > MAX_PAGES_PER_DAY
        ):
            return False

        with get_session() as db:

            book = ReadingService._find_book(db, book_id)

            if not book or book.finished_on:
                return False

            log = (
                db.query(ReadingLog)
                .filter(
                    ReadingLog.book_id == book_id,
                    ReadingLog.log_date == log_date
                )
                .first()
            )

            if pages == 0:

                if log:
                    db.delete(log)

            elif log:

                log.pages = pages

            else:

                db.add(
                    ReadingLog(
                        book_id=book_id,
                        log_date=log_date,
                        pages=pages
                    )
                )

            db.commit()

            return True

    @staticmethod
    def get_books(student_id):
        """
        Returns a student's active books with their logs, by title. Nothing
        if they aren't available to the current user.
        """

        with get_session() as db:

            if not ReadingService._can_use_student(db, student_id):
                return []

            return (
                db.query(Book)
                .options(
                    selectinload(Book.logs)
                )
                .filter(
                    Book.student_id == student_id,
                    Book.family_id == CurrentUser.get_family_id(),
                    Book.active.is_(True)
                )
                .order_by(Book.title)
                .all()
            )

    @staticmethod
    def pages_read(book):
        """
        Returns a book's total pages read. Needs its logs loaded.
        """

        return sum(log.pages for log in book.logs)

    @staticmethod
    def pages_on(
        book,
        day
    ):
        """
        Returns the pages logged for a book on one date. Needs its logs
        loaded.
        """

        return next(
            (log.pages for log in book.logs if log.log_date == day),
            0
        )

    @staticmethod
    def streaks(
        days_read,
        today
    ):
        """
        Returns (current, best) from the dates anything was read. Every
        calendar day counts, weekends included. Today can only add to a
        streak, since there's still time to read.
        """

        best = 0
        run = 0
        previous = None

        for day in sorted(days_read):

            if day > today:
                continue

            run = (
                run + 1
                if previous == day - timedelta(days=1)
                else 1
            )

            best = max(best, run)

            previous = day

        if previous is None or previous < today - timedelta(days=1):
            return 0, best

        return run, best

    @staticmethod
    def summary(
        books,
        today
    ):
        """
        Returns a student's reading {"streak", "best_streak",
        "pages_this_week", "total_pages", "books_finished", "badges"}. Books
        need their logs loaded. Weeks start on Sunday, like the calendar.
        """

        logs = [
            log
            for book in books
            for log in book.logs
        ]

        current, best = ReadingService.streaks(
            {log.log_date for log in logs},
            today
        )

        week_start = today - timedelta(days=(today.weekday() + 1) % 7)

        total = sum(log.pages for log in logs)

        finished = sum(1 for book in books if book.finished_on)

        badges = [
            (f"reading_books_{goal}", icon, name, text, finished >= goal)
            for goal, icon, name, text in FINISHED_BADGES
        ]

        badges += [
            (f"reading_pages_{goal}", icon, name, text, total >= goal)
            for goal, icon, name, text in PAGE_BADGES
        ]

        badges += [
            (f"reading_streak_{goal}", icon, name, text, best >= goal)
            for goal, icon, name, text in READING_STREAK_BADGES
        ]

        return {
            "streak": current,
            "best_streak": best,
            "pages_this_week": sum(
                log.pages
                for log in logs
                if week_start <= log.log_date <= today
            ),
            "total_pages": total,
            "books_finished": finished,
            "badges": [
                {
                    "key": key,
                    "icon": icon,
                    "name": name,
                    "description": description,
                    "earned": earned,
                }
                for key, icon, name, description, earned in badges
            ],
        }
