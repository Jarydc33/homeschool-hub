"""
The API (api/): logins, family scoping, and the first student endpoints.
Supabase is never called: tokens are checked by a stand-in.
"""
import json
from types import SimpleNamespace
from unittest import mock

import pytest

from api_support import _auth, _token
from database.db import SessionLocal
from database.models import AssignmentOccurrence, Student, User, UserRole
from services.auth_provider import AuthProvider
from services.current_user import CurrentUser
from services.pairing_service import PairingService
from services.student_mode_service import StudentModeService

PIN = "2468"


# ----- Logging in -----


def test_health_needs_no_login(api):
    assert api.get("/health").json() == {"status": "ok"}


def test_no_login_is_refused(api):
    response = api.get("/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Please log in again."


@pytest.mark.parametrize(
    "header",
    ["Bearer " + _token("nobody"), "Basic abc", "Bearer ", "nonsense"],
)
def test_a_bad_login_is_refused(api, header):
    assert api.get("/me", headers={"Authorization": header}).status_code == 401


def test_supabase_being_down_asks_to_try_again(api):
    with mock.patch.object(
        AuthProvider, "get_auth_user_for_token", side_effect=ConnectionError("down")
    ):
        response = api.get("/me", headers=_auth(_token("smith_parent")))

    assert response.status_code == 503
    assert "try again" in response.json()["detail"]
    assert "down" not in response.json()["detail"]


def test_me_for_a_parent(api, world):
    me = api.get("/me", headers=_auth(_token("smith_parent"))).json()

    assert me["role"] == "parent"
    assert me["family_id"] == world.smith
    assert me["family_name"] == "Smith"
    assert me["student_mode"] is False
    assert me["today"] == world.due.isoformat()


def test_me_for_a_student(api, world):
    me = api.get("/me", headers=_auth(_token("bob"))).json()

    assert me["role"] == "student"
    assert me["student_id"] == world.bob


def test_an_archived_student_cant_log_in(api, world):
    db = SessionLocal()
    try:
        db.get(Student, world.bob).active = False
        db.commit()
    finally:
        db.close()

    assert api.get("/me", headers=_auth(_token("bob"))).status_code == 401


def test_one_request_doesnt_leak_its_user_into_the_next(api):
    assert api.get("/me", headers=_auth(_token("smith_parent"))).status_code == 200
    assert api.get("/me").status_code == 401
    assert CurrentUser.get() is None


# ----- Students -----


def test_a_parent_lists_their_active_students(api):
    students = api.get("/students", headers=_auth(_token("smith_parent"))).json()

    assert {s["name"] for s in students} == {"Ann", "Bob", "Cat"}


def test_a_student_lists_only_themselves(api, world):
    students = api.get("/students", headers=_auth(_token("bob"))).json()

    assert [s["id"] for s in students] == [world.bob]


def test_another_family_cant_see_a_students_dashboard(api, world):
    response = api.get(
        f"/students/{world.ann}/dashboard", headers=_auth(_token("jones_parent"))
    )

    assert response.status_code == 404


def test_a_student_cant_see_a_siblings_dashboard(api, world):
    response = api.get(f"/students/{world.ann}/dashboard", headers=_auth(_token("bob")))

    assert response.status_code == 404


def test_the_dashboard_groups_todays_work(api, world):
    bob = api.get(
        f"/students/{world.bob}/dashboard", headers=_auth(_token("bob"))
    ).json()

    assert [w["title"] for w in bob["today_work"]] == ["Essay"]
    assert bob["today_work"][0]["subject"]["name"] == "Art"
    assert bob["progress"] == {"done": 0, "total": 1}
    assert bob["message"]

    ann = api.get(
        f"/students/{world.ann}/dashboard", headers=_auth(_token("smith_parent"))
    ).json()

    assert [w["title"] for w in ann["completed_today"]] == ["Essay"]
    assert ann["progress"] == {"done": 1, "total": 1}
    # Archived assignments aren't shown.
    assert "Archived" not in json.dumps(ann)


# ----- Checking off work -----


def _status(occurrence_id):
    db = SessionLocal()
    try:
        return db.get(AssignmentOccurrence, occurrence_id).status
    finally:
        db.close()


def test_a_student_checks_off_their_own_work(api, world):
    response = api.put(
        f"/occurrences/{world.bob_essay_day}/completed",
        json={"completed": True},
        headers=_auth(_token("bob")),
    )

    assert response.status_code == 200
    assert response.json()["work"]["completed"] is True
    assert response.json()["work"]["title"] == "Essay"
    # Finishing all of today's work starts a streak, which earns a badge.
    assert response.json()["new_badges"]
    assert all(badge["earned"] for badge in response.json()["new_badges"])
    assert _status(world.bob_essay_day) == "Complete"

    api.put(
        f"/occurrences/{world.bob_essay_day}/completed",
        json={"completed": False},
        headers=_auth(_token("bob")),
    )

    assert _status(world.bob_essay_day) == "Not Started"


def test_a_student_cant_check_off_a_siblings_work(api, world):
    response = api.put(
        f"/occurrences/{world.ann_essay_day}/completed",
        json={"completed": False},
        headers=_auth(_token("bob")),
    )

    assert response.status_code == 404
    assert _status(world.ann_essay_day) == "Complete"


def test_another_family_cant_check_off_work(api, world):
    response = api.put(
        f"/occurrences/{world.bob_essay_day}/completed",
        json={"completed": True},
        headers=_auth(_token("jones_parent")),
    )

    assert response.status_code == 404
    assert _status(world.bob_essay_day) != "Complete"


def test_check_off_needs_a_yes_or_no(api, world):
    response = api.put(
        f"/occurrences/{world.bob_essay_day}/completed",
        json={},
        headers=_auth(_token("bob")),
    )

    assert response.status_code == 422


# ----- Student Mode and paired devices -----


def test_student_mode_follows_the_login_session(api, world):
    parent = SimpleNamespace(
        id=None,
        family_id=world.smith,
        family=None,
        role=UserRole.PARENT.value,
        student_id=None,
    )
    db = SessionLocal()
    try:
        parent.id = (
            db.query(User).filter(User.email == "smith_parent@x.test").one().id
        )
    finally:
        db.close()

    with CurrentUser.acting_as(parent, "session-a"):
        assert StudentModeService.set_pin(PIN, PIN)[0]
        assert StudentModeService.start(world.ann)[0]

    in_mode = api.get("/me", headers=_auth(_token("smith_parent", "session-a"))).json()
    other_login = api.get("/me", headers=_auth(_token("smith_parent", "session-b"))).json()

    assert in_mode["role"] == "student"
    assert in_mode["student_mode"] is True
    assert in_mode["student_id"] == world.ann
    assert other_login["role"] == "parent"

    # In Student Mode, the parent's login can't open another student's work.
    response = api.get(
        f"/students/{world.bob}/dashboard",
        headers=_auth(_token("smith_parent", "session-a")),
    )
    assert response.status_code == 404


def test_a_paired_device_is_its_student(api, world):
    paired = SimpleNamespace(
        family_id=world.smith,
        family=SimpleNamespace(family_name="Smith", timezone="America/Chicago"),
        role=UserRole.STUDENT.value,
        student_id=world.cat,
        id=None,
    )

    with mock.patch.object(PairingService, "find_paired", return_value=paired) as find:
        me = api.get("/me", headers={"X-Device-Token": "device-key"}).json()

    find.assert_called_once_with("device-key")
    assert me["role"] == "student"
    assert me["student_id"] == world.cat


def test_a_login_wins_over_a_device_key(api, world):
    with mock.patch.object(PairingService, "find_paired") as find:
        me = api.get(
            "/me",
            headers={**_auth(_token("smith_parent")), "X-Device-Token": "device-key"},
        ).json()

    find.assert_not_called()
    assert me["role"] == "parent"
