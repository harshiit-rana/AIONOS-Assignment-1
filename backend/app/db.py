"""SQLite persistence.

Three things are stored, and each earns its place:

* sources     -- the ingested data pack, so the API can serve provenance for
                 any citation without re-parsing files.
* runs        -- every brief generation, with the as-of date and the mode
                 (llm vs deterministic) it ran in. Reproducibility.
* audit_log   -- every question asked and every answer returned, with the
                 source ids that grounded it. The brief asks for commitments
                 to be traceable; an executive tool that cannot show why it
                 said something is not deployable.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import (JSON, Column, DateTime, Float, Integer, String, Text,
                        create_engine)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DB_PATH

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class SourceRow(Base):
    __tablename__ = "sources"
    id = Column(String, primary_key=True)
    kind = Column(String, index=True)
    ts = Column(DateTime, index=True)
    speaker = Column(String, index=True)
    audience = Column(JSON, default=list)
    text = Column(Text)
    label = Column(String)
    meta = Column(JSON, default=dict)


class RunRow(Base):
    __tablename__ = "runs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    as_of = Column(String, index=True)
    mode = Column(String)
    n_sources = Column(Integer)
    n_commitments = Column(Integer)
    payload = Column(JSON)


class AuditRow(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    as_of = Column(String)
    mode = Column(String)
    action = Column(String, index=True)      # brief | ask
    question = Column(Text, nullable=True)
    intent = Column(String, nullable=True)
    answer = Column(Text, nullable=True)
    citations = Column(JSON, default=list)
    grounded = Column(Integer, default=0)
    latency_ms = Column(Float, default=0.0)


def init_db() -> None:
    Base.metadata.create_all(engine)


def seed_sources() -> int:
    """Load the data pack into SQL once, so provenance lookups are a query."""
    from app.agent.ingest import load_sources

    init_db()
    with SessionLocal() as s:
        if s.query(SourceRow).count():
            return s.query(SourceRow).count()
        for u in load_sources():
            s.add(SourceRow(
                id=u.id, kind=u.kind, ts=u.ts, speaker=u.speaker,
                audience=list(u.audience), text=u.text, label=u.label,
                meta=dict(u.meta),
            ))
        s.commit()
        return s.query(SourceRow).count()


def log_audit(**kw) -> None:
    with SessionLocal() as s:
        s.add(AuditRow(**kw))
        s.commit()


def record_run(as_of: str, mode: str, n_sources: int, n_commitments: int,
               payload: dict) -> None:
    with SessionLocal() as s:
        s.add(RunRow(as_of=as_of, mode=mode, n_sources=n_sources,
                     n_commitments=n_commitments, payload=payload))
        s.commit()
