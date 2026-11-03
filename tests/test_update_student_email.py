"""Changing a student's login email keeps Supabase and the users table together."""
from datetime import datetime
from types import SimpleNamespace
from unittest import mock

import pytest

from database.db import SessionLocal
from database.models import User, UserRole
from services.auth_provider import AuthProvider
from services.auth_service import AuthService
from services.user_service import UserService

OLD = "bob@old.test"
NEW = "bob@new.test"
AUTH_ID = "00000000-0000-0000-0000-00000000000b"


def account(email=OLD, finished=True):
    return SimpleNamespace(
        id=AUTH_ID,
        email=email,
        email_confirmed_at=datetime(2026, 1, 1) if finished else None,
    )


@pytest.fixture
def bob(world):
    db = SessionLocal()
    try:
        user = User(
            family_id=world.smith, student_id=world.bob, email=OLD, role="Student"
        )
        db.add(user)
        db.commit()
        return user.id
    finally:
        db.close()


@pytest.fixture
def admin():
    """The Supabase admin API, with one finished account for Bob."""
    fake = mock.Mock()
    fake.list_users.return_value = [account()]
    client = mock.Mock()
    client.auth.admin = fake
    with mock.patch(
        "services.auth_provider.SupabaseService.get_admin_client", return_value=client
    ):
        yield fake


@pytest.fixture
def parent(smith_parent, bob, admin):
    return smith_parent


def saved_email(user_id):
    db = SessionLocal()
    try:
        return db.get(User, user_id).email
    finally:
        db.close()


def change(world, email=NEW):
    return AuthService.update_student_email(world.bob, email)


# ----- A student who has finished setting up -----


def test_finished_account_changes_both_and_stays_confirmed(parent, admin, bob):
    updated, message = change(parent)

    assert updated is True
    admin.update_user_by_id.assert_called_once_with(
        AUTH_ID, {"email": NEW, "email_confirm": True}
    )
    assert saved_email(bob) == NEW
    assert "same password" in message


def test_finished_account_gets_no_invitation(parent, admin):
    change(parent)

    admin.invite_user_by_email.assert_not_called()


def test_new_email_is_cleaned_up(parent, admin, bob):
    updated, _ = change(parent, "  Bob@NEW.test ")

    assert updated is True
    assert saved_email(bob) == NEW


def test_login_lookup_finds_the_new_email(parent, bob):
    change(parent)

    assert UserService.get_user_by_email(NEW).id == bob
    assert UserService.get_user_by_email(OLD) is None


# ----- A student with a pending invite -----


def test_pending_invite_moves_and_sends_a_new_one(parent, admin, bob):
    admin.list_users.return_value = [account(finished=False)]

    updated, message = change(parent)

    assert updated is True
    admin.update_user_by_id.assert_called_once_with(AUTH_ID, {"email": NEW})
    assert admin.invite_user_by_email.call_args.args[0] == NEW
    assert saved_email(bob) == NEW
    assert "new invitation" in message


def test_pending_account_is_changed_before_inviting(parent, admin):
    # Inviting first would create a second account at the new address.
    admin.list_users.return_value = [account(finished=False)]

    change(parent)

    names = [call[0] for call in admin.method_calls]
    assert names.index("update_user_by_id") < names.index("invite_user_by_email")


def test_login_row_with_no_supabase_account_gets_invited(parent, admin, bob):
    admin.list_users.return_value = []

    updated, _ = change(parent)

    assert updated is True
    admin.update_user_by_id.assert_not_called()
    assert admin.invite_user_by_email.call_args.args[0] == NEW
    assert saved_email(bob) == NEW


# ----- Refused before anything changes -----


def assert_nothing_changed(admin, bob):
    admin.update_user_by_id.assert_not_called()
    admin.invite_user_by_email.assert_not_called()
    assert saved_email(bob) == OLD


@pytest.mark.parametrize("email", ["", "   ", None, "nope", "a@b", "a b@c.test", "@c.test"])
def test_invalid_email_is_refused(parent, admin, bob, email):
    updated, message = AuthService.update_student_email(parent.bob, email)

    assert updated is False
    assert "valid email" in message
    assert_nothing_changed(admin, bob)


def test_same_email_is_refused(parent, admin, bob):
    updated, message = change(parent, " BOB@old.test ")

    assert updated is False
    assert "already this student's email" in message
    assert_nothing_changed(admin, bob)


def test_email_used_by_another_app_user_is_refused(parent, admin, bob):
    UserService.create_parent_user(parent.jones, NEW)

    updated, message = change(parent)

    assert updated is False
    assert "already has an account" in message
    assert_nothing_changed(admin, bob)


def test_email_with_a_supabase_account_is_refused(parent, admin, bob):
    admin.list_users.return_value = [account(), account(NEW)]

    updated, message = change(parent)

    assert updated is False
    assert "already has an account" in message
    assert_nothing_changed(admin, bob)


def test_supabase_lookup_failure_changes_nothing(parent, admin, bob):
    admin.list_users.side_effect = RuntimeError("secret detail")

    updated, message = change(parent)

    assert updated is False
    assert "secret" not in message
    assert_nothing_changed(admin, bob)


# ----- Who can do this -----


def test_other_familys_student_is_refused(world, login, bob, admin):
    login(world.jones)

    updated, _ = AuthService.update_student_email(world.bob, NEW)

    assert updated is False
    assert_nothing_changed(admin, bob)


def test_student_without_a_login_is_refused(parent, admin):
    updated, message = AuthService.update_student_email(parent.ann, NEW)

    assert updated is False
    assert "doesn't have a login" in message
    admin.update_user_by_id.assert_not_called()


@pytest.mark.parametrize("role", [UserRole.STUDENT, UserRole.ADMIN])
def test_only_parents_can_do_this(world, login, bob, admin, role):
    login(world.smith, role, world.bob)

    updated, _ = AuthService.update_student_email(world.bob, NEW)

    assert updated is False
    assert_nothing_changed(admin, bob)


def test_parent_without_a_family_is_refused(world, login, bob, admin):
    login(None)

    updated, _ = AuthService.update_student_email(world.bob, NEW)

    assert updated is False
    assert_nothing_changed(admin, bob)


def test_user_table_update_is_scoped_to_the_family(parent, bob):
    assert UserService.update_user_email(bob, parent.jones, NEW) is None
    assert saved_email(bob) == OLD


# ----- Failures partway through -----


def test_supabase_refusal_leaves_the_table_alone(parent, admin, bob):
    admin.update_user_by_id.side_effect = RuntimeError("secret detail")

    updated, message = change(parent)

    assert updated is False
    assert "nothing was changed" in message
    assert "secret" not in message
    assert saved_email(bob) == OLD


def test_failed_invite_restores_supabase(parent, admin, bob):
    admin.list_users.return_value = [account(finished=False)]
    admin.invite_user_by_email.side_effect = RuntimeError("down")

    updated, _ = change(parent)

    assert updated is False
    assert admin.update_user_by_id.call_args_list[-1] == mock.call(
        AUTH_ID, {"email": OLD}
    )
    assert saved_email(bob) == OLD


def test_failed_table_update_restores_supabase(parent, admin, bob):
    with mock.patch.object(
        UserService, "update_user_email", side_effect=RuntimeError("db down")
    ):
        updated, _ = change(parent)

    assert updated is False
    assert admin.update_user_by_id.call_args_list[-1] == mock.call(
        AUTH_ID, {"email": OLD, "email_confirm": True}
    )
    assert saved_email(bob) == OLD


def test_failed_restore_is_logged_and_still_reports_failure(parent, admin, bob, caplog):
    admin.update_user_by_id.side_effect = [None, RuntimeError("down")]

    with mock.patch.object(UserService, "update_user_email", return_value=None):
        updated, _ = change(parent)

    assert updated is False
    assert "out of step" in caplog.text


def test_logs_leave_out_email_addresses(parent, admin, caplog):
    admin.update_user_by_id.side_effect = RuntimeError(f"{NEW} {OLD}")

    change(parent)

    assert NEW not in caplog.text
    assert OLD not in caplog.text


# ----- Finding accounts -----


def test_finding_accounts_goes_through_every_page(admin):
    full_page = [account(f"u{i}@x.test") for i in range(200)]
    admin.list_users.side_effect = [full_page, [account()]]

    found = AuthProvider.find_auth_users(OLD)

    assert found[OLD].id == AUTH_ID
    assert admin.list_users.call_count == 2


def test_finding_accounts_stops_once_everything_is_found(admin):
    admin.list_users.side_effect = [[account(f"u{i}@x.test") for i in range(199)] + [account()]]

    AuthProvider.find_auth_users(OLD)

    assert admin.list_users.call_count == 1


def test_finding_accounts_ignores_case(admin):
    admin.list_users.return_value = [account("BOB@Old.test")]

    assert OLD in AuthProvider.find_auth_users(OLD)


def test_finding_accounts_handles_accounts_with_no_email(admin):
    admin.list_users.return_value = [account(None), account()]

    assert OLD in AuthProvider.find_auth_users(OLD)
