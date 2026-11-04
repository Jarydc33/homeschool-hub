"""Registration creates everything, or leaves nothing behind."""
from types import SimpleNamespace
from unittest import mock

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from supabase_auth.errors import AuthApiError, AuthWeakPasswordError

from database.db import SessionLocal
from database.models import Family, User
from services.auth_provider import AuthProvider
from services.auth_service import AuthService
from services.family_service import FamilyService

AUTH_ID = "00000000-0000-0000-0000-00000000000a"
OTHER_ID = "00000000-0000-0000-0000-00000000000b"
EMAIL = "pat@smith.test"


def _count(model):
    db = SessionLocal()
    try:
        return db.query(model).count()
    finally:
        db.close()


def _sign_up_result(identities=("email",), session=None):
    return SimpleNamespace(
        user=SimpleNamespace(id=AUTH_ID, identities=list(identities)),
        session=session,
    )


@pytest.fixture
def provider():
    """Stands in for Supabase. Sign-up works unless a test says otherwise."""
    with (
        mock.patch.object(AuthProvider, "register", return_value=_sign_up_result()) as sign_up,
        mock.patch.object(AuthProvider, "delete_auth_user") as delete,
    ):
        yield SimpleNamespace(sign_up=sign_up, delete=delete)


def test_saves_the_family_and_parent_together(provider):
    session = object()
    provider.sign_up.return_value = _sign_up_result(session=session)

    user, returned_session, error = AuthService.register_parent(
        "Smith", " Pat@Smith.test ", "password1"
    )

    assert error is None
    assert returned_session is session
    assert user.email == EMAIL
    assert user.role == "Parent"
    assert user.auth_user_id == AUTH_ID
    assert user.family_id is not None
    assert _count(Family) == 1
    provider.delete.assert_not_called()


def test_family_and_parent_share_one_commit():
    with mock.patch.object(Session, "commit", autospec=True) as commit:
        FamilyService.create_family_with_parent("Smith", EMAIL, AUTH_ID)

    assert commit.call_count == 1


def test_a_new_family_is_separate_from_existing_ones(provider, world):
    user, _, _ = AuthService.register_parent("New", EMAIL, "password1")

    assert user.family_id not in (world.smith, world.jones)


def test_a_failed_save_leaves_no_family_and_removes_the_account(provider):
    # The email is already in users, so the parent can't be saved.
    FamilyService.create_family_with_parent("Earlier", EMAIL, OTHER_ID)

    user, session, error = AuthService.register_parent("Smith", EMAIL, "password1")

    assert (user, session) == (None, None)
    assert "nothing was saved" in error
    assert _count(Family) == 1
    assert _count(User) == 1
    provider.delete.assert_called_once_with(AUTH_ID)


def test_a_failed_save_is_friendly_even_if_removing_the_account_fails(provider, caplog):
    provider.delete.side_effect = RuntimeError("supabase is down")
    clash = IntegrityError("INSERT", {}, Exception("private detail"))

    with mock.patch.object(FamilyService, "create_family_with_parent", side_effect=clash):
        _, _, error = AuthService.register_parent("Smith", EMAIL, "password1")

    assert "nothing was saved" in error
    assert "private detail" not in error
    assert AUTH_ID in caplog.text


def test_a_taken_email_removes_nothing(provider):
    # Supabase's stand-in id for a taken email isn't a real account.
    provider.sign_up.return_value = _sign_up_result(identities=())

    _, _, error = AuthService.register_parent("Smith", EMAIL, "password1")

    assert "already has an account" in error
    assert _count(Family) == 0
    provider.delete.assert_not_called()


@pytest.mark.parametrize(
    "failure, expected",
    [
        (AuthApiError("private detail", 429, "over_email_send_rate_limit"), "wait a few minutes"),
        (AuthApiError("private detail", 422, "email_address_invalid"), "check your email"),
        (AuthApiError("private detail", 500, "unexpected_failure"), "right now"),
        (AuthWeakPasswordError("private detail", 422, []), "stronger password"),
        (RuntimeError("private detail"), "right now"),
    ],
    ids=["rate-limit", "bad-input", "supabase-error", "weak-password", "other"],
)
def test_sign_up_errors_are_friendly_and_save_nothing(provider, failure, expected):
    provider.sign_up.side_effect = failure

    _, _, error = AuthService.register_parent("Smith", EMAIL, "password1")

    assert expected in error
    assert "private detail" not in error
    assert _count(Family) == 0
    provider.delete.assert_not_called()


def test_signing_up_with_someones_unconfirmed_email_changes_nothing(provider):
    # Supabase hands back the real account for an unconfirmed email.
    FamilyService.create_family_with_parent("Earlier", EMAIL, AUTH_ID)

    user, _, error = AuthService.register_parent("Smith", EMAIL, "password1")

    assert user is None
    assert "already has an account" in error
    assert _count(Family) == 1
    provider.delete.assert_not_called()
