"""Add pairing codes, so a student's own device can sign in without email.

device_sessions gains token_hash for paired devices, and auth_session_id
becomes optional since a paired device has no parent login behind it.
Existing Student Mode rows keep their auth_session_id. pairing_codes
starts empty.

Revision ID: 0014
Revises: 0013
"""
from alembic import op
import sqlalchemy as sa


revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("device_sessions") as batch:
        batch.alter_column(
            "auth_session_id",
            existing_type=sa.String(),
            nullable=True,
        )
        batch.add_column(
            sa.Column("token_hash", sa.String(), nullable=True)
        )
        batch.create_unique_constraint(
            "device_sessions_token_hash_key", ["token_hash"]
        )

    op.create_table(
        "pairing_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["families.id"],
            name="pairing_codes_family_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name="pairing_codes_student_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="pairing_codes_created_by_fkey",
        ),
    )

    op.create_index(
        "ix_pairing_codes_family_id",
        "pairing_codes",
        ["family_id"],
    )

    op.create_index(
        "ix_pairing_codes_code_hash",
        "pairing_codes",
        ["code_hash"],
    )


def downgrade():
    op.drop_index("ix_pairing_codes_code_hash", table_name="pairing_codes")
    op.drop_index("ix_pairing_codes_family_id", table_name="pairing_codes")
    op.drop_table("pairing_codes")

    # Paired devices have no auth_session_id, so they can't survive the
    # column becoming required again.
    op.execute("DELETE FROM device_sessions WHERE auth_session_id IS NULL")

    with op.batch_alter_table("device_sessions") as batch:
        batch.drop_constraint(
            "device_sessions_token_hash_key", type_="unique"
        )
        batch.drop_column("token_hash")
        batch.alter_column(
            "auth_session_id",
            existing_type=sa.String(),
            nullable=False,
        )
