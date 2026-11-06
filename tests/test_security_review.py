"""Fixes from the 2026-11-06 security review."""
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest
from supabase_auth.errors import AuthApiError

from database.models import Subject, UserRole
from services.assignment_service import AssignmentService
from services.auth_provider import AuthProvider
from services.login_limit_service import (
    LOCKED_MESSAGE,
    MAX_FAILURES,
    LoginLimitService,
)
from services.session_service import SessionService
from services.student_service import StudentService
from services.subject_service import DEFAULT_COLOR, SubjectService

ROOT = Path(__file__).resolve().parent.parent

WRONG_PASSWORD = AuthApiError("Invalid login credentials", 400, "invalid_credentials")


@pytest.fixture(autouse=True)
def fresh_limits():
    LoginLimitService.reset()
    yield
    LoginLimitService.reset()


# ----- Login limit -----


def test_too_many_wrong_passwords_lock_the_email():
    now = datetime(2026, 11, 6, 12, 0)

    for _ in range(MAX_FAILURES - 1):
        LoginLimitService.record_failure("mom@x.test", now)
    assert not LoginLimitService.is_locked("mom@x.test", now)

    LoginLimitService.record_failure("mom@x.test", now)

    assert LoginLimitService.is_locked("mom@x.test", now)
    # Spaces and capitals don't make it a different email.
    assert LoginLimitService.is_locked(" MOM@x.test ", now)
    assert not LoginLimitService.is_locked("dad@x.test", now)


def test_the_lock_ends_after_fifteen_minutes():
    now = datetime(2026, 11, 6, 12, 0)
    for _ in range(MAX_FAILURES):
        LoginLimitService.record_failure("mom@x.test", now)

    assert LoginLimitService.is_locked("mom@x.test", now + timedelta(minutes=14))
    assert not LoginLimitService.is_locked("mom@x.test", now + timedelta(minutes=16))


def test_logging_in_clears_earlier_failures():
    for _ in range(MAX_FAILURES - 1):
        LoginLimitService.record_failure("mom@x.test")

    LoginLimitService.record_success("mom@x.test")
    LoginLimitService.record_failure("mom@x.test")

    assert not LoginLimitService.is_locked("mom@x.test")


def test_only_a_wrong_password_counts_as_a_failure():
    assert AuthProvider.is_wrong_password(WRONG_PASSWORD)
    assert not AuthProvider.is_wrong_password(
        AuthApiError("Email not confirmed", 400, "email_not_confirmed")
    )
    assert not AuthProvider.is_wrong_password(
        AuthApiError("Too many requests", 429, "over_request_rate_limit")
    )
    assert not AuthProvider.is_wrong_password(ConnectionError())


def test_the_login_page_stops_trying_once_locked():
    with (
        mock.patch.object(SessionService, "sync_browser", return_value=None),
        mock.patch.object(SessionService, "get_access_token", return_value=None),
        mock.patch.object(st, "page_link"),
        mock.patch.object(st, "switch_page"),
        mock.patch.object(AuthProvider, "login", side_effect=WRONG_PASSWORD) as login,
    ):
        at = AppTest.from_file(
            str(next((ROOT / "pages").glob("*_Login.py"))), default_timeout=30
        ).run()

        for _ in range(MAX_FAILURES + 1):
            at.text_input[0].input("mom@x.test")
            at.text_input[1].input("guess")
            at.button[0].click().run()

        assert not at.exception
        assert login.call_count == MAX_FAILURES
        assert LOCKED_MESSAGE in [box.value for box in at.error]


# ----- Parent-only changes -----


@pytest.fixture
def as_student(world, login):
    login(world.smith, UserRole.STUDENT, world.bob)
    return world


def test_students_cant_change_students(as_student, fetch):
    w = as_student
    from database.models import Student

    assert StudentService.create_student("Sneaky") is None
    assert StudentService.update_student(w.bob, name="Renamed") is None
    assert StudentService.archive_student(w.ann) is None
    assert StudentService.restore_student(w.gone) is None
    assert StudentService.get_archived_students() == []
    assert fetch(Student, w.bob).name == "Bob"
    assert fetch(Student, w.ann).active


def test_students_cant_change_subjects(as_student, fetch):
    w = as_student

    assert SubjectService.create_subject("Recess") is None
    assert SubjectService.update_subject(w.art, name="Nap") is None
    assert SubjectService.archive_subject(w.art) is None
    assert fetch(Subject, w.art).name == "Art"
    assert fetch(Subject, w.art).active


def test_students_cant_change_assignments(as_student, fetch):
    w = as_student
    from database.models import Assignment

    assert (
        AssignmentService.create_assignment(
            subject_id=w.art, title="No homework", student_ids=[w.bob]
        )
        is None
    )
    assert AssignmentService.archive_assignment(w.essay) is None
    assert fetch(Assignment, w.essay).active


def test_a_student_can_only_look_up_themselves(as_student):
    w = as_student

    assert StudentService.get_student_by_id(w.bob).name == "Bob"
    assert StudentService.get_student_by_id(w.ann) is None


def test_parents_can_still_look_up_any_of_their_students(smith_parent):
    w = smith_parent

    assert StudentService.get_student_by_id(w.ann).name == "Ann"
    assert StudentService.get_student_by_id(w.jones_kid) is None


# ----- Subject colors -----


@pytest.mark.parametrize(
    "color",
    [None, "", "red", "#12345", "#1234567", '#fff"></div><img src=x onerror=alert(1)>'],
)
def test_anything_but_a_hex_color_shows_the_default(color):
    assert SubjectService.display_color(color) == DEFAULT_COLOR


def test_a_hex_color_is_kept():
    assert SubjectService.display_color("#a1B2c3") == "#a1B2c3"


def test_a_bad_color_isnt_saved(smith_parent, fetch):
    w = smith_parent
    bad = '#fff"><script>alert(1)</script>'

    subject = SubjectService.create_subject("Music", bad)
    SubjectService.update_subject(w.art, color=bad)

    assert fetch(Subject, subject.id).color == DEFAULT_COLOR
    assert fetch(Subject, w.art).color == DEFAULT_COLOR
