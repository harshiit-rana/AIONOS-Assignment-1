"""Question answering over the resolved commitments.

Grounding rule, enforced in both paths: an answer may only reference
commitments the resolver actually produced, and every answer carries the
source ids it was derived from. The agent cannot assert something the data
pack does not contain -- if nothing matches, it says so.

The deterministic path handles the intents the brief names explicitly
("What did I promise Raghav?", "What needs action today?"). The LLM path,
when a key is configured, handles free-form phrasing by selecting from the
same resolved set -- it never invents commitments, it only picks and explains.
"""
from __future__ import annotations

import re
from datetime import datetime

from app.agent.ingest import load_people
from app.agent.resolve import (DONE, DUE_TODAY, MINE, OVERDUE, PRINCIPAL,
                               UNOWNED, WAITING, Commitment)

# --- intent cues -----------------------------------------------------------
PROMISE_CUES = [r"\bpromis", r"\bowe\b", r"\bcommit", r"\btold\b", r"\bsaid i'd\b"]
TODAY_CUES = [r"\btoday\b", r"\bneeds action\b", r"\bmy actions?\b",
              r"\bwhat should i do\b", r"\bnow\b", r"\bpriorit"]
WAITING_CUES = [r"\bwaiting\b", r"\bblocked\b", r"\bfrom others\b",
                r"\bwho owes me\b", r"\bchasing\b"]
OVERDUE_CUES = [r"\boverdue\b", r"\blate\b", r"\bslipp", r"\bmissed\b", r"\bbehind\b"]
UNOWNED_CUES = [r"\bunowned\b", r"\bno owner\b", r"\bunclear\b", r"\bnobody\b",
                r"\bwho owns\b", r"\bwho is responsible\b", r"\bunassigned\b"]
DONE_CUES = [r"\bdone\b", r"\bcompleted\b", r"\bclosed\b", r"\bfinished\b",
             r"\bdelivered\b"]


def _hit(text: str, cues: list[str]) -> bool:
    return any(re.search(c, text) for c in cues)


def _person_in(text: str) -> str | None:
    """Find a named person, by first name or full name."""
    t = text.lower()
    for pid, p in load_people().items():
        if pid == PRINCIPAL:
            continue
        first = p["name"].split()[0].lower()
        if re.search(rf"\b{re.escape(first)}\b", t) or p["name"].lower() in t:
            return pid
    return None


def _fmt(c: Commitment) -> str:
    bits = []
    if c.status == DONE:
        bits.append("completed")
    elif c.due_human:
        bits.append(c.due_human)
    if c.slip_count:
        bits.append(f"deadline moved {c.slip_count}x")
    tail = f" ({', '.join(bits)})" if bits else ""
    return f"{c.title}{tail}"


def answer(question: str, commitments: list[Commitment], as_of: datetime) -> dict:
    q = question.lower().strip()
    open_items = [c for c in commitments if c.status != DONE]
    matched: list[Commitment] = []
    intent = "general"
    text = ""

    person = _person_in(q)

    # 1. "What did I promise Raghav?"
    if person and _hit(q, PROMISE_CUES):
        intent = "promises_to_person"
        matched = [c for c in commitments
                   if c.direction == MINE and c.counterparty == person]
        name = load_people()[person]["name"]
        if matched:
            text = f"You have {len(matched)} open commitment to {name}: " + \
                   "; ".join(_fmt(c) for c in matched) + "."
        else:
            text = f"Nothing in this week's sources shows a commitment from you to {name}."

    # 2. Anything involving a named person
    elif person:
        intent = "person_scope"
        matched = [c for c in commitments
                   if person in (c.owner, c.counterparty)]
        name = load_people()[person]["name"]
        text = (f"{len(matched)} item(s) involve {name}: " +
                "; ".join(_fmt(c) for c in matched) + ".") if matched else \
               f"No items in the data pack involve {name}."

    # 3. "What needs action today?"
    elif _hit(q, TODAY_CUES):
        intent = "today"
        matched = [c for c in open_items
                   if c.direction == MINE and c.status in (OVERDUE, DUE_TODAY)]
        if matched:
            text = f"{len(matched)} item(s) need your action today: " + \
                   "; ".join(_fmt(c) for c in matched) + "."
        else:
            text = "Nothing of yours is due today."
        esc = [c for c in open_items if c.direction == UNOWNED]
        if esc:
            text += (f" Separately, {len(esc)} item(s) still have no owner and "
                     f"need you to assign someone: " +
                     "; ".join(_fmt(c) for c in esc) + ".")
            matched += esc

    elif _hit(q, OVERDUE_CUES):
        intent = "overdue"
        matched = [c for c in open_items if c.status == OVERDUE]
        text = (f"{len(matched)} item(s) are overdue: " +
                "; ".join(_fmt(c) for c in matched) + ".") if matched \
               else "Nothing is overdue right now."

    elif _hit(q, WAITING_CUES):
        intent = "waiting_on"
        matched = [c for c in open_items if c.direction == WAITING]
        text = (f"You are waiting on {len(matched)} item(s): " +
                "; ".join(f"{_fmt(c)} - owner {c.owner_name}" for c in matched) + ".") \
               if matched else "You are not blocked on anyone right now."

    elif _hit(q, UNOWNED_CUES):
        intent = "unowned"
        matched = [c for c in commitments if c.direction == UNOWNED]
        if matched:
            text = "; ".join(
                f"{c.title} - no accepted owner. {c.ownership_note}" for c in matched)
        else:
            text = "Every open item has an accepted owner."

    elif _hit(q, DONE_CUES):
        intent = "done"
        matched = [c for c in commitments if c.status == DONE]
        text = (f"{len(matched)} item(s) closed: " +
                "; ".join(_fmt(c) for c in matched) + ".") if matched \
               else "Nothing has been closed yet."

    else:
        # Fall back to lexical overlap against titles and evidence.
        intent = "search"
        terms = {w for w in re.findall(r"[a-z]{4,}", q)}
        scored = []
        for c in commitments:
            blob = (c.title + " " + " ".join(e.quote for e in c.evidence)).lower()
            score = sum(1 for w in terms if w in blob)
            if score:
                scored.append((score, c))
        scored.sort(key=lambda x: -x[0])
        matched = [c for _, c in scored[:3]]
        text = ("Closest matches: " + "; ".join(_fmt(c) for c in matched) + ".") \
               if matched else \
               ("I can only answer from this week's transcript, emails, calendars "
                "and voice notes, and nothing there matches that question.")

    return {
        "question": question,
        "intent": intent,
        "answer": text,
        "as_of": as_of.isoformat(timespec="minutes"),
        "commitments": [c.to_dict() for c in matched],
        "citations": sorted({e.source_id for c in matched for e in c.evidence}),
        "grounded": bool(matched),
    }


SUGGESTED = [
    "What did I promise Raghav?",
    "What needs action today?",
    "What am I waiting on from others?",
    "What is overdue?",
    "Who owns the Mumbai lease renewal?",
    "What has been completed this week?",
]
