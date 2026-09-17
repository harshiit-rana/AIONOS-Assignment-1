"""Deterministic extraction: source text -> commitment mentions.

This is the fallback path that runs with no API key, and it is also the
reference the LLM path is validated against. It produces Mention records --
one per (source, topic) pair -- which resolve.py then clusters and reconciles.

Two things make it work on real conversational data:

1. Topic carries forward. "I'll have it ready Wednesday evening" names no
   subject; it only means anything because of the line before it. Transcript
   utterances inherit the topic of the previous utterance, and emails inherit
   their thread subject.
2. Speech acts, not keywords. The same topic word means opposite things in
   "I'll send it" (commitment), "can you send it?" (delegation) and "not on
   my end" (disclaimer). Ownership is decided by the act, never by proximity.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from app.agent.dates import ResolvedDue, resolve_due
from app.agent.ingest import SourceUnit

UNCLEAR = "UNCLEAR"

# --- Topic lexicon ---------------------------------------------------------
# Multi-word anchors score higher than single words, so "call" alone never
# outvotes "expense variance report".
TOPICS: dict[str, dict] = {
    "vendor_list": {
        "title": "Send updated vendor list to Raghav",
        "strong": ["vendor list"],
        "weak": ["vendor"],
    },
    "campaign_deck": {
        "title": "Q3 campaign deck review with Neha",
        "strong": ["campaign deck", "q3 campaign", "deck review", "data slides"],
        "weak": ["deck", "campaign"],
    },
    "expense_variance": {
        "title": "July expense variance report from Divya",
        "strong": ["expense variance", "variance report", "july variance",
                   "variance numbers"],
        "weak": ["variance"],
    },
    "meridian_call": {
        "title": "Reconfirm Meridian Logistics call time with Priya",
        "strong": ["meridian", "call reschedule", "reconfirm"],
        "weak": ["new time", "reschedule", "bumped"],
    },
    "mumbai_lease": {
        "title": "Mumbai office lease renewal signature",
        "strong": ["mumbai", "lease renewal", "office renewal", "lease"],
        "weak": ["renewal", "signature", "sign off", "paperwork"],
    },
}

# --- Speech-act cues -------------------------------------------------------
ACTS: dict[str, list[str]] = {
    # Speaker takes the obligation on themselves.
    "COMMIT": [r"\bi'll\b", r"\bi will\b", r"\bwill send\b", r"\bi'd send\b",
               r"\bneed to get\b", r"\bi owe\b", r"\bneed to lock\b",
               r"\btargeting\b", r"\bprioritize\b", r"\bdoable\b",
               r"\bneed to reconfirm\b", r"\bstarting on\b"],
    # Speaker pushes the obligation to someone else.
    "REQUEST": [r"\bcan you\b", r"\bcould you\b", r"\bcan i get\b",
                r"\bhow about\b", r"\bneeds someone\b", r"\brequires\b",
                r"\bpropose a new time\b", r"\bin my hands\b"],
    # The thing was actually produced.
    "DELIVER": [r"\battached\b", r"\battaching\b", r"\bsent as promised\b",
                r"\bis ready\b"],
    # Agreement that closes the loop.
    "CONFIRM": [r"\bconfirmed\b", r"\bworks on our end\b", r"\bgot it\b",
                r"\bsee you at\b"],
    # Nudge -- evidence of pressure, not of progress.
    "CHASE": [r"\bjust checking\b", r"\bstill good\b", r"\bfollowing up\b",
              r"\bquick check\b", r"\bstill on for\b", r"\bsecond reminder\b",
              r"\breminder:\b", r"\bhas anyone\b", r"\bstill pending\b",
              r"\bconfirm who\b", r"\bone day out\b"],
    # Explicit denial of ownership -- the signal that stops the agent guessing.
    "DISCLAIM": [r"\bnot on my end\b", r"\bthink it's me\b",
                 r"\bnot sure whose\b", r"\bbeen assigned\b",
                 r"\bpick it up\b", r"\bstill unowned\b",
                 r"\bnot us\b", r"\bneeds to own\b",
                 r"\bneeds someone to sign off\b", r"\bdon't assume\b"],
    # The deadline moved.
    "RESCHEDULE": [r"\bshifting\b", r"\binstead\b", r"\bgot pushed\b",
                   r"\bgot bumped\b", r"\bmight slip\b"],
}

# Phrases naming a party that ownership might sit with, used only to record
# the *suggestion*, never to assign the owner.
OWNER_HINTS = [(r"\bfacilities\b", "facilities")]


@dataclass
class Mention:
    """One topic as it appears in one source. The atom of the pipeline."""
    source_id: str
    topic: str
    ts: datetime
    speaker: str
    acts: list[str] = field(default_factory=list)
    due: ResolvedDue | None = None
    owner_claim: str | None = None      # who this source puts on the hook
    counterparty: str | None = None
    owner_hint: str | None = None       # a *guess* someone voiced
    text: str = ""
    label: str = ""

    @property
    def is_closing(self) -> bool:
        return "DELIVER" in self.acts or "CONFIRM" in self.acts


def _score_topic(text: str) -> tuple[str | None, float]:
    t = text.lower()
    best, best_score = None, 0.0
    for key, cfg in TOPICS.items():
        score = sum(3.0 for s in cfg["strong"] if s in t)
        score += sum(1.0 for w in cfg["weak"] if re.search(rf"\b{re.escape(w)}\b", t))
        if score > best_score:
            best, best_score = key, score
    return best, best_score


def _detect_acts(text: str) -> list[str]:
    t = text.lower()
    return [act for act, pats in ACTS.items() if any(re.search(p, t) for p in pats)]


def _owner_hint(text: str) -> str | None:
    t = text.lower()
    for pat, who in OWNER_HINTS:
        if re.search(pat, t):
            return who
    return None


def _segments(text: str) -> list[str]:
    """Split on sentence boundaries and 'Also/Separately' pivots.

    Executives pack two unrelated obligations into one breath -- voice note 2
    covers both the variance report and the Meridian call.
    """
    parts = re.split(
        r"(?<=[.?!])\s+|\s*\bAlso,?\s+|\s*\bSeparately,?\s+",
        text, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p and p.strip()]


def _resolve_parties(unit: SourceUnit, acts: list[str]) -> tuple[str | None, str | None]:
    """Who owns it and who is the counterparty, decided by speech act."""
    if "DISCLAIM" in acts and "COMMIT" not in acts:
        return None, None
    if "COMMIT" in acts:
        owner = unit.speaker
        other = unit.audience[0] if unit.audience else None
        return owner, other
    if "REQUEST" in acts:
        # The asker delegates to the addressee.
        target = unit.audience[0] if unit.audience else None
        return target, unit.speaker
    if "DELIVER" in acts:
        return unit.speaker, (unit.audience[0] if unit.audience else None)
    return None, None


def extract_mentions(units: list[SourceUnit]) -> list[Mention]:
    mentions: list[Mention] = []
    last_topic: str | None = None       # transcript dialogue state

    for unit in units:
        if unit.kind == "calendar":
            continue  # calendars corroborate; they don't create commitments

        # Emails inherit their thread subject as topic context.
        subject_topic = None
        if unit.kind == "email" and unit.meta.get("subject"):
            subject_topic, _ = _score_topic(unit.meta["subject"])

        seen_in_unit: dict[str, Mention] = {}
        carried = last_topic if unit.kind == "transcript" else subject_topic

        for seg in _segments(unit.text):
            topic, score = _score_topic(seg)
            if score < 3.0:
                # No strong anchor in this clause -> it continues the current
                # subject (transcript reply, or the email's thread).
                topic = topic if (score > 0 and carried is None) else carried
            if not topic:
                continue

            acts = _detect_acts(seg)
            due = resolve_due(seg, unit.ts)
            hint = _owner_hint(seg)

            if not acts and not due:
                continue  # no obligation and no deadline -> noise

            if topic in seen_in_unit:
                m = seen_in_unit[topic]
                m.acts = sorted(set(m.acts) | set(acts))
                m.due = m.due or due
                m.owner_hint = m.owner_hint or hint
                if m.owner_claim is None:
                    m.owner_claim, m.counterparty = _resolve_parties(unit, m.acts)
            else:
                owner, other = _resolve_parties(unit, acts)
                m = Mention(
                    source_id=unit.id, topic=topic, ts=unit.ts, speaker=unit.speaker,
                    acts=acts, due=due, owner_claim=owner, counterparty=other,
                    owner_hint=hint, text=unit.text, label=unit.label,
                )
                seen_in_unit[topic] = m
            carried = topic

        if unit.kind == "transcript":
            last_topic = carried or last_topic
        mentions.extend(seen_in_unit.values())

    mentions.sort(key=lambda m: (m.ts, m.source_id))
    return mentions
