"""Link users to their Supabase account by UUID instead of by email.

Existing users are matched to auth.users by email, this one last time. If any
user has no matching account, the NOT NULL step fails and the whole migration
is rolled back, so nothing is left half done.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("auth_user_id", sa.Uuid(as_uuid=False), nullable=True),
    )

    if op.get_context().dialect.name == "postgresql":
        # A Postgres database outside Supabase has no auth schema to read.
        op.execute(
            """
            DO $$
            BEGIN
                IF to_regclass('auth.users') IS NOT NULL THEN
                    UPDATE public.users AS u
                    SET auth_user_id = a.id
                    FROM auth.users AS a
                    WHERE lower(a.email) = lower(u.email);
                END IF;
            END $$
            """
        )

    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "auth_user_id",
            existing_type=sa.Uuid(as_uuid=False),
            nullable=False,
        )
        batch.create_unique_constraint(
            "users_auth_user_id_key", ["auth_user_id"]
        )


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("users_auth_user_id_key", type_="unique")
        batch.drop_column("auth_user_id")
