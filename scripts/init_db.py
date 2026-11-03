import os

from alembic import command
from alembic.config import Config

ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)


def initialize_database():
    command.upgrade(
        Config(os.path.join(ROOT, "alembic.ini")),
        "head"
    )
    print("✅ Database is up to date.")


if __name__ == "__main__":
    initialize_database()
