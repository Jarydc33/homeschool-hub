"""Add occurrences: one row per assignment, per student, per date.

Nothing reads or writes this table yet. Existing work moves over in a later
migration.

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assignment_occurrences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("occurrence_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="Not Started",
        ),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("notes", sa.Text()),
        sa.Column("score", sa.Numeric(6, 2)),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["assignments.id"],
            name="assignment_occurrences_assignment_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name="assignment_occurrences_student_id_fkey",
        ),
        sa.UniqueConstraint(
            "assignment_id",
            "student_id",
            "occurrence_date",
            name="uq_assignment_occurrences_assignment_student_date",
        ),
    )

    op.create_index(
        "ix_assignment_occurrences_student_date",
        "assignment_occurrences",
        ["student_id", "occurrence_date"],
    )


def downgrade():
    op.drop_index(
        "ix_assignment_occurrences_student_date",
        table_name="assignment_occurrences",
    )
    op.drop_table("assignment_occurrences")
