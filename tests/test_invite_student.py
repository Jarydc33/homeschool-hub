"""Inviting a student saves their login, or leaves nothing unused behind."""
from types import SimpleNamespace
from unittest import mock

import pytest

from database.models import UserRole
from services.auth_provider import AuthProvider
from services.auth_service import AuthService
from services.user_service import UserService

OTHER_ACCOUNT = "00000000-0000-0000-0000-0000000000b2"


NEW_EMAIL = "new.kid@smith.test"
NEW_ACCOUNT = "00000000-0000-0000-0000-0000000000a1"


@pytest.fixture
def invite_provider():
    invite = SimpleNamespace(user=SimpleNamespace(id=NEW_ACCOUNT))
    with (
        mock.patch.object(AuthProvider, "create_student_account", return_value=invite) as send,
        mock.patch.object(AuthProvider, "delete_auth_user") as delete,
    ):
        yield SimpleNamespace(send=send, delete=delete)


def test_inviting_saves_the_login(smith_parent, invite_provider):
    invited, message = AuthService.invite_student(smith_parent.ann, " New.Kid@Smith.test ")

    assert invited is True
    assert NEW_EMAIL in message
    assert UserService.get_user_by_auth_id(NEW_ACCOUNT).student_id == smith_parent.ann
    invite_provider.delete.assert_not_called()


def test_a_failed_save_removes_the_invited_account(smith_parent, invite_provider):
    with mock.patch.object(
        UserService, "create_student_user", side_effect=RuntimeError("private detail")
    ):
        invited, message = AuthService.invite_student(smith_parent.ann, NEW_EMAIL)

    assert invited is False
    assert "private detail" not in message
    invite_provider.delete.assert_called_once_with(NEW_ACCOUNT)


def test_another_familys_student_cant_be_invited(smith_parent, invite_provider):
    invited, _ = AuthService.invite_student(smith_parent.jones_kid, NEW_EMAIL)

    assert invited is False
    assert UserService.get_user_by_auth_id(NEW_ACCOUNT) is None
    invite_provider.delete.assert_called_once_with(NEW_ACCOUNT)


def test_an_archived_student_cant_be_invited(smith_parent, invite_provider):
    invited, _ = AuthService.invite_student(smith_parent.gone, NEW_EMAIL)

    assert invited is False
    invite_provider.delete.assert_called_once_with(NEW_ACCOUNT)


def test_an_account_someone_uses_is_never_removed(smith_parent, invite_provider):
    # Another student's invite is still pending, and the save below loses a race.
    UserService.create_student_user(smith_parent.smith, smith_parent.bob, "bob@x.test", NEW_ACCOUNT)

    with mock.patch.object(
        UserService, "create_student_user", side_effect=RuntimeError("clash")
    ):
        invited, _ = AuthService.invite_student(smith_parent.ann, NEW_EMAIL)

    assert invited is False
    invite_provider.delete.assert_not_called()


def test_an_account_that_cant_be_checked_is_not_removed(smith_parent, invite_provider):
    with (
        mock.patch.object(
            UserService, "create_student_user", side_effect=RuntimeError("database down")
        ),
        mock.patch.object(
            UserService, "get_user_by_auth_id", side_effect=RuntimeError("database down")
        ),
    ):
        invited, _ = AuthService.invite_student(smith_parent.ann, NEW_EMAIL)

    assert invited is False
    invite_provider.delete.assert_not_called()


@pytest.mark.parametrize(
    "email, expected",
    [("", "valid email"), ("not-an-email", "valid email")],
)
def test_a_bad_email_sends_no_invite(smith_parent, invite_provider, email, expected):
    invited, message = AuthService.invite_student(smith_parent.ann, email)

    assert invited is False
    assert expected in message
    invite_provider.send.assert_not_called()


def test_a_taken_email_sends_no_invite(smith_parent, invite_provider):
    UserService.create_student_user(smith_parent.smith, smith_parent.bob, NEW_EMAIL, OTHER_ACCOUNT)

    invited, message = AuthService.invite_student(smith_parent.ann, NEW_EMAIL)

    assert invited is False
    assert "already has an account" in message
    invite_provider.send.assert_not_called()


def test_a_student_with_a_login_sends_no_invite(smith_parent, invite_provider):
    UserService.create_student_user(smith_parent.smith, smith_parent.ann, "ann@x.test", OTHER_ACCOUNT)

    invited, message = AuthService.invite_student(smith_parent.ann, NEW_EMAIL)

    assert invited is False
    assert "already has a login" in message
    invite_provider.send.assert_not_called()


def test_a_student_cant_send_invites(world, login, invite_provider):
    login(world.smith, role=UserRole.STUDENT, student_id=world.ann)

    invited, _ = AuthService.invite_student(world.bob, NEW_EMAIL)

    assert invited is False
    invite_provider.send.assert_not_called()
