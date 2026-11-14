"""Experiment years/fuels, full-text index on chunks, cache for AI-generated text.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("experiments", sa.Column("years", sa.Text(), nullable=True))
    op.add_column("experiments", sa.Column("fuels", sa.Text(), nullable=True))
    op.execute(
        "CREATE INDEX ix_chunks_content_fts ON chunks USING gin (to_tsvector('english', content))"
    )
    op.create_table(
        "ai_cache",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("ai_cache")
    op.execute("DROP INDEX IF EXISTS ix_chunks_content_fts")
    op.drop_column("experiments", "fuels")
    op.drop_column("experiments", "years")
