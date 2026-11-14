"""Add feedback: messages parents send from the app's feedback form.

Nothing changes for existing data, since the table starts empty.

Revision ID: 0015
Revises: 0014
"""
from alembic import op
import sqlalchemy as sa


revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["families.id"],
            name="feedback_family_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="feedback_user_id_fkey",
        ),
    )

    op.create_index(
        "ix_feedback_family_id",
        "feedback",
        ["family_id"],
    )


def downgrade():
    op.drop_index("ix_feedback_family_id", table_name="feedback")
    op.drop_table("feedback")
