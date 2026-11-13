"""Expired saved logins renew themselves, and login errors are friendly."""
from types import SimpleNamespace
from unittest import mock

import pytest
import streamlit as st
from supabase_auth.errors import AuthApiError, AuthRetryableError

from services import session_service
from services.auth_provider import AuthProvider
from services.session_service import SessionService
from services.supabase_service import SupabaseService


class Rerun(Exception):
    pass


def api_error(status=400, code=None):
    return AuthApiError("detail for logs only", status, code)


@pytest.fixture
def state():
    values = {}
    with mock.patch.object(st, "session_state", values), mock.patch.object(
        st, "rerun", side_effect=Rerun
    ):
        yield values


@pytest.fixture
def client():
    fake = mock.Mock()
    fake.auth.refresh_session.return_value = SimpleNamespace(
        session=SimpleNamespace(access_token="new", refresh_token="new-refresh")
    )
    with mock.patch(
        "services.auth_provider.SupabaseService.get_client", return_value=fake
    ):
        yield fake


def saved_login(state, access="old", refresh="old-refresh"):
    state[SessionService.TOKEN_STATE] = access
    state[SessionService.REFRESH_TOKEN_STATE] = refresh


# ----- A valid token -----


def test_valid_token_does_not_refresh(state, client):
    saved_login(state)

    assert AuthProvider.get_current_auth_user() is client.auth.get_user.return_value
    client.auth.refresh_session.assert_not_called()


def test_no_saved_login_contacts_nobody(state, client):
    state[SessionService.TOKEN_STATE] = None

    assert AuthProvider.get_current_auth_user() is None
    client.auth.get_user.assert_not_called()


# ----- An expired token -----


def test_expired_token_is_refreshed_with_the_saved_token(state, client):
    saved_login(state)
    client.auth.get_user.side_effect = api_error(403)

    with pytest.raises(Rerun):
        AuthProvider.get_current_auth_user()

    client.auth.refresh_session.assert_called_once_with("old-refresh")


def test_new_tokens_are_queued_for_the_browser_before_rerunning(state, client):
    saved_login(state)
    client.auth.get_user.side_effect = api_error(403)

    with pytest.raises(Rerun):
        AuthProvider.get_current_auth_user()

    assert state[SessionService.PENDING_STATE] == {
        "action": "save",
        "token": "new",
        "refresh_token": "new-refresh",
    }
    assert SessionService.get_known_token() == "new"
    assert SessionService.get_known_refresh_token() == "new-refresh"


def test_login_with_no_refresh_token_ends_cleanly(state, client):
    saved_login(state, refresh=None)
    client.auth.get_user.side_effect = api_error(403)

    assert AuthProvider.get_current_auth_user() is None
    assert SessionService.get_known_token() is None
    client.auth.refresh_session.assert_not_called()


def test_rejected_refresh_token_ends_the_login(state, client):
    saved_login(state)
    client.auth.get_user.side_effect = api_error(403)
    client.auth.refresh_session.side_effect = api_error(400, "refresh_token_not_found")

    assert AuthProvider.get_current_auth_user() is None
    assert SessionService.get_known_token() is None
    assert SessionService.get_known_refresh_token() is None


def test_ended_login_only_tries_once_per_session(state, client):
    # get_current_user runs many times per page, and a repeat would look
    # like a stolen token being reused.
    saved_login(state)
    client.auth.get_user.side_effect = api_error(403)
    client.auth.refresh_session.side_effect = api_error(400)

    for _ in range(3):
        assert AuthProvider.get_current_auth_user() is None

    assert client.auth.refresh_session.call_count == 1


def test_ended_login_is_not_queued_as_a_logout(state, client):
    # A queued clear would say "You have been logged out."
    saved_login(state)
    client.auth.get_user.side_effect = api_error(403)
    client.auth.refresh_session.side_effect = api_error(400)

    AuthProvider.get_current_auth_user()

    assert SessionService.PENDING_STATE not in state


# ----- Network problems keep the login -----


def test_network_problem_checking_token_keeps_the_login(state, client):
    saved_login(state)
    client.auth.get_user.side_effect = AuthRetryableError("down", 503)

    assert AuthProvider.get_current_auth_user() is None
    assert SessionService.get_known_token() == "old"
    client.auth.refresh_session.assert_not_called()


def test_network_problem_refreshing_keeps_the_login(state, client):
    saved_login(state)
    client.auth.get_user.side_effect = api_error(403)
    client.auth.refresh_session.side_effect = AuthRetryableError("down", 503)

    assert AuthProvider.get_current_auth_user() is None
    assert SessionService.get_known_refresh_token() == "old-refresh"


# ----- Saving both tokens -----


def test_browser_is_asked_to_save_both_tokens(state):
    component = mock.Mock(
        return_value={"request": 0, "token": "a", "refresh_token": "b"}
    )
    SessionService.save_session("a", "b")

    with mock.patch.object(session_service, "_browser_session", component):
        SessionService.sync_browser()

    assert component.call_args.kwargs["token"] == "a"
    assert component.call_args.kwargs["refresh_token"] == "b"


def test_reading_picks_up_both_tokens(state):
    component = mock.Mock(
        return_value={"request": 0, "token": "a", "refresh_token": "b"}
    )

    with mock.patch.object(session_service, "_browser_session", component):
        assert SessionService.get_access_token() == "a"

    assert SessionService.get_known_refresh_token() == "b"


# ----- The Supabase client -----


@pytest.mark.parametrize("get", ["get_client", "get_admin_client", "get_token_client"])
def test_clients_never_refresh_in_the_background(get):
    # A background refresh would use up the token saved in the browser.
    client = getattr(SupabaseService, get)()

    assert client.auth._auto_refresh_token is False
    assert client.auth._persist_session is False


def test_clients_are_not_shared():
    assert SupabaseService.get_client() is not SupabaseService.get_client()


# ----- Logging out with an expired token -----


def test_logout_with_expired_token_still_ends_the_session(client):
    client.auth.admin.sign_out.side_effect = [api_error(403), None]

    AuthProvider.sign_out("old", "old-refresh")

    client.auth.refresh_session.assert_called_once_with("old-refresh")
    client.auth.admin.sign_out.assert_called_with("new", "local")


def test_logout_failure_never_raises(client):
    client.auth.admin.sign_out.side_effect = api_error(403)
    client.auth.refresh_session.side_effect = api_error(400)

    AuthProvider.sign_out("old", "old-refresh")


def test_logout_without_refresh_token_does_not_raise(client):
    client.auth.admin.sign_out.side_effect = api_error(403)

    AuthProvider.sign_out("old")

    client.auth.refresh_session.assert_not_called()


def test_valid_logout_does_not_use_the_refresh_token(client):
    AuthProvider.sign_out("old", "old-refresh")

    client.auth.refresh_session.assert_not_called()


# ----- Friendly login errors -----


@pytest.mark.parametrize(
    "error, expected",
    [
        (api_error(400, "invalid_credentials"), "Incorrect email or password."),
        (api_error(400, "validation_failed"), "Incorrect email or password."),
        (api_error(400, "email_not_confirmed"), "Please confirm your email"),
        (api_error(429, "over_request_rate_limit"), "Too many login attempts"),
        (api_error(500), "couldn't log you in"),
        (AuthRetryableError("down", 503), "couldn't log you in"),
        (RuntimeError("password authentication failed for postgres"), "couldn't log you in"),
    ],
)
def test_login_errors_are_friendly(error, expected):
    assert expected in AuthProvider.login_error_message(error)


def test_login_errors_never_show_the_raw_detail():
    message = AuthProvider.login_error_message(RuntimeError("secret database detail"))

    assert "secret" not in message


def test_login_error_log_leaves_out_the_detail(caplog):
    AuthProvider.login_error_message(RuntimeError("secret database detail"))

    assert "RuntimeError" in caplog.text
    assert "secret" not in caplog.text


def test_token_checks_share_one_client():
    # Only for get_user(token), which stores nothing on the client. Reusing it
    # saves a new connection to Supabase on every API request.
    assert SupabaseService.get_token_client() is SupabaseService.get_token_client()
    assert SupabaseService.get_token_client() is not SupabaseService.get_client()


def test_checking_a_token_uses_the_shared_client():
    fake = mock.Mock()
    fake.auth.get_user.return_value = "user"

    with mock.patch(
        "services.auth_provider.SupabaseService.get_token_client", return_value=fake
    ):
        assert AuthProvider.get_auth_user_for_token("token") == "user"

    fake.auth.get_user.assert_called_once_with("token")
