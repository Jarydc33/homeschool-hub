"""Users are tied to their Supabase account by UUID, not by email."""
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from database.db import SessionLocal
from database.models import User
from services.auth_provider import AuthProvider
from services.user_service import UserService

AUTH_ID = "00000000-0000-0000-0000-00000000000a"


def sign_up_result(identities):
    return SimpleNamespace(user=SimpleNamespace(id=AUTH_ID, identities=identities))


def test_new_sign_up_gives_its_account_id():
    assert AuthProvider.new_account_id(sign_up_result(["email"])) == AUTH_ID


def test_sign_up_for_a_taken_email_gives_no_id():
    # Supabase's stand-in user has an id that belongs to no account.
    assert AuthProvider.new_account_id(sign_up_result([])) is None


def test_sign_up_without_a_user_gives_no_id():
    assert AuthProvider.new_account_id(SimpleNamespace(user=None)) is None


def test_parent_is_saved_with_their_account(world):
    user = UserService.create_parent_user(world.smith, "P@X.test ", AUTH_ID)

    assert user.auth_user_id == AUTH_ID
    assert UserService.get_user_by_auth_id(AUTH_ID).id == user.id


def test_student_is_saved_with_their_account(world):
    user = UserService.create_student_user(world.smith, world.ann, "a@x.test", AUTH_ID)

    assert UserService.get_user_by_auth_id(AUTH_ID).id == user.id


def test_lookup_accepts_a_uuid_object(world):
    user = UserService.create_parent_user(world.smith, "p@x.test", UUID(AUTH_ID))

    assert UserService.get_user_by_auth_id(UUID(AUTH_ID)).id == user.id


def test_unknown_account_finds_nobody(world):
    UserService.create_parent_user(world.smith, "p@x.test", AUTH_ID)

    assert UserService.get_user_by_auth_id(str(uuid4())) is None


def test_two_users_cannot_share_an_account(world):
    UserService.create_parent_user(world.smith, "a@x.test", AUTH_ID)

    with pytest.raises(IntegrityError):
        UserService.create_parent_user(world.jones, "b@x.test", AUTH_ID)


def test_a_user_cannot_be_saved_without_an_account(world):
    db = SessionLocal()
    try:
        db.add(User(family_id=world.smith, email="a@x.test", role="Parent"))

        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.close()
