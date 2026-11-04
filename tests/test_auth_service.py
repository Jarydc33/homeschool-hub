"""Archived students can't use their login until they're unarchived.

These tests use the real AuthService.get_current_user, not the login fixture,
with Streamlit's session state and Supabase Auth replaced.
"""
from types import SimpleNamespace
from unittest import mock
from uuid import uuid4

import pytest
import streamlit as st

from database.db import SessionLocal
from database.models import Student, User
from services.auth_provider import AuthProvider
from services.auth_service import AuthService
from services.navigation_service import NavigationService
from services.student_service import StudentService
from services.user_service import UserService

EMAIL = "bob@smith.test"
AUTH_ID = "00000000-0000-0000-0000-00000000000b"


@pytest.fixture
def session_state():
    state = {}
    with mock.patch.object(st, "session_state", state):
        yield state


@pytest.fixture
def no_saved_login():
    with mock.patch.object(AuthProvider, "get_current_auth_user", return_value=None):
        yield


@pytest.fixture
def saved_login():
    """A valid Supabase token saved in the browser for the student."""
    auth_user = SimpleNamespace(user=SimpleNamespace(id=AUTH_ID, email=EMAIL))
    with mock.patch.object(
        AuthProvider, "get_current_auth_user", return_value=auth_user
    ):
        yield


def add_user(**fields):
    fields.setdefault("auth_user_id", str(uuid4()))
    db = SessionLocal()
    try:
        user = User(**fields)
        db.add(user)
        db.commit()
        return user.id
    finally:
        db.close()


@pytest.fixture
def bob_user(world):
    return add_user(
        family_id=world.smith,
        student_id=world.bob,
        email=EMAIL,
        auth_user_id=AUTH_ID,
        role="Student",
    )


def set_student_active(student_id, active):
    db = SessionLocal()
    try:
        db.get(Student, student_id).active = active
        db.commit()
    finally:
        db.close()


# ----- is_archived_student -----


def test_user_lookups_can_read_student_after_session_closes(world, bob_user):
    assert UserService.get_user_by_id(bob_user).student.name == "Bob"
    assert UserService.get_user_by_email(EMAIL).student.name == "Bob"
    assert UserService.get_user_by_auth_id(AUTH_ID).student.name == "Bob"


def test_active_student_is_not_archived(world, bob_user):
    assert not AuthService.is_archived_student(UserService.get_user_by_id(bob_user))


def test_archived_student_is_archived(world, bob_user):
    set_student_active(world.bob, False)

    assert AuthService.is_archived_student(UserService.get_user_by_id(bob_user))


def test_student_login_without_a_student_is_blocked(world):
    user_id = add_user(family_id=world.smith, email="x@x.test", role="Student")

    assert AuthService.is_archived_student(UserService.get_user_by_id(user_id))


@pytest.mark.parametrize("role", ["Parent", "Admin"])
def test_other_roles_are_never_blocked(world, role):
    user_id = add_user(family_id=None, email="x@x.test", role=role)

    assert not AuthService.is_archived_student(UserService.get_user_by_id(user_id))


# ----- get_current_user: signed in during this session -----


def test_active_student_stays_signed_in(world, bob_user, session_state, no_saved_login):
    AuthService.set_current_user(bob_user)

    assert AuthService.get_current_user().id == bob_user
    assert "account_inactive" not in session_state


def test_archiving_ends_a_signed_in_students_access(
    world, bob_user, session_state, no_saved_login
):
    AuthService.set_current_user(bob_user)
    set_student_active(world.bob, False)

    assert AuthService.get_current_user() is None
    assert AuthService.is_authenticated() is False
    assert AuthService.is_student() is False
    assert AuthService.get_current_family() is None
    assert session_state["account_inactive"] is True


def test_unarchiving_restores_access(world, bob_user, session_state, no_saved_login):
    AuthService.set_current_user(bob_user)
    set_student_active(world.bob, False)
    assert AuthService.get_current_user() is None

    set_student_active(world.bob, True)
    AuthService.start_page_run()

    assert AuthService.get_current_user().id == bob_user


# ----- get_current_user: returning with a saved login -----


def test_saved_login_works_for_active_student(
    world, bob_user, session_state, saved_login
):
    assert AuthService.get_current_user().id == bob_user
    assert session_state["current_user_id"] == bob_user


def test_saved_login_is_blocked_for_archived_student(
    world, bob_user, session_state, saved_login
):
    set_student_active(world.bob, False)

    assert AuthService.get_current_user() is None
    assert "current_user_id" not in session_state
    assert session_state["account_inactive"] is True


def test_saved_login_with_matching_email_but_other_account_gets_nothing(
    world, bob_user, session_state
):
    # Someone else's Supabase account using Bob's email isn't Bob.
    stranger = SimpleNamespace(user=SimpleNamespace(id=str(uuid4()), email=EMAIL))

    with mock.patch.object(
        AuthProvider, "get_current_auth_user", return_value=stranger
    ):
        assert AuthService.get_current_user() is None

    assert "current_user_id" not in session_state


def test_saved_login_follows_the_account_when_the_email_differs(
    world, bob_user, session_state
):
    # The account is what counts, even if the two emails ever disagree.
    moved = SimpleNamespace(user=SimpleNamespace(id=AUTH_ID, email="new@x.test"))

    with mock.patch.object(AuthProvider, "get_current_auth_user", return_value=moved):
        assert AuthService.get_current_user().id == bob_user


# ----- Effects of being blocked -----


def test_archived_student_cannot_check_off_work(
    world, bob_user, session_state, no_saved_login, fetch
):
    from database.models import AssignmentOccurrence

    AuthService.set_current_user(bob_user)
    set_student_active(world.bob, False)

    assert StudentService.update_occurrence_status(world.bob_essay_day, True) is None
    assert fetch(AssignmentOccurrence, world.bob_essay_day).status == "Not Started"


def test_page_guard_sends_archived_student_to_login(
    world, bob_user, session_state, no_saved_login
):
    AuthService.set_current_user(bob_user)
    set_student_active(world.bob, False)

    with (
        mock.patch.object(st, "warning"),
        mock.patch.object(st, "switch_page") as switch_page,
        mock.patch.object(st, "stop"),
    ):
        NavigationService.require_authentication()

    assert "Login" in switch_page.call_args.args[0]


def test_parent_is_unaffected_by_an_archived_student(
    world, session_state, no_saved_login
):
    parent_id = add_user(family_id=world.smith, email="p@x.test", role="Parent")
    set_student_active(world.bob, False)
    AuthService.set_current_user(parent_id)

    assert AuthService.get_current_user().id == parent_id
    assert "account_inactive" not in session_state
