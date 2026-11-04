"""'Today' is the family's local date, not the server's."""
from datetime import date, datetime, timezone
from unittest import mock

import pytest
import streamlit as st

from database.db import SessionLocal
from database.models import Assignment, BannerMessage, Family, StudentAssignment
from services.auth_provider import AuthProvider
from services.auth_service import AuthService
from services.banner_service import BannerService
from services.dashboard_service import DashboardService
from services.family_service import FamilyService

# 2am UTC on Nov 5 is still the evening of Nov 4 in Wisconsin, and already
# morning on Nov 5 in Tokyo.
UTC_NOW = datetime(2026, 11, 5, 2, 0, tzinfo=timezone.utc)
NOV_4 = date(2026, 11, 4)
NOV_5 = date(2026, 11, 5)


class FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return UTC_NOW.astimezone(tz)


@pytest.fixture(autouse=True)
def frozen_clock():
    with mock.patch("services.auth_service.datetime", FrozenDatetime):
        yield


@pytest.fixture
def session_state():
    state = {}
    with (
        mock.patch.object(st, "session_state", state),
        mock.patch.object(AuthProvider, "get_current_auth_user", return_value=None),
    ):
        yield state


def _log_in_new_family(zone, email="pat@x.test", auth_id="00000000-0000-0000-0000-00000000000a"):
    user = FamilyService.create_family_with_parent("Family", email, auth_id, zone)
    AuthService.set_current_user(user.id)
    return user


def _zone_of(family_id):
    db = SessionLocal()
    try:
        return db.get(Family, family_id).timezone
    finally:
        db.close()


@pytest.mark.parametrize(
    "zone, expected",
    [("America/Chicago", NOV_4), ("Asia/Tokyo", NOV_5)],
)
def test_today_is_the_familys_local_date(session_state, zone, expected):
    _log_in_new_family(zone)

    assert AuthService.get_today() == expected


def test_each_family_gets_its_own_today(session_state):
    _log_in_new_family("America/Chicago")
    assert AuthService.get_today() == NOV_4

    _log_in_new_family("Asia/Tokyo", "tokyo@x.test", "00000000-0000-0000-0000-00000000000b")
    assert AuthService.get_today() == NOV_5


def test_no_family_gets_utcs_date(session_state):
    assert AuthService.get_today() == NOV_5


def test_a_bad_stored_zone_falls_back_to_utc(session_state):
    user = _log_in_new_family("America/Chicago")
    db = SessionLocal()
    try:
        db.get(Family, user.family_id).timezone = "Not/AZone"
        db.commit()
    finally:
        db.close()
    AuthService.start_page_run()

    assert AuthService.get_today() == NOV_5


def test_a_new_family_saves_its_zone():
    user = FamilyService.create_family_with_parent(
        "Family", "pat@x.test", "00000000-0000-0000-0000-00000000000a", "Asia/Tokyo"
    )

    assert _zone_of(user.family_id) == "Asia/Tokyo"


def test_an_unknown_zone_at_sign_up_uses_the_default():
    user = FamilyService.create_family_with_parent(
        "Family", "pat@x.test", "00000000-0000-0000-0000-00000000000a", "Not/AZone"
    )

    assert _zone_of(user.family_id) == "America/Chicago"


def test_dropdown_lists_common_zones_first():
    choices = FamilyService.timezone_choices()

    assert choices[:2] == ["America/New_York", "America/Chicago"]
    assert "Asia/Tokyo" in choices
    assert len(choices) == len(set(choices))
    assert FamilyService.timezone_label("America/Chicago") == "US Central (America/Chicago)"
    assert FamilyService.timezone_label("Asia/Tokyo") == "Asia/Tokyo"


@pytest.mark.parametrize(
    "browser, expected",
    [
        ("Asia/Tokyo", "Asia/Tokyo"),
        (None, "America/Chicago"),
        ("Not/AZone", "America/Chicago"),
    ],
)
def test_browser_zone_is_preselected_when_known(browser, expected):
    assert FamilyService.preferred_timezone(browser) == expected


def test_dashboard_sorts_work_by_the_familys_today(world, login):
    db = SessionLocal()
    try:
        for title, due in (("Due Nov 4", NOV_4), ("Due Nov 5", NOV_5)):
            assignment = Assignment(
                family_id=world.smith, subject_id=world.art, title=title, due_date=due
            )
            db.add(assignment)
            db.flush()
            db.add(StudentAssignment(assignment_id=assignment.id, student_id=world.ann))
        db.commit()
    finally:
        db.close()
    login(world.smith)

    data = DashboardService.get_dashboard_data()

    assert data["today"] == NOV_4
    assert [a.title for a in data["today_assignments"]] == ["Due Nov 4"]


def test_a_banner_starting_tomorrow_stays_hidden_in_the_familys_evening(world, login):
    db = SessionLocal()
    try:
        db.add(
            BannerMessage(
                family_id=world.smith,
                title="Tomorrow",
                message="Soon",
                start_date=NOV_5,
                end_date=NOV_5,
            )
        )
        db.commit()
    finally:
        db.close()
    login(world.smith)

    assert BannerService.get_active_banners() == []
