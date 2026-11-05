"""Parents can change their family's name and time zone, and the sidebar is
grouped for each role."""
from pathlib import Path
from unittest import mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from components.navigation import (
    ADMIN_LINKS,
    LOGGED_OUT_LINKS,
    PARENT_LINKS,
    STUDENT_LINKS,
)
from database.db import SessionLocal
from database.models import Family, User, UserRole
from services.family_service import FamilyService
from services.session_service import SessionService

ROOT = Path(__file__).resolve().parent.parent


# ----- Settings -----


def test_a_parent_changes_the_name_and_time_zone(smith_parent, fetch):
    w = smith_parent

    assert FamilyService.update_settings(" The Smiths ", "America/New_York")

    family = fetch(Family, w.smith)
    assert family.family_name == "The Smiths"
    assert family.timezone == "America/New_York"


@pytest.mark.parametrize(
    "name, zone, expected",
    [
        ("  ", "America/Chicago", "family name"),
        ("x" * 101, "America/Chicago", "shorter"),
        ("Smith", "Mars/Olympus", "time zone"),
        ("Smith", None, "time zone"),
    ],
)
def test_bad_settings_say_whats_wrong_and_change_nothing(
    smith_parent, fetch, name, zone, expected
):
    assert expected in FamilyService.settings_error(name, zone)
    assert FamilyService.update_settings(name, zone) is None
    assert fetch(Family, smith_parent.smith).family_name == "Smith"


def test_students_and_admins_cant_change_settings(smith_parent, login, fetch):
    w = smith_parent

    login(w.smith, role=UserRole.STUDENT, student_id=w.ann)
    assert FamilyService.update_settings("Taken", "America/New_York") is None

    login(None, role=UserRole.ADMIN)
    assert FamilyService.update_settings("Taken", "America/New_York") is None

    assert fetch(Family, w.smith).family_name == "Smith"


def test_a_parent_only_changes_their_own_family(smith_parent, login, fetch):
    w = smith_parent

    login(w.jones)
    assert FamilyService.update_settings("Changed", "America/Denver")

    assert fetch(Family, w.jones).family_name == "Changed"
    assert fetch(Family, w.smith).family_name == "Smith"
    assert fetch(Family, w.smith).timezone == "America/Chicago"


# ----- The sidebar -----


def _pages(groups):
    return [page for _, links in groups for page, _, _ in links]


@pytest.mark.parametrize(
    "groups",
    [PARENT_LINKS, STUDENT_LINKS, ADMIN_LINKS, LOGGED_OUT_LINKS],
)
def test_every_link_points_at_a_real_page(groups):
    for page in _pages(groups):
        assert (ROOT / page).is_file(), page


def test_every_parent_page_is_linked_once():
    pages = _pages(PARENT_LINKS)
    expected = {
        f"pages/{path.name}"
        for path in (ROOT / "pages").glob("*.py")
        if not path.stem.endswith(
            ("Landing_Page", "Login", "Register", "Complete_Account", "Forgot_Password")
        )
    }

    assert len(pages) == len(set(pages))
    assert set(pages) == expected


def test_students_dont_get_parent_only_pages():
    pages = " ".join(_pages(STUDENT_LINKS))

    for parent_only in ("Assignments", "Subjects", "Students", "Announcements", "Settings", "Parent_Dashboard"):
        assert parent_only not in pages


def test_groups_are_plan_track_and_family():
    assert [heading for heading, _ in PARENT_LINKS] == [None, "Plan", "Track", "Family"]
    assert [heading for heading, _ in STUDENT_LINKS] == [None, "Plan", "Track"]


# ----- The page -----


@pytest.fixture
def page_as(world):
    def _open(role, student_id=None):
        db = SessionLocal()
        try:
            user = User(
                family_id=world.smith,
                student_id=student_id,
                email=f"{role.lower()}@x.test",
                auth_user_id="00000000-0000-0000-0000-00000000000a",
                role=role,
            )
            db.add(user)
            db.commit()
            user_id = user.id
        finally:
            db.close()

        at = AppTest.from_file(
            str(next((ROOT / "pages").glob("*_Settings.py"))), default_timeout=30
        )
        at.session_state["current_user_id"] = user_id
        return at

    with (
        mock.patch.object(SessionService, "sync_browser", return_value=None),
        mock.patch.object(st, "page_link"),
        mock.patch.object(st, "switch_page") as switch_page,
    ):
        yield _open, switch_page


def _labelled(widgets, label):
    return next(widget for widget in widgets if widget.label == label)


def test_settings_page_shows_and_saves(world, page_as, fetch):
    open_page, _ = page_as
    at = open_page("Parent").run()

    assert not at.exception
    assert _labelled(at.text_input, "Family Name").value == "Smith"
    assert _labelled(at.selectbox, "Time Zone").value == "America/Chicago"

    _labelled(at.text_input, "Family Name").set_value("The Smiths")
    _labelled(at.selectbox, "Time Zone").set_value("America/Denver")
    next(b for b in at.button if b.label == "💾 Save Settings").click().run()

    assert not at.exception
    assert fetch(Family, world.smith).family_name == "The Smiths"
    assert fetch(Family, world.smith).timezone == "America/Denver"
    assert _labelled(at.text_input, "Family Name").value == "The Smiths"


def test_a_blank_name_shows_a_friendly_error(world, page_as, fetch):
    open_page, _ = page_as
    at = open_page("Parent").run()

    _labelled(at.text_input, "Family Name").set_value("  ")
    next(b for b in at.button if b.label == "💾 Save Settings").click().run()

    assert not at.exception
    assert any("family name" in error.value for error in at.error)
    assert fetch(Family, world.smith).family_name == "Smith"


def test_students_are_sent_away_from_settings(world, page_as):
    open_page, switch_page = page_as
    open_page("Student", student_id=world.bob).run()

    assert switch_page.called
