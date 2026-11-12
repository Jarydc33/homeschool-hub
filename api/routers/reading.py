from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.auth import signed_in
from api.errors import could_not_save, invalid, not_found
from api.schemas import Message, Name, ReadingSummary, Title
from services.current_user import CurrentUser
from services.reading_service import ReadingService

# Students track their own reading; parents any of their students'.
router = APIRouter(tags=["reading"], dependencies=[Depends(signed_in)])

NOT_FOUND_MESSAGE = "This book could not be found."

BOOK_DETAILS_MESSAGE = "Please check the book's title and page count."

PAGES_MESSAGE = (
    "Those pages couldn't be saved. Pages can't be logged for a future date "
    "or a finished book."
)


class ReadingLogOut(BaseModel):
    date: date
    pages: int


class BookOut(BaseModel):
    id: int
    student_id: int
    title: str
    author: str | None
    total_pages: int | None
    finished_on: date | None
    pages_read: int
    pages_today: int
    logs: list[ReadingLogOut]


class Bookshelf(BaseModel):
    books: list[BookOut]
    summary: ReadingSummary


class BookIn(BaseModel):
    title: Title
    author: Name | None = None
    total_pages: int | None = Field(default=None, ge=1, le=10000)


class FinishedIn(BaseModel):
    finished: bool


class PagesIn(BaseModel):
    # Zero removes that date.
    pages: int = Field(ge=0, le=2000)


def _book_out(book, today):
    """Needs the book's logs loaded."""

    return BookOut(
        id=book.id,
        student_id=book.student_id,
        title=book.title,
        author=book.author,
        total_pages=book.total_pages,
        finished_on=book.finished_on,
        pages_read=ReadingService.pages_read(book),
        pages_today=ReadingService.pages_on(book, today),
        logs=sorted(
            (ReadingLogOut(date=log.log_date, pages=log.pages) for log in book.logs),
            key=lambda log: log.date,
            reverse=True,
        ),
    )


def _reload(book):
    """Reads a book back with its logs, from its student's shelf."""

    for fresh in ReadingService.get_books(book.student_id):
        if fresh.id == book.id:
            return _book_out(fresh, CurrentUser.get_today())

    raise not_found(NOT_FOUND_MESSAGE)


@router.get("/students/{student_id}/books", response_model=Bookshelf)
def bookshelf(student_id: int):
    """A student's books, by title, with their reading streak and badges."""

    today = CurrentUser.get_today()

    books = ReadingService.get_books(student_id)

    return Bookshelf(
        books=[_book_out(book, today) for book in books],
        summary=ReadingSummary(**ReadingService.summary(books, today)),
    )


@router.post("/students/{student_id}/books", response_model=BookOut, status_code=201)
def add_book(student_id: int, body: BookIn):

    book = ReadingService.add_book(
        student_id,
        body.title,
        body.author or None,
        body.total_pages,
    )

    if not book:
        raise could_not_save(BOOK_DETAILS_MESSAGE)

    return _reload(book)


@router.put("/books/{book_id}", response_model=BookOut)
def update_book(book_id: int, body: BookIn):

    book = ReadingService.update_book(
        book_id,
        body.title,
        body.author or None,
        body.total_pages,
    )

    if not book:
        raise could_not_save(BOOK_DETAILS_MESSAGE)

    return _reload(book)


@router.post("/books/{book_id}/archive", response_model=Message)
def archive_book(book_id: int):
    """Hides a book added by mistake, and takes its pages out of the totals."""

    if not ReadingService.archive_book(book_id):
        raise not_found(NOT_FOUND_MESSAGE)

    return Message(message="Book removed.")


@router.put("/books/{book_id}/finished", response_model=BookOut)
def set_finished(book_id: int, body: FinishedIn):

    book = ReadingService.set_finished(book_id, body.finished)

    if not book:
        raise not_found(NOT_FOUND_MESSAGE)

    return _reload(book)


@router.put("/books/{book_id}/pages/{log_date}", response_model=Message)
def log_pages(book_id: int, log_date: date, body: PagesIn):
    """Sets the pages read on one date, replacing what was there."""

    if not ReadingService.log_pages(book_id, log_date, body.pages):
        raise invalid(PAGES_MESSAGE)

    return Message(message="Pages saved." if body.pages else "Pages removed.")
