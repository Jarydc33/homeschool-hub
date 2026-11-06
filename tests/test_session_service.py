"""Login and logout wait for the browser to confirm before moving on.

The browser component is replaced with a stand-in, and st.stop() with an
exception, which is how Streamlit ends a run.
"""
from unittest import mock

import pytest
import streamlit as st

from services import session_service
from services.auth_provider import AuthProvider
from services.auth_service import AuthService
from services.session_service import SessionService


class ScriptStopped(Exception):
    pass


class FakeBrowser:
    """Stands in for the component. Replies only when told it's connected."""

    def __init__(self, token=None):
        self.token = token
        self.refresh_token = None
        self.device_token = None
        self.connected = True
        self.calls = []

    def __call__(
        self, action, token, refresh_token, request, key, default, device_token=None
    ):
        self.calls.append((action, key))
        if not self.connected:
            return default
        if action == "save":
            self.token = token
            self.refresh_token = refresh_token
        elif action == "clear":
            self.token = None
            self.refresh_token = None
        elif action == "save_device":
            self.device_token = device_token
        elif action == "clear_device":
            self.device_token = None
        return {
            "request": request,
            "token": self.token,
            "refresh_token": self.refresh_token,
            "device_token": self.device_token,
        }


@pytest.fixture
def state():
    values = {}
    with mock.patch.object(st, "session_state", values), mock.patch.object(
        st, "stop", side_effect=ScriptStopped
    ):
        yield values


@pytest.fixture
def browser():
    fake = FakeBrowser()
    with mock.patch.object(session_service, "_browser_session", fake):
        yield fake


# ----- Reading -----


def test_read_stops_the_script_until_the_browser_replies(state, browser):
    browser.connected = False

    with pytest.raises(ScriptStopped):
        SessionService.get_access_token()

    assert SessionService.TOKEN_STATE not in state


def test_read_returns_saved_token_after_reply(state, browser):
    browser.token = "saved"

    assert SessionService.get_access_token() == "saved"


def test_read_reports_no_saved_login(state, browser):
    assert SessionService.get_access_token() is None


def test_read_asks_the_browser_once(state, browser):
    browser.token = "saved"

    SessionService.get_access_token()
    SessionService.get_access_token()

    assert len(browser.calls) == 1


def test_waiting_read_keeps_the_same_key_across_reruns(state, browser):
    browser.connected = False

    for _ in range(2):
        with pytest.raises(ScriptStopped):
            SessionService.get_access_token()

    assert browser.calls[0][1] == browser.calls[1][1]


def test_reply_to_an_older_request_is_ignored(state):
    stale = mock.Mock(return_value={"request": 99, "token": "old"})

    with mock.patch.object(session_service, "_browser_session", stale):
        with pytest.raises(ScriptStopped):
            SessionService.get_access_token()


def test_known_token_never_asks_the_browser(state, browser):
    assert SessionService.get_known_token() is None
    assert browser.calls == []


# ----- Writing -----


def test_nothing_to_sync_does_nothing(state, browser):
    assert SessionService.sync_browser() is None
    assert browser.calls == []


def test_save_is_queued_until_sync(state, browser):
    SessionService.save_session("new")

    assert browser.token is None
    assert SessionService.get_known_token() == "new"

    assert SessionService.sync_browser() == "save"
    assert browser.token == "new"


def test_save_stays_queued_until_the_browser_confirms(state, browser):
    SessionService.save_session("new")
    browser.connected = False

    with pytest.raises(ScriptStopped):
        SessionService.sync_browser()

    assert SessionService.PENDING_STATE in state

    browser.connected = True

    assert SessionService.sync_browser() == "save"
    assert SessionService.PENDING_STATE not in state
    assert browser.token == "new"


def test_clear_stays_queued_until_the_browser_confirms(state, browser):
    browser.token = "saved"
    SessionService.clear_session()
    browser.connected = False

    with pytest.raises(ScriptStopped):
        SessionService.sync_browser()

    assert browser.token == "saved"

    browser.connected = True

    assert SessionService.sync_browser() == "clear"
    assert browser.token is None


def test_each_finished_write_gets_a_new_key(state, browser):
    SessionService.save_session("one")
    SessionService.sync_browser()
    SessionService.clear_session()
    SessionService.sync_browser()

    assert browser.calls[0][1] != browser.calls[1][1]


def test_sync_only_writes_once(state, browser):
    SessionService.save_session("new")
    SessionService.sync_browser()

    assert SessionService.sync_browser() is None
    assert len(browser.calls) == 1


def test_after_clear_the_browser_is_not_read_again(state, browser):
    browser.token = "saved"
    SessionService.get_access_token()
    SessionService.clear_session()
    SessionService.sync_browser()
    calls = len(browser.calls)

    assert SessionService.get_access_token() is None
    assert len(browser.calls) == calls


# ----- Logging out -----


def logged_in(state, browser):
    state["current_user_id"] = 1
    state[SessionService.TOKEN_STATE] = "saved"
    state[SessionService.REFRESH_TOKEN_STATE] = "saved-refresh"
    browser.token = "saved"
    browser.refresh_token = "saved-refresh"


def test_logout_ends_the_session_in_supabase(state, browser):
    logged_in(state, browser)

    with mock.patch.object(AuthProvider, "sign_out") as sign_out:
        AuthService.logout()

    sign_out.assert_called_once_with("saved", "saved-refresh")


def test_logout_forgets_the_refresh_token_too(state, browser):
    logged_in(state, browser)

    with mock.patch.object(AuthProvider, "sign_out"):
        AuthService.logout()
    SessionService.sync_browser()

    assert SessionService.get_known_refresh_token() is None
    assert browser.refresh_token is None


def test_logout_signs_out_of_this_device_only():
    client = mock.Mock()

    with mock.patch(
        "services.auth_provider.SupabaseService.get_client", return_value=client
    ):
        AuthProvider.sign_out("saved")

    client.auth.admin.sign_out.assert_called_once_with("saved", "local")


def test_logout_forgets_the_user_and_queues_the_clear(state, browser):
    logged_in(state, browser)

    with mock.patch.object(AuthProvider, "sign_out"):
        AuthService.logout()

    assert "current_user_id" not in state
    assert SessionService.get_known_token() is None
    assert state[SessionService.PENDING_STATE] == {"action": "clear"}


def test_logout_never_waits_on_the_browser(state, browser):
    # It runs during a button click, which a stop would lose.
    logged_in(state, browser)
    browser.connected = False

    with mock.patch.object(AuthProvider, "sign_out"):
        AuthService.logout()

    assert browser.calls == []


def test_logout_without_a_known_token_skips_supabase(state, browser):
    state["current_user_id"] = 1

    with mock.patch.object(AuthProvider, "sign_out") as sign_out:
        AuthService.logout()

    sign_out.assert_not_called()
    assert state[SessionService.PENDING_STATE] == {"action": "clear"}


def test_supabase_failure_cannot_block_logout(state, browser):
    logged_in(state, browser)
    client = mock.Mock()
    client.auth.admin.sign_out.side_effect = RuntimeError("expired")

    with mock.patch(
        "services.auth_provider.SupabaseService.get_client", return_value=client
    ):
        AuthService.logout()

    assert "current_user_id" not in state
    assert state[SessionService.PENDING_STATE] == {"action": "clear"}


def test_failure_log_does_not_include_the_token(state, browser, caplog):
    client = mock.Mock()
    client.auth.admin.sign_out.side_effect = RuntimeError("token-value-here")

    with mock.patch(
        "services.auth_provider.SupabaseService.get_client", return_value=client
    ):
        AuthProvider.sign_out("token-value-here")

    assert "token-value-here" not in caplog.text


# ----- Paired device key -----


def test_the_device_key_is_read_with_the_login(state, browser):
    browser.device_token = "device-key"

    assert SessionService.get_access_token() is None
    assert SessionService.get_device_token() == "device-key"


def test_device_key_writes_wait_for_sync_and_survive_logout(state, browser):
    SessionService.save_device_token("device-key")
    assert browser.device_token is None

    assert SessionService.sync_browser() == "save_device"
    assert browser.device_token == "device-key"

    # Logging out of a parent login leaves the pairing alone.
    SessionService.clear_session()
    SessionService.sync_browser()
    assert browser.device_token == "device-key"

    SessionService.clear_device_token()
    assert SessionService.get_device_token() is None
    assert SessionService.sync_browser() == "clear_device"
    assert browser.device_token is None

