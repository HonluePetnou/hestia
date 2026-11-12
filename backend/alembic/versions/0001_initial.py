"""Initial schema: pgvector extension + all Phase 1 tables.

Revision ID: 0001
Revises:
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from app.config import get_settings

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GRAVITY = ("microgravity", "lunar", "martian", "earth")
OUTCOME = ("spread", "extinction", "disruption", "complete_burn", "unknown")


def upgrade() -> None:
    dim = get_settings().embedding_dim
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ntrs_id", sa.String(32), nullable=False, unique=True, index=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("authors", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("year", sa.Integer),
        sa.Column("url", sa.Text),
        sa.Column("pdf_path", sa.Text),
        sa.Column("text_path", sa.Text),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer,
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("page", sa.Integer, nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", Vector(dim)),
        sa.Column("token_count", sa.Integer),
    )
    # HNSW supports up to 2000 dimensions.
    op.create_index(
        "ix_chunks_embedding_hnsw",
        "chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "experiments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True, index=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("platform", sa.Text),
        sa.Column("description", sa.Text),
        sa.Column("objectives", sa.Text),
        sa.Column("psi_doi", sa.Text),
    )

    op.create_table(
        "test_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "experiment_id",
            sa.Integer,
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("run_label", sa.Text),
        sa.Column("fuel", sa.Text),
        sa.Column("oxygen_percent", sa.Float),
        sa.Column("pressure_kpa", sa.Float),
        sa.Column("flow_velocity_cm_s", sa.Float),
        sa.Column("gravity", sa.Enum(*GRAVITY, name="gravity"), nullable=False),
        sa.Column("initial_diameter_mm", sa.Float),
        sa.Column("outcome", sa.Enum(*OUTCOME, name="outcome"), nullable=False),
        sa.Column("burn_rate_k", sa.Float),
        sa.Column("extra", postgresql.JSONB, nullable=False, server_default="{}"),
    )

    op.create_table(
        "findings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "experiment_id", sa.Integer, sa.ForeignKey("experiments.id", ondelete="SET NULL")
        ),
        sa.Column("statement", sa.Text, nullable=False),
        sa.Column("relevance_moon", sa.Float, nullable=False, server_default="0"),
        sa.Column("relevance_mars", sa.Float, nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
        sa.CheckConstraint("relevance_moon BETWEEN 0 AND 1", name="ck_findings_moon"),
        sa.CheckConstraint("relevance_mars BETWEEN 0 AND 1", name="ck_findings_mars"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_findings_confidence"),
    )

    op.create_table(
        "finding_sources",
        sa.Column(
            "finding_id",
            sa.Integer,
            sa.ForeignKey("findings.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "document_id",
            sa.Integer,
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("page", sa.Integer, primary_key=True),
    )


def downgrade() -> None:
    for table in ("finding_sources", "findings", "test_runs", "experiments", "chunks", "documents"):
        op.drop_table(table)
    op.execute("DROP TYPE IF EXISTS outcome")
    op.execute("DROP TYPE IF EXISTS gravity")
