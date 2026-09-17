"""Normalize four very different source formats into one timestamped stream.

Transcript utterances, emails, calendar entries and voice notes all become
SourceUnit records. Everything downstream -- extraction, dedup, supersession,
citations -- works on this single shape, which is why adding a fifth source
type later costs one function, not a rewrite.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from functools import lru_cache

from app.config import DATA_DIR


@dataclass
class SourceUnit:
    id: str
    kind: str                 # transcript | email | calendar | voice_note
    ts: datetime              # when it was said/sent -- anchors date resolution
    speaker: str              # person id who produced it
    audience: list[str] = field(default_factory=list)
    text: str = ""
    label: str = ""           # human-readable provenance, shown in the UI
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ts"] = self.ts.isoformat(timespec="minutes")
        return d


def _load(name: str) -> dict:
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_people() -> dict:
    raw = _load("people.json")
    return {p["id"]: p for p in raw["people"]}


@lru_cache(maxsize=1)
def name_of(pid: str) -> str:
    return load_people().get(pid, {}).get("name", pid)


@lru_cache(maxsize=1)
def load_sources() -> tuple[SourceUnit, ...]:
    units: list[SourceUnit] = []

    # --- Meeting transcript -------------------------------------------------
    tr = _load("transcript.json")
    base = datetime.fromisoformat(f"{tr['date']}T{tr['time'].split('-')[0]}")
    for u in tr["utterances"]:
        units.append(SourceUnit(
            id=u["id"], kind="transcript", ts=base, speaker=u["speaker"],
            audience=[a for a in tr["attendees"] if a != u["speaker"]],
            text=u["text"],
            label=f"{tr['title']}, Mon 21 Sep 9:00 AM - {name_of(u['speaker'])}",
            meta={"title": tr["title"]},
        ))

    # --- Email threads ------------------------------------------------------
    em = _load("emails.json")
    for thread in em["threads"]:
        for m in thread["messages"]:
            ts = datetime.fromisoformat(m["ts"])
            units.append(SourceUnit(
                id=m["id"], kind="email", ts=ts, speaker=m["from"],
                audience=m["to"], text=m["body"],
                label=f"Email \"{thread['subject']}\", {ts:%a %d %b %H:%M} - from {name_of(m['from'])}",
                meta={"subject": thread["subject"], "thread_id": thread["thread_id"]},
            ))

    # --- Voice notes --------------------------------------------------------
    vn = _load("voice_notes.json")
    for n in vn["notes"]:
        ts = datetime.fromisoformat(n["ts"])
        units.append(SourceUnit(
            id=n["id"], kind="voice_note", ts=ts, speaker=n["speaker"],
            audience=[], text=n["text"],
            label=f"Voice note, {ts:%a %d %b %H:%M}" + (f" ({n['context']})" if n.get("context") else ""),
            meta={"context": n.get("context", "")},
        ))

    # --- Calendars ----------------------------------------------------------
    cal = _load("calendars.json")
    for owner, entries in cal["calendars"].items():
        for e in entries:
            ts = datetime.fromisoformat(f"{e['date']}T{e['start']}")
            units.append(SourceUnit(
                id=e["id"], kind="calendar", ts=ts, speaker=owner,
                audience=[], text=e["event"],
                label=f"{name_of(owner)}'s calendar, {ts:%a %d %b} {e['start']}-{e['end']} - {e['event']}",
                meta={"owner": owner, "start": e["start"], "end": e["end"], "date": e["date"]},
            ))

    units.sort(key=lambda u: (u.ts, u.id))
    return tuple(units)


def sources_upto(as_of: datetime) -> list[SourceUnit]:
    """Only what the executive could actually have seen by `as_of`.

    This is what makes the week replayable: ask for Tuesday's brief and the
    agent genuinely does not know about Wednesday's emails.
    """
    return [u for u in load_sources() if u.ts <= as_of]
