"""Verify the live LLM path end to end.

Run after putting a key in .env:   python check_llm.py

Checks, in order:
  1. the key is actually loaded
  2. the configured model exists on the provider (and names alternatives if not)
  3. a real answer comes back, grounded and citing real sources
  4. a dead key still degrades to the deterministic answer

Exit code is non-zero if the live path is not usable, so this is a go/no-go
before recording the demo.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import active_provider  # noqa: E402

WED = datetime.fromisoformat("2026-09-23T09:00")
OK, BAD = "  [OK]  ", "  [FAIL]"


def line(msg):
    print(msg, flush=True)


def main() -> int:
    line("\n=== 1. key loaded? ===")
    p = active_provider()
    if not p:
        line(BAD + " No key found. Put GROQ_API_KEY in backend/.env")
        return 1
    if "PASTE_YOUR_KEY" in p["key"]:
        line(BAD + " .env still has the placeholder - paste your real key")
        return 1
    line(OK + f"provider={p['name']}  model={p['model']}  key=...{p['key'][-4:]}")

    line("\n=== 2. model reachable? ===")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=p["key"], base_url=p["base_url"], timeout=20)
        available = sorted(m.id for m in client.models.list().data)
        if p["model"] in available:
            line(OK + f"{p['model']} is available")
        else:
            line(BAD + f"{p['model']} NOT available.")
            line("         Pick one of these and set GROQ_MODEL in .env:")
            for m in available[:15]:
                line(f"           {m}")
            return 1
    except Exception as e:
        line(BAD + f" could not reach provider: {type(e).__name__}: {e}")
        return 1

    line("\n=== 3. live answer, grounded? ===")
    from app.agent.extract import extract_mentions
    from app.agent.ingest import sources_upto
    from app.agent.qa import answer_best
    from app.agent.resolve import resolve_commitments

    commitments = resolve_commitments(extract_mentions(sources_upto(WED)), WED)
    real_sources = {e.source_id for c in commitments for e in c.evidence}

    questions = [
        "What did I promise Raghav?",
        "I'm about to walk into board prep - what do I actually need to worry about?",
        "Who is responsible for the Mumbai lease?",
    ]
    failures = 0
    for q in questions:
        r = answer_best(q, commitments, WED)
        tag = "llm" if r["used_llm"] else "RULES (fell back)"
        line(f"\n  Q: {q}")
        line(f"     path : {r['path']}  [{tag}]")
        line(f"     answer: {r['answer'][:190]}")
        if not r["used_llm"]:
            line(BAD + " fell back - the live path did not run")
            failures += 1
            continue
        stray = set(r["citations"]) - real_sources
        if stray:
            line(BAD + f" invented citations: {stray}")
            failures += 1
        else:
            line(OK + f"{len(r['citations'])} citations, all real")
        # The refusal must survive the LLM rewriting it.
        if "mumbai" in q.lower() or "responsible" in q.lower():
            a = r["answer"].lower()
            if "arjun" in a and "unclear" not in a and "no one" not in a \
                    and "nobody" not in a and "not accepted" not in a:
                line(BAD + " may have assigned an owner to the unowned item - READ IT")
                failures += 1
            else:
                line(OK + "still refuses to name an owner")

    line("\n=== 4. dead key still degrades safely? ===")
    real = os.environ.get("GROQ_API_KEY")
    try:
        os.environ["GROQ_API_KEY"] = "gsk_deliberately_invalid_key"
        import importlib

        import app.config as cfg
        importlib.reload(cfg)
        import app.agent.llm as llm
        importlib.reload(llm)
        import app.agent.qa as qa
        importlib.reload(qa)
        r = qa.answer_best("What did I promise Raghav?", commitments, WED)
        if r["used_llm"]:
            line(BAD + " claimed to use the LLM with a bad key")
            failures += 1
        elif "vendor list" in r["answer"].lower():
            line(OK + "bad key -> deterministic answer, demo survives")
        else:
            line(BAD + " fallback answer looks wrong")
            failures += 1
    finally:
        if real:
            os.environ["GROQ_API_KEY"] = real

    line("\n" + "=" * 58)
    if failures:
        line(f"  {failures} problem(s). Safest move: remove the key from .env")
        line("  and demo in deterministic mode - it is fully working.")
        return 1
    line("  LIVE LLM PATH IS GOOD. Safe to demo with the key in place.")
    line("=" * 58 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
