"""Require the foreign keys that must always be set, stop duplicate student
links, and index every family_id.

users.family_id (Admins), users.student_id (parents) and
banner_messages.family_id (system-wide announcements) stay nullable on purpose.

If any row breaks a new rule, the whole migration fails and is rolled back.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

REQUIRED_COLUMNS = {
    "students": ["family_id"],
    "subjects": ["family_id"],
    "assignments": ["family_id", "subject_id"],
    "student_assignments": ["assignment_id", "student_id"],
}

FAMILY_ID_TABLES = [
    "users",
    "students",
    "subjects",
    "assignments",
    "banner_messages",
]

UNIQUE_LINK = "student_assignments_assignment_id_student_id_key"


def _set_required(required):
    for table, columns in REQUIRED_COLUMNS.items():
        with op.batch_alter_table(table) as batch:
            for column in columns:
                batch.alter_column(
                    column,
                    existing_type=sa.Integer(),
                    nullable=not required,
                )


def upgrade():
    _set_required(True)

    with op.batch_alter_table("student_assignments") as batch:
        batch.create_unique_constraint(
            UNIQUE_LINK, ["assignment_id", "student_id"]
        )

    for table in FAMILY_ID_TABLES:
        op.create_index(f"ix_{table}_family_id", table, ["family_id"])


def downgrade():
    for table in FAMILY_ID_TABLES:
        op.drop_index(f"ix_{table}_family_id", table_name=table)

    with op.batch_alter_table("student_assignments") as batch:
        batch.drop_constraint(UNIQUE_LINK, type_="unique")

    _set_required(False)
