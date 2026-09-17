"""Assemble the daily action brief.

The brief is deliberately opinionated about ordering: what is late, then what
is due today, then what the executive is blocked on, then what nobody owns.
An executive reads the top three lines and nothing else, so the ranking is the
product.
"""
from __future__ import annotations

from datetime import datetime

from app.agent.resolve import (DONE, DUE_TODAY, MINE, OVERDUE, UNOWNED,
                               WAITING, Commitment)


def _line(c: Commitment) -> dict:
    d = c.to_dict()
    # A finished item should not shout a stale deadline at anyone.
    if c.status == DONE:
        d["due_human"] = "completed"
    return d


def build_brief(commitments: list[Commitment], as_of: datetime) -> dict:
    mine = [c for c in commitments if c.direction == MINE]
    waiting = [c for c in commitments if c.direction == WAITING]
    unowned = [c for c in commitments if c.direction == UNOWNED]

    overdue = [c for c in mine if c.status == OVERDUE]
    today = [c for c in mine if c.status == DUE_TODAY]
    upcoming = [c for c in mine if c.status not in (OVERDUE, DUE_TODAY, DONE)]
    done = [c for c in commitments if c.status == DONE]

    open_waiting = [c for c in waiting if c.status != DONE]

    # The headline is the single most useful sentence the agent can produce.
    if overdue:
        headline = (f"{len(overdue)} commitment{'s' if len(overdue) > 1 else ''} "
                    f"of yours {'are' if len(overdue) > 1 else 'is'} overdue.")
    elif today:
        headline = (f"{len(today)} of your commitments "
                    f"{'are' if len(today) > 1 else 'is'} due today.")
    else:
        headline = "Nothing of yours is due today."
    if unowned:
        headline += f" {len(unowned)} item{'s' if len(unowned) > 1 else ''} still has no owner."

    return {
        "as_of": as_of.isoformat(timespec="minutes"),
        "as_of_human": f"{as_of:%A %d %B %Y, %H:%M}",
        "headline": headline,
        "counts": {
            "overdue": len(overdue), "due_today": len(today),
            "upcoming": len(upcoming), "waiting_on": len(open_waiting),
            "unowned": len(unowned), "done": len(done),
            "total_open": len(commitments) - len(done),
        },
        "sections": [
            {"key": "overdue", "title": "Overdue - your commitments",
             "hint": "You promised these and the date has passed.",
             "items": [_line(c) for c in overdue]},
            {"key": "due_today", "title": "Due today - your commitments",
             "hint": "Owed by you before end of day.",
             "items": [_line(c) for c in today]},
            {"key": "waiting_on", "title": "Waiting on others",
             "hint": "Not your action. Chase only if the date is at risk.",
             "items": [_line(c) for c in open_waiting]},
            {"key": "unowned", "title": "Unclear ownership - needs a decision",
             "hint": "The agent will not assign these. Someone must.",
             "items": [_line(c) for c in unowned]},
            {"key": "upcoming", "title": "Upcoming - your commitments",
             "hint": "Not yet due.",
             "items": [_line(c) for c in upcoming]},
            {"key": "done", "title": "Closed this week",
             "hint": "Delivered or confirmed. Shown so you know it is handled.",
             "items": [_line(c) for c in done]},
        ],
    }
