"""Reconcile many mentions of the same obligation into one Commitment.

This is where the assignment's traps are actually handled:

* Dedup          -- the vendor list is mentioned in the transcript, four
                    emails and a voice note. One commitment, six citations.
* Supersession   -- the last authoritative statement wins, and the ones it
                    replaced are kept as a visible trail rather than deleted.
* Ownership      -- an owner is asserted only by a COMMIT. If every party
                    disclaims and nobody commits, the owner is UNCLEAR and the
                    item is escalated. The agent never guesses.
* Closure        -- a DELIVER/CONFIRM later than the final commitment closes
                    the item, so finished work stops nagging the executive.
* Direction      -- "my actions" vs "waiting on others", relative to Arjun.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.agent.dates import humanize
from app.agent.extract import TOPICS, UNCLEAR, Mention
from app.agent.ingest import name_of

PRINCIPAL = "arjun"
NON_PERSONS = {"all_staff", "facilities"}   # distribution lists own nothing

# Direction
MINE = "mine"
WAITING = "waiting_on"
UNOWNED = "unowned"

# Status
DONE = "done"
OVERDUE = "overdue"
DUE_TODAY = "due_today"
UPCOMING = "upcoming"
NO_DEADLINE = "no_deadline"


@dataclass
class Evidence:
    source_id: str
    label: str
    ts: str
    quote: str
    acts: list[str]


@dataclass
class HistoryEvent:
    ts: str
    source_id: str
    kind: str          # committed | rescheduled | chased | delivered | disclaimed
    detail: str


@dataclass
class Commitment:
    id: str
    title: str
    owner: str                 # person id or UNCLEAR
    owner_name: str
    counterparty: str | None
    counterparty_name: str | None
    direction: str
    status: str
    due_at: str | None
    due_phrase: str | None
    due_human: str | None
    confidence: float
    slip_count: int
    needs_escalation: bool
    ownership_note: str | None
    evidence: list[Evidence] = field(default_factory=list)
    history: list[HistoryEvent] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "title": self.title,
            "owner": self.owner, "owner_name": self.owner_name,
            "counterparty": self.counterparty, "counterparty_name": self.counterparty_name,
            "direction": self.direction, "status": self.status,
            "due_at": self.due_at, "due_phrase": self.due_phrase,
            "due_human": self.due_human, "confidence": self.confidence,
            "slip_count": self.slip_count,
            "needs_escalation": self.needs_escalation,
            "ownership_note": self.ownership_note,
            "evidence": [e.__dict__ for e in self.evidence],
            "history": [h.__dict__ for h in self.history],
        }


def _valid_owner(pid: str | None) -> str | None:
    if not pid or pid in NON_PERSONS:
        return None
    return pid


def _classify_status(due: datetime | None, closed_at: datetime | None,
                     as_of: datetime, owner: str) -> str:
    if closed_at is not None:
        return DONE
    if owner == UNCLEAR:
        return OVERDUE if (due and due < as_of) else (
            DUE_TODAY if (due and due.date() == as_of.date()) else UPCOMING)
    if due is None:
        return NO_DEADLINE
    if due < as_of:
        return OVERDUE
    if due.date() == as_of.date():
        return DUE_TODAY
    return UPCOMING


def resolve_commitments(mentions: list[Mention], as_of: datetime) -> list[Commitment]:
    by_topic: dict[str, list[Mention]] = {}
    for m in mentions:
        by_topic.setdefault(m.topic, []).append(m)

    out: list[Commitment] = []
    for topic, ms in by_topic.items():
        ms.sort(key=lambda m: m.ts)

        # --- Ownership --------------------------------------------------
        commits = [m for m in ms if "COMMIT" in m.acts and _valid_owner(m.owner_claim)]
        disclaims = [m for m in ms if "DISCLAIM" in m.acts]
        delegations = [m for m in ms if "REQUEST" in m.acts and _valid_owner(m.owner_claim)]

        owner, ownership_note = UNCLEAR, None
        if commits:
            owner = commits[-1].owner_claim          # latest person to accept it
        elif delegations and not disclaims:
            owner = delegations[-1].owner_claim      # asked, not yet accepted
        else:
            voiced = {m.owner_hint for m in ms if m.owner_hint}
            who = ", ".join(sorted(voiced)) if voiced else None
            ownership_note = (
                f"No one has accepted this. {len(disclaims)} source(s) explicitly "
                f"disclaim or question ownership"
                + (f"; {who} was suggested but never confirmed." if who
                   else "; no owner was ever named.")
            )

        # --- Counterparty -----------------------------------------------
        counterparty = None
        for m in reversed(ms):
            if _valid_owner(m.counterparty) and m.counterparty != owner:
                counterparty = m.counterparty
                break

        # --- Deadline: latest authoritative statement wins ---------------
        authoritative = [m for m in ms if m.due and (
            {"COMMIT", "REQUEST", "RESCHEDULE"} & set(m.acts))]
        due_source = authoritative[-1] if authoritative else None
        if due_source is None:
            dated = [m for m in ms if m.due]
            due_source = dated[-1] if dated else None

        due_at = due_source.due.due_at if due_source else None
        due_phrase = due_source.due.phrase if due_source else None

        # How many times the deadline actually moved.
        seen_dues, slips = [], 0
        for m in authoritative:
            d = m.due.due_at
            if seen_dues and d != seen_dues[-1]:
                slips += 1
            seen_dues.append(d)

        # --- Closure ------------------------------------------------------
        last_commit_ts = commits[-1].ts if commits else None
        closed_at = None
        for m in ms:
            # A chase or a disclaimer can contain the word "confirmed"
            # ("has anyone confirmed who's signing off?") -- that is a question
            # about the item, not the closing of it.
            if {"CHASE", "DISCLAIM"} & set(m.acts):
                continue
            if m.is_closing and (last_commit_ts is None or m.ts >= last_commit_ts):
                closed_at = m.ts
                break
        # Nothing nobody owns can be finished.
        if owner == UNCLEAR:
            closed_at = None

        status = _classify_status(due_at, closed_at, as_of, owner)

        # --- Direction ----------------------------------------------------
        if owner == UNCLEAR:
            direction = UNOWNED
        elif owner == PRINCIPAL:
            direction = MINE
        else:
            direction = WAITING

        # --- Confidence ----------------------------------------------------
        conf = 0.5
        conf += 0.2 if commits else 0.0
        conf += 0.1 if len(ms) >= 3 else 0.0
        conf += 0.1 if due_source and due_source.due.explicit else 0.0
        if owner == UNCLEAR:
            conf = min(conf, 0.45)
        conf = round(min(conf, 0.98), 2)

        # --- Evidence + history --------------------------------------------
        evidence = [Evidence(m.source_id, m.label, m.ts.isoformat(timespec="minutes"),
                             m.text, m.acts) for m in ms]
        history: list[HistoryEvent] = []
        prev_due = None
        for m in ms:
            ts = m.ts.isoformat(timespec="minutes")
            if "COMMIT" in m.acts and m.due:
                if prev_due is None:
                    kind, verb = "committed", "set the deadline to"
                elif m.due.due_at != prev_due:
                    kind, verb = "rescheduled", "moved the deadline to"
                else:
                    # Same date said again -- a restatement, not a new promise.
                    # Labelling it "committed" makes the trail read as though
                    # the deadline reset when it did not.
                    kind, verb = "restated", "restated the deadline as"
                history.append(HistoryEvent(ts, m.source_id, kind,
                    f"{name_of(m.speaker)} {verb} "
                    f"{m.due.due_at:%a %d %b %H:%M} (\"{m.due.phrase}\")"))
                prev_due = m.due.due_at
            elif "RESCHEDULE" in m.acts and m.due:
                history.append(HistoryEvent(ts, m.source_id, "rescheduled",
                    f"{name_of(m.speaker)} moved it to {m.due.due_at:%a %d %b %H:%M}"))
                prev_due = m.due.due_at
            elif m.is_closing:
                history.append(HistoryEvent(ts, m.source_id, "delivered",
                    f"{name_of(m.speaker)} closed the loop"))
            elif "CHASE" in m.acts:
                history.append(HistoryEvent(ts, m.source_id, "chased",
                    f"{name_of(m.speaker)} followed up"))
            elif "DISCLAIM" in m.acts:
                history.append(HistoryEvent(ts, m.source_id, "disclaimed",
                    f"{name_of(m.speaker)} did not take ownership"))

        out.append(Commitment(
            id=topic,
            title=TOPICS[topic]["title"],
            owner=owner,
            owner_name=UNCLEAR if owner == UNCLEAR else name_of(owner),
            counterparty=counterparty,
            counterparty_name=name_of(counterparty) if counterparty else None,
            direction=direction,
            status=status,
            due_at=due_at.isoformat(timespec="minutes") if due_at else None,
            due_phrase=due_phrase,
            due_human=humanize(due_at, as_of) if due_at else None,
            confidence=conf,
            slip_count=slips,
            needs_escalation=(owner == UNCLEAR),
            ownership_note=ownership_note,
            evidence=evidence,
            history=history,
        ))

    order = {OVERDUE: 0, DUE_TODAY: 1, UPCOMING: 2, NO_DEADLINE: 3, DONE: 4}
    out.sort(key=lambda c: (order.get(c.status, 9), c.due_at or "9999"))
    return out
