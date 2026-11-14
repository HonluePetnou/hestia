"""Multi-source documents (NTRS + PSI + NASA resources) and idempotent chunk tracking.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-13

documents
  + source_type   'ntrs' (default) | 'psi' | 'nasa_resource'
  + external_id   NTRS id, PSI id ("PSI-159") or resource slug; unique per source_type
  + doi, meta     DOI when one exists; flexible JSONB metadata
  ~ ntrs_id       now NULLABLE (kept, unique, for backward compatibility)
chunks
  ~ page          now NULLABLE (PSI pages have no page number)
  + meta          JSONB (psi_id, fuel_category, pillars, fire_safety_tier, doi, source_url, ...)
  + chunk_key     stable key per document (idempotent upserts)
  + content_hash  sha256 of the exact text that was embedded
  + embedding_model  "<provider>:<model>:<dim>" that produced `embedding`

Existing NTRS rows are backfilled (external_id = ntrs_id, chunk_key = "p<page>#<index>").
`embedding_model` stays NULL for old chunks: they are treated as "unknown provider" and
re-embedded by the next `make ingest` (the HANDOFF says current vectors are mock ones).
The vector dimension is NOT changed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("source_type", sa.String(16), nullable=False, server_default="ntrs"),
    )
    op.add_column("documents", sa.Column("external_id", sa.String(64), nullable=True))
    op.add_column("documents", sa.Column("doi", sa.Text(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("meta", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.execute("UPDATE documents SET external_id = ntrs_id WHERE external_id IS NULL")
    op.alter_column("documents", "external_id", nullable=False)
    op.alter_column("documents", "ntrs_id", existing_type=sa.String(32), nullable=True)
    op.create_unique_constraint(
        "uq_documents_source_external", "documents", ["source_type", "external_id"]
    )

    op.alter_column("chunks", "page", existing_type=sa.Integer(), nullable=True)
    op.add_column(
        "chunks", sa.Column("meta", postgresql.JSONB(), nullable=False, server_default="{}")
    )
    op.add_column("chunks", sa.Column("chunk_key", sa.String(128), nullable=True))
    op.add_column("chunks", sa.Column("content_hash", sa.String(64), nullable=True))
    op.add_column("chunks", sa.Column("embedding_model", sa.String(96), nullable=True))
    op.execute(
        "UPDATE chunks SET chunk_key = 'p' || page || '#' || chunk_index, "
        "content_hash = encode(sha256(convert_to(content, 'UTF8')), 'hex')"
    )
    op.alter_column("chunks", "chunk_key", nullable=False)
    op.create_unique_constraint("uq_chunks_doc_key", "chunks", ["document_id", "chunk_key"])
    op.execute("CREATE INDEX ix_chunks_meta_gin ON chunks USING gin (meta jsonb_path_ops)")


def downgrade() -> None:
    # PSI / resource rows cannot exist in the 0003 schema (no page, no ntrs_id): remove them
    # first. NTRS rows are untouched. This is the only destructive step and it only affects
    # rows that the previous schema could not represent.
    op.execute("DELETE FROM documents WHERE source_type <> 'ntrs'")
    op.execute("DELETE FROM chunks WHERE page IS NULL")
    op.execute("UPDATE documents SET ntrs_id = external_id WHERE ntrs_id IS NULL")
    op.execute("DROP INDEX IF EXISTS ix_chunks_meta_gin")
    op.drop_constraint("uq_chunks_doc_key", "chunks", type_="unique")
    for col in ("embedding_model", "content_hash", "chunk_key", "meta"):
        op.drop_column("chunks", col)
    op.alter_column("chunks", "page", existing_type=sa.Integer(), nullable=False)
    op.drop_constraint("uq_documents_source_external", "documents", type_="unique")
    op.alter_column("documents", "ntrs_id", existing_type=sa.String(32), nullable=False)
    for col in ("meta", "doi", "external_id", "source_type"):
        op.drop_column("documents", col)
