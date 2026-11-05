"""Add the P.E. tracker: one row per activity, per student.

Nothing changes for existing data, since the table starts empty.

Revision ID: 0012
Revises: 0011
"""
from alembic import op
import sqlalchemy as sa


revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("activity", sa.String(), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["families.id"],
            name="activity_logs_family_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name="activity_logs_student_id_fkey",
        ),
    )

    op.create_index(
        "ix_activity_logs_family_id",
        "activity_logs",
        ["family_id"],
    )

    op.create_index(
        "ix_activity_logs_student_date",
        "activity_logs",
        ["student_id", "log_date"],
    )


def downgrade():
    op.drop_index(
        "ix_activity_logs_student_date",
        table_name="activity_logs",
    )
    op.drop_index(
        "ix_activity_logs_family_id",
        table_name="activity_logs",
    )
    op.drop_table("activity_logs")
