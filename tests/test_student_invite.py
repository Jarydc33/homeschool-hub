"""Setting a password from an invite link uses only that link's token."""
from types import SimpleNamespace
from unittest import mock

import pytest
import streamlit as st
from supabase_auth.errors import AuthApiError, AuthWeakPasswordError

from services.auth_provider import AuthProvider
from services.session_service import SessionService


def session(name="invite"):
    return SimpleNamespace(access_token=name, refresh_token=f"{name}-refresh")


@pytest.fixture
def state():
    values = {}
    with mock.patch.object(st, "session_state", values):
        yield values


@pytest.fixture
def client():
    fake = mock.Mock()
    fake.auth.verify_otp.return_value = SimpleNamespace(session=session())
    fake.auth.set_session.return_value = SimpleNamespace(session=session("resumed"))
    with mock.patch(
        "services.auth_provider.SupabaseService.get_client", return_value=fake
    ):
        yield fake


def weak():
    return AuthWeakPasswordError("weak", 422, ["length"])


def test_success_verifies_the_token_then_sets_the_password(state, client):
    assert AuthProvider.complete_invite("hash", "longenough1") is None

    client.auth.verify_otp.assert_called_once_with(
        {"token_hash": "hash", "type": "invite"}
    )
    client.auth.update_user.assert_called_once_with({"password": "longenough1"})


def test_password_is_set_on_the_client_that_verified(state, client):
    # A different client has no session, which is what used to fail.
    with mock.patch(
        "services.auth_provider.SupabaseService.get_client", return_value=client
    ) as get_client:
        AuthProvider.complete_invite("hash", "longenough1")

    calls = [c for c in client.auth.method_calls if c[0] in ("verify_otp", "update_user")]
    assert [c[0] for c in calls] == ["verify_otp", "update_user"]
    assert get_client.call_count >= 1


def test_saved_login_is_never_consulted_or_changed(state, client):
    state[SessionService.TOKEN_STATE] = "parents-token"
    state[SessionService.REFRESH_TOKEN_STATE] = "parents-refresh"

    AuthProvider.complete_invite("hash", "longenough1")

    client.auth.get_user.assert_not_called()
    assert state[SessionService.TOKEN_STATE] == "parents-token"
    assert state[SessionService.REFRESH_TOKEN_STATE] == "parents-refresh"
    assert SessionService.PENDING_STATE not in state


def test_setup_session_is_ended_and_forgotten(state, client):
    AuthProvider.complete_invite("hash", "longenough1")

    client.auth.admin.sign_out.assert_called_once_with("invite", "local")
    assert "invite_session" not in state


@pytest.mark.parametrize("code", ["otp_expired", "validation_failed", None])
def test_used_or_expired_link_is_explained(state, client, code):
    client.auth.verify_otp.side_effect = AuthApiError("detail", 403, code)

    message = AuthProvider.complete_invite("hash", "longenough1")

    assert "expired or has already been used" in message
    client.auth.update_user.assert_not_called()


def test_network_problem_verifying_does_not_blame_the_link(state, client):
    client.auth.verify_otp.side_effect = RuntimeError("secret detail")

    message = AuthProvider.complete_invite("hash", "longenough1")

    assert "try again" in message
    assert "expired" not in message
    assert "secret" not in message


def test_rejected_password_keeps_the_verified_session(state, client):
    client.auth.update_user.side_effect = weak()

    message = AuthProvider.complete_invite("hash", "password1")

    assert "stronger" in message
    assert state["invite_session"].access_token == "invite"
    client.auth.admin.sign_out.assert_not_called()


def test_retry_after_rejected_password_does_not_spend_the_token_again(state, client):
    client.auth.update_user.side_effect = [weak(), mock.DEFAULT]

    AuthProvider.complete_invite("hash", "password1")
    assert AuthProvider.complete_invite("hash", "longenough1") is None

    client.auth.verify_otp.assert_called_once()
    client.auth.set_session.assert_called_once_with("invite", "invite-refresh")
    assert "invite_session" not in state


def test_retry_with_a_dead_session_explains_and_resets(state, client):
    state["invite_session"] = session()
    client.auth.set_session.side_effect = AuthApiError("detail", 400, "session_expired")

    message = AuthProvider.complete_invite("hash", "longenough1")

    assert "expired or has already been used" in message
    assert "invite_session" not in state


def test_other_password_failures_are_friendly(state, client):
    client.auth.update_user.side_effect = RuntimeError("secret detail")

    message = AuthProvider.complete_invite("hash", "longenough1")

    assert "couldn't save that password" in message
    assert "secret" not in message


def test_sign_out_failure_does_not_fail_setup(state, client):
    client.auth.admin.sign_out.side_effect = RuntimeError("down")

    assert AuthProvider.complete_invite("hash", "longenough1") is None


def test_logs_never_contain_the_password_or_token(state, client, caplog):
    client.auth.update_user.side_effect = RuntimeError("longenough1 hash")

    AuthProvider.complete_invite("hash", "longenough1")

    assert "longenough1" not in caplog.text


def test_existing_account_invite_error_is_friendly():
    error = AuthApiError("detail", 422, "email_exists")

    assert "already has an account" in AuthProvider.invite_send_error_message(error)


def test_other_invite_errors_hide_the_detail():
    message = AuthProvider.invite_send_error_message(RuntimeError("service key bad"))

    assert "couldn't send the invitation" in message
    assert "service key" not in message
