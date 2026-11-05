"""Add a lesson number to occurrences, for curriculum work.

Empty for everything else, so existing rows don't change.

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("assignment_occurrences") as batch:
        batch.add_column(sa.Column("lesson_number", sa.Integer()))


def downgrade():
    with op.batch_alter_table("assignment_occurrences") as batch:
        batch.drop_column("lesson_number")
