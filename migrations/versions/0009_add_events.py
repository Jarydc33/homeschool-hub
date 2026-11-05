"""Add events, and which students each one is for.

Nothing changes for existing data, since both tables start empty. An event
with no event_students rows is for the whole family.

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date()),
        sa.Column("start_time", sa.Time()),
        sa.Column("recurrence_pattern", sa.String()),
        sa.Column("repeat_until", sa.Date()),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["families.id"],
            name="events_family_id_fkey",
        ),
    )

    op.create_index(
        "ix_events_family_id",
        "events",
        ["family_id"],
    )

    op.create_table(
        "event_students",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name="event_students_event_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name="event_students_student_id_fkey",
        ),
        sa.UniqueConstraint(
            "event_id",
            "student_id",
            name="uq_event_students_event_student",
        ),
    )


def downgrade():
    op.drop_table("event_students")
    op.drop_index("ix_events_family_id", table_name="events")
    op.drop_table("events")
