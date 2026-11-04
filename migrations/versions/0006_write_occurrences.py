"""Require due dates, add an end date for recurring work, and copy existing
student links into occurrences.

Each link becomes one occurrence on the assignment's due date, keeping its
status, completion time and notes. A recurring assignment needs a full set of
dates instead, so if any exist, this stops and changes nothing. There were
none when this was written. So does any assignment with no due date.

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _refuse_recurring_work():
    # There's no database to ask when only printing the SQL.
    if op.get_context().as_sql:
        return

    count = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT COUNT(*) FROM assignments "
                "WHERE assignment_type = 'Recurring'"
            )
        )
        .scalar()
    )

    if count:
        raise RuntimeError(
            f"{count} recurring assignment(s) exist, and this migration can't "
            "work out their dates. Nothing was changed. Remove them or extend "
            "this migration, then run it again."
        )


def upgrade():
    _refuse_recurring_work()

    with op.batch_alter_table("assignments") as batch:
        batch.add_column(sa.Column("end_date", sa.Date()))
        batch.alter_column(
            "due_date",
            existing_type=sa.Date(),
            nullable=False,
        )

    op.execute(
        """
        INSERT INTO assignment_occurrences
            (assignment_id, student_id, occurrence_date,
             status, completed_at, notes)
        SELECT
            link.assignment_id,
            link.student_id,
            assignment.due_date,
            COALESCE(link.status, 'Not Started'),
            link.completed_at,
            link.notes
        FROM student_assignments AS link
        JOIN assignments AS assignment
            ON assignment.id = link.assignment_id
        """
    )


def downgrade():
    # student_assignments still holds what was copied. Anything newer, such
    # as dates for recurring work, is lost.
    op.execute("DELETE FROM assignment_occurrences")

    with op.batch_alter_table("assignments") as batch:
        batch.alter_column(
            "due_date",
            existing_type=sa.Date(),
            nullable=True,
        )
        batch.drop_column("end_date")
