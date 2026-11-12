"""
CurrentUser.acting_as: how an API request will say who's signed in, with no
Streamlit session involved.
"""
import threading
from types import SimpleNamespace
from unittest import mock

import pytest

from database.db import SessionLocal
from database.models import DEFAULT_TIMEZONE, User, UserRole
from services.current_user import CurrentUser
from services.student_mode_service import StudentModeService
from services.student_service import StudentService

PIN = "2468"


def _parent(family_id, email="parent@x.test"):
    """Saves a parent row and returns a stand-in for it, as a request would."""
    db = SessionLocal()
    try:
        row = User(
            family_id=family_id,
            email=email,
            auth_user_id=f"00000000-0000-0000-0000-{family_id:012d}",
            role=UserRole.PARENT.value,
        )
        db.add(row)
        db.commit()
        user_id = row.id
    finally:
        db.close()

    return SimpleNamespace(
        id=user_id,
        family_id=family_id,
        family=SimpleNamespace(timezone=DEFAULT_TIMEZONE),
        role=UserRole.PARENT.value,
        student_id=None,
    )


def _student(family_id, student_id):
    return SimpleNamespace(
        id=None,
        family_id=family_id,
        family=SimpleNamespace(timezone=DEFAULT_TIMEZONE),
        role=UserRole.STUDENT.value,
        student_id=student_id,
    )


@pytest.fixture
def no_fallback():
    """Runs as an API would: no Streamlit AuthService to fall back on."""
    with mock.patch.object(CurrentUser, "_fallback", None):
        yield


def test_with_no_request_user_everything_fails_closed(world, no_fallback):
    assert CurrentUser.get() is None
    assert not CurrentUser.is_parent()
    assert not CurrentUser.is_student()
    assert CurrentUser.get_family_id() is None
    assert StudentService.get_current_family_students() == []


def test_acting_as_a_parent_scopes_services_to_their_family(world, no_fallback):
    parent = _parent(world.smith)

    with CurrentUser.acting_as(parent, "session-a"):
        assert CurrentUser.is_parent()
        assert CurrentUser.get_family_id() == world.smith
        names = {s.name for s in StudentService.get_current_family_students()}

    assert names == {"Ann", "Bob", "Cat"}


def test_one_family_cant_read_anothers_data(world, no_fallback):
    jones_parent = _parent(world.jones, "jones@x.test")

    with CurrentUser.acting_as(jones_parent):
        assert StudentService.get_student_by_id(world.ann) is None
        names = {s.name for s in StudentService.get_current_family_students()}

    assert names == {"Jones kid"}
    assert CurrentUser.get() is None


def test_acting_as_a_student(world, no_fallback):
    with CurrentUser.acting_as(_student(world.smith, world.bob)):
        assert CurrentUser.is_student()
        assert not CurrentUser.is_parent()
        assert CurrentUser.get_student_id() == world.bob


def test_the_user_is_forgotten_after_the_block_even_after_an_error(
    world, no_fallback
):
    with pytest.raises(RuntimeError):
        with CurrentUser.acting_as(_parent(world.smith)):
            raise RuntimeError("request failed")

    assert CurrentUser.get() is None


def test_another_thread_doesnt_see_this_requests_user(world, no_fallback):
    seen = []

    with CurrentUser.acting_as(_parent(world.smith)):
        thread = threading.Thread(target=lambda: seen.append(CurrentUser.get()))
        thread.start()
        thread.join()

    assert seen == [None]


def test_student_mode_follows_the_login_session(world, no_fallback):
    parent = _parent(world.smith)

    with CurrentUser.acting_as(parent, "session-a"):
        assert StudentModeService.set_pin(PIN, PIN)[0]
        assert StudentModeService.start(world.ann)[0]

        assert CurrentUser.is_student()
        assert not CurrentUser.is_parent()
        assert CurrentUser.get_student_id() == world.ann

    # The same parent on another login session isn't in Student Mode.
    with CurrentUser.acting_as(parent, "session-b"):
        assert CurrentUser.is_parent()

    with CurrentUser.acting_as(parent, "session-a"):
        assert CurrentUser.is_student()
        assert StudentModeService.exit(PIN)[0]
        assert CurrentUser.is_parent()
