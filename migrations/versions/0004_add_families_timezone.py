"""Give each family a time zone, so "today" can be the family's local date.

Existing families get America/Chicago.

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "families",
        sa.Column(
            "timezone",
            sa.String(),
            nullable=False,
            server_default="America/Chicago",
        ),
    )


def downgrade():
    with op.batch_alter_table("families") as batch:
        batch.drop_column("timezone")
