"""Drop progress from student_assignments, which now only says who is assigned.

Occurrences hold status, completion time and notes for each date. Deploy the
code that stops using these columns before running this, or the app breaks.

Downgrading brings the columns back empty, since there's no single value to
restore from a set of dates.

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("student_assignments") as batch:
        batch.drop_column("status")
        batch.drop_column("completed_at")
        batch.drop_column("notes")


def downgrade():
    with op.batch_alter_table("student_assignments") as batch:
        batch.add_column(sa.Column("status", sa.String()))
        batch.add_column(sa.Column("completed_at", sa.DateTime()))
        batch.add_column(sa.Column("notes", sa.Text()))

    op.execute("UPDATE student_assignments SET status = 'Not Started'")
