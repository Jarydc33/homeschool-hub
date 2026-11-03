"""Baseline: the Supabase schema as it stood when Alembic was added.

The live database already has these tables, so it gets stamped with this
revision instead of running it. Brand-new databases run it to create them.
Constraint names match the live database so later migrations can use them.

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "families",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime()),
    )

    op.create_table(
        "students",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_id", sa.Integer()),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("grade_level", sa.String()),
        sa.Column("birth_year", sa.Integer()),
        sa.Column("active", sa.Boolean()),
        sa.Column("created_at", sa.DateTime()),
        sa.ForeignKeyConstraint(
            ["family_id"], ["families.id"], name="students_family_id_fkey"
        ),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_id", sa.Integer()),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String()),
        sa.Column("role", sa.String()),
        sa.Column("is_active", sa.Boolean()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("student_id", sa.Integer()),
        sa.ForeignKeyConstraint(
            ["family_id"], ["families.id"], name="users_family_id_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.id"], name="fk_users_student"
        ),
        sa.UniqueConstraint("email", name="users_email_key"),
    )

    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_id", sa.Integer()),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("color", sa.String()),
        sa.Column("active", sa.Boolean()),
        sa.Column("created_at", sa.DateTime()),
        sa.ForeignKeyConstraint(
            ["family_id"], ["families.id"], name="subjects_family_id_fkey"
        ),
    )

    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_id", sa.Integer()),
        sa.Column("subject_id", sa.Integer()),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("assignment_type", sa.String()),
        sa.Column("recurrence_pattern", sa.String()),
        sa.Column("due_date", sa.Date()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("active", sa.Boolean()),
        sa.ForeignKeyConstraint(
            ["family_id"], ["families.id"], name="assignments_family_id_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subjects.id"], name="assignments_subject_id_fkey"
        ),
    )

    op.create_table(
        "student_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assignment_id", sa.Integer()),
        sa.Column("student_id", sa.Integer()),
        sa.Column("status", sa.String()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("notes", sa.Text()),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["assignments.id"],
            name="student_assignments_assignment_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name="student_assignments_student_id_fkey",
        ),
    )

    op.create_table(
        "banner_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("active", sa.Boolean()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("family_id", sa.Integer()),
        sa.ForeignKeyConstraint(
            ["family_id"], ["families.id"], name="banner_messages_family_id_fkey"
        ),
    )


def downgrade():
    # Undoing the baseline would drop every table and all its data.
    raise NotImplementedError("The baseline migration can't be downgraded.")
