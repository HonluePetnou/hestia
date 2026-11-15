"""Read and validate the prepared PSI corpus (data/psi_corpus/out/chunks.jsonl).

The 323 chunks are used as they are: no re-chunking, text and metadata preserved. The only
text edit is removing the team's "curated habitat relevance" sentence that
`build_corpus.py` appends to each investigation's overview chunk: it is an annotation, not
NASA text. It is kept in the chunk metadata, labelled as such.

Document mapping
    source_type == "psi_investigation"  ->  Document(source_type="psi", external_id="PSI-xx")
    anything else (Apollo, Mir, guide)  ->  Document(source_type="nasa_resource", doc_id)
Pages: only the Researcher's Guide has them ("Page N" sections); nothing is invented elsewhere.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.models import SOURCE_PSI, SOURCE_RESOURCE
from pipeline.chunk import estimate_tokens
from pipeline.sync import ChunkSpec

log = logging.getLogger("psi")

ANNOTATION_NOTE = (
    "Team annotation (annotations_curated.json), not NASA text and not an experimental result."
)
_CURATED = re.compile(r";\s*curated habitat relevance:\s*(?P<value>.*)\Z", re.S | re.I)
_PAGE_SECTION = re.compile(r"^Page\s+(\d+)(?:\s*\(\d+\))?$", re.I)


class PsiChunk(BaseModel):
    model_config = ConfigDict(extra="allow")

    chunk_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source_type: str = "psi_investigation"
    psi_id: str | None = None
    acronym: str | None = None
    source_url: str | None = None
    doi: str | None = None
    project_type: str | None = None
    fuel_category: str | None = None
    hardware: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None
    fire_safety_tier: int | None = None
    pillars: list[str] | None = None
    section: str | None = None
    tags: Any = None


@dataclass
class PsiDocument:
    source_type: str  # documents.source_type
    external_id: str
    title: str
    url: str | None
    doi: str | None
    meta: dict[str, Any]
    chunks: list[ChunkSpec] = field(default_factory=list)


def strip_curated(text: str) -> tuple[str, str | None]:
    """Split off the team annotation appended to overview chunks."""
    m = _CURATED.search(text)
    if not m:
        return text, None
    return text[: m.start()].rstrip(), m.group("value").strip()


def read_psi_chunks(path: Path) -> tuple[list[PsiChunk], list[str]]:
    """Parse and validate chunks.jsonl; returns (valid records, error messages)."""
    records: list[PsiChunk] = []
    errors: list[str] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rec = PsiChunk.model_validate(json.loads(line))
            except (json.JSONDecodeError, ValidationError) as exc:
                errors.append(f"line {n}: {exc.__class__.__name__}: {str(exc)[:120]}")
                continue
            if rec.chunk_id in seen:
                errors.append(f"line {n}: duplicate chunk_id {rec.chunk_id}")
                continue
            seen.add(rec.chunk_id)
            records.append(rec)
    return records, errors


def _clean(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v not in (None, "", [])}


def build_documents(records: list[PsiChunk]) -> list[PsiDocument]:
    """Group chunks by source document and build their metadata. Nothing is fabricated."""
    docs: dict[str, PsiDocument] = {}
    for rec in records:
        is_psi = rec.source_type == "psi_investigation"
        external_id = (rec.psi_id or rec.doc_id).upper() if is_psi else rec.doc_id
        doc = docs.get(external_id)
        if doc is None:
            doc_meta = _clean(
                {
                    "corpus": "psi_corpus",
                    "psi_id": rec.psi_id,
                    "acronym": rec.acronym,
                    "doc_id": rec.doc_id,
                    "kind": rec.source_type,
                    "project_type": rec.project_type,
                    "fuel_category": rec.fuel_category,
                    "hardware": rec.hardware,
                    "start_date": rec.start_date,
                    "end_date": rec.end_date,
                    "fire_safety_tier": rec.fire_safety_tier,
                    "pillars": rec.pillars,
                }
            )
            if is_psi:
                doc_meta["curated_fields"] = ["fire_safety_tier", "pillars"]
            doc = PsiDocument(
                SOURCE_PSI if is_psi else SOURCE_RESOURCE,
                external_id,
                rec.title.strip(),
                rec.source_url,
                rec.doi,
                doc_meta,
            )
            docs[external_id] = doc
        doc.url = doc.url or rec.source_url
        doc.doi = doc.doi or rec.doi

        text, curated = strip_curated(rec.text.strip())
        page = None
        if rec.section and (pm := _PAGE_SECTION.match(rec.section)) and not is_psi:
            page = int(pm.group(1))
        meta = _clean(
            {
                "chunk_id": rec.chunk_id,
                "psi_id": rec.psi_id,
                "acronym": rec.acronym,
                "section": rec.section,
                "kind": rec.source_type,
                "fuel_category": rec.fuel_category,
                "hardware": rec.hardware,
                "pillars": rec.pillars,
                "fire_safety_tier": rec.fire_safety_tier,
                "doi": rec.doi,
                "source_url": rec.source_url,
                "tags": rec.tags,
            }
        )
        if is_psi:
            meta["curated_fields"] = ["fire_safety_tier", "pillars"]
        if curated:
            meta["curated_habitat_relevance"] = curated
            meta["annotation_note"] = ANNOTATION_NOTE
        doc.chunks.append(
            ChunkSpec(
                chunk_key=rec.chunk_id,
                chunk_index=len(doc.chunks),
                content=text,
                embed_text=text,  # already starts with a context header (id, title, fuel, ...)
                page=page,
                token_count=estimate_tokens(text),
                meta=meta,
            )
        )
    return list(docs.values())
