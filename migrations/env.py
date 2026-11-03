"""Runs migrations against whatever DATABASE_URL points to. Check it first."""
from logging.config import fileConfig

from alembic import context

from database.db import Base, engine
from database import models  # noqa: F401  (registers the tables on Base)

config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Supabase's REST API can reach any public table without RLS, and the app
# connects as the owner, so RLS with no policies only closes that door. Running
# this after every migration covers new tables and alembic_version itself.
ENABLE_RLS = """
DO $$
DECLARE t record;
BEGIN
    FOR t IN
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
          AND tableowner = current_user
          AND NOT rowsecurity
    LOOP
        EXECUTE 'ALTER TABLE public.' || quote_ident(t.tablename)
            || ' ENABLE ROW LEVEL SECURITY';
    END LOOP;
END $$
"""


def run_in_transaction():
    with context.begin_transaction():
        context.run_migrations()

        migration_context = context.get_context()
        if (
            migration_context.dialect.name == "postgresql"
            and not migration_context.opts.get("dont_mutate")
        ):
            context.execute(ENABLE_RLS)


if context.is_offline_mode():
    context.configure(
        url=engine.url,
        target_metadata=Base.metadata,
        literal_binds=True,
    )
    run_in_transaction()
else:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            # SQLite can't alter most things in place, and tests run on it.
            render_as_batch=connection.dialect.name == "sqlite",
        )
        run_in_transaction()
