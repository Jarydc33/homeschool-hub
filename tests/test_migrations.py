"""The migrations, not create_all(), are what build real databases."""
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from database.db import Base, engine

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def empty_database():
    Base.metadata.drop_all(engine)
    yield
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        # SQLite can't roll back a failed migration, which leaves this behind.
        connection.execute(text("DROP TABLE IF EXISTS _alembic_tmp_assignments"))


def _config():
    return Config(str(ROOT / "alembic.ini"))


def test_migrations_build_every_table(empty_database):
    command.upgrade(_config(), "head")

    assert set(Base.metadata.tables) <= set(inspect(engine).get_table_names())


def test_migrations_match_the_models(empty_database):
    """Fails when a model changes without a migration."""
    command.upgrade(_config(), "head")

    with engine.connect() as connection:
        differences = compare_metadata(
            MigrationContext.configure(connection), Base.metadata
        )

    assert differences == []


def test_baseline_refuses_to_downgrade(empty_database):
    command.upgrade(_config(), "head")

    with pytest.raises(NotImplementedError):
        command.downgrade(_config(), "base")


def test_auth_user_id_migration_can_be_undone(empty_database):
    command.upgrade(_config(), "head")
    command.downgrade(_config(), "0001")

    columns = {column["name"] for column in inspect(engine).get_columns("users")}
    assert "auth_user_id" not in columns

    command.upgrade(_config(), "head")


def test_constraints_migration_can_be_undone(empty_database):
    command.upgrade(_config(), "head")
    command.downgrade(_config(), "0002")

    inspector = inspect(engine)
    assert inspector.get_indexes("students") == []
    assert inspector.get_unique_constraints("student_assignments") == []
    nullable = {c["name"]: c["nullable"] for c in inspector.get_columns("students")}
    assert nullable["family_id"] is True

    command.upgrade(_config(), "head")


def test_existing_families_get_the_default_time_zone(empty_database):
    command.upgrade(_config(), "0003")
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO families (family_name) VALUES ('Smith')"))

    command.upgrade(_config(), "head")

    with engine.connect() as connection:
        zone = connection.execute(text("SELECT timezone FROM families")).scalar()
    assert zone == "America/Chicago"


def test_timezone_migration_can_be_undone(empty_database):
    command.upgrade(_config(), "head")
    command.downgrade(_config(), "0003")

    columns = {column["name"] for column in inspect(engine).get_columns("families")}
    assert "timezone" not in columns

    command.upgrade(_config(), "head")


def test_occurrences_migration_can_be_undone(empty_database):
    command.upgrade(_config(), "0005")
    command.downgrade(_config(), "0004")

    assert "assignment_occurrences" not in inspect(engine).get_table_names()

    command.upgrade(_config(), "head")


def _add_old_assignment(connection, assignment_type="One Time", due_date="'2026-11-04'"):
    connection.execute(text("INSERT INTO families (id, family_name) VALUES (1, 'Smith')"))
    connection.execute(text("INSERT INTO subjects (id, family_id, name) VALUES (1, 1, 'Math')"))
    connection.execute(text("INSERT INTO students (id, family_id, name) VALUES (1, 1, 'Ann')"))
    connection.execute(text("INSERT INTO students (id, family_id, name) VALUES (2, 1, 'Bob')"))
    connection.execute(
        text(
            "INSERT INTO assignments "
            "(id, family_id, subject_id, title, assignment_type, due_date) "
            f"VALUES (1, 1, 1, 'Essay', '{assignment_type}', {due_date})"
        )
    )


def test_links_are_copied_to_occurrences(empty_database):
    command.upgrade(_config(), "0005")
    with engine.begin() as connection:
        _add_old_assignment(connection)
        connection.execute(
            text(
                "INSERT INTO student_assignments "
                "(assignment_id, student_id, status, completed_at, notes) VALUES "
                "(1, 1, 'Complete', '2026-11-03 09:00:00', 'Well done'), "
                "(1, 2, NULL, NULL, NULL)"
            )
        )

    command.upgrade(_config(), "head")

    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT student_id, occurrence_date, status, completed_at, notes "
                "FROM assignment_occurrences ORDER BY student_id"
            )
        ).all()

    assert [tuple(row) for row in rows] == [
        (1, "2026-11-04", "Complete", "2026-11-03 09:00:00", "Well done"),
        (2, "2026-11-04", "Not Started", None, None),
    ]


def test_the_migration_refuses_recurring_work(empty_database):
    command.upgrade(_config(), "0005")
    with engine.begin() as connection:
        _add_old_assignment(connection, assignment_type="Recurring")

    with pytest.raises(RuntimeError, match="recurring"):
        command.upgrade(_config(), "head")


def test_the_migration_refuses_a_missing_due_date(empty_database):
    command.upgrade(_config(), "0005")
    with engine.begin() as connection:
        _add_old_assignment(connection, due_date="NULL")

    with pytest.raises(Exception):
        command.upgrade(_config(), "head")


def test_write_occurrences_migration_can_be_undone(empty_database):
    command.upgrade(_config(), "head")
    command.downgrade(_config(), "0005")

    columns = {column["name"]: column for column in inspect(engine).get_columns("assignments")}
    assert "end_date" not in columns
    assert columns["due_date"]["nullable"] is True

    command.upgrade(_config(), "head")
