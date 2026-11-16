"""Deleting a family's account: all its data and logins, and nobody else's."""
from datetime import date, datetime, timedelta
from unittest import mock

import pytest

from api_support import as_
from database.db import SessionLocal
from database.models import (
    ActivityLog,
    Assignment,
    AssignmentOccurrence,
    BannerMessage,
    Book,
    DeviceSession,
    Event,
    EventStudent,
    Family,
    Feedback,
    GradingPeriod,
    PairingCode,
    ReadingLog,
    Student,
    StudentAssignment,
    Subject,
    User,
    UserRole,
)
from services.account_service import AccountService
from services.auth_provider import AuthProvider

SMITH = as_("smith_parent")
JONES = as_("jones_parent")
BOB = as_("bob")

DAY = date(2026, 11, 4)

EVERY_TABLE = [
    ActivityLog,
    Assignment,
    AssignmentOccurrence,
    Book,
    DeviceSession,
    Event,
    EventStudent,
    Feedback,
    GradingPeriod,
    PairingCode,
    ReadingLog,
    Student,
    StudentAssignment,
    Subject,
    User,
]


def _fill(family_id, student_id, user_id):
    """One row in every family table, for one family."""
    db = SessionLocal()
    try:
        event = Event(family_id=family_id, title="Field trip", start_date=DAY)
        book = Book(family_id=family_id, student_id=student_id, title="Charlotte's Web")
        db.add_all([event, book])
        db.flush()
        db.add_all(
            [
                EventStudent(event_id=event.id, student_id=student_id),
                ReadingLog(book_id=book.id, log_date=DAY, pages=10),
                GradingPeriod(
                    family_id=family_id, name="Fall", start_date=DAY, end_date=DAY
                ),
                ActivityLog(
                    family_id=family_id,
                    student_id=student_id,
                    log_date=DAY,
                    activity="Soccer",
                    minutes=30,
                ),
                DeviceSession(
                    family_id=family_id,
                    student_id=student_id,
                    mode="paired",
                    created_by=user_id,
                    token_hash=f"hash-{family_id}",
                ),
                PairingCode(
                    family_id=family_id,
                    student_id=student_id,
                    code_hash=f"code-{family_id}",
                    created_by=user_id,
                    expires_at=datetime(2030, 1, 1),
                ),
                Feedback(family_id=family_id, user_id=user_id, message="Love it"),
                BannerMessage(
                    family_id=family_id,
                    title="Family news",
                    message="Hi",
                    start_date=DAY,
                    end_date=DAY + timedelta(days=7),
                ),
            ]
        )
        db.commit()
    finally:
        db.close()


def _system_banner():
    db = SessionLocal()
    try:
        db.add(
            BannerMessage(
                family_id=None,
                title="For everyone",
                message="Hi",
                start_date=DAY,
                end_date=DAY + timedelta(days=7),
            )
        )
        db.commit()
    finally:
        db.close()


def _user_id(auth_id_suffix):
    db = SessionLocal()
    try:
        return (
            db.query(User.id)
            .filter(User.auth_user_id == f"00000000-0000-0000-0000-0000000000{auth_id_suffix}")
            .scalar()
        )
    finally:
        db.close()


def _counts(family_id):
    """How many rows each table has that belong to the family."""
    db = SessionLocal()
    try:
        students = [s for (s,) in db.query(Student.id).filter(Student.family_id == family_id)]
        assignments = [
            a for (a,) in db.query(Assignment.id).filter(Assignment.family_id == family_id)
        ]
        events = [e for (e,) in db.query(Event.id).filter(Event.family_id == family_id)]
        books = [b for (b,) in db.query(Book.id).filter(Book.family_id == family_id)]

        counts = {}
        for model in EVERY_TABLE:
            query = db.query(model)
            if model is EventStudent:
                query = query.filter(EventStudent.event_id.in_(events or [-1]))
            elif model is ReadingLog:
                query = query.filter(ReadingLog.book_id.in_(books or [-1]))
            elif model in (AssignmentOccurrence, StudentAssignment):
                query = query.filter(
                    model.assignment_id.in_(assignments or [-1])
                    | model.student_id.in_(students or [-1])
                )
            else:
                query = query.filter(model.family_id == family_id)
            counts[model.__tablename__] = query.count()

        counts["family_banners"] = (
            db.query(BannerMessage).filter(BannerMessage.family_id == family_id).count()
        )
        counts["family"] = db.query(Family).filter(Family.id == family_id).count()
        counts["system_banners"] = (
            db.query(BannerMessage).filter(BannerMessage.family_id.is_(None)).count()
        )
        return counts
    finally:
        db.close()


@pytest.fixture
def filled(api, world):
    _fill(world.smith, world.ann, _user_id("a1"))
    _fill(world.jones, world.jones_kid, _user_id("a2"))
    _system_banner()
    return world


def test_deleting_removes_every_row_of_the_family(api, filled):
    w = filled
    jones_before = _counts(w.jones)

    # Every table has something of the Smiths' to delete.
    assert all(n > 0 for n in _counts(w.smith).values())

    with mock.patch.object(AuthProvider, "delete_auth_user") as delete_auth:
        response = api.post("/account/delete", json={"confirm": "delete"}, headers=SMITH)

    assert response.status_code == 200

    smith = _counts(w.smith)
    assert {name: n for name, n in smith.items() if name != "system_banners"} == {
        name: 0 for name in smith if name != "system_banners"
    }

    # The Smiths' two logins (parent and Bob) go from Supabase too.
    deleted = {call.args[0] for call in delete_auth.call_args_list}
    assert deleted == {
        "00000000-0000-0000-0000-0000000000a1",
        "00000000-0000-0000-0000-0000000000a3",
    }

    # Nobody else's data, and system-wide announcements stay.
    assert _counts(w.jones) == jones_before
    assert smith["system_banners"] == 1


def test_a_deleted_family_can_no_longer_sign_in(api, filled):
    with mock.patch.object(AuthProvider, "delete_auth_user"):
        api.post("/account/delete", json={"confirm": "DELETE"}, headers=SMITH)

    assert api.get("/me", headers=SMITH).status_code in (401, 403)
    assert api.get("/me", headers=JONES).status_code == 200


def test_deleting_needs_the_word_delete(api, filled):
    with mock.patch.object(AuthProvider, "delete_auth_user") as delete_auth:
        response = api.post("/account/delete", json={"confirm": "yes"}, headers=SMITH)

    assert response.status_code == 400
    assert _counts(filled.smith)["family"] == 1
    delete_auth.assert_not_called()


def test_students_cant_delete_the_account(api, filled):
    with mock.patch.object(AuthProvider, "delete_auth_user") as delete_auth:
        response = api.post("/account/delete", json={"confirm": "DELETE"}, headers=BOB)

    assert response.status_code == 403
    assert _counts(filled.smith)["family"] == 1
    delete_auth.assert_not_called()


def test_a_supabase_failure_still_deletes_the_data(api, filled, caplog):
    with mock.patch.object(
        AuthProvider, "delete_auth_user", side_effect=RuntimeError("Supabase is down")
    ):
        response = api.post("/account/delete", json={"confirm": "DELETE"}, headers=SMITH)

    assert response.status_code == 200
    assert _counts(filled.smith)["family"] == 0
    assert "to remove by hand in Supabase" in caplog.text


def test_the_service_refuses_anyone_but_a_parent(world, login):
    login(world.smith, UserRole.STUDENT, world.bob)

    assert AccountService.delete_family() is False
    assert _counts(world.smith)["family"] == 1
