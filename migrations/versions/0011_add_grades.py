"""Add grading: which assignments are graded, what each date is out of, and
grading periods.

Existing assignments start as not graded, and nothing else changes for them.

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa


revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("assignments") as batch:
        batch.add_column(
            sa.Column(
                "graded",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    with op.batch_alter_table("assignment_occurrences") as batch:
        batch.add_column(sa.Column("points_possible", sa.Numeric(6, 2)))

    op.create_table(
        "grading_periods",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["families.id"],
            name="grading_periods_family_id_fkey",
        ),
    )

    op.create_index(
        "ix_grading_periods_family_id",
        "grading_periods",
        ["family_id"],
    )


def downgrade():
    op.drop_index(
        "ix_grading_periods_family_id",
        table_name="grading_periods",
    )
    op.drop_table("grading_periods")

    with op.batch_alter_table("assignment_occurrences") as batch:
        batch.drop_column("points_possible")

    with op.batch_alter_table("assignments") as batch:
        batch.drop_column("graded")
