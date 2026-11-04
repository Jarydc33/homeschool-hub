"""The database itself refuses bad rows, even if a service has a bug."""
from datetime import date
from unittest import mock

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.db import SessionLocal, engine
from database.models import (
    Assignment,
    BannerMessage,
    Student,
    StudentAssignment,
    Subject,
    User,
)
from services.assignment_service import AssignmentService


def _save(row):
    db = SessionLocal()
    try:
        db.add(row)
        db.commit()
    finally:
        db.close()


def test_a_student_cant_be_linked_to_an_assignment_twice(world):
    with pytest.raises(IntegrityError):
        _save(StudentAssignment(assignment_id=world.essay, student_id=world.ann))


@pytest.mark.parametrize(
    "make_row",
    [
        lambda w: Student(name="No family"),
        lambda w: Subject(name="No family"),
        lambda w: Assignment(subject_id=w.art, title="No family"),
        lambda w: Assignment(family_id=w.smith, title="No subject"),
        lambda w: StudentAssignment(student_id=w.ann),
        lambda w: StudentAssignment(assignment_id=w.essay),
    ],
    ids=[
        "student-family",
        "subject-family",
        "assignment-family",
        "assignment-subject",
        "link-assignment",
        "link-student",
    ],
)
def test_required_foreign_keys_cant_be_empty(world, make_row):
    with pytest.raises(IntegrityError):
        _save(make_row(world))


def test_admins_and_system_wide_announcements_still_have_no_family():
    _save(
        User(
            email="admin@example.com",
            auth_user_id="00000000-0000-0000-0000-000000000001",
            role="Admin",
        )
    )
    _save(
        BannerMessage(
            title="Maintenance",
            message="Back soon",
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 2),
        )
    )


@pytest.mark.parametrize(
    "table",
    ["users", "students", "subjects", "assignments", "banner_messages"],
)
def test_every_family_id_is_indexed(table):
    indexed = [index["column_names"] for index in inspect(engine).get_indexes(table)]

    assert ["family_id"] in indexed


def test_update_returns_none_if_another_tab_links_the_student_first(
    smith_parent, fetch
):
    w = smith_parent
    clash = IntegrityError("INSERT", {}, Exception("duplicate link"))

    with mock.patch.object(Session, "commit", side_effect=clash):
        updated = AssignmentService.update_assignment(
            assignment_id=w.essay,
            title="Changed",
            description=None,
            due_date=None,
            subject_id=w.art,
            student_ids=[w.ann, w.bob, w.cat],
            assignment_type="One Time",
            recurrence_pattern=None,
        )

    assert updated is None
    assert fetch(Assignment, w.essay).title == "Essay"
