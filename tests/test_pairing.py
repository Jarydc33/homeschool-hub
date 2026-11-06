"""Pairing codes: a student's own device, signed in without email."""
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import bcrypt
import pytest
import streamlit as st
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from streamlit.testing.v1 import AppTest

from database.db import Base, SessionLocal, engine
from database.models import (
    DEFAULT_TIMEZONE,
    DeviceSession,
    Family,
    PairingCode,
    Student,
    User,
    UserRole,
)
from services.auth_service import AuthService
from services.pairing_service import (
    APP_GUESSES,
    SESSION_GUESSES,
    SESSION_GUESSES_STATE,
    TOO_MANY_GUESSES_MESSAGE,
    WRONG_CODE_MESSAGE,
    PairedUser,
    PairingService,
)
from services.session_service import SessionService
from services.student_mode_service import (
    LOCKED_MESSAGE,
    MAX_PIN_ATTEMPTS,
    StudentModeService,
    WRONG_PIN_MESSAGE,
)

ROOT = Path(__file__).resolve().parent.parent

PIN = "2468"

NOW = datetime(2026, 11, 6, 15, 0)


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


@pytest.fixture(autouse=True)
def fresh_guesses():
    PairingService.reset_guesses()
    yield
    PairingService.reset_guesses()


def _parent_row(family_id):
    db = SessionLocal()
    try:
        user = User(
            family_id=family_id,
            email=f"parent{family_id}@x.test",
            auth_user_id=f"00000000-0000-0000-0000-{family_id:012d}",
            role=UserRole.PARENT.value,
        )
        db.add(user)
        db.commit()
        return user.id
    finally:
        db.close()


@pytest.fixture
def act_as(world):
    """
    act_as(family_id) signs in as that family's parent; act_as(user=...)
    as any user object, such as a paired device. Call again to switch.
    """
    user_ids = {}
    patches = []

    def _as(family_id=None, user=None):
        for patcher in reversed(patches):
            patcher.stop()
        patches.clear()

        if user is None:
            if family_id not in user_ids:
                user_ids[family_id] = _parent_row(family_id)
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
                mock.patch.object(AuthService, "get_auth_session_id", return_value=None),
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
def smith(act_as, world):
    act_as(world.smith)
    StudentModeService.set_pin(PIN, PIN)
    return world


def _code_for(student_id, now=NOW):
    code, expires_at, message = PairingService.create_code(student_id, now)
    assert code, message
    return code


def _pair(student_id, now=NOW):
    token, message = PairingService.redeem(_code_for(student_id, now), now)
    assert token, message
    return token


def _one(model):
    db = SessionLocal()
    try:
        rows = db.query(model).all()
        assert len(rows) == 1
        return rows[0]
    finally:
        db.close()


def _set_archived(student_id):
    db = SessionLocal()
    try:
        db.get(Student, student_id).active = False
        db.commit()
    finally:
        db.close()


# ----- Making codes -----


def test_a_code_is_six_digits_and_stored_hashed(smith):
    code, expires_at, _ = PairingService.create_code(smith.bob, NOW)

    row = _one(PairingCode)
    assert len(code) == 6 and code.isdigit()
    assert row.code_hash == sha(code) != code
    assert expires_at == NOW + timedelta(minutes=10)
    assert row.student_id == smith.bob and row.family_id == smith.smith


def test_codes_need_a_family_pin(act_as, world):
    act_as(world.smith)

    code, _, message = PairingService.create_code(world.bob, NOW)

    assert code is None
    assert "PIN" in message


@pytest.mark.parametrize("name", ["jones_kid", "gone"])
def test_no_codes_for_another_familys_or_an_archived_student(smith, name):
    code, _, _ = PairingService.create_code(getattr(smith, name), NOW)

    assert code is None


def test_students_cant_make_codes(smith, act_as):
    act_as(user=SimpleNamespace(
        id=None, family_id=smith.smith, family=None,
        role=UserRole.STUDENT.value, student_id=smith.bob,
    ))

    assert PairingService.create_code(smith.bob, NOW)[0] is None


# ----- Redeeming -----


def test_a_code_pairs_the_device_once(smith):
    code = _code_for(smith.bob)

    token, _ = PairingService.redeem(code, NOW + timedelta(minutes=2))

    device = _one(DeviceSession)
    assert device.mode == "paired"
    assert device.token_hash == sha(token) != token
    assert device.auth_session_id is None
    assert (device.family_id, device.student_id) == (smith.smith, smith.bob)
    assert _one(PairingCode).used_at is not None

    assert PairingService.redeem(code, NOW + timedelta(minutes=3)) == (
        None,
        WRONG_CODE_MESSAGE,
    )


def test_spaces_and_dashes_in_a_code_are_fine(smith):
    code = _code_for(smith.bob)

    token, _ = PairingService.redeem(f" {code[:3]}-{code[3:]} ", NOW)

    assert token


def test_an_expired_code_doesnt_work(smith):
    code = _code_for(smith.bob)

    assert PairingService.redeem(code, NOW + timedelta(minutes=11))[0] is None


def test_a_code_doesnt_work_once_the_student_is_archived(smith):
    code = _code_for(smith.bob)
    _set_archived(smith.bob)

    assert PairingService.redeem(code, NOW)[0] is None


def test_a_malformed_code_asks_for_six_digits(smith):
    assert PairingService.redeem("12ab", NOW) == (None, "Please enter the 6-digit code.")


# ----- Guessing -----


def test_too_many_wrong_codes_in_one_session_stop_tries():
    for _ in range(SESSION_GUESSES):
        assert PairingService.redeem("000000", NOW)[1] == WRONG_CODE_MESSAGE

    assert PairingService.redeem("000000", NOW)[1] == TOO_MANY_GUESSES_MESSAGE
    assert not PairingService.too_many_guesses(NOW + timedelta(minutes=11))


def test_the_app_wide_limit_stops_guessing_across_sessions():
    for attempt in range(APP_GUESSES):
        # A new browser session each time, so only the app-wide limit applies.
        st.session_state.pop(SESSION_GUESSES_STATE, None)
        assert PairingService.redeem("000000", NOW)[1] == WRONG_CODE_MESSAGE

    st.session_state.pop(SESSION_GUESSES_STATE, None)
    assert PairingService.redeem("000000", NOW)[1] == TOO_MANY_GUESSES_MESSAGE


def test_even_the_right_code_waits_out_the_limit(smith):
    code = _code_for(smith.bob)
    for _ in range(SESSION_GUESSES):
        PairingService.redeem("000000", NOW)

    assert PairingService.redeem(code, NOW)[0] is None


# ----- Being a paired device -----


def test_a_paired_device_is_its_student(smith, act_as):
    token = _pair(smith.bob)

    paired = PairingService.find_paired(token, NOW)
    act_as(user=paired)

    assert isinstance(paired, PairedUser)
    assert AuthService.is_paired_device()
    assert AuthService.is_student()
    assert not AuthService.is_parent()
    assert AuthService.get_current_student() == smith.bob
    assert AuthService.get_current_family() == smith.smith
    assert paired.student.name == "Bob"
    assert paired.family.timezone


def test_parent_only_actions_are_refused_on_a_paired_device(smith, act_as):
    act_as(user=PairingService.find_paired(_pair(smith.bob), NOW))

    assert PairingService.create_code(smith.ann, NOW)[0] is None
    assert StudentModeService.list_sessions() == []
    assert not StudentModeService.end_session(_one(DeviceSession).id)


@pytest.mark.parametrize("token", [None, "", "not-a-real-key"])
def test_an_unknown_key_isnt_paired(token):
    assert PairingService.find_paired(token, NOW) is None


def test_an_ended_device_isnt_paired(smith):
    token = _pair(smith.bob)

    assert StudentModeService.end_session(_one(DeviceSession).id)

    assert PairingService.find_paired(token, NOW) is None


def test_archiving_the_student_ends_their_paired_devices(smith):
    token = _pair(smith.bob)

    _set_archived(smith.bob)

    assert PairingService.find_paired(token, NOW) is None


def test_last_seen_updates_only_when_stale(smith):
    token = _pair(smith.bob)

    PairingService.find_paired(token, NOW + timedelta(minutes=1))
    assert _one(DeviceSession).last_seen_at == NOW

    PairingService.find_paired(token, NOW + timedelta(minutes=10))
    assert _one(DeviceSession).last_seen_at == NOW + timedelta(minutes=10)


# ----- Unpairing -----


def test_the_right_pin_unpairs_and_forgets_the_key(smith, act_as):
    token = _pair(smith.bob)
    act_as(user=PairingService.find_paired(token, NOW))

    unpaired, _ = PairingService.unpair(PIN, NOW)

    assert unpaired
    assert _one(DeviceSession).revoked_at is not None
    assert PairingService.find_paired(token, NOW) is None
    assert st.session_state[SessionService.PENDING_STATE] == {"action": "clear_device"}


def test_a_wrong_pin_keeps_the_device_and_locks_after_five(smith, act_as):
    act_as(user=PairingService.find_paired(_pair(smith.bob), NOW))

    for _ in range(MAX_PIN_ATTEMPTS - 1):
        assert PairingService.unpair("0000", NOW) == (False, WRONG_PIN_MESSAGE)

    assert PairingService.unpair("0000", NOW) == (False, LOCKED_MESSAGE)
    assert PairingService.unpair(PIN, NOW + timedelta(minutes=1)) == (False, LOCKED_MESSAGE)
    assert _one(DeviceSession).revoked_at is None

    assert PairingService.unpair(PIN, NOW + timedelta(minutes=6))[0]


def test_only_a_paired_device_can_unpair(smith):
    assert not PairingService.unpair(PIN, NOW)[0]


# ----- Family isolation -----


def test_another_family_cant_see_or_end_our_paired_devices(smith, act_as):
    token = _pair(smith.bob)
    device_id = _one(DeviceSession).id

    act_as(smith.jones)

    assert StudentModeService.list_sessions() == []
    assert not StudentModeService.end_session(device_id)
    assert PairingService.find_paired(token, NOW) is not None


def test_parents_see_paired_devices_in_the_devices_list(smith):
    _pair(smith.bob)

    devices = StudentModeService.list_sessions()

    assert [(d.student.name, d.mode) for d in devices] == [("Bob", "paired")]


# ----- Pages -----


@pytest.fixture
def page():
    def _open(name, device_token=None, user_id=None):
        at = AppTest.from_file(
            str(next((ROOT / "pages").glob(f"*_{name}.py"))), default_timeout=30
        )
        at.session_state[SessionService.TOKEN_STATE] = None
        at.session_state[SessionService.REFRESH_TOKEN_STATE] = None
        at.session_state[SessionService.DEVICE_TOKEN_STATE] = device_token
        if user_id:
            at.session_state["current_user_id"] = user_id
        return at

    with (
        mock.patch.object(SessionService, "sync_browser", return_value=None),
        mock.patch.object(st, "page_link"),
        mock.patch.object(st, "switch_page") as switch_page,
    ):
        _open.switch_page = switch_page
        yield _open


def _paired_in_db(w, student_id):
    """A paired device for a student, made without the service."""
    parent_id = _parent_row(w.smith)
    db = SessionLocal()
    try:
        db.get(Family, w.smith).parent_pin_hash = bcrypt.hashpw(
            PIN.encode(), bcrypt.gensalt()
        ).decode()
        db.add(
            DeviceSession(
                family_id=w.smith,
                student_id=student_id,
                mode="paired",
                token_hash=sha("device-key"),
                created_by=parent_id,
            )
        )
        db.commit()
        return parent_id
    finally:
        db.close()


def test_a_paired_device_sees_its_students_dashboard(world, page):
    _paired_in_db(world, world.bob)

    at = page("Student_Dashboard", "device-key").run()

    assert not at.exception
    labels = [button.label for button in at.sidebar.button]
    assert "🔒 Unpair This Device" in labels
    assert "Logout" not in labels
    assert any("Bob" in box.value for box in at.sidebar.success)
    assert not at.selectbox


def test_a_paired_device_cant_open_parent_pages(world, page):
    _paired_in_db(world, world.bob)

    page("Settings", "device-key").run()

    page.switch_page.assert_any_call("pages/🎓_Student_Dashboard.py")


def test_without_a_key_the_device_is_logged_out(world, page):
    page("Student_Dashboard", None).run()

    page.switch_page.assert_any_call("pages/🔐_Login.py")


def test_the_login_page_pairs_a_device(smith, page, act_as):
    code = _code_for(smith.bob, datetime.utcnow())
    mock.patch.stopall()

    at = page("Login").run()
    code_box = next(box for box in at.text_input if box.label == "Pairing Code")
    code_box.input(code)
    next(b for b in at.button if b.label == "Pair This Device").click().run()

    assert not at.exception
    assert _one(DeviceSession).student_id == smith.bob
    assert at.session_state[SessionService.DEVICE_TOKEN_STATE]


def test_settings_lists_paired_devices(world, page):
    parent_id = _paired_in_db(world, world.ann)

    at = page("Settings", user_id=parent_id).run()

    assert not at.exception
    assert any("Ann" in item.value and "Paired" in item.value for item in at.markdown)
    assert "➕ Pair a Device" in [button.label for button in at.button]


# ----- Migration -----


@pytest.fixture
def empty_database():
    Base.metadata.drop_all(engine)
    yield
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))


def test_pairing_migration_can_be_undone(empty_database):
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    command.downgrade(config, "0013")

    tables = inspect(engine).get_table_names()
    columns = {c["name"] for c in inspect(engine).get_columns("device_sessions")}
    assert "pairing_codes" not in tables
    assert "token_hash" not in columns
