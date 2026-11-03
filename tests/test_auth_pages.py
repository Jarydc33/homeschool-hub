"""Runs the real Login, Register and invite pages, with Supabase replaced."""
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from database.db import SessionLocal
from database.models import Family, User
from services.auth_provider import AuthProvider
from services.session_service import SessionService
from services.supabase_service import SupabaseService
from services.user_service import UserService

PAGES = Path(__file__).resolve().parent.parent / "pages"
AUTH_ID = "00000000-0000-0000-0000-00000000000a"
OTHER_ID = "00000000-0000-0000-0000-00000000000f"
EMAIL = "pat@smith.test"


def page(name):
    return AppTest.from_file(str(next(PAGES.glob(f"*{name}.py"))), default_timeout=30)


@pytest.fixture(autouse=True)
def no_browser_or_saved_login():
    with (
        mock.patch.object(SessionService, "sync_browser", return_value=None),
        mock.patch.object(AuthProvider, "get_current_auth_user", return_value=None),
        # These only resolve when the whole app is running.
        mock.patch.object(st, "page_link"),
        mock.patch.object(st, "switch_page"),
    ):
        yield


def errors(at):
    return " ".join(e.value for e in at.error)


def count(model):
    db = SessionLocal()
    try:
        return db.query(model).count()
    finally:
        db.close()


# ----- Login -----


def log_in(auth_id):
    result = SimpleNamespace(user=SimpleNamespace(id=auth_id, email=EMAIL), session=None)

    with mock.patch.object(AuthProvider, "login", return_value=result):
        at = page("Login").run()
        at.text_input[0].set_value(EMAIL)
        at.text_input[1].set_value("password1")
        return at.button[0].click().run()


def test_login_finds_the_user_by_account(world):
    user = UserService.create_parent_user(world.smith, EMAIL, AUTH_ID)

    at = log_in(AUTH_ID)

    assert at.session_state["current_user_id"] == user.id


def test_login_refuses_another_account_with_the_same_email(world):
    UserService.create_parent_user(world.smith, EMAIL, AUTH_ID)

    at = log_in(OTHER_ID)

    assert "current_user_id" not in at.session_state
    assert "couldn't find" in errors(at)


# ----- Registration -----


def register(identities):
    result = SimpleNamespace(
        user=SimpleNamespace(id=AUTH_ID, identities=identities), session=None
    )

    with mock.patch.object(AuthProvider, "register", return_value=result):
        at = page("Register").run()
        at.text_input[0].set_value("Smith")
        at.text_input[1].set_value(EMAIL)
        at.text_input[2].set_value("password1")
        at.text_input[3].set_value("password1")
        return at.button[0].click().run()


def test_registering_saves_the_account_id():
    register(["email"])

    assert UserService.get_user_by_auth_id(AUTH_ID).email == EMAIL


def test_registering_a_taken_email_creates_nothing():
    at = register([])

    assert "already has an account" in errors(at)
    assert count(Family) == 0
    assert count(User) == 0


# ----- Inviting a student -----


def test_inviting_a_student_saves_the_account_id(world):
    parent = UserService.create_parent_user(world.smith, EMAIL, OTHER_ID)
    admin = mock.Mock()
    admin.auth.admin.invite_user_by_email.return_value = SimpleNamespace(
        user=SimpleNamespace(id=AUTH_ID)
    )
    # A dialog's second click needs the browser, so the clicks are stood in for.
    clicks = ["🔐 Create Student Login", "Create Login"]
    real_input = st.text_input

    def click_once(label, *args, **kwargs):
        if label in clicks:
            clicks.remove(label)
            return True
        return False

    def type_email(label, *args, **kwargs):
        if label == "Student Email":
            return "ann@smith.test"
        return real_input(label, *args, **kwargs)

    with (
        mock.patch.object(SupabaseService, "get_admin_client", return_value=admin),
        mock.patch.object(st, "dialog", lambda title: lambda fn: fn),
        mock.patch.object(st, "button", click_once),
        mock.patch.object(st, "text_input", type_email),
    ):
        at = page("Student_Dashboard")
        at.session_state["current_user_id"] = parent.id
        at.run()

    assert not at.exception
    user = UserService.get_user_by_auth_id(AUTH_ID)
    assert user.email == "ann@smith.test"
    assert user.student_id == world.ann
