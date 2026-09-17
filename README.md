# Executive Productivity Agent

**AIONOS — Agentic AI Factory · Assignment 1**

Turns a week of messy executive inputs — a meeting transcript, four calendars,
five email threads and two voice notes — into a **daily action brief** with full
provenance, and answers questions about it.

Built for **Arjun Malhotra (VP Sales)**, week of **21–25 September 2026**.

---

## Run it

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000** — UI
Open **http://127.0.0.1:8000/docs** — interactive API (Swagger)

No API key is required. The agent runs its deterministic pipeline out of the
box. To enable the LLM path, copy `.env.example` to `.env` and add a key
(Groq is free at [console.groq.com/keys](https://console.groq.com/keys)):

```bash
GROQ_API_KEY=gsk_...
GROQ_MODEL=openai/gpt-oss-120b
```

Then verify the live path before relying on it:

```bash
python backend/check_llm.py
```

It checks the key loads, the model still exists on the provider (Groq retires
models regularly — it lists the current ones if yours is gone), that live
answers cite only real source ids, that the unowned item is *still* refused an
owner when an LLM phrases the reply, and that a dead key degrades to the
deterministic answer. Non-zero exit means don't demo with it.

```bash
pytest -q          # 27 tests, all mapped to assignment requirements
```

---

## What it does

| Requirement from the brief | Where it happens |
|---|---|
| Identify commitments made by the executive | `agent/extract.py` — speech-act detection |
| Separate "my actions" from "waiting on others" | `agent/resolve.py` — `direction` |
| Detect deadlines and overdue items | `agent/dates.py` + `resolve.py` — `status` |
| Deduplicate the same action across sources | `agent/resolve.py` — topic clustering |
| Flag unclear ownership rather than inventing it | `agent/resolve.py` — `UNCLEAR` + escalation |
| Produce a daily brief | `agent/brief.py` |
| Answer questions | `agent/qa.py` (+ optional `agent/llm.py`) |

---

## Architecture

```
                    ┌─────────────────────────────────────────────┐
 DATA PACK          │  data/*.json  (transcript, calendars,       │
 (fixed, supplied)  │   emails, voice notes)                      │
                    └──────────────────────┬──────────────────────┘
                                           │
                    ┌──────────────────────▼──────────────────────┐
   1. INGEST        │  ingest.py                                  │
                    │  4 formats → one SourceUnit stream           │
                    │  {id, kind, ts, speaker, audience, text}     │
                    │  sources_upto(as_of) ── time travel          │
                    └──────────────────────┬──────────────────────┘
                                           │  71 units
                    ┌──────────────────────▼──────────────────────┐
   2. EXTRACT       │  extract.py   (deterministic, always)        │
                    │  • topic lexicon, weighted                   │
                    │  • topic carries forward across turns        │
                    │  • speech acts: COMMIT / REQUEST / DELIVER   │
                    │    CONFIRM / CHASE / DISCLAIM / RESCHEDULE   │
                    │  • dates.py resolves "EOD tomorrow" against  │
                    │    the timestamp of the source that said it  │
                    └──────────────────────┬──────────────────────┘
                                           │  37 mentions
                    ┌──────────────────────▼──────────────────────┐
   3. RESOLVE       │  resolve.py     ← the judgement layer        │
                    │  • cluster mentions by topic     (DEDUP)     │
                    │  • latest authoritative statement wins       │
                    │                                  (SUPERSEDE) │
                    │  • owner only from an accepted COMMIT        │
                    │    all disclaim + none commit → UNCLEAR      │
                    │  • DELIVER/CONFIRM after last COMMIT → done  │
                    │  • status vs as_of → overdue / due / upcoming│
                    └──────────────────────┬──────────────────────┘
                                           │  5 commitments
                    ┌──────────────────────▼──────────────────────┐
   4. SERVE         │  brief.py   ranked daily brief               │
                    │  qa.py      grounded Q&A + citations         │
                    │  llm.py     OPTIONAL: phrases the answer by  │
                    │             selecting from resolved items;   │
                    │             ids validated, always fallible   │
                    │  db.py      SQLite: sources, runs, audit_log │
                    └──────────────────────┬──────────────────────┘
                                           │
                    ┌──────────────────────▼──────────────────────┐
   5. INTERFACE     │  FastAPI REST  ──  React SPA                 │
                    │  /api/brief /api/ask /api/commitments        │
                    │  /api/sources /api/audit /api/health         │
                    └─────────────────────────────────────────────┘
```

**The design rule: the LLM reads, the rules decide.**
Dedup, supersession, overdue arithmetic and ownership are decided by
deterministic code, so the brief is reproducible, auditable and identical on
every run. An executive tool that reorders your day each time you refresh is
not trustworthy.

Concretely, in the build as it stands: **extraction is deterministic in every
mode**, and the LLM — when a key is configured — only phrases the answer to a
free-form question by selecting among commitments the resolver already
produced. It cannot create, re-own or re-date one. That boundary is enforced
by a validation gate, not by prompt wording, and is covered by four tests.

---

## Process flow — how one commitment is built

Following the vendor list, which appears in **seven** sources:

| # | Source | When | What it says | Effect |
|---|---|---|---|---|
| 1 | `TR-03` transcript | Mon 09:00 | "I told Raghav I'd send him the updated vendor list… by end of day tomorrow" | **COMMIT**, owner Arjun, due **Tue 23:59** |
| 2 | `EM-T1-01` email | Mon 09:50 | "can you send the updated vendor list today?" | CHASE from Raghav |
| 3 | `EM-T1-02` email | Mon 17:40 | "Running behind, will send first thing tomorrow morning" | **slip 1** → Tue 12:00 |
| 4 | `VN-01` voice note | Mon 18:40 | "need to get Raghav that vendor list… might slip to tomorrow" | same item, no new date |
| 5 | `EM-T1-03` email | Tue 09:15 | "whenever you get a chance today works" | Raghav relaxes |
| 6 | `EM-T1-04` email | Tue 18:30 | "will send by tomorrow (Wednesday) morning for sure" | **slip 2** → Wed 12:00 |
| 7 | `EM-T1-05` email | Wed 08:45 | "Just checking — still good for this morning?" | CHASE |

**Result: one commitment**, owner Arjun, due Wed 12:00, `slip_count = 3`,
7 citations. On Thursday it flips to **OVERDUE** — never delivered.

---

## The five things the data pack is testing

1. **Dedup** — vendor list is in the transcript, 5 emails and a voice note.
   → 1 commitment, 7 citations. Not 7 to-dos.
2. **Supersession** — the deck review moves Wed → Thu 09:30; the variance
   report is pulled Thu → Wed evening. The last authoritative word wins, and
   the trail is kept visible rather than overwritten.
3. **Overdue** — the vendor list slips three times and is late by Thursday.
4. **Unclear ownership** — the Mumbai lease is disclaimed by everyone:
   Raghav ("not sure whose desk"), Divya ("not on my end… sits with
   Facilities"), Arjun ("I don't think it's me"). Facilities is *suggested*
   but never accepts. **The agent refuses to assign it** and escalates,
   capping confidence at 0.45. `test_mumbai_lease_is_never_assigned_to_anyone`
   asserts this at three points in the week.
5. **Closure** — the report was delivered Wed 18:00 and the Meridian call
   confirmed. Finished work stops appearing as open.

A sixth, subtler one: **"has anyone *confirmed* who's signing off?"** contains
the word *confirmed* but is a question, not a closure. Treating it as one
marked the unowned item DONE — caught and fixed in `resolve.py`.

---

## Inputs, sources and assumptions

**Inputs** — only the supplied data pack. Nothing is invented.

| Source | Count | Role |
|---|---|---|
| Meeting transcript (Leadership Sync, Mon) | 10 utterances | Origin of most commitments |
| Calendars (Arjun, Neha, Raghav, Divya) | 34 entries | Corroboration; never creates commitments |
| Email threads | 5 × 5 = 25 | Where deadlines slip and get superseded |
| Voice notes (Arjun, to himself) | 2 | First-party restatements of his own items |
| **Total** | **71 source units** | |

**Assumptions**

1. **"Today" is a parameter, not the wall clock.** The pack describes a fixed
   past week, so the brief takes an `as_of` timestamp and only reads sources
   at or before it. This makes the week replayable and every output
   reproducible.
2. **Calendars corroborate, they do not commit.** A meeting in a calendar is
   not a promise. Calendars confirm that agreed times were really booked.
3. **Voice notes are first-party.** They are Arjun talking to himself, so they
   are treated like his own meeting statements — a source of *his* commitments,
   never as instructions from a third party.
4. **Distribution lists cannot own work.** `facilities@` and "All Staff" are
   addresses, not accountable people, so they can never be resolved as owner.
5. **An unqualified deadline means end of day** (23:59). "Morning" = 12:00,
   "afternoon" = 17:00, "evening" = 20:00. The agent never invents a precise
   hour that nobody stated; `due_phrase` always shows the original words.
6. **Ownership requires acceptance.** Being asked is not owning. An owner is
   only set by an explicit COMMIT. If everyone disclaims and nobody commits,
   the owner is `UNCLEAR` and the item escalates.
7. **The three garbled calendar tables in the source PDF were reconstructed**
   by aligning the day, time and event columns, then cross-checked against
   Arjun's calendar — every shared meeting (Leadership Sync, Budget Review,
   Board Prep, Facilities Check-in, and Neha's Thu 09:30 deck review) matches
   on both sides.

**Out of scope** — no real mail/calendar integration, no auth, no
multi-user support. The data pack is the system of record.

---

## AI tools used, and how

| Tool | How it was used |
|---|---|
| **Claude Opus 5 (Claude Code)** | Primary development environment. Used to read and parse the assignment PDFs, design the ingest → extract → resolve architecture, write the agent pipeline, API, React UI and test suite, and debug. Two real bugs it caught and fixed mid-build are documented below. |
| **Groq API** (`llama-3.3-70b-versatile`) | Optional LLM path for **free-form question answering only** (`agent/llm.py`), behind a provider-agnostic interface (Groq / OpenAI / Anthropic). Off by default. The model selects among already-resolved commitments and cannot invent one — ids it returns are validated against the resolved set and unknown ids are dropped. Any failure (no key, bad key, rate limit, timeout, bad JSON) falls back to the deterministic answer. |
| **FastAPI auto-generated OpenAPI** | Swagger docs at `/docs`, used to exercise endpoints during development. |

**How AI was actually used — honestly:** the architecture decisions (deterministic
resolution layer, `as_of` time travel, ownership-requires-acceptance) were the
design work; AI accelerated implementation and caught bugs. Two examples of the
latter, both found by testing rather than by reading:

- `"shifting the review to Thursday morning instead of Wednesday"` resolved to
  **Wednesday**, because weekdays were matched in dictionary order. The
  reschedule — the whole point of that email — was being silently dropped.
  Fixed by stripping superseded days and preferring the correction after a
  contrast marker, scoped to the same sentence.
- The Mumbai lease briefly showed **DONE**, because `"has anyone confirmed
  who's signing off?"` matched the confirmation cue. A question was closing an
  open item. Fixed by excluding CHASE/DISCLAIM mentions from closure, and by
  making an unowned item impossible to complete.

---

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/brief?as_of=` | The daily action brief |
| `GET` | `/api/commitments?direction=&status=` | Filtered commitments |
| `POST` | `/api/ask` | Grounded Q&A `{question, as_of}` |
| `GET` | `/api/sources?kind=&ids=` | Provenance lookup |
| `GET` | `/api/audit` | Every brief and question, with citations |
| `GET` | `/api/people` | Directory |
| `GET` | `/api/health` | Status, active provider, and exactly what the LLM is used for |

Example:

```bash
curl "http://127.0.0.1:8000/api/brief?as_of=2026-09-24T17:00"

curl -X POST http://127.0.0.1:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What did I promise Raghav?","as_of":"2026-09-23T09:00"}'
```

---

## Project layout

```
backend/
  app/
    main.py            FastAPI app + routes
    config.py          provider-agnostic LLM config
    db.py              SQLite: sources, runs, audit_log
    agent/
      ingest.py        4 formats → one SourceUnit stream
      dates.py         relative-date resolution
      extract.py       speech-act extraction (deterministic)
      llm.py           optional LLM answering, validated + always fallible
      resolve.py       dedup, supersession, ownership, status
      brief.py         ranked daily brief
      qa.py            grounded question answering
  data/                the supplied data pack, as JSON
  static/              React SPA (assets vendored — runs offline)
  tests/test_agent.py  23 tests, one per requirement
```

---

## Known limitations

- The topic lexicon is tuned to this data pack. A new domain needs new anchors,
  or the LLM extraction path enabled — the resolution layer is unchanged either
  way.
- **The LLM is used for answering only, not for extraction.** `llm.py` is
  given the commitments the resolver already produced and selects among them;
  it cannot create one. Extraction, dedup, supersession, ownership and status
  are deterministic in every mode — `/api/health` reports exactly this under
  `llm_used_for` and `always_deterministic`, and each answer carries
  `used_llm` and `path` so the UI can never claim a model answered when it
  did not. Re-extraction via LLM with structured-output validation against the
  deterministic result is the next step, not a current claim.
- The React SPA is served from a single file with vendored libraries rather
  than a Vite/Next.js build. This was a deliberate trade for a hard deadline:
  it removes any build step that could fail, and the app runs with no network.
