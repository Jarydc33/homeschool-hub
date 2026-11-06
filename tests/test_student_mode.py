"""Student Mode: a parent's login switched to one student until the PIN."""
import base64
import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from zoneinfo import ZoneInfo

import bcrypt
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from database.db import SessionLocal
from database.models import (
    DEFAULT_TIMEZONE,
    DeviceSession,
    Family,
    User,
    UserRole,
)
from services.auth_provider import AuthProvider
from services.auth_service import AuthService
from services.session_service import SessionService
from services.student_mode_service import (
    LOCKED_MESSAGE,
    MAX_PIN_ATTEMPTS,
    StudentModeService,
    WRONG_PIN_MESSAGE,
)

ROOT = Path(__file__).resolve().parent.parent

PIN = "2468"


def _parent_row(family_id, email):
    db = SessionLocal()
    try:
        user = User(
            family_id=family_id,
            email=email,
            auth_user_id=f"00000000-0000-0000-0000-{family_id:012d}",
            role=UserRole.PARENT.value,
        )
        db.add(user)
        db.commit()
        return user.id
    finally:
        db.close()


@pytest.fixture
def as_parent(world):
    """
    Returns a function that signs in as a family's parent on a login
    session, without Supabase. Switch families or sessions by calling again.
    """
    user_ids = {}
    patches = []

    def _as(family_id, session_id="session-a"):
        for patcher in reversed(patches):
            patcher.stop()
        patches.clear()

        if family_id not in user_ids:
            user_ids[family_id] = _parent_row(family_id, f"p{family_id}@x.test")

        user = SimpleNamespace(
            id=user_ids[family_id],
            family_id=family_id,
            family=SimpleNamespace(timezone=DEFAULT_TIMEZONE),
            role=UserRole.PARENT.value,
            student_id=None,
        )
        patches.extend(
            [
                mock.patch.object(AuthService, "get_current_user", return_value=user),
                mock.patch.object(
                    AuthService, "get_auth_session_id", return_value=session_id
                ),
            ]
        )
        for patcher in patches:
            patcher.start()
        AuthService.forget_student_mode()
        return world

    yield _as

    for patcher in reversed(patches):
        patcher.stop()
    AuthService.forget_student_mode()


@pytest.fixture
def smith(as_parent, world):
    as_parent(world.smith)
    StudentModeService.set_pin(PIN, PIN)
    return world


def _rows():
    db = SessionLocal()
    try:
        return db.query(DeviceSession).order_by(DeviceSession.id).all()
    finally:
        db.close()


def _family(family_id):
    db = SessionLocal()
    try:
        return db.get(Family, family_id)
    finally:
        db.close()


# ----- PIN -----


@pytest.mark.parametrize("pin", ["", "123", "12345", "12a4", " 1234"])
def test_a_pin_must_be_exactly_four_digits(pin):
    assert StudentModeService.pin_error(pin)


def test_a_four_digit_pin_is_fine():
    assert StudentModeService.pin_error("0123") is None


def test_the_pin_is_stored_hashed(smith):
    saved = _family(smith.smith).parent_pin_hash

    assert saved != PIN
    assert bcrypt.checkpw(PIN.encode(), saved.encode())
    assert StudentModeService.has_pin()


def test_mismatched_pins_arent_saved(as_parent, world):
    as_parent(world.smith)

    saved, message = StudentModeService.set_pin("1111", "2222")

    assert not saved
    assert "match" in message
    assert _family(world.smith).parent_pin_hash is None


def test_one_familys_pin_doesnt_affect_another(smith, as_parent):
    as_parent(smith.jones)

    assert not StudentModeService.has_pin()


# ----- Starting -----


def test_student_mode_needs_a_pin_first(as_parent, world):
    as_parent(world.smith)

    started, message = StudentModeService.start(world.bob)

    assert not started
    assert "PIN" in message
    assert _rows() == []


def test_starting_makes_this_login_the_student(smith):
    started, _ = StudentModeService.start(smith.bob)

    assert started
    assert AuthService.is_student()
    assert not AuthService.is_parent()
    assert AuthService.get_current_student() == smith.bob
    assert AuthService.get_current_family() == smith.smith


def test_parent_only_actions_are_refused_in_student_mode(smith):
    StudentModeService.start(smith.bob)

    assert StudentModeService.set_pin("1357", "1357") == (
        False,
        mock.ANY,
    )
    assert StudentModeService.list_sessions() == []
    assert not StudentModeService.end_session(_rows()[0].id)
    assert not StudentModeService.start(smith.ann)[0]


def test_another_login_session_isnt_in_student_mode(smith, as_parent):
    StudentModeService.start(smith.bob)

    as_parent(smith.smith, session_id="session-b")

    assert AuthService.is_parent()
    assert not AuthService.is_student()


def test_cant_start_for_another_familys_student(smith):
    started, _ = StudentModeService.start(smith.jones_kid)

    assert not started
    assert _rows() == []


def test_cant_start_for_an_archived_student(smith):
    assert not StudentModeService.start(smith.gone)[0]


def test_starting_needs_the_login_session(smith):
    with mock.patch.object(AuthService, "get_auth_session_id", return_value=None):
        started, _ = StudentModeService.start(smith.bob)

    assert not started
    assert _rows() == []


# ----- Exiting -----


def test_the_right_pin_ends_student_mode(smith):
    StudentModeService.start(smith.bob)

    exited, _ = StudentModeService.exit(PIN)

    assert exited
    assert AuthService.is_parent()
    assert _rows()[0].revoked_at is not None


def test_a_wrong_pin_keeps_student_mode(smith):
    StudentModeService.start(smith.bob)

    assert StudentModeService.exit("0000") == (False, WRONG_PIN_MESSAGE)
    assert AuthService.is_student()
    assert _rows()[0].failed_pin_attempts == 1


def test_too_many_wrong_pins_lock_it_for_a_while(smith):
    StudentModeService.start(smith.bob)
    now = datetime.utcnow()

    for _ in range(MAX_PIN_ATTEMPTS - 1):
        assert StudentModeService.exit("0000", now)[1] == WRONG_PIN_MESSAGE

    assert StudentModeService.exit("0000", now) == (False, LOCKED_MESSAGE)
    # Even the right PIN waits until the lock ends.
    assert StudentModeService.exit(PIN, now + timedelta(minutes=1)) == (
        False,
        LOCKED_MESSAGE,
    )
    assert AuthService.is_student()

    assert StudentModeService.exit(PIN, now + timedelta(minutes=6))[0]


def test_logging_out_ends_student_mode_without_the_pin(smith):
    StudentModeService.start(smith.bob)

    StudentModeService.end_current_for_logout()

    assert _rows()[0].revoked_at is not None
    assert not AuthService.is_student()


def test_a_new_pin_works_for_devices_already_in_student_mode(smith, as_parent):
    StudentModeService.start(smith.bob)

    as_parent(smith.smith, session_id="session-b")
    StudentModeService.set_pin("1357", "1357")
    as_parent(smith.smith, session_id="session-a")

    assert not StudentModeService.exit(PIN)[0]
    assert StudentModeService.exit("1357")[0]


# ----- Devices -----


def test_parents_see_and_end_devices_from_another_login(smith, as_parent):
    StudentModeService.start(smith.bob)

    as_parent(smith.smith, session_id="session-b")
    devices = StudentModeService.list_sessions()

    assert [device.student.name for device in devices] == ["Bob"]
    assert StudentModeService.end_session(devices[0].id)
    assert StudentModeService.list_sessions() == []

    as_parent(smith.smith, session_id="session-a")
    assert AuthService.is_parent()


def test_another_family_cant_see_or_end_our_devices(smith, as_parent):
    StudentModeService.start(smith.bob)
    device_id = _rows()[0].id

    as_parent(smith.jones, session_id="session-a")

    assert StudentModeService.list_sessions() == []
    assert not StudentModeService.end_session(device_id)
    # Even with the same session id, it's not their Student Mode.
    assert AuthService.is_parent()
    assert _rows()[0].revoked_at is None


def test_last_seen_updates_only_when_stale(smith):
    StudentModeService.start(smith.bob)
    row = _rows()[0]

    soon = row.last_seen_at + timedelta(minutes=1)
    later = row.last_seen_at + timedelta(minutes=10)

    StudentModeService.find_active(smith.smith, "session-a", soon)
    assert _rows()[0].last_seen_at == row.last_seen_at

    found = StudentModeService.find_active(smith.smith, "session-a", later)
    assert _rows()[0].last_seen_at == later
    assert found.student.name == "Bob"


def test_times_show_in_the_familys_zone():
    moment = datetime(2026, 11, 6, 21, 5)

    assert (
        StudentModeService.describe_time(moment, ZoneInfo("America/Chicago"))
        == "Nov 6, 3:05 PM"
    )


# ----- Login token -----


def _token(claims):
    def part(data):
        raw = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
        return raw.rstrip("=")

    return f"{part({'alg': 'HS256'})}.{part(claims)}.signature"


def test_the_session_id_comes_from_the_login_token():
    token = _token({"sub": "abc", "session_id": "5f0c-session"})

    assert AuthProvider.session_id_from_token(token) == "5f0c-session"


@pytest.mark.parametrize("token", [None, "", "not-a-token", "a.!!!.c"])
def test_a_bad_token_has_no_session_id(token):
    assert AuthProvider.session_id_from_token(token) is None


# ----- Pages -----


@pytest.fixture
def page():
    def _open(name, user_id, session_id):
        at = AppTest.from_file(
            str(next((ROOT / "pages").glob(f"*_{name}.py"))), default_timeout=30
        )
        at.session_state["current_user_id"] = user_id
        at.session_state[SessionService.TOKEN_STATE] = _token(
            {"session_id": session_id}
        )
        return at

    with (
        mock.patch.object(SessionService, "sync_browser", return_value=None),
        mock.patch.object(st, "page_link"),
        mock.patch.object(st, "switch_page") as switch_page,
    ):
        _open.switch_page = switch_page
        yield _open


def _in_student_mode(w, student_id, session_id="session-a"):
    user_id = _parent_row(w.smith, "page@x.test")
    db = SessionLocal()
    try:
        family = db.get(Family, w.smith)
        family.parent_pin_hash = bcrypt.hashpw(PIN.encode(), bcrypt.gensalt()).decode()
        db.add(
            DeviceSession(
                family_id=w.smith,
                student_id=student_id,
                mode="student_mode",
                auth_session_id=session_id,
                created_by=user_id,
            )
        )
        db.commit()
        return user_id
    finally:
        db.close()


def test_student_mode_sidebar_has_exit_and_no_logout(world, page):
    user_id = _in_student_mode(world, world.bob)

    at = page("Student_Dashboard", user_id, "session-a").run()

    assert not at.exception
    labels = [button.label for button in at.sidebar.button]
    assert "🔒 Exit Student Mode" in labels
    assert "Logout" not in labels
    assert any("Bob" in box.value for box in at.sidebar.success)
    # It's Bob's own view, with no student picker.
    assert not at.selectbox


def test_parent_pages_send_student_mode_to_the_student_dashboard(world, page):
    user_id = _in_student_mode(world, world.bob)

    page("Settings", user_id, "session-a").run()

    page.switch_page.assert_any_call("pages/🎓_Student_Dashboard.py")


def test_the_parents_other_logins_are_unaffected(world, page):
    user_id = _in_student_mode(world, world.bob)

    at = page("Settings", user_id, "session-b").run()

    assert not at.exception
    assert "🔒 Family PIN" in [s.value for s in at.subheader]
    assert any("Bob" in item.value for item in at.markdown)
