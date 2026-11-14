from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.integration.conftest import alembic, reset_schema


def test_upgrade_downgrade_roundtrip_and_backfill(engine) -> None:
    reset_schema(engine)
    alembic("upgrade", "0003")
    with Session(engine) as s:
        s.execute(
            text("INSERT INTO documents (ntrs_id, title) VALUES ('20150023456', 'FLEX report')")
        )
        s.execute(
            text(
                "INSERT INTO chunks (document_id, page, chunk_index, content) "
                "SELECT id, 12, 3, 'droplet flame text' FROM documents"
            )
        )
        s.commit()

    alembic("upgrade", "head")
    with Session(engine) as s:
        doc = s.execute(text("SELECT source_type, external_id, ntrs_id FROM documents")).one()
        assert tuple(doc) == ("ntrs", "20150023456", "20150023456")
        ch = s.execute(text("SELECT chunk_key, content_hash, embedding_model FROM chunks")).one()
        assert ch.chunk_key == "p12#3" and len(ch.content_hash) == 64 and ch.embedding_model is None
        # PSI-style rows are now representable: no ntrs_id, no page
        s.execute(
            text(
                "INSERT INTO documents (source_type, external_id, title) "
                "VALUES ('psi','PSI-159','CFI-G')"
            )
        )
        s.execute(
            text(
                "INSERT INTO chunks (document_id, chunk_index, chunk_key, content) "
                "SELECT id, 0, 'psi-159#00', 'x' FROM documents WHERE external_id='PSI-159'"
            )
        )
        s.commit()

    alembic("downgrade", "0003")  # drops only what 0003 cannot represent
    with Session(engine) as s:
        assert s.scalar(text("SELECT count(*) FROM documents")) == 1
        assert s.scalar(text("SELECT count(*) FROM chunks")) == 1
        assert s.scalar(text("SELECT ntrs_id FROM documents")) == "20150023456"
    alembic("upgrade", "head")
