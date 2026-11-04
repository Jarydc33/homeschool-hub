"""Shared test setup.

Tests run against a temporary SQLite file. These variables are set before any
app module is imported, and load_dotenv() doesn't override existing values, so
the tests can't reach the Supabase project configured in .env.
"""
import os
import tempfile
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest import mock

_db_dir = tempfile.mkdtemp(prefix="homeschool_hub_tests_")
_db_path = os.path.join(_db_dir, "test.db").replace("\\", "/")

os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["SUPABASE_URL"] = "http://localhost:1"
os.environ["SUPABASE_KEY"] = "test"
os.environ["SERVICE_KEY"] = "test"

import pytest

from database.db import Base, SessionLocal, engine
from database.models import (
    Assignment,
    AssignmentOccurrence,
    DEFAULT_TIMEZONE,
    Family,
    Student,
    StudentAssignment,
    Subject,
    UserRole,
)
from services.auth_service import AuthService

assert engine.url.drivername == "sqlite", "tests must not run on a real database"


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    engine.dispose()


def _add(**rows):
    """Saves the rows and returns their ids, keyed by the given names."""
    db = SessionLocal()
    try:
        db.add_all(rows.values())
        db.commit()
        return SimpleNamespace(**{name: row.id for name, row in rows.items()})
    finally:
        db.close()


@pytest.fixture
def world():
    """Two families. The Smiths are the family under test; the Jones are other."""
    families = _add(smith=Family(family_name="Smith"), jones=Family(family_name="Jones"))
    smith, jones = families.smith, families.jones

    people = _add(
        math=Subject(family_id=smith, name="Math"),
        art=Subject(family_id=smith, name="Art"),
        old_subject=Subject(family_id=smith, name="Old", active=False),
        other_old_subject=Subject(family_id=smith, name="Older", active=False),
        jones_subject=Subject(family_id=jones, name="Jones subject"),
        ann=Student(family_id=smith, name="Ann"),
        bob=Student(family_id=smith, name="Bob"),
        cat=Student(family_id=smith, name="Cat"),
        gone=Student(family_id=smith, name="Gone", active=False),
        other_gone=Student(family_id=smith, name="Other gone", active=False),
        jones_kid=Student(family_id=jones, name="Jones kid"),
    )

    due = date.today() + timedelta(days=30)

    work = _add(
        essay=Assignment(
            family_id=smith, subject_id=people.art, title="Essay", due_date=due
        ),
        on_old=Assignment(
            family_id=smith,
            subject_id=people.old_subject,
            title="On old subject",
            due_date=due,
        ),
        archived=Assignment(
            family_id=smith,
            subject_id=people.art,
            title="Archived",
            due_date=due,
            active=False,
        ),
        jones_work=Assignment(
            family_id=jones,
            subject_id=people.jones_subject,
            title="Jones work",
            due_date=due,
        ),
    )

    done_at = datetime(2026, 11, 1, 9, 0)
    links = _add(
        ann_essay=StudentAssignment(assignment_id=work.essay, student_id=people.ann),
        bob_essay=StudentAssignment(assignment_id=work.essay, student_id=people.bob),
        gone_essay=StudentAssignment(assignment_id=work.essay, student_id=people.gone),
        ann_archived=StudentAssignment(
            assignment_id=work.archived, student_id=people.ann
        ),
        jones_link=StudentAssignment(
            assignment_id=work.jones_work, student_id=people.jones_kid
        ),
    )

    occurrences = _add(
        ann_essay_day=AssignmentOccurrence(
            assignment_id=work.essay,
            student_id=people.ann,
            occurrence_date=due,
            status="Complete",
            completed_at=done_at,
            notes="Well done",
        ),
        bob_essay_day=AssignmentOccurrence(
            assignment_id=work.essay, student_id=people.bob, occurrence_date=due
        ),
        gone_essay_day=AssignmentOccurrence(
            assignment_id=work.essay,
            student_id=people.gone,
            occurrence_date=due,
            status="Complete",
            completed_at=done_at,
        ),
        ann_archived_day=AssignmentOccurrence(
            assignment_id=work.archived, student_id=people.ann, occurrence_date=due
        ),
        jones_link_day=AssignmentOccurrence(
            assignment_id=work.jones_work, student_id=people.jones_kid, occurrence_date=due
        ),
    )

    return SimpleNamespace(
        smith=smith,
        jones=jones,
        done_at=done_at,
        due=due,
        **vars(people),
        **vars(work),
        **vars(links),
        **vars(occurrences),
    )


@pytest.fixture
def login():
    """Signs in as a parent or student, without touching Supabase Auth."""
    patches = []

    def _login(family_id, role=UserRole.PARENT, student_id=None):
        user = SimpleNamespace(
            family_id=family_id,
            family=SimpleNamespace(timezone=DEFAULT_TIMEZONE) if family_id else None,
            role=role.value,
            student_id=student_id,
        )
        patcher = mock.patch.object(AuthService, "get_current_user", return_value=user)
        patcher.start()
        patches.append(patcher)

    yield _login

    # Newest first, or a test that logs in twice leaves a fake user behind.
    for patcher in reversed(patches):
        patcher.stop()


@pytest.fixture
def smith_parent(world, login):
    login(world.smith)
    return world


@pytest.fixture
def fetch():
    """Reads a row fresh from the database, ignoring family scoping."""

    def _fetch(model, row_id):
        db = SessionLocal()
        try:
            return db.get(model, row_id)
        finally:
            db.close()

    return _fetch
