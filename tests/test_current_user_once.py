"""The current user is looked up once per page run, and never kept past it."""
import re
from pathlib import Path
from unittest import mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from database.db import SessionLocal
from database.models import Student, User
from services.auth_provider import AuthProvider
from services.auth_service import AuthService
from services.session_service import SessionService
from services.user_service import UserService

ROOT = Path(__file__).resolve().parent.parent
PAGES = sorted((ROOT / "pages").glob("*.py"))
EMAIL = "bob@smith.test"
AUTH_ID = "00000000-0000-0000-0000-00000000000b"


@pytest.fixture
def session_state():
    state = {}
    with mock.patch.object(st, "session_state", state):
        yield state


@pytest.fixture
def lookups():
    """Counts database lookups of the current user."""
    with mock.patch.object(
        UserService, "get_user_by_id", wraps=UserService.get_user_by_id
    ) as counter:
        yield counter


@pytest.fixture
def bob_user(world):
    return UserService.create_student_user(world.smith, world.bob, EMAIL, AUTH_ID).id


def set_student_active(student_id, active):
    db = SessionLocal()
    try:
        db.get(Student, student_id).active = active
        db.commit()
    finally:
        db.close()


def read_the_user_everywhere():
    AuthService.get_current_user()
    AuthService.is_authenticated()
    AuthService.is_parent()
    AuthService.is_student()
    AuthService.is_admin()
    AuthService.get_current_family()
    AuthService.get_current_student()


def test_many_reads_in_a_page_run_look_up_once(bob_user, session_state, lookups):
    AuthService.set_current_user(bob_user)

    read_the_user_everywhere()

    assert lookups.call_count == 1


def test_each_page_run_looks_up_again(bob_user, session_state, lookups):
    AuthService.set_current_user(bob_user)

    read_the_user_everywhere()
    AuthService.start_page_run()
    read_the_user_everywhere()

    assert lookups.call_count == 2


def test_having_no_user_only_asks_supabase_once(session_state):
    with mock.patch.object(
        AuthProvider, "get_current_auth_user", return_value=None
    ) as ask_supabase:
        read_the_user_everywhere()

    assert ask_supabase.call_count == 1


def test_archiving_a_student_takes_effect_on_the_next_page_run(
    world, bob_user, session_state
):
    AuthService.set_current_user(bob_user)
    assert AuthService.get_current_user().id == bob_user

    set_student_active(world.bob, False)
    AuthService.start_page_run()

    assert AuthService.get_current_user() is None


def test_logging_in_replaces_having_no_user(bob_user, session_state):
    with mock.patch.object(AuthProvider, "get_current_auth_user", return_value=None):
        assert AuthService.get_current_user() is None

    AuthService.set_current_user(bob_user)

    assert AuthService.get_current_user().id == bob_user


def test_logging_out_forgets_the_user_straight_away(bob_user, session_state):
    AuthService.set_current_user(bob_user)
    assert AuthService.get_current_user().id == bob_user

    with (
        mock.patch.object(SessionService, "get_known_token", return_value=None),
        mock.patch.object(SessionService, "clear_session"),
        mock.patch.object(AuthProvider, "get_current_auth_user", return_value=None),
    ):
        AuthService.logout()

        assert AuthService.get_current_user() is None


def test_a_real_page_looks_up_the_user_once_per_run(world, lookups):
    db = SessionLocal()
    try:
        parent = User(
            family_id=world.smith,
            email="pat@smith.test",
            auth_user_id=AUTH_ID,
            role="Parent",
        )
        db.add(parent)
        db.commit()
        parent_id = parent.id
    finally:
        db.close()

    with (
        mock.patch.object(SessionService, "sync_browser", return_value=None),
        mock.patch.object(st, "page_link"),
        mock.patch.object(st, "switch_page"),
    ):
        page = next(path for path in PAGES if path.name.endswith("Parent_Dashboard.py"))
        at = AppTest.from_file(str(page), default_timeout=30)
        at.session_state["current_user_id"] = parent_id

        at.run()
        assert not at.exception
        assert lookups.call_count == 1

        at.run()
        assert not at.exception
        assert lookups.call_count == 2


@pytest.mark.parametrize("page", PAGES, ids=lambda path: path.stem)
def test_no_page_can_read_a_user_from_the_last_run(page):
    source = page.read_text(encoding="utf-8")
    first_read = re.search(r"\bAuthService\.", source)

    if first_read:
        render = source.find("NavigationComponent.render()")
        assert 0 <= render < first_read.start()


def test_the_router_starts_a_new_page_run():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    first_read = re.search(r"\bAuthService\.", source)

    assert source[first_read.end():].startswith("start_page_run")
