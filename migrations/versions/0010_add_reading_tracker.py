"""Add the reading tracker: each student's books, and pages read per date.

Nothing changes for existing data, since both tables start empty.

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa


revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "books",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("author", sa.String()),
        sa.Column("total_pages", sa.Integer()),
        sa.Column("finished_on", sa.Date()),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["families.id"],
            name="books_family_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name="books_student_id_fkey",
        ),
    )

    op.create_index(
        "ix_books_family_id",
        "books",
        ["family_id"],
    )

    op.create_index(
        "ix_books_student_id",
        "books",
        ["student_id"],
    )

    op.create_table(
        "reading_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("pages", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["book_id"],
            ["books.id"],
            name="reading_logs_book_id_fkey",
        ),
        sa.UniqueConstraint(
            "book_id",
            "log_date",
            name="uq_reading_logs_book_date",
        ),
    )


def downgrade():
    op.drop_table("reading_logs")
    op.drop_index("ix_books_student_id", table_name="books")
    op.drop_index("ix_books_family_id", table_name="books")
    op.drop_table("books")
