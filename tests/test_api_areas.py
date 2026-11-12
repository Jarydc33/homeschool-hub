"""
The API's areas beyond logging in: each works for the right people, refuses
students where it's parents only, and never reaches another family's data.

The api fixture's people: smith_parent, bob (a Smith student), and
jones_parent. Today is world.due.
"""
from datetime import date, timedelta
from types import SimpleNamespace
from unittest import mock

import pytest

from api_support import as_
from services.account_service import AccountService
from services.auth_provider import AuthProvider

PIN = "2468"

SMITH = as_("smith_parent")
BOB = as_("bob")
JONES = as_("jones_parent")


# ----- Parent dashboard and banners -----


def test_parent_dashboard(api, world):
    data = api.get("/dashboard", headers=SMITH).json()

    assert {m["student"]["name"] for m in data["students"]} == {"Ann", "Bob", "Cat"}
    assert [w["title"] for w in data["due_today"]] == ["Essay"]
    # Everyone it's due for today; Bob hasn't finished, so it's listed.
    assert data["due_today"][0]["student_names"] == ["Ann", "Bob"]
    assert data["today"] == world.due.isoformat()
    assert data["message"]
    assert data["has_curriculum"] is False
    assert data["upcoming_events"] == []


def test_students_cant_open_the_parent_dashboard(api):
    response = api.get("/dashboard", headers=BOB)

    assert response.status_code == 403
    assert response.json()["detail"] == "Only a parent can do this."


def test_the_student_dashboard_has_everything(api, world):
    data = api.get(f"/students/{world.bob}/dashboard", headers=BOB).json()

    for key in ("achievements", "reading", "pe", "upcoming_events", "banners"):
        assert key in data
    assert data["achievements"]["badges"]


# ----- Students -----


def test_parent_manages_students(api, world):
    created = api.post("/students", json={"name": "  Dee ", "grade_level": "2"}, headers=SMITH)
    assert created.status_code == 201
    dee = created.json()
    assert dee["name"] == "Dee"

    renamed = api.put(f"/students/{dee['id']}", json={"name": "Deedee"}, headers=SMITH)
    assert renamed.json()["name"] == "Deedee"

    assert api.post(f"/students/{dee['id']}/archive", headers=SMITH).status_code == 200
    assert "Deedee" not in {s["name"] for s in api.get("/students", headers=SMITH).json()}
    assert "Deedee" in {s["name"] for s in api.get("/students/archived", headers=SMITH).json()}

    assert api.post(f"/students/{dee['id']}/restore", headers=SMITH).status_code == 200
    assert "Deedee" in {s["name"] for s in api.get("/students", headers=SMITH).json()}


def test_a_blank_student_name_is_refused(api):
    assert api.post("/students", json={"name": "   "}, headers=SMITH).status_code == 422


def test_students_cant_manage_students(api, world):
    assert api.post("/students", json={"name": "Sneaky"}, headers=BOB).status_code == 403
    assert api.put(f"/students/{world.bob}", json={"name": "X"}, headers=BOB).status_code == 403


def test_another_family_cant_change_a_student(api, world, fetch):
    from database.models import Student

    assert api.put(f"/students/{world.ann}", json={"name": "Hacked"}, headers=JONES).status_code == 404
    assert api.post(f"/students/{world.ann}/archive", headers=JONES).status_code == 404
    assert fetch(Student, world.ann).name == "Ann"
    assert fetch(Student, world.ann).active


def test_student_login_invite(api, world):
    assert api.get(f"/students/{world.ann}/login", headers=SMITH).json() == {"email": None}

    invite = SimpleNamespace(user=SimpleNamespace(id="00000000-0000-0000-0000-0000000000b1"))

    with mock.patch.object(AuthProvider, "create_student_account", return_value=invite):
        response = api.post(
            f"/students/{world.ann}/login", json={"email": "Ann@X.test"}, headers=SMITH
        )

    assert response.status_code == 200
    assert api.get(f"/students/{world.ann}/login", headers=SMITH).json() == {
        "email": "ann@x.test"
    }


def test_a_bad_invite_email_is_explained(api, world):
    response = api.post(f"/students/{world.ann}/login", json={"email": "nope"}, headers=SMITH)

    assert response.status_code == 400
    assert response.json()["detail"] == "Please enter a valid email address."


def test_another_family_cant_invite_a_student(api, world):
    with mock.patch.object(AuthProvider, "create_student_account") as create:
        response = api.post(
            f"/students/{world.ann}/login", json={"email": "x@x.test"}, headers=JONES
        )

    assert response.status_code == 404
    create.assert_not_called()


# ----- Subjects -----


def test_parent_manages_subjects(api):
    subjects = api.get("/subjects", headers=SMITH).json()
    assert {s["name"]: s["assignment_count"] for s in subjects} == {"Art": 1, "Math": 0}

    science = api.post("/subjects", json={"name": "Science", "color": "#336699"}, headers=SMITH).json()
    assert science["color"] == "#336699"

    api.post(f"/subjects/{science['id']}/archive", headers=SMITH)
    assert "Science" in {s["name"] for s in api.get("/subjects/archived", headers=SMITH).json()}

    api.post(f"/subjects/{science['id']}/restore", headers=SMITH)
    assert "Science" in {s["name"] for s in api.get("/subjects", headers=SMITH).json()}


def test_students_can_list_but_not_change_subjects(api, world):
    assert api.get("/subjects", headers=BOB).status_code == 200
    assert api.post("/subjects", json={"name": "X"}, headers=BOB).status_code == 403


def test_another_family_cant_change_a_subject(api, world):
    assert api.put(f"/subjects/{world.math}", json={"name": "X"}, headers=JONES).status_code == 404
    assert "Math" not in {s["name"] for s in api.get("/subjects", headers=JONES).json()}


# ----- Assignments -----


def _one_time(world, **changes):
    body = {
        "title": "Worksheet",
        "subject_id": world.math,
        "student_ids": [world.ann, world.bob],
        "assignment_type": "One Time",
        "due_date": world.due.isoformat(),
    }
    body.update(changes)
    return body


def test_parent_creates_and_edits_an_assignment(api, world):
    created = api.post("/assignments", json=_one_time(world), headers=SMITH)
    assert created.status_code == 201
    work = created.json()
    assert {s["name"] for s in work["students"]} == {"Ann", "Bob"}
    assert work["progress"] == {"done": 0, "total": 2}

    # Bob sees it today.
    bob = api.get(f"/students/{world.bob}/dashboard", headers=BOB).json()
    assert "Worksheet" in {w["title"] for w in bob["today_work"]}

    edited = api.put(
        f"/assignments/{work['id']}",
        json=_one_time(world, title="Worksheet 2", student_ids=[world.ann]),
        headers=SMITH,
    ).json()
    assert edited["title"] == "Worksheet 2"
    assert [s["name"] for s in edited["students"]] == ["Ann"]


def test_a_bad_schedule_is_explained(api, world):
    response = api.post(
        "/assignments",
        json=_one_time(world, assignment_type="Recurring", recurrence_pattern=None),
        headers=SMITH,
    )

    assert response.status_code == 400
    assert isinstance(response.json()["detail"], str)


def test_a_curriculum_gets_its_lessons(api, world):
    monday = world.due - timedelta(days=world.due.weekday())

    work = api.post(
        "/assignments",
        json=_one_time(
            world,
            title="Math book",
            assignment_type="Curriculum",
            recurrence_pattern="Mon,Wed,Fri",
            due_date=monday.isoformat(),
            lesson_count=6,
            student_ids=[world.ann],
        ),
        headers=SMITH,
    ).json()

    assert work["lesson_count"] == 6
    assert work["finish_date"] == (monday + timedelta(days=11)).isoformat()


def test_archive_and_restore_an_assignment(api, world):
    assert api.post(f"/assignments/{world.essay}/archive", headers=SMITH).status_code == 200
    assert "Essay" not in {a["title"] for a in api.get("/assignments", headers=SMITH).json()}
    assert "Essay" in {a["title"] for a in api.get("/assignments/archived", headers=SMITH).json()}

    restored = api.post(f"/assignments/{world.essay}/restore", headers=SMITH)
    assert restored.json()["title"] == "Essay"


def test_notes_for_a_date(api, world):
    rows = api.get(f"/assignments/{world.essay}/notes", headers=SMITH).json()
    assert {r["student"]["name"] for r in rows} == {"Ann", "Bob"}

    saved = api.put(
        f"/assignments/{world.essay}/notes",
        json={"date": world.due.isoformat(), "student_ids": [world.bob], "note": "Neat work"},
        headers=SMITH,
    )
    assert saved.status_code == 200

    bob = api.get(f"/students/{world.bob}/dashboard", headers=BOB).json()
    assert bob["today_work"][0]["notes"] == "Neat work"


def test_assignments_are_for_parents(api, world):
    assert api.get("/assignments", headers=BOB).status_code == 403
    assert api.post("/assignments", json=_one_time(world), headers=BOB).status_code == 403


def test_another_family_cant_reach_an_assignment(api, world):
    assert api.get(f"/assignments/{world.essay}", headers=JONES).status_code == 404
    assert api.post(f"/assignments/{world.essay}/archive", headers=JONES).status_code == 404
    assert api.get(f"/assignments/{world.essay}/notes", headers=JONES).json() == []
    # Nor use the Smiths' subject or students in their own.
    response = api.post("/assignments", json=_one_time(world), headers=JONES)
    assert response.status_code == 400


def test_missed_day_info(api):
    info = api.get("/assignments/missed-day", headers=SMITH).json()

    assert info == {"has_curriculum": False, "students_behind": []}


def test_missed_day_cant_resume_in_the_past(api, world):
    response = api.post(
        "/assignments/missed-day",
        json={"student_ids": [world.ann], "resume_on": (world.due - timedelta(days=1)).isoformat()},
        headers=SMITH,
    )

    assert response.status_code == 400


# ----- Events and the calendar -----


def _event(world, **changes):
    body = {"title": "Field trip", "start_date": world.due.isoformat()}
    body.update(changes)
    return body


def test_events_for_the_whole_family_and_one_student(api, world):
    family_event = api.post("/events", json=_event(world), headers=SMITH)
    assert family_event.status_code == 201
    assert family_event.json()["audience"] == "Whole family"

    api.post(
        "/events",
        json=_event(world, title="Ann's lesson", student_ids=[world.ann]),
        headers=SMITH,
    )

    bob_sees = {e["event"]["title"] for e in api.get("/events", headers=BOB).json()["upcoming"]}
    parent_sees = {e["event"]["title"] for e in api.get("/events", headers=SMITH).json()["upcoming"]}

    assert bob_sees == {"Field trip"}
    assert parent_sees == {"Field trip", "Ann's lesson"}


def test_an_event_ending_before_it_starts_is_explained(api, world):
    response = api.post(
        "/events",
        json=_event(world, end_date=(world.due - timedelta(days=1)).isoformat()),
        headers=SMITH,
    )

    assert response.status_code == 400


def test_events_are_changed_only_by_their_familys_parents(api, world):
    event = api.post("/events", json=_event(world), headers=SMITH).json()

    assert api.post("/events", json=_event(world), headers=BOB).status_code == 403
    assert api.get(f"/events/{event['id']}", headers=JONES).status_code == 404
    assert api.put(f"/events/{event['id']}", json=_event(world), headers=JONES).status_code == 400
    assert api.post(f"/events/{event['id']}/archive", headers=JONES).status_code == 404
    assert api.get("/events", headers=JONES).json()["upcoming"] == []

    assert api.post(f"/events/{event['id']}/archive", headers=SMITH).status_code == 200
    assert api.get("/events", headers=SMITH).json()["upcoming"] == []


def test_the_calendar(api, world):
    days = api.get(
        "/calendar",
        params={"first": world.due.isoformat(), "last": world.due.isoformat()},
        headers=BOB,
    ).json()

    assert [d["date"] for d in days] == [world.due.isoformat()]
    assert [i["title"] for i in days[0]["items"]] == ["Essay"]


@pytest.mark.parametrize("span", [-1, 63])
def test_the_calendar_refuses_bad_ranges(api, world, span):
    response = api.get(
        "/calendar",
        params={"first": world.due.isoformat(), "last": (world.due + timedelta(days=span)).isoformat()},
        headers=SMITH,
    )

    assert response.status_code == 400


def test_another_family_sees_nothing_on_the_calendar(api, world):
    days = api.get(
        "/calendar",
        params={"first": world.due.isoformat(), "last": world.due.isoformat()},
        headers=JONES,
    ).json()

    assert "Essay" not in str(days)


# ----- Reading -----


def test_a_student_tracks_their_reading(api, world):
    book = api.post(
        f"/students/{world.bob}/books",
        json={"title": "Charlotte's Web", "total_pages": 184},
        headers=BOB,
    )
    assert book.status_code == 201
    book_id = book.json()["id"]

    assert api.put(
        f"/books/{book_id}/pages/{world.due.isoformat()}", json={"pages": 20}, headers=BOB
    ).status_code == 200

    shelf = api.get(f"/students/{world.bob}/books", headers=BOB).json()
    assert shelf["books"][0]["pages_read"] == 20
    assert shelf["books"][0]["pages_today"] == 20
    assert shelf["summary"]["pages_this_week"] >= 20

    finished = api.put(f"/books/{book_id}/finished", json={"finished": True}, headers=BOB)
    assert finished.json()["finished_on"] == world.due.isoformat()


def test_reading_stays_with_its_student_and_family(api, world):
    book_id = api.post(
        f"/students/{world.bob}/books", json={"title": "Mine"}, headers=BOB
    ).json()["id"]

    # Bob can't add to his sister's shelf, and the Jones can't see or change his.
    assert api.post(f"/students/{world.ann}/books", json={"title": "X"}, headers=BOB).status_code == 400
    assert api.get(f"/students/{world.bob}/books", headers=JONES).json()["books"] == []
    assert api.post(f"/books/{book_id}/archive", headers=JONES).status_code == 404
    assert api.put(
        f"/books/{book_id}/pages/{world.due.isoformat()}", json={"pages": 5}, headers=JONES
    ).status_code == 400


def test_pages_cant_be_logged_for_the_future(api, world):
    book_id = api.post(
        f"/students/{world.bob}/books", json={"title": "Mine"}, headers=BOB
    ).json()["id"]

    tomorrow = (world.due + timedelta(days=1)).isoformat()

    assert api.put(f"/books/{book_id}/pages/{tomorrow}", json={"pages": 5}, headers=BOB).status_code == 400


# ----- P.E. -----


def test_a_student_logs_and_deletes_activity(api, world):
    saved = api.post(
        "/pe",
        json={"student_ids": [world.bob], "date": world.due.isoformat(), "activity": "Bike", "minutes": 30},
        headers=BOB,
    )
    assert saved.json() == {"saved": 1}

    log = api.get(f"/students/{world.bob}/pe", headers=BOB).json()
    assert log["summary"]["total_minutes"] == 30
    assert log["known_activities"] == ["Bike"]

    log_id = log["logs"][0]["id"]
    assert api.delete(f"/pe/{log_id}", headers=JONES).status_code == 404
    assert api.delete(f"/pe/{log_id}", headers=BOB).status_code == 200


def test_pe_stays_within_the_family(api, world):
    body = {"student_ids": [world.ann], "date": world.due.isoformat(), "activity": "Run", "minutes": 10}

    assert api.post("/pe", json=body, headers=BOB).status_code == 400
    assert api.post("/pe", json=body, headers=JONES).status_code == 400
    assert api.post("/pe", json=body, headers=SMITH).status_code == 201


def test_bad_minutes_are_explained(api, world):
    response = api.post(
        "/pe",
        json={"student_ids": [world.bob], "date": world.due.isoformat(), "activity": "Run", "minutes": 0},
        headers=BOB,
    )

    assert response.status_code == 400


# ----- Grades -----


def _graded_essay(api, world):
    from database.db import SessionLocal
    from database.models import Assignment

    db = SessionLocal()
    try:
        db.get(Assignment, world.essay).graded = True
        db.commit()
    finally:
        db.close()


def test_parent_grades_and_student_sees_it(api, world):
    _graded_essay(api, world)

    queue = api.get(f"/students/{world.ann}/grading", headers=SMITH).json()
    assert [w["title"] for w in queue["finished"]] == ["Essay"]

    saved = api.put(
        f"/occurrences/{world.ann_essay_day}/grade",
        json={"score": 18, "points_possible": 20},
        headers=SMITH,
    )
    assert saved.status_code == 200

    report = api.get(f"/students/{world.ann}/grades", headers=SMITH).json()
    assert report["overall"] == {"percent": 90.0, "letter": "A"}
    assert report["subjects"] == [{"subject": "Art", "grade": {"percent": 90.0, "letter": "A"}}]

    assert api.delete(f"/occurrences/{world.ann_essay_day}/grade", headers=SMITH).status_code == 200
    assert api.get(f"/students/{world.ann}/grades", headers=SMITH).json()["overall"] is None


def test_a_score_over_the_total_is_explained(api, world):
    _graded_essay(api, world)

    response = api.put(
        f"/occurrences/{world.ann_essay_day}/grade",
        json={"score": 1000, "points_possible": 20},
        headers=SMITH,
    )

    assert response.status_code == 400


def test_grading_is_for_parents_of_the_family(api, world):
    _graded_essay(api, world)
    body = {"score": 20, "points_possible": 20}

    assert api.put(f"/occurrences/{world.bob_essay_day}/grade", json=body, headers=BOB).status_code == 403
    assert api.put(f"/occurrences/{world.ann_essay_day}/grade", json=body, headers=JONES).status_code == 404
    assert api.get(f"/students/{world.ann}/grades", headers=JONES).status_code == 404
    assert api.get(f"/students/{world.ann}/grades", headers=BOB).status_code == 404


def test_grading_periods(api, world):
    start = date(2026, 8, 1)

    fall = api.post(
        "/grading-periods",
        json={"name": "Fall", "start_date": start.isoformat(), "end_date": date(2026, 12, 31).isoformat()},
        headers=SMITH,
    )
    assert fall.status_code == 201

    overlap = api.post(
        "/grading-periods",
        json={"name": "Overlap", "start_date": date(2026, 12, 1).isoformat(), "end_date": date(2027, 1, 31).isoformat()},
        headers=SMITH,
    )
    assert overlap.status_code == 400

    assert [p["name"] for p in api.get("/grading-periods", headers=BOB).json()] == ["Fall"]
    assert api.get("/grading-periods", headers=JONES).json() == []
    assert api.post(f"/grading-periods/{fall.json()['id']}/archive", headers=JONES).status_code == 404
    assert api.post(f"/grading-periods/{fall.json()['id']}/archive", headers=SMITH).status_code == 200


# ----- Family settings, Student Mode and devices -----


def test_family_settings(api):
    assert api.get("/family", headers=SMITH).json()["family_name"] == "Smith"

    saved = api.put(
        "/family", json={"family_name": "The Smiths", "timezone": "America/Denver"}, headers=SMITH
    )
    assert saved.json()["timezone"] == "America/Denver"

    bad = api.put("/family", json={"family_name": "X", "timezone": "Mars/Base"}, headers=SMITH)
    assert bad.status_code == 400

    assert api.get("/family", headers=BOB).status_code == 403
    assert api.get("/family", headers=JONES).json()["family_name"] == "Jones"


def test_timezones_need_no_login(api):
    zones = api.get("/timezones").json()

    assert zones and {"name", "label"} <= set(zones[0])


def test_student_mode_with_the_pin(api, world):
    no_pin = api.post("/student-mode", json={"student_id": world.ann}, headers=SMITH)
    assert no_pin.status_code == 400

    assert api.put("/family/pin", json={"pin": PIN, "confirm_pin": "1111"}, headers=SMITH).status_code == 400
    assert api.put("/family/pin", json={"pin": PIN, "confirm_pin": PIN}, headers=SMITH).status_code == 200

    assert api.post("/student-mode", json={"student_id": world.ann}, headers=SMITH).status_code == 200
    assert api.get("/me", headers=SMITH).json()["role"] == "student"

    # Parent-only things are closed while it's on.
    assert api.get("/dashboard", headers=SMITH).status_code == 403

    assert api.post("/student-mode/exit", json={"pin": "0000"}, headers=SMITH).status_code == 400
    assert api.post("/student-mode/exit", json={"pin": PIN}, headers=SMITH).status_code == 200
    assert api.get("/me", headers=SMITH).json()["role"] == "parent"


def test_logging_out_ends_student_mode_without_the_pin(api, world):
    api.put("/family/pin", json={"pin": PIN, "confirm_pin": PIN}, headers=SMITH)
    api.post("/student-mode", json={"student_id": world.ann}, headers=SMITH)

    assert api.post("/logout", headers=SMITH).status_code == 200
    assert api.get("/me", headers=SMITH).json()["role"] == "parent"


def test_pairing_a_device(api, world):
    api.put("/family/pin", json={"pin": PIN, "confirm_pin": PIN}, headers=SMITH)

    code = api.post(f"/students/{world.cat}/pairing-code", headers=SMITH).json()["code"]

    token = api.post("/pairing/redeem", json={"code": code}).json()["device_token"]
    device = {"X-Device-Token": token}

    me = api.get("/me", headers=device).json()
    assert me["role"] == "student"
    assert me["student_id"] == world.cat
    assert me["paired_device"] is True

    devices = api.get("/family/devices", headers=SMITH).json()
    assert [d["student"]["name"] for d in devices] == ["Cat"]
    assert api.get("/family/devices", headers=JONES).json() == []

    assert api.post("/pairing/unpair", json={"pin": "0000"}, headers=device).status_code == 400
    assert api.post("/pairing/unpair", json={"pin": PIN}, headers=device).status_code == 200
    assert api.get("/me", headers=device).status_code == 401


def test_a_code_works_once(api, world):
    api.put("/family/pin", json={"pin": PIN, "confirm_pin": PIN}, headers=SMITH)
    code = api.post(f"/students/{world.cat}/pairing-code", headers=SMITH).json()["code"]

    assert api.post("/pairing/redeem", json={"code": code}).status_code == 200
    assert api.post("/pairing/redeem", json={"code": code}).status_code == 400


def test_wrong_codes_are_limited_per_device(api):
    from services.pairing_service import SESSION_GUESSES, TOO_MANY_GUESSES_MESSAGE

    for _ in range(SESSION_GUESSES):
        api.post("/pairing/redeem", json={"code": "000000"})

    response = api.post("/pairing/redeem", json={"code": "000000"})

    assert response.json()["detail"] == TOO_MANY_GUESSES_MESSAGE


def test_another_family_cant_pair_or_end_devices(api, world):
    api.put("/family/pin", json={"pin": PIN, "confirm_pin": PIN}, headers=JONES)

    assert api.post(f"/students/{world.cat}/pairing-code", headers=JONES).status_code == 400

    api.put("/family/pin", json={"pin": PIN, "confirm_pin": PIN}, headers=SMITH)
    api.post(f"/students/{world.cat}/pairing-code", headers=SMITH)
    code = api.post(f"/students/{world.cat}/pairing-code", headers=SMITH).json()["code"]
    api.post("/pairing/redeem", json={"code": code})
    device_id = api.get("/family/devices", headers=SMITH).json()[0]["id"]

    assert api.post(f"/family/devices/{device_id}/end", headers=JONES).status_code == 404
    assert api.post(f"/family/devices/{device_id}/end", headers=SMITH).status_code == 200


# ----- Announcements -----


def _banner(world, **changes):
    body = {
        "title": "Co-op",
        "message": "Friday at 10",
        "start_date": world.due.isoformat(),
        "end_date": (world.due + timedelta(days=7)).isoformat(),
    }
    body.update(changes)
    return body


def test_family_announcements(api, world):
    created = api.post("/announcements", json=_banner(world), headers=SMITH)
    assert created.status_code == 201
    banner = created.json()
    assert banner["system_wide"] is False

    assert "Co-op" in {b["title"] for b in api.get("/banners", headers=BOB).json()}
    assert "Co-op" not in {b["title"] for b in api.get("/banners", headers=JONES).json()}

    assert api.post("/announcements", json=_banner(world), headers=BOB).status_code == 403
    assert api.put(
        f"/announcements/{banner['id']}", json=_banner(world, title="X"), headers=JONES
    ).status_code == 404

    backwards = _banner(world, end_date=(world.due - timedelta(days=1)).isoformat())
    assert api.post("/announcements", json=backwards, headers=SMITH).status_code == 400

    assert api.post(f"/announcements/{banner['id']}/archive", headers=SMITH).status_code == 200
    assert "Co-op" not in {b["title"] for b in api.get("/banners", headers=BOB).json()}


# ----- Signing up -----


def test_register(api):
    session = SimpleNamespace(access_token="access", refresh_token="refresh")

    with mock.patch.object(
        AccountService, "register_parent", return_value=(object(), session, None)
    ) as register:
        response = api.post(
            "/register",
            json={
                "family_name": "Lee",
                "email": "lee@x.test",
                "password": "long enough",
                "timezone": "Not/AZone",
            },
        )

    assert response.status_code == 201
    assert response.json() == {
        "confirm_email": False,
        "access_token": "access",
        "refresh_token": "refresh",
    }
    # An unknown time zone falls back to the default.
    assert register.call_args.args[3] == "America/Chicago"


def test_register_with_email_confirmation(api):
    with mock.patch.object(AccountService, "register_parent", return_value=(object(), None, None)):
        response = api.post(
            "/register",
            json={"family_name": "Lee", "email": "lee@x.test", "password": "long enough"},
        )

    assert response.json()["confirm_email"] is True


def test_register_explains_problems(api):
    short = api.post(
        "/register", json={"family_name": "Lee", "email": "lee@x.test", "password": "short"}
    )
    assert short.status_code == 400

    with mock.patch.object(
        AccountService, "register_parent", return_value=(None, None, "This email already has an account.")
    ):
        taken = api.post(
            "/register",
            json={"family_name": "Lee", "email": "lee@x.test", "password": "long enough"},
        )

    assert taken.json()["detail"] == "This email already has an account."


def test_missed_day_moves_a_behind_curriculum(api, world):
    # A Mon/Wed/Fri curriculum that started two weeks ago, with nothing done.
    start = world.due - timedelta(days=14)
    start -= timedelta(days=start.weekday())

    api.post(
        "/assignments",
        json=_one_time(
            world,
            title="Math book",
            assignment_type="Curriculum",
            recurrence_pattern="Mon,Wed,Fri",
            due_date=start.isoformat(),
            lesson_count=10,
            student_ids=[world.ann],
        ),
        headers=SMITH,
    )

    info = api.get("/assignments/missed-day", headers=SMITH).json()
    assert info == {"has_curriculum": True, "students_behind": [world.ann]}

    plan = api.get(
        "/assignments/missed-day/plan",
        params={"student_ids": [world.ann], "resume_on": world.due.isoformat()},
        headers=SMITH,
    ).json()
    assert [step["title"] for step in plan] == ["Math book"]
    assert plan[0]["next_lesson"] == 1

    moved = api.post(
        "/assignments/missed-day",
        json={"student_ids": [world.ann], "resume_on": world.due.isoformat()},
        headers=SMITH,
    )
    assert moved.json()["lessons_moved"] == 10
    assert api.get("/assignments/missed-day", headers=SMITH).json()["students_behind"] == []

    # The Jones can't move the Smiths' lessons.
    assert api.post(
        "/assignments/missed-day",
        json={"student_ids": [world.ann], "resume_on": world.due.isoformat()},
        headers=JONES,
    ).json() == {"lessons_moved": 0}
