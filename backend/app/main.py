"""Executive Productivity Agent -- REST API.

Endpoints are deliberately thin: all judgement lives in app/agent/, so the
same pipeline can be driven by this API, by a test, or by a CLI without
duplicating logic.
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.agent.brief import build_brief
from app.agent.extract import extract_mentions
from app.agent.ingest import load_people, load_sources, sources_upto
from app.agent.qa import SUGGESTED, answer_best
from app.agent.resolve import resolve_commitments
from app.config import (DEFAULT_AS_OF, WEEK_END, WEEK_START, active_provider,
                        llm_enabled, mode)
from app.db import SessionLocal, SourceRow, log_audit, record_run, seed_sources

app = FastAPI(
    title="Executive Productivity Agent",
    version="1.0.0",
    description=(
        "Turns a week of messy executive inputs -- a meeting transcript, four "
        "calendars, five email threads and two voice notes -- into a daily "
        "action brief with full provenance.\n\n"
        "Built for the AIONOS Agentic AI Factory assignment."
    ),
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


# Initialize at import rather than on a startup event: this keeps the API
# correct under TestClient, under `uvicorn --reload`, and on hosted cold
# starts, where startup hooks are easy to miss. seed_sources() is idempotent.
seed_sources()


def _parse_as_of(as_of: str | None) -> datetime:
    raw = as_of or DEFAULT_AS_OF
    try:
        return datetime.fromisoformat(raw if "T" in raw else f"{raw}T09:00")
    except ValueError:
        raise HTTPException(422, f"as_of must be ISO-8601, got {raw!r}")


def _pipeline(as_of: datetime):
    """ingest -> extract -> resolve. The whole agent in one line."""
    units = sources_upto(as_of)
    commitments = resolve_commitments(extract_mentions(units), as_of)
    return units, commitments


# --------------------------------------------------------------------------
@app.get("/api/health", tags=["meta"])
def health() -> dict:
    p = active_provider()
    return {
        "status": "ok",
        "mode": mode(),
        "llm_enabled": llm_enabled(),
        "provider": p["name"] if p else None,
        "model": p["model"] if p else None,
        # Be exact about what a configured key actually changes. The brief is
        # deterministic in every mode by design, so a green "LLM" badge must
        # never imply the ranking or the deadlines came from a model.
        "llm_used_for": ["ask"] if llm_enabled() else [],
        "always_deterministic": ["brief", "commitments", "dedup",
                                 "supersession", "ownership", "status"],
        "week": {"start": WEEK_START, "end": WEEK_END},
        "default_as_of": DEFAULT_AS_OF,
    }


@app.get("/api/brief", tags=["agent"])
def get_brief(as_of: str | None = Query(None, description="ISO datetime inside the week, e.g. 2026-09-23T09:00")) -> dict:
    t0 = time.perf_counter()
    dt = _parse_as_of(as_of)
    units, commitments = _pipeline(dt)
    payload = build_brief(commitments, dt)
    payload["mode"] = mode()
    payload["sources_considered"] = len(units)
    payload["fragments_heard"] = len(units)
    ms = (time.perf_counter() - t0) * 1000

    record_run(dt.isoformat(timespec="minutes"), mode(), len(units), len(commitments), payload)
    log_audit(as_of=dt.isoformat(timespec="minutes"), mode=mode(), action="brief",
              citations=[c.id for c in commitments], grounded=1, latency_ms=ms)
    payload["latency_ms"] = round(ms, 1)
    return payload


@app.get("/api/commitments", tags=["agent"])
def get_commitments(as_of: str | None = None, direction: str | None = None,
                    status: str | None = None) -> dict:
    dt = _parse_as_of(as_of)
    _, commitments = _pipeline(dt)
    items = [c.to_dict() for c in commitments]
    if direction:
        items = [c for c in items if c["direction"] == direction]
    if status:
        items = [c for c in items if c["status"] == status]
    return {"as_of": dt.isoformat(timespec="minutes"), "count": len(items), "items": items}


class AskBody(BaseModel):
    question: str = Field(..., min_length=2, examples=["What did I promise Raghav?"])
    as_of: str | None = Field(None, examples=["2026-09-23T09:00"])


@app.post("/api/ask", tags=["agent"])
def ask(body: AskBody) -> dict:
    t0 = time.perf_counter()
    dt = _parse_as_of(body.as_of)
    _, commitments = _pipeline(dt)
    res = answer_best(body.question, commitments, dt)
    ms = (time.perf_counter() - t0) * 1000
    res["mode"] = mode()
    res["latency_ms"] = round(ms, 1)
    log_audit(as_of=dt.isoformat(timespec="minutes"), mode=mode(), action="ask",
              question=body.question, intent=res["intent"], answer=res["answer"],
              citations=res["citations"], grounded=int(res["grounded"]), latency_ms=ms)
    return res


@app.get("/api/suggested", tags=["agent"])
def suggested() -> dict:
    return {"questions": SUGGESTED}


@app.get("/api/sources", tags=["provenance"])
def get_sources(kind: str | None = None, ids: str | None = None) -> dict:
    with SessionLocal() as s:
        q = s.query(SourceRow)
        if kind:
            q = q.filter(SourceRow.kind == kind)
        if ids:
            q = q.filter(SourceRow.id.in_([i.strip() for i in ids.split(",")]))
        rows = q.order_by(SourceRow.ts).all()
        return {"count": len(rows), "items": [{
            "id": r.id, "kind": r.kind, "ts": r.ts.isoformat(timespec="minutes"),
            "speaker": r.speaker, "audience": r.audience, "text": r.text,
            "label": r.label, "meta": r.meta,
        } for r in rows]}


@app.get("/api/people", tags=["provenance"])
def people() -> dict:
    return {"people": list(load_people().values())}


@app.get("/api/audit", tags=["provenance"])
def audit(limit: int = 50) -> dict:
    from app.db import AuditRow
    with SessionLocal() as s:
        rows = s.query(AuditRow).order_by(AuditRow.id.desc()).limit(limit).all()
        return {"count": len(rows), "items": [{
            "id": r.id, "at": r.created_at.isoformat(timespec="seconds"),
            "as_of": r.as_of, "mode": r.mode, "action": r.action,
            "question": r.question, "intent": r.intent, "answer": r.answer,
            "citations": r.citations, "grounded": bool(r.grounded),
            "latency_ms": round(r.latency_ms or 0, 1),
        } for r in rows]}


# --- UI --------------------------------------------------------------------
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")
