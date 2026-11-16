"""Add hours tracking: usual minutes and a core flag on subjects, minutes on
assignments, and the minutes saved on each day's work.

Every column is new and empty (is_core starts false), so nothing changes
for existing data.

Revision ID: 0016
Revises: 0015
"""
from alembic import op
import sqlalchemy as sa


revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "subjects",
        sa.Column("default_minutes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "subjects",
        sa.Column(
            "is_core",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "assignments",
        sa.Column("minutes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "assignment_occurrences",
        sa.Column("minutes", sa.Integer(), nullable=True),
    )


def downgrade():
    # Batch mode, so SQLite can drop columns too.
    with op.batch_alter_table("assignment_occurrences") as batch:
        batch.drop_column("minutes")

    with op.batch_alter_table("assignments") as batch:
        batch.drop_column("minutes")

    with op.batch_alter_table("subjects") as batch:
        batch.drop_column("is_core")
        batch.drop_column("default_minutes")
