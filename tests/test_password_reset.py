"""Password reset links, and resending invites."""
from types import SimpleNamespace
from unittest import mock

import pytest
import streamlit as st
from supabase_auth.errors import AuthApiError, AuthRetryableError

from services.auth_provider import AuthProvider


@pytest.fixture
def state():
    values = {}
    with mock.patch.object(st, "session_state", values):
        yield values


@pytest.fixture
def client():
    fake = mock.Mock()
    fake.auth.verify_otp.return_value = SimpleNamespace(
        session=SimpleNamespace(access_token="link", refresh_token="link-refresh")
    )
    with mock.patch(
        "services.auth_provider.SupabaseService.get_client", return_value=fake
    ):
        yield fake


# ----- Requesting a reset -----


def test_reset_request_emails_the_address(client):
    assert AuthProvider.send_password_reset("a@x.test") is None

    client.auth.reset_password_for_email.assert_called_once_with("a@x.test")


def test_reset_rate_limit_is_explained(client):
    client.auth.reset_password_for_email.side_effect = AuthApiError(
        "detail", 429, "over_email_send_rate_limit"
    )

    assert "wait a few minutes" in AuthProvider.send_password_reset("a@x.test")


def test_reset_bad_address_is_explained(client):
    client.auth.reset_password_for_email.side_effect = AuthApiError(
        "detail", 400, "validation_failed"
    )

    assert "check the email" in AuthProvider.send_password_reset("nope")


@pytest.mark.parametrize(
    "error",
    [AuthRetryableError("down", 503), AuthApiError("d", 500, None), RuntimeError("secret")],
)
def test_reset_outage_is_friendly(client, error):
    client.auth.reset_password_for_email.side_effect = error

    message = AuthProvider.send_password_reset("a@x.test")

    assert "couldn't send the email" in message
    assert "secret" not in message


def test_reset_log_leaves_out_the_email(client, caplog):
    client.auth.reset_password_for_email.side_effect = RuntimeError("a@x.test")

    AuthProvider.send_password_reset("a@x.test")

    assert "a@x.test" not in caplog.text


# ----- Using a reset link -----


def test_reset_link_verifies_as_recovery(state, client):
    assert AuthProvider.complete_email_link("hash", "recovery", "longenough1") is None

    client.auth.verify_otp.assert_called_once_with(
        {"token_hash": "hash", "type": "recovery"}
    )
    client.auth.update_user.assert_called_once_with({"password": "longenough1"})


def test_reset_logs_out_every_device(state, client):
    AuthProvider.complete_email_link("hash", "recovery", "longenough1")

    client.auth.admin.sign_out.assert_called_once_with("link", "global")


def test_invite_only_ends_its_own_session(state, client):
    AuthProvider.complete_email_link("hash", "invite", "longenough1")

    client.auth.admin.sign_out.assert_called_once_with("link", "local")


def test_rejected_reset_password_does_not_log_anyone_out(state, client):
    client.auth.update_user.side_effect = RuntimeError("no")

    AuthProvider.complete_email_link("hash", "recovery", "longenough1")

    client.auth.admin.sign_out.assert_not_called()


def test_expired_reset_link_says_to_request_a_new_one(state, client):
    client.auth.verify_otp.side_effect = AuthApiError("d", 403, "otp_expired")

    message = AuthProvider.complete_email_link("hash", "recovery", "longenough1")

    assert "password reset link" in message
    assert "request a new one" in message


def test_expired_invite_says_to_ask_a_parent(state, client):
    client.auth.verify_otp.side_effect = AuthApiError("d", 403, "otp_expired")

    message = AuthProvider.complete_email_link("hash", "invite", "longenough1")

    assert "ask a parent" in message


def test_sign_out_uses_the_given_scope_after_an_expired_token(client):
    client.auth.admin.sign_out.side_effect = [AuthApiError("d", 403, "bad_jwt"), None]
    client.auth.refresh_session.return_value = SimpleNamespace(
        session=SimpleNamespace(access_token="new")
    )

    AuthProvider.sign_out("old", "old-refresh", "global")

    client.auth.admin.sign_out.assert_called_with("new", "global")


# ----- Resending an invite -----


def test_resend_to_finished_account_points_to_forgot_password():
    error = AuthApiError("detail", 422, "email_exists")

    message = AuthProvider.resend_invite_error_message(error)

    assert "already set up" in message
    assert "Forgot your password?" in message


def test_resend_too_soon_is_explained():
    error = AuthApiError("detail", 429, "over_email_send_rate_limit")

    assert "wait a few minutes" in AuthProvider.resend_invite_error_message(error)


def test_resend_failure_hides_the_detail():
    message = AuthProvider.resend_invite_error_message(RuntimeError("service key"))

    assert "couldn't send the invitation" in message
    assert "service key" not in message
