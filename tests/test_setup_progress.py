"""
The Parent Dashboard's Getting Started checklist: each step ticks from what
the family has actually done, and never from another family's data.
"""
from api_support import as_
from database.db import SessionLocal
from database.models import (
    DeviceMode,
    DeviceSession,
    Family,
    Student,
    Subject,
    User,
    UserRole,
)
from services.dashboard_service import DashboardService


def _progress():
    return DashboardService.get_setup_progress(
        DashboardService.get_dashboard_data()
    )


def _new_family():
    db = SessionLocal()
    try:
        family = Family(family_name="New")
        db.add(family)
        db.commit()
        return family.id
    finally:
        db.close()


def _add(row):
    db = SessionLocal()
    try:
        db.add(row)
        db.commit()
    finally:
        db.close()


def test_a_new_family_has_done_nothing(world, login):
    login(_new_family())

    assert _progress() == {
        "students": False,
        "subjects": False,
        "work": False,
        "kids": False,
    }


def test_archived_rows_dont_count(world, login):
    family_id = _new_family()
    db = SessionLocal()
    try:
        db.add_all(
            [
                Student(family_id=family_id, name="Gone", active=False),
                Subject(family_id=family_id, name="Old", active=False),
            ]
        )
        db.commit()
    finally:
        db.close()

    login(family_id)

    progress = _progress()
    assert progress["students"] is False
    assert progress["subjects"] is False


def test_planning_steps_tick_from_the_familys_data(smith_parent):
    progress = _progress()

    assert progress["students"] is True
    assert progress["subjects"] is True
    assert progress["work"] is True


def test_kids_step_ticks_with_a_pin(world, login):
    login(world.jones)
    assert _progress()["kids"] is False

    db = SessionLocal()
    try:
        db.get(Family, world.jones).parent_pin_hash = "not-a-real-hash"
        db.commit()
    finally:
        db.close()

    assert _progress()["kids"] is True


def test_kids_step_ticks_with_a_device(world, login):
    db = SessionLocal()
    try:
        parent = User(
            family_id=world.jones,
            email="jones@x.test",
            auth_user_id="00000000-0000-0000-0000-0000000000b1",
            role=UserRole.PARENT.value,
        )
        db.add(parent)
        db.commit()
        parent_id = parent.id
    finally:
        db.close()

    _add(
        DeviceSession(
            family_id=world.jones,
            student_id=world.jones_kid,
            mode=DeviceMode.PAIRED.value,
            token_hash="abc",
            created_by=parent_id,
        )
    )
    login(world.jones)

    assert _progress()["kids"] is True


def test_kids_step_ticks_with_a_student_login(world, login):
    _add(
        User(
            family_id=world.jones,
            student_id=world.jones_kid,
            email="kid@x.test",
            auth_user_id="00000000-0000-0000-0000-0000000000b2",
            role=UserRole.STUDENT.value,
        )
    )
    login(world.jones)

    assert _progress()["kids"] is True


def test_another_familys_setup_doesnt_count(world, login):
    # The Smiths have a PIN and a student login; the Joneses have neither.
    db = SessionLocal()
    try:
        db.get(Family, world.smith).parent_pin_hash = "not-a-real-hash"
        db.add(
            User(
                family_id=world.smith,
                student_id=world.ann,
                email="ann@x.test",
                auth_user_id="00000000-0000-0000-0000-0000000000b3",
                role=UserRole.STUDENT.value,
            )
        )
        db.commit()
    finally:
        db.close()

    login(world.jones)

    assert _progress()["kids"] is False


def test_the_dashboard_endpoint_reports_setup(api, world):
    # The api fixture gives the Smiths a student login (Bob); not the Joneses.
    smith = api.get("/dashboard", headers=as_("smith_parent")).json()["setup"]
    jones = api.get("/dashboard", headers=as_("jones_parent")).json()["setup"]

    assert smith == {"students": True, "subjects": True, "work": True, "kids": True}
    assert jones == {"students": True, "subjects": True, "work": True, "kids": False}
