"""Resolve the vague date language executives actually use.

Every phrase is resolved relative to the timestamp of the source that uttered
it -- "tomorrow" in Monday's transcript and "tomorrow" in Tuesday's email are
different days. Getting this wrong is what makes naive agents miss slippage.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

WEEKDAYS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2, "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4, "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}

# Time-of-day buckets. An unqualified deadline means end of day: we must not
# invent a precise hour the source never gave.
BUCKETS = {
    "morning": (12, 0, "morning"),
    "first thing": (9, 0, "morning"),
    "afternoon": (17, 0, "afternoon"),
    "evening": (20, 0, "evening"),
    "end of day": (23, 59, "end of day"),
    "eod": (23, 59, "end of day"),
}

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "sept": 9, "october": 10,
    "november": 11, "december": 12,
}


@dataclass
class ResolvedDue:
    """A deadline plus the exact words it came from -- never a bare datetime."""
    due_at: datetime
    phrase: str
    precision: str          # "datetime" | "end of day" | "morning" | ...
    explicit: bool          # True if an actual date/weekday was named

    def iso(self) -> str:
        return self.due_at.isoformat(timespec="minutes")


def _bucket_for(text: str) -> tuple[int, int, str]:
    for key, val in BUCKETS.items():
        if key in text:
            return val
    return (23, 59, "end of day")


def _weekday_in_week(target_wd: int, ref: date) -> date:
    """Map a weekday name onto the data pack's Mon-Fri week.

    The pack is one fixed week, so a named weekday means that weekday of this
    week. We only roll forward when the named day is strictly before the
    reference day AND the reference is late in the week -- otherwise "Friday"
    said on Monday would wrongly jump to next week.
    """
    monday = ref - timedelta(days=ref.weekday())
    return monday + timedelta(days=target_wd)


def resolve_due(text: str, source_ts: datetime) -> ResolvedDue | None:
    """Extract the first deadline expression in `text`, relative to `source_ts`."""
    if not text:
        return None
    t = text.lower()
    ref = source_ts.date()

    # 1. Explicit calendar date: "Friday, 25 September"
    m = re.search(r"(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|sept|october|november|december)", t)
    if m:
        day, month = int(m.group(1)), MONTHS[m.group(2)]
        hh, mm, prec = _bucket_for(t)
        return ResolvedDue(datetime(source_ts.year, month, day, hh, mm), m.group(0), prec, True)

    # 2. Clock time today: "3:00 PM", "9:30 AM"
    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", t)
    clock = None
    if m:
        hh = int(m.group(1)) % 12
        if m.group(3) == "pm":
            hh += 12
        clock = (hh, int(m.group(2) or 0))

    # 3. Named weekday -- but people correct themselves mid-sentence:
    #      "shifting to Thursday morning instead of Wednesday"
    #      "I said Wednesday, but realistically Thursday morning is safer"
    #    A naive first-match reads both as Wednesday and silently misses the
    #    reschedule. We drop days that are explicitly superseded, then prefer
    #    whatever follows a contrast marker.
    scan = re.sub(r"instead of\s+\w+", " ", t)
    scan = re.sub(r"\bnot\s+(" + "|".join(WEEKDAYS) + r")\b", " ", scan)

    hits = [(m.start(), WEEKDAYS[m.group(1)], m.group(1))
            for m in re.finditer(r"\b(" + "|".join(WEEKDAYS) + r")\b", scan)]
    if hits:
        pivot = max((scan.rfind(" but "), scan.rfind(" instead"), scan.rfind("rather than")))
        after = []
        if pivot > -1:
            # The correction has to land in the same sentence. In "...by
            # Wednesday evening instead? Want time to review before Thursday."
            # the Thursday belongs to a new sentence and is context, not the
            # deadline.
            end = re.search(r"[.?!]", scan[pivot:])
            stop = pivot + end.start() if end else len(scan)
            after = [h for h in hits if pivot < h[0] < stop]
        pos, wd, name = (after or hits)[0]
        d = _weekday_in_week(wd, ref)
        if clock:
            return ResolvedDue(datetime(d.year, d.month, d.day, *clock), name, "datetime", True)
        hh, mm, prec = _bucket_for(t)
        return ResolvedDue(datetime(d.year, d.month, d.day, hh, mm), name, prec, True)

    # 4. Relative: today / tomorrow
    if "tomorrow" in t:
        d = ref + timedelta(days=1)
        if clock:
            return ResolvedDue(datetime(d.year, d.month, d.day, *clock), "tomorrow", "datetime", False)
        hh, mm, prec = _bucket_for(t)
        return ResolvedDue(datetime(d.year, d.month, d.day, hh, mm), "tomorrow", prec, False)

    if "today" in t or "this morning" in t:
        d = ref
        if clock:
            return ResolvedDue(datetime(d.year, d.month, d.day, *clock), "today", "datetime", False)
        hh, mm, prec = _bucket_for(t)
        return ResolvedDue(datetime(d.year, d.month, d.day, hh, mm), "today", prec, False)

    # 5. "this week" -> Friday end of day
    if "this week" in t:
        d = _weekday_in_week(4, ref)
        return ResolvedDue(datetime(d.year, d.month, d.day, 23, 59), "this week", "end of day", False)

    return None


def humanize(due: datetime, as_of: datetime) -> str:
    """'overdue by 1 day', 'due today', 'in 2 days' -- relative to the brief date."""
    delta_days = (due.date() - as_of.date()).days
    if due < as_of:
        if delta_days == 0:
            return "overdue (earlier today)"
        n = abs(delta_days)
        return f"overdue by {n} day{'s' if n != 1 else ''}"
    if delta_days == 0:
        return "due today"
    if delta_days == 1:
        return "due tomorrow"
    return f"due in {delta_days} days"
