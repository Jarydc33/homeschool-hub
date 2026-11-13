"""
Once the new app takes over, APP_MOVED_TO makes every Streamlit page say
where tally went, except Complete_Account, which links sent before the move
still need.
"""
from pathlib import Path
from unittest import mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from config import get_optional_setting
from services.auth_provider import AuthProvider
from services.session_service import SessionService

PAGES = Path(__file__).resolve().parent.parent / "pages"
NEW_APP = "https://app.tallyhomeschool.com"


def page(name):
    return AppTest.from_file(str(next(PAGES.glob(f"*{name}.py"))), default_timeout=30)


@pytest.fixture(autouse=True)
def no_browser_or_saved_login():
    with (
        mock.patch.object(SessionService, "sync_browser", return_value=None),
        mock.patch.object(AuthProvider, "get_current_auth_user", return_value=None),
        mock.patch.object(st, "page_link"),
        mock.patch.object(st, "switch_page"),
    ):
        yield


def test_an_unset_setting_is_none(monkeypatch):
    monkeypatch.delenv("APP_MOVED_TO", raising=False)

    assert get_optional_setting("APP_MOVED_TO") is None


def test_pages_say_where_tally_moved(monkeypatch):
    monkeypatch.setenv("APP_MOVED_TO", NEW_APP)

    at = page("Login").run()

    assert at.title[0].value == "tally has moved"
    assert not at.text_input  # The old login form is gone.
    assert NEW_APP in at.caption[0].value


def test_pages_work_as_before_without_the_setting(monkeypatch):
    monkeypatch.delenv("APP_MOVED_TO", raising=False)

    at = page("Login").run()

    assert all(title.value != "tally has moved" for title in at.title)
    assert at.text_input


def test_email_links_sent_before_the_move_still_work(monkeypatch):
    monkeypatch.setenv("APP_MOVED_TO", NEW_APP)

    at = page("Complete_Account")
    at.query_params["token_hash"] = "abc"
    at.query_params["type"] = "invite"
    at.run()

    assert all(title.value != "tally has moved" for title in at.title)
    assert len(at.text_input) == 2  # Password and Confirm Password.
