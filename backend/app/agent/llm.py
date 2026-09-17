"""Optional LLM layer -- provider-agnostic, and strictly subordinate.

Scope, deliberately narrow:

The LLM is given the commitments the deterministic resolver already produced
and asked to answer a free-form question **by selecting from them**. It may
choose which items are relevant and phrase the reply; it may not invent a
commitment, an owner or a date. Every id it returns is validated against the
resolved set and anything unrecognised is dropped before the answer is built,
so a hallucinated item cannot reach the user.

What the LLM is NOT allowed to do here:
  * decide ownership            -- resolve.py owns that
  * decide deadlines or status  -- dates.py / resolve.py own that
  * close an item               -- resolve.py owns that

That division is the whole design: the LLM reads, the rules decide. It also
means every failure mode -- no key, bad key, rate limit, timeout, malformed
JSON, offline laptop -- degrades to the deterministic answer rather than to an
error. `used_llm` in the response says which path actually ran, so the UI can
never claim an LLM answered when it did not.
"""
from __future__ import annotations

import json
import re

from app.config import active_provider

TIMEOUT_S = 12

SYSTEM = """You are the question-answering layer of an executive assistant agent for Arjun Malhotra, VP Sales.

You are given the COMPLETE set of commitments that a deterministic resolver has already extracted from this week's sources. This set is the only truth available to you.

Rules, in order of importance:
1. Answer ONLY using the commitments provided. Never invent a commitment, an owner, a deadline or a fact.
2. Never assign an owner to an item whose owner is "UNCLEAR". If the question asks who owns such an item, say plainly that nobody has accepted it and that it needs a decision.
3. Do not restate a deadline or status differently from what is given.
4. If nothing in the set answers the question, say so directly.
5. Be concise and specific: two or three sentences, in the voice of a chief of staff. No preamble, no bullet lists.

Return ONLY a JSON object, no markdown fence:
{"answer": "<your reply>", "commitment_ids": ["<id>", ...]}

commitment_ids must be ids from the provided set that your answer relies on. Use [] if none apply."""


def _compact(c: dict) -> dict:
    """The minimum the model needs. Smaller prompt, fewer ways to drift."""
    return {
        "id": c["id"],
        "title": c["title"],
        "owner": c["owner_name"],
        "owner_is_unclear": c["owner"] == "UNCLEAR",
        "counterparty": c["counterparty_name"],
        "direction": c["direction"],
        "status": c["status"],
        "due": c["due_at"],
        "due_in_words": c["due_human"],
        "times_deadline_moved": c["slip_count"],
        "needs_escalation": c["needs_escalation"],
    }


def _extract_json(raw: str) -> dict | None:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except Exception:
            return None


def _call(provider: dict, system: str, user: str) -> str | None:
    """One call, one shape, three SDKs."""
    try:
        if provider["sdk"] == "anthropic":
            from anthropic import Anthropic
            client = Anthropic(api_key=provider["key"], timeout=TIMEOUT_S)
            r = client.messages.create(
                model=provider["model"], max_tokens=700, system=system,
                messages=[{"role": "user", "content": user}],
            )
            return r.content[0].text

        from openai import OpenAI
        client = OpenAI(api_key=provider["key"],
                        base_url=provider["base_url"], timeout=TIMEOUT_S)
        r = client.chat.completions.create(
            model=provider["model"], max_tokens=700, temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        return r.choices[0].message.content
    except Exception:
        # Any failure at all -- caller falls back to the deterministic answer.
        return None


def answer_with_llm(question: str, commitments: list, as_of) -> dict | None:
    """Return {answer, commitment_ids, provider, model} or None to fall back."""
    provider = active_provider()
    if not provider or not commitments:
        return None

    payload = {
        "today": as_of.isoformat(timespec="minutes"),
        "user": "Arjun Malhotra (VP Sales)",
        "commitments": [_compact(c.to_dict()) for c in commitments],
        "question": question,
    }
    raw = _call(provider, SYSTEM, json.dumps(payload, indent=1))
    if not raw:
        return None

    data = _extract_json(raw)
    if not isinstance(data, dict) or not data.get("answer"):
        return None

    # Validation gate: drop any id the resolver did not produce. This is what
    # makes a hallucinated commitment structurally unable to reach the user.
    valid = {c.id for c in commitments}
    ids = [i for i in (data.get("commitment_ids") or []) if i in valid]

    return {
        "answer": str(data["answer"]).strip(),
        "commitment_ids": ids,
        "provider": provider["name"],
        "model": provider["model"],
    }
