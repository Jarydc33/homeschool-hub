"""Add Student Mode: a family PIN and a table of devices in Student Mode.

Nothing changes for existing data. The PIN starts empty and the table starts
empty, so Student Mode is off until a parent sets a PIN and starts it.

Revision ID: 0013
Revises: 0012
"""
from alembic import op
import sqlalchemy as sa


revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "families",
        sa.Column("parent_pin_hash", sa.String(), nullable=True),
    )

    op.create_table(
        "device_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("auth_session_id", sa.String(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column(
            "failed_pin_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["families.id"],
            name="device_sessions_family_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name="device_sessions_student_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="device_sessions_created_by_fkey",
        ),
    )

    op.create_index(
        "ix_device_sessions_family_id",
        "device_sessions",
        ["family_id"],
    )

    op.create_index(
        "ix_device_sessions_auth_session_id",
        "device_sessions",
        ["auth_session_id"],
    )


def downgrade():
    op.drop_index(
        "ix_device_sessions_auth_session_id",
        table_name="device_sessions",
    )
    op.drop_index(
        "ix_device_sessions_family_id",
        table_name="device_sessions",
    )
    op.drop_table("device_sessions")

    with op.batch_alter_table("families") as batch:
        batch.drop_column("parent_pin_hash")
