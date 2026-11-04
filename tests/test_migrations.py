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
