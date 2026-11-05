"""Parents can bring back archived subjects and assignments, with everything
they had."""
from pathlib import Path
from unittest import mock

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from database.db import SessionLocal
from database.models import Assignment, AssignmentOccurrence, Subject, User, UserRole
from services.assignment_service import AssignmentService
from services.session_service import SessionService
from services.subject_service import SubjectService

ROOT = Path(__file__).resolve().parent.parent


# ----- Subjects -----


def test_archived_subjects_are_listed_by_name(smith_parent):
    assert [s.name for s in SubjectService.get_archived_subjects()] == [
        "Old",
        "Older",
    ]


def test_restoring_a_subject_makes_it_choosable_again(smith_parent, fetch):
    w = smith_parent

    assert SubjectService.restore_subject(w.old_subject)

    assert fetch(Subject, w.old_subject).active is True
    assert "Old" in [s.name for s in SubjectService.get_current_family_subjects()]
    assert "Old" not in [s.name for s in SubjectService.get_archived_subjects()]


# ----- Assignments -----


def test_archived_assignments_are_listed(smith_parent):
    assert [a.title for a in AssignmentService.get_archived_assignments()] == [
        "Archived"
    ]


def test_restoring_brings_back_check_offs_notes_and_grades(smith_parent, fetch):
    w = smith_parent

    AssignmentService.archive_assignment(w.essay)

    assert w.essay not in [
        a.id for a in AssignmentService.get_current_family_assignments()
    ]

    assert AssignmentService.restore_assignment(w.essay)

    assert fetch(Assignment, w.essay).active is True
    assert w.essay in [
        a.id for a in AssignmentService.get_current_family_assignments()
    ]

    row = fetch(AssignmentOccurrence, w.ann_essay_day)
    assert row.status == "Complete"
    assert row.completed_at == w.done_at
    assert row.notes == "Well done"


# ----- Who can do what -----


def test_one_family_cant_see_or_restore_anothers(smith_parent, login, fetch):
    w = smith_parent

    login(w.jones)

    assert SubjectService.get_archived_subjects() == []
    assert AssignmentService.get_archived_assignments() == []
    assert SubjectService.restore_subject(w.old_subject) is None
    assert AssignmentService.restore_assignment(w.archived) is None
    assert fetch(Subject, w.old_subject).active is False
    assert fetch(Assignment, w.archived).active is False


@pytest.mark.parametrize("role", [UserRole.STUDENT, UserRole.ADMIN])
def test_students_and_admins_cant_restore(smith_parent, login, fetch, role):
    w = smith_parent

    if role == UserRole.STUDENT:
        login(w.smith, role=role, student_id=w.ann)
    else:
        login(None, role=role)

    assert SubjectService.get_archived_subjects() == []
    assert AssignmentService.get_archived_assignments() == []
    assert SubjectService.restore_subject(w.old_subject) is None
    assert AssignmentService.restore_assignment(w.archived) is None
    assert fetch(Subject, w.old_subject).active is False
    assert fetch(Assignment, w.archived).active is False


# ----- The pages -----


@pytest.fixture
def parent_page(world):
    db = SessionLocal()
    try:
        user = User(
            family_id=world.smith,
            email="pat@smith.test",
            auth_user_id="00000000-0000-0000-0000-00000000000a",
            role="Parent",
        )
        db.add(user)
        db.commit()
        user_id = user.id
    finally:
        db.close()

    def _open(name):
        at = AppTest.from_file(
            str(next((ROOT / "pages").glob(f"*_{name}.py"))), default_timeout=30
        )
        at.session_state["current_user_id"] = user_id
        return at

    with (
        mock.patch.object(SessionService, "sync_browser", return_value=None),
        mock.patch.object(st, "page_link"),
        mock.patch.object(st, "switch_page"),
    ):
        yield _open


def test_restoring_from_the_subjects_page(world, parent_page, fetch):
    at = parent_page("Subjects").run()

    assert not at.exception
    assert any("Archived Subjects (2)" in e.label for e in at.expander)

    at.button(key=f"restore_subject_{world.old_subject}").click().run()

    assert not at.exception
    assert fetch(Subject, world.old_subject).active is True
    assert any("Archived Subjects (1)" in e.label for e in at.expander)


def test_restoring_from_the_assignments_page(world, parent_page, fetch):
    at = parent_page("Assignments").run()

    assert not at.exception
    assert any("Archived Assignments (1)" in e.label for e in at.expander)

    at.button(key=f"restore_assignment_{world.archived}").click().run()

    assert not at.exception
    assert fetch(Assignment, world.archived).active is True
    assert not any("Archived Assignments" in e.label for e in at.expander)
    assert any("Archived" in item.value for item in at.markdown)
