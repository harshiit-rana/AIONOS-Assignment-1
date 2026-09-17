# Demo script & interview prep

## Before you record

```bash
cd backend
uvicorn app.main:app --port 8000
```

Open **http://127.0.0.1:8000**. Have a second tab on **/docs**.
Keep the window narrow-ish (≈1280px) so text stays readable when compressed.

**Target: 3–4 minutes.** Under 10 MB — record at 1280×720, and if it is too
large, re-encode:
`ffmpeg -i in.mp4 -vcodec libx264 -crf 30 -preset slow -an out.mp4`

---

## The 7 beats

**1 · What this is (15s)**
> "An Executive Productivity Agent for Arjun Malhotra, VP Sales. It reads a
> week of his inputs — a meeting transcript, four calendars, five email threads
> and two voice notes — and produces a daily action brief. 71 source units in,
> 5 real commitments out."

**2 · The brief (30s)** — land on Wednesday.
> "Ranked by what matters: overdue first, then due today, then what he's
> waiting on others for, then the item nobody owns. Two of his own commitments
> are due today; one item still has no owner."

Point at the counters.

**3 · Dedup — click the vendor list card (45s)** ← *the strongest moment*
> "This one item was assembled from seven different sources — the transcript,
> five emails and a voice note. A naive agent gives you seven to-dos. Here it's
> one commitment with seven citations."

Scroll the drawer to the timeline.
> "And the deadline moved three times. Monday he said end of day Tuesday; by
> Monday evening it was Tuesday morning; by Tuesday evening it was Wednesday
> morning. The agent keeps the whole trail instead of overwriting it."

**4 · Time travel (30s)** — click **Thu 24**.
> "The agent only sees what had happened by the selected moment. Jump to
> Thursday and the vendor list is now overdue — he never sent it. Meanwhile
> three other items have closed themselves, because they were actually
> delivered."

**5 · The refusal (45s)** — click the Mumbai lease.
> "This is the one I'd point at. The lease needs a signature by Friday. Raghav
> doesn't know whose desk it's on. Divya says it's Facilities, not her. Arjun
> says he doesn't think it's his. Facilities never accepts it."
>
> "So the owner is UNCLEAR, confidence is capped at 0.45, and it's escalated.
> It would have been easy to assign this to Arjun and look more helpful. That's
> exactly the failure — an agent that invents an owner teaches you to distrust
> every other line in the brief."

**6 · Ask (40s)** — the two questions the brief names.
> "What did I promise Raghav?" → vendor list, deadline moved 3×, with citations.
> "What needs action today?" → his two items, *plus* the unowned one flagged
> as needing a decision.

Then ask something outside the pack — *"What's our Q4 revenue forecast?"*
> "It refuses. It only answers from this week's sources."

**7 · Under the hood (25s)** — Sources tab, then `/docs`.
> "Every source is queryable, and it's a real REST API — brief, ask,
> commitments, sources, and an audit log that records every question with the
> sources that grounded it. FastAPI, SQLite, React. 23 tests."

Close on: *"The design rule is — the LLM reads, the rules decide."*

---

## Defending it

**"Why not just use an LLM for everything?"**
Extraction is language-shaped — an LLM is good at it. But dedup, supersession,
overdue arithmetic and ownership are decisions, and they must be identical on
every run. An executive tool that reorders your day each time you refresh is
not trustworthy. So the LLM reads and the rules decide. It also means the demo
runs with no API key.

**"So is there actually any AI in it?"**
Yes — the extraction layer is provider-agnostic (Groq, OpenAI, Anthropic) and
turns on with one env var. I built the deterministic path first deliberately:
it's the reference implementation the LLM path is validated against, and it
makes the system testable. Be straight about this: with the key off, the
intelligence is in the speech-act model and the resolution rules, not in a
model call.

**"How does dedup actually work?"**
A weighted topic lexicon, plus two things that matter on real dialogue: topic
carries forward across turns — *"I'll have it ready Wednesday evening"* names
no subject, it only means something because of the previous line — and emails
inherit their thread subject. Then mentions cluster by topic and the resolver
reconciles them.

**"What if two different tasks share a topic word?"**
That's the current weakness. Multi-word anchors outscore single words, so
"call" never outvotes "expense variance report", but a second vendor-list task
in the same week would merge. The fix is the LLM extraction path with an
explicit `is_same_obligation` check.

**"How do you know the deadline is right?"**
Every relative date resolves against the timestamp of the source that said it —
"tomorrow" on Monday and "tomorrow" on Tuesday are different days. Then the
latest *authoritative* statement wins: one from the owner or the delegator, not
a bystander's. `due_phrase` always shows the original wording so you can check.

**"What was the hardest bug?"**
Two, both found by tests rather than reading. `"shifting the review to Thursday
morning instead of Wednesday"` resolved to Wednesday, because weekdays matched
in dictionary order — the reschedule was silently dropped. And `"has anyone
confirmed who's signing off?"` marked the unowned lease DONE, because a
question matched the confirmation cue.

**"What would you do with another week?"**
Real Gmail/Calendar connectors behind the same `SourceUnit` interface, draft
(never send) actions like the chase email to Raghav, and vector retrieval —
a week fits in memory, a quarter doesn't.

**"Why no Next.js frontend?"**
Deliberate trade against the deadline. It's React, but single-file with
vendored libraries, so there's no build step to fail and it runs with no
network. With more time I'd move it to Vite with the same components.

---

## Don't get caught out

- **Know `resolve.py`.** That's where the judgement is, and it's what they'll
  ask about. Be able to explain ownership resolution and closure from memory.
- **Never claim the LLM path is doing work when the key is off.** The health
  badge in the UI says which mode is live — let it speak for you.
- **If asked something you didn't build, say so and say what you'd do.** The
  limitations slide exists so you're the one who raised them first.
