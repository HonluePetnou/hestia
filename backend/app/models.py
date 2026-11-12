"""SQLAlchemy models (PROJECT_SPEC §4)."""

import enum
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.config import get_settings

EMBEDDING_DIM = get_settings().embedding_dim


class Base(DeclarativeBase):
    pass


class Gravity(enum.StrEnum):
    microgravity = "microgravity"
    lunar = "lunar"
    martian = "martian"
    earth = "earth"


class Outcome(enum.StrEnum):
    spread = "spread"
    extinction = "extinction"
    disruption = "disruption"
    complete_burn = "complete_burn"
    unknown = "unknown"


def _pg_enum(cls: type[enum.Enum], name: str) -> Enum:
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    ntrs_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    authors: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    year: Mapped[int | None] = mapped_column(Integer)
    url: Mapped[str | None] = mapped_column(Text)
    pdf_path: Mapped[str | None] = mapped_column(Text)
    text_path: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    page: Mapped[int] = mapped_column(Integer)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    token_count: Mapped[int | None] = mapped_column(Integer)

    document: Mapped[Document] = relationship(back_populates="chunks")


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(Text)
    platform: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    objectives: Mapped[str | None] = mapped_column(Text)
    psi_doi: Mapped[str | None] = mapped_column(Text)

    test_runs: Mapped[list["TestRun"]] = relationship(back_populates="experiment")
    findings: Mapped[list["Finding"]] = relationship(back_populates="experiment")


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"))
    run_label: Mapped[str | None] = mapped_column(Text)
    fuel: Mapped[str | None] = mapped_column(Text)
    oxygen_percent: Mapped[float | None] = mapped_column(Float)
    pressure_kpa: Mapped[float | None] = mapped_column(Float)
    flow_velocity_cm_s: Mapped[float | None] = mapped_column(Float)
    gravity: Mapped[Gravity] = mapped_column(
        _pg_enum(Gravity, "gravity"), default=Gravity.microgravity
    )
    initial_diameter_mm: Mapped[float | None] = mapped_column(Float)
    outcome: Mapped[Outcome] = mapped_column(_pg_enum(Outcome, "outcome"), default=Outcome.unknown)
    burn_rate_k: Mapped[float | None] = mapped_column(Float)
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    experiment: Mapped[Experiment] = relationship(back_populates="test_runs")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int | None] = mapped_column(
        ForeignKey("experiments.id", ondelete="SET NULL")
    )
    statement: Mapped[str] = mapped_column(Text)
    relevance_moon: Mapped[float] = mapped_column(Float, default=0.0)
    relevance_mars: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    experiment: Mapped[Experiment | None] = relationship(back_populates="findings")
    sources: Mapped[list["FindingSource"]] = relationship(back_populates="finding")


class FindingSource(Base):
    __tablename__ = "finding_sources"

    finding_id: Mapped[int] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), primary_key=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    page: Mapped[int] = mapped_column(Integer, primary_key=True)

    finding: Mapped[Finding] = relationship(back_populates="sources")
    document: Mapped[Document] = relationship()
