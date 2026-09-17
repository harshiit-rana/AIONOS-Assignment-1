"""Generate the 10-slide submission deck.

Run:  python docs/make_ppt.py "24BCS1234" "Harshit Rana"
"""
from __future__ import annotations

import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROLL = sys.argv[1] if len(sys.argv) > 1 else "ROLLNO"
NAME = sys.argv[2] if len(sys.argv) > 2 else "Your Name"
OUT = Path(__file__).resolve().parent.parent / f"{ROLL}_{NAME.replace(' ', '_')}.pptx"

BG      = RGBColor(0x0A, 0x0E, 0x14)
CARD    = RGBColor(0x12, 0x18, 0x22)
CARD2   = RGBColor(0x17, 0x1F, 0x2B)
FG      = RGBColor(0xE8, 0xEE, 0xF6)
MUTED   = RGBColor(0x8A, 0x9A, 0xB0)
DIM     = RGBColor(0x64, 0x74, 0x8B)
ACCENT  = RGBColor(0x7C, 0x8CFF & 0xFF, 0xFA) if False else RGBColor(0x8B, 0x9CFF & 0xFF, 0xFF)
INDIGO  = RGBColor(0x81, 0x8C, 0xF8)
CYAN    = RGBColor(0x4D, 0xD0, 0xE1)
ROSE    = RGBColor(0xFB, 0x7185 & 0xFF, 0x8F)
AMBER   = RGBColor(0xFB, 0xBF, 0x24)
EMERALD = RGBColor(0x34, 0xD3, 0x99)
FUCHSIA = RGBColor(0xE8, 0x79, 0xF9)

FONT = "Segoe UI"
MONO = "Consolas"

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
W, H = prs.slide_width, prs.slide_height


def slide(n_label: str | None = None):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg = s.shapes.add_shape(1, 0, 0, W, H)
    bg.fill.solid(); bg.fill.fore_color.rgb = BG; bg.line.fill.background()
    bg.shadow.inherit = False
    if n_label:
        tb = s.shapes.add_textbox(Inches(11.9), Inches(6.85), Inches(1.2), Inches(0.4))
        p = tb.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.RIGHT
        r = p.add_run(); r.text = n_label
        r.font.size = Pt(10); r.font.color.rgb = DIM; r.font.name = FONT
    return s


def box(s, x, y, w, h, fill=CARD, line=None):
    sh = s.shapes.add_shape(5, x, y, w, h)  # rounded rect
    sh.fill.solid(); sh.fill.fore_color.rgb = fill
    if line:
        sh.line.color.rgb = line; sh.line.width = Pt(1)
    else:
        sh.line.fill.background()
    sh.shadow.inherit = False
    try:
        sh.adjustments[0] = 0.06
    except Exception:
        pass
    return sh


def text(s, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.15):
    """runs: list of (text, size, color, bold, font) or ('', ...) for spacer."""
    tb = s.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    first = True
    for item in runs:
        txt, size, color, bold = item[0], item[1], item[2], item[3]
        fname = item[4] if len(item) > 4 else FONT
        space_before = item[5] if len(item) > 5 else 0
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = align
        p.line_spacing = spacing
        if space_before:
            p.space_before = Pt(space_before)
        r = p.add_run(); r.text = txt
        r.font.size = Pt(size); r.font.color.rgb = color
        r.font.bold = bold; r.font.name = fname
    return tb


def title(s, kicker, head, sub=None):
    text(s, Inches(0.75), Inches(0.5), Inches(11.8), Inches(0.3),
         [(kicker.upper(), 11, INDIGO, True)])
    text(s, Inches(0.75), Inches(0.85), Inches(11.8), Inches(0.6),
         [(head, 30, FG, True)])
    if sub:
        text(s, Inches(0.75), Inches(1.52), Inches(11.8), Inches(0.4),
             [(sub, 13.5, MUTED, False)])


def bullets(s, x, y, w, items, size=13, gap=9, color=FG):
    runs = []
    for i, (b, d) in enumerate(items):
        runs.append((b, size, color, True, FONT, 0 if i == 0 else gap))
        if d:
            runs.append((d, size - 1.5, MUTED, False, FONT, 2))
    return text(s, x, y, w, Inches(0.4), runs, spacing=1.2)


def chip(s, x, y, w, h, label, color, fill):
    b = box(s, x, y, w, h, fill=fill)
    text(s, x, y + Emu(int(h * 0.22)), w, h, [(label, 10.5, color, True)], align=PP_ALIGN.CENTER)
    return b


# ===========================================================  1. TITLE
s = slide()
box(s, Inches(0), Inches(0), Inches(0.09), H, fill=INDIGO)
text(s, Inches(0.95), Inches(1.75), Inches(11), Inches(0.4),
     [("AIONOS  ·  AGENTIC AI FACTORY  ·  ASSIGNMENT 1", 12.5, INDIGO, True)])
text(s, Inches(0.95), Inches(2.25), Inches(11.5), Inches(1.2),
     [("Executive Productivity Agent", 44, FG, True)])
text(s, Inches(0.95), Inches(3.35), Inches(10.6), Inches(1.0),
     [("Turns a week of messy executive inputs into a daily action brief "
       "— with full provenance, and an explicit refusal to guess.", 16, MUTED, False)],
     spacing=1.3)

for i, (n, lab, col) in enumerate([
        ("71", "source units", CYAN), ("5", "real commitments", INDIGO),
        ("7→1", "dedup ratio", EMERALD), ("23", "tests passing", AMBER)]):
    x = Inches(0.95 + i * 2.35)
    box(s, x, Inches(4.5), Inches(2.05), Inches(1.0), fill=CARD)
    text(s, x, Inches(4.63), Inches(2.05), Inches(0.4), [(n, 21, col, True)], align=PP_ALIGN.CENTER)
    text(s, x, Inches(5.05), Inches(2.05), Inches(0.3), [(lab, 10.5, DIM, False)], align=PP_ALIGN.CENTER)

text(s, Inches(0.95), Inches(6.35), Inches(11), Inches(0.6),
     [(f"{NAME}   ·   {ROLL}", 13.5, FG, True),
      ("FastAPI · SQLite · React · provider-agnostic LLM (Groq / OpenAI / Anthropic)", 11, DIM, False, FONT, 4)])

# ===========================================================  2. PROBLEM
s = slide("2 / 10")
title(s, "The problem", "An executive's commitments are scattered and contradictory",
      "Nothing in the pack states a task cleanly. Every real item must be reconstructed across sources.")

items = [
    ("Said once, restated three times",
     "The vendor list appears in the transcript, five emails and a voice note. Naive extraction produces six to-dos."),
    ("Deadlines move, and the sources disagree",
     "\"Wednesday\" becomes \"Thursday morning\" becomes \"9:30 AM Thursday.\" The earliest mention is the one most systems keep."),
    ("\"Tomorrow\" means different days",
     "Said Monday it means Tuesday; said Tuesday it means Wednesday. Relative dates are only meaningful against their own source."),
    ("Some work belongs to nobody",
     "The Mumbai lease is disclaimed by everyone. The tempting failure is to assign it to the user."),
    ("Finished work keeps nagging",
     "The variance report was delivered Wednesday 18:00. It must stop appearing as open."),
]
bullets(s, Inches(0.75), Inches(2.25), Inches(7.4), items, size=13.5, gap=13)

box(s, Inches(8.55), Inches(2.25), Inches(4.0), Inches(4.2), fill=CARD)
text(s, Inches(8.85), Inches(2.5), Inches(3.4), Inches(0.3),
     [("WHAT THE BRIEF ASKS FOR", 10, INDIGO, True)])
reqs = ["Identify commitments", "Separate mine vs waiting on",
        "Detect deadlines & overdue", "Deduplicate across sources",
        "Flag unclear ownership", "Produce a daily brief", "Answer questions"]
text(s, Inches(8.85), Inches(2.95), Inches(3.4), Inches(3.2),
     [(f"✓  {r}", 12, FG, False, FONT, 10 if i else 0) for i, r in enumerate(reqs)],
     spacing=1.25)

# ===========================================================  3. DATA PACK
s = slide("3 / 10")
title(s, "Inputs & sources", "The data pack — 71 source units, nothing invented",
      "Week of 21–25 September 2026 · Arjun Malhotra, VP Sales · only this material is used.")

cols = [("Meeting transcript", "10", "utterances", "Leadership Sync, Mon 09:00.\nOrigin of most commitments.", CYAN),
        ("Calendars", "34", "entries", "Arjun, Neha, Raghav, Divya.\nCorroborate — never commit.", INDIGO),
        ("Email threads", "25", "messages", "5 threads × 5.\nWhere deadlines slip.", AMBER),
        ("Voice notes", "2", "memos", "Arjun to himself.\nFirst-party restatements.", FUCHSIA)]
for i, (h, n, unit, d, col) in enumerate(cols):
    x = Inches(0.75 + i * 3.05)
    box(s, x, Inches(2.3), Inches(2.8), Inches(2.0), fill=CARD)
    text(s, x + Inches(0.25), Inches(2.5), Inches(2.3), Inches(0.3), [(h, 12, FG, True)])
    text(s, x + Inches(0.25), Inches(2.85), Inches(2.3), Inches(0.4),
         [(n, 26, col, True), (unit, 10, DIM, False)])
    text(s, x + Inches(0.25), Inches(3.62), Inches(2.4), Inches(0.6), [(d, 10, MUTED, False)], spacing=1.25)

text(s, Inches(0.75), Inches(4.65), Inches(11.8), Inches(0.3),
     [("KEY ASSUMPTIONS", 10.5, INDIGO, True)])
asm = [
    ("\"Today\" is a parameter, not the wall clock",
     "The pack is a fixed past week, so the brief takes an as_of timestamp and reads only sources at or before it — the week is replayable and every output reproducible."),
    ("Ownership requires acceptance, and lists cannot own work",
     "Being asked is not owning; an owner is set only by an explicit commitment. facilities@ and \"All Staff\" are addresses, not accountable people."),
    ("An unqualified deadline means end of day; the original words are always kept",
     "\"Morning\"=12:00, \"evening\"=20:00. The agent never invents an hour nobody stated — due_phrase shows the source wording."),
]
bullets(s, Inches(0.75), Inches(5.05), Inches(11.8), asm, size=12, gap=10)

# ===========================================================  4. ARCHITECTURE
s = slide("4 / 10")
title(s, "Architecture", "Five stages — the LLM reads, the rules decide")

stages = [
    ("1  INGEST", "ingest.py", "4 formats → one SourceUnit stream\nsources_upto(as_of) gates visibility", "71 units", CYAN),
    ("2  EXTRACT", "extract.py  ⇄  llm.py", "Topic lexicon + speech acts\nCOMMIT / REQUEST / DELIVER /\nCONFIRM / CHASE / DISCLAIM", "37 mentions", AMBER),
    ("3  RESOLVE", "resolve.py", "Dedup · supersession · ownership\nstatus vs as_of  — deterministic", "5 commitments", INDIGO),
    ("4  SERVE", "brief.py · qa.py · db.py", "Ranked brief, grounded Q&A\nSQLite: sources, runs, audit_log", "JSON + citations", EMERALD),
]
y = Inches(2.15)
for i, (num, mod, body, out, col) in enumerate(stages):
    yy = y + Inches(i * 1.13)
    box(s, Inches(0.75), yy, Inches(9.1), Inches(0.98), fill=CARD)
    box(s, Inches(0.75), yy, Inches(0.055), Inches(0.98), fill=col)
    text(s, Inches(1.05), yy + Inches(0.14), Inches(1.6), Inches(0.3), [(num, 12, col, True)])
    text(s, Inches(2.5), yy + Inches(0.13), Inches(2.5), Inches(0.3), [(mod, 11, FG, True, MONO)])
    text(s, Inches(5.1), yy + Inches(0.1), Inches(4.5), Inches(0.8), [(body, 9.8, MUTED, False)], spacing=1.15)
    chip(s, Inches(10.05), yy + Inches(0.3), Inches(1.5), Inches(0.38), out, col, CARD2)

box(s, Inches(0.75), Inches(6.75), Inches(11.8), Inches(0.55), fill=CARD2)
text(s, Inches(1.05), Inches(6.88), Inches(11.2), Inches(0.4),
     [("Design rule:  ", 12, INDIGO, True),
      ], align=PP_ALIGN.LEFT)
text(s, Inches(2.05), Inches(6.88), Inches(10.2), Inches(0.4),
     [("extraction is language-shaped and may use an LLM; dedup, supersession, overdue arithmetic and ownership are deterministic — so the brief is identical on every run.", 11.5, FG, False)])

# ===========================================================  5. PROCESS FLOW
s = slide("5 / 10")
title(s, "Process flow", "One commitment, reconstructed from seven sources",
      "The vendor list — how dedup, slippage and supersession actually resolve.")

rows = [
    ("TR-03", "Mon 09:00", "transcript", "\"I told Raghav I'd send him the updated vendor list… by end of day tomorrow\"", "COMMIT → due Tue 23:59", INDIGO),
    ("EM-T1-01", "Mon 09:50", "email", "\"can you send the updated vendor list today?\"", "chase from Raghav", DIM),
    ("EM-T1-02", "Mon 17:40", "email", "\"Running behind, will send first thing tomorrow morning\"", "SLIP 1 → Tue 12:00", AMBER),
    ("VN-01", "Mon 18:40", "voice", "\"need to get Raghav that vendor list… might slip\"", "same item · no new date", DIM),
    ("EM-T1-03", "Tue 09:15", "email", "\"whenever you get a chance today works\"", "Raghav relaxes", DIM),
    ("EM-T1-04", "Tue 18:30", "email", "\"will send by tomorrow (Wednesday) morning for sure\"", "SLIP 2 → Wed 12:00", AMBER),
    ("EM-T1-05", "Wed 08:45", "email", "\"Just checking — still good for this morning?\"", "chase", DIM),
]
yy = Inches(2.2)
for i, (sid, when, kind, quote, effect, col) in enumerate(rows):
    y2 = yy + Inches(i * 0.52)
    if i % 2 == 0:
        box(s, Inches(0.75), y2 - Inches(0.04), Inches(11.8), Inches(0.48), fill=CARD)
    text(s, Inches(0.95), y2 + Inches(0.05), Inches(1.1), Inches(0.3), [(sid, 9.5, MUTED, False, MONO)])
    text(s, Inches(2.05), y2 + Inches(0.05), Inches(1.0), Inches(0.3), [(when, 9.5, DIM, False, MONO)])
    text(s, Inches(3.1), y2 + Inches(0.04), Inches(5.9), Inches(0.35), [(quote, 10.5, FG, False)])
    text(s, Inches(9.2), y2 + Inches(0.05), Inches(3.3), Inches(0.3), [(effect, 10, col, True)])

box(s, Inches(0.75), Inches(6.1), Inches(11.8), Inches(1.0), fill=CARD2)
text(s, Inches(1.05), Inches(6.25), Inches(11.2), Inches(0.8),
     [("Result:  one commitment", 14, EMERALD, True),
      ("owner Arjun · due Wed 12:00 · slip_count = 3 · 7 citations retained · flips to OVERDUE on Thursday, never delivered.",
       12, FG, False, FONT, 4)])

# ===========================================================  6. REFUSAL
s = slide("6 / 10")
title(s, "The hardest requirement", "Flagging unclear ownership instead of inventing it",
      "The Mumbai office lease needs a signature by Friday. Four people discuss it. Nobody accepts it.")

quotes = [
    ("Raghav, Mon", "\"needs someone to sign off… Not sure whose desk that's on right now.\""),
    ("Divya, Mon", "\"supposed to be Facilities, but I haven't seen anyone pick it up.\""),
    ("Arjun, Mon", "\"Okay, flag it, don't assume.\""),
    ("Arjun, voice note", "\"someone needs to own that, I don't think it's me.\""),
    ("Divya, Wed", "\"Not on my end — I believe this typically sits with Facilities, not us.\""),
    ("Raghav, Thu", "\"This is now one day out and still unowned.\""),
]
text(s, Inches(0.75), Inches(2.25), Inches(6.6), Inches(0.3), [("WHAT THE SOURCES SAY", 10, INDIGO, True)])
runs = []
for i, (who, q) in enumerate(quotes):
    runs.append((who, 10, DIM, True, FONT, 0 if i == 0 else 9))
    runs.append((q, 11.5, FG, False, FONT, 1))
text(s, Inches(0.75), Inches(2.65), Inches(6.5), Inches(4.0), runs, spacing=1.15)

box(s, Inches(7.6), Inches(2.25), Inches(4.95), Inches(2.5), fill=CARD, line=FUCHSIA)
text(s, Inches(7.9), Inches(2.5), Inches(4.4), Inches(0.3), [("WHAT THE AGENT OUTPUTS", 10, FUCHSIA, True)])
text(s, Inches(7.9), Inches(2.9), Inches(4.4), Inches(1.8),
     [("owner:  UNCLEAR", 14, FUCHSIA, True, MONO),
      ("needs_escalation:  true", 12, FG, False, MONO, 6),
      ("confidence:  0.45  (capped)", 12, FG, False, MONO, 4),
      ("direction:  unowned", 12, FG, False, MONO, 4),
      ("\"No one has accepted this. 5 sources disclaim or question ownership; "
       "Facilities was suggested but never confirmed.\"", 10.5, MUTED, False, FONT, 8)], spacing=1.2)

box(s, Inches(7.6), Inches(4.95), Inches(4.95), Inches(1.7), fill=CARD2)
text(s, Inches(7.9), Inches(5.15), Inches(4.4), Inches(1.4),
     [("Why it matters", 12, FG, True),
      ("Assigning it to Arjun would look more \"helpful\" and be wrong. "
       "An agent that quietly invents an owner teaches its user to distrust every "
       "other line in the brief.", 11, MUTED, False, FONT, 5),
      ("Asserted at three points in the week by test_mumbai_lease_is_never_assigned_to_anyone.",
       9.5, DIM, False, MONO, 6)], spacing=1.2)

# ===========================================================  7. DEMO
s = slide("7 / 10")
title(s, "The prototype", "Daily brief · replay the week · ask questions · inspect every source")

feats = [
    ("Daily brief, ranked by what matters", "Overdue → due today → waiting on others → unowned → upcoming → closed. Counts at the top.", INDIGO),
    ("Replay the week, day by day", "Mon/Tue/Wed/Thu/Fri switch the as_of timestamp. The agent genuinely does not know about future emails — watch the vendor list go from upcoming to due to overdue.", CYAN),
    ("Click any item for its evidence", "Every source that mentioned it, the speech acts detected, and a timeline of how the deadline moved.", AMBER),
    ("Ask, with citations", "\"What did I promise Raghav?\" · \"What needs action today?\" Every answer carries the source ids it came from, and refuses when nothing matches.", EMERALD),
]
for i, (h, d, col) in enumerate(feats):
    y2 = Inches(2.2 + i * 1.12)
    box(s, Inches(0.75), y2, Inches(7.6), Inches(0.98), fill=CARD)
    box(s, Inches(0.75), y2, Inches(0.055), Inches(0.98), fill=col)
    text(s, Inches(1.1), y2 + Inches(0.13), Inches(7.0), Inches(0.3), [(h, 12.5, FG, True)])
    text(s, Inches(1.1), y2 + Inches(0.42), Inches(7.0), Inches(0.5), [(d, 10.2, MUTED, False)], spacing=1.15)

box(s, Inches(8.65), Inches(2.2), Inches(3.9), Inches(4.3), fill=CARD)
text(s, Inches(8.95), Inches(2.42), Inches(3.3), Inches(0.3), [("REST API", 10, INDIGO, True)])
eps = [("GET", "/api/brief?as_of="), ("GET", "/api/commitments"), ("POST", "/api/ask"),
       ("GET", "/api/sources"), ("GET", "/api/audit"), ("GET", "/api/health"), ("GET", "/docs")]
runs = []
for i, (m, p) in enumerate(eps):
    runs.append((f"{m:<5}{p}", 10.5, FG, False, MONO, 0 if i == 0 else 7))
text(s, Inches(8.95), Inches(2.8), Inches(3.4), Inches(2.2), runs, spacing=1.2)
text(s, Inches(8.95), Inches(5.35), Inches(3.4), Inches(1.0),
     [("Swagger auto-generated at /docs.", 10, MUTED, False),
      ("SQLite stores every brief and question with its citations — a full audit trail.",
       10, MUTED, False, FONT, 6)], spacing=1.2)

# ===========================================================  8. AI TOOLS
s = slide("8 / 10")
title(s, "AI tools used", "What each tool did, and what it actually caught")

tools = [
    ("Claude Opus 5  (Claude Code)", "Primary build environment",
     "Parsed the assignment PDFs and reconstructed three garbled calendar tables; designed the ingest → extract → resolve architecture; wrote the pipeline, REST API, React SPA and the 23-test suite; debugged.", INDIGO),
    ("Groq API — llama-3.3-70b-versatile", "Optional LLM path",
     "Extraction and free-form Q&A behind a provider-agnostic interface (Groq / OpenAI / Anthropic). Off by default: the deterministic path is the reference implementation and the demo cannot be broken by a missing key.", AMBER),
    ("FastAPI OpenAPI / Swagger", "Auto-generated API surface",
     "Interactive docs at /docs, used to exercise every endpoint during development.", CYAN),
]
for i, (n, role, d, col) in enumerate(tools):
    y2 = Inches(2.15 + i * 1.18)
    box(s, Inches(0.75), y2, Inches(11.8), Inches(1.03), fill=CARD)
    box(s, Inches(0.75), y2, Inches(0.055), Inches(1.03), fill=col)
    text(s, Inches(1.1), y2 + Inches(0.12), Inches(5.0), Inches(0.3), [(n, 12.5, FG, True)])
    text(s, Inches(1.1), y2 + Inches(0.4), Inches(4.6), Inches(0.3), [(role, 10, col, False)])
    text(s, Inches(6.0), y2 + Inches(0.15), Inches(6.3), Inches(0.8), [(d, 10.2, MUTED, False)], spacing=1.15)

text(s, Inches(0.75), Inches(5.85), Inches(11.8), Inches(0.3),
     [("TWO BUGS FOUND BY TESTING, NOT BY READING", 10.5, ROSE, True)])
text(s, Inches(0.75), Inches(6.2), Inches(11.8), Inches(1.0),
     [("\"shifting the review to Thursday morning instead of Wednesday\"  →  resolved to Wednesday.", 11.5, FG, True, MONO),
      ("Weekdays were matched in dictionary order, so the reschedule — the entire point of that email — was silently dropped. Fixed by removing superseded days and preferring the correction after a contrast marker, scoped to one sentence.", 10.3, MUTED, False, FONT, 2),
      ("\"has anyone confirmed who's signing off?\"  →  marked the unowned lease DONE.", 11.5, FG, True, MONO, 7),
      ("A question matched the confirmation cue and closed an open item. Fixed by excluding chases and disclaimers from closure, and making an unowned item impossible to complete.", 10.3, MUTED, False, FONT, 2)],
     spacing=1.15)

# ===========================================================  9. RESULTS
s = slide("9 / 10")
title(s, "Results", "Every requirement in the brief, and how it is verified")

table = [
    ("Identify commitments made by the executive", "speech-act extraction", "5 found from 71 sources"),
    ("Separate \"my actions\" from \"waiting on others\"", "direction on each item", "2 mine · 2 waiting · 1 unowned"),
    ("Detect deadlines and overdue items", "dates.py + status vs as_of", "vendor list overdue by Thu"),
    ("Deduplicate the same action across sources", "topic clustering", "7 sources → 1 commitment"),
    ("Flag unclear ownership rather than inventing it", "UNCLEAR + escalation", "Mumbai lease, never assigned"),
    ("Produce a daily brief", "ranked sections + headline", "any day of the week"),
    ("Allow the user to ask questions", "grounded Q&A + citations", "refuses when ungrounded"),
]
hdr_y = Inches(2.2)
text(s, Inches(1.05), hdr_y, Inches(5.4), Inches(0.3), [("REQUIREMENT", 9.5, DIM, True)])
text(s, Inches(6.6), hdr_y, Inches(2.6), Inches(0.3), [("IMPLEMENTATION", 9.5, DIM, True)])
text(s, Inches(9.5), hdr_y, Inches(3.0), Inches(0.3), [("EVIDENCE", 9.5, DIM, True)])
for i, (req, impl, ev) in enumerate(table):
    y2 = Inches(2.6 + i * 0.5)
    if i % 2 == 0:
        box(s, Inches(0.75), y2 - Inches(0.05), Inches(11.8), Inches(0.46), fill=CARD)
    text(s, Inches(1.05), y2 + Inches(0.02), Inches(5.4), Inches(0.35), [("✓  " + req, 11, FG, False)])
    text(s, Inches(6.6), y2 + Inches(0.03), Inches(2.8), Inches(0.35), [(impl, 10, MUTED, False, MONO)])
    text(s, Inches(9.5), y2 + Inches(0.03), Inches(3.0), Inches(0.35), [(ev, 10, EMERALD, False)])

for i, (n, lab, col) in enumerate([("23", "tests passing", EMERALD), ("0.2s", "full suite", CYAN),
                                   ("~7ms", "brief latency", AMBER), ("0", "API keys required", INDIGO)]):
    x = Inches(0.75 + i * 3.0)
    box(s, x, Inches(6.25), Inches(2.75), Inches(0.85), fill=CARD2)
    text(s, x, Inches(6.38), Inches(2.75), Inches(0.35), [(n, 17, col, True)], align=PP_ALIGN.CENTER)
    text(s, x, Inches(6.75), Inches(2.75), Inches(0.3), [(lab, 9.5, DIM, False)], align=PP_ALIGN.CENTER)

# ===========================================================  10. CLOSE
s = slide("10 / 10")
title(s, "Limitations & next", "What I would build next, and what I would not claim")

left = [
    ("The topic lexicon is tuned to this data pack",
     "A new domain needs new anchors, or the LLM extraction path switched on. The resolution layer — where the real judgement lives — is unchanged either way."),
    ("The LLM path selects, it does not yet re-extract",
     "Next: structured-output extraction validated against the deterministic result, with disagreements surfaced rather than silently preferred."),
    ("Single-file React SPA, not a Vite/Next.js build",
     "A deliberate trade against a hard deadline: no build step that can fail, and the app runs with no network at all."),
]
text(s, Inches(0.75), Inches(2.25), Inches(6.4), Inches(0.3), [("HONEST LIMITATIONS", 10, ROSE, True)])
bullets(s, Inches(0.75), Inches(2.62), Inches(6.3), left, size=12, gap=13)

nxt = [
    ("Real connectors", "Gmail / Google Calendar / Slack ingestion behind the same SourceUnit interface — one adapter per source, nothing downstream changes."),
    ("Write actions, with confirmation", "Draft the chase email to Raghav; propose the Meridian slot against both calendars. Never send without approval."),
    ("Vector retrieval at scale", "A week fits in memory; a quarter does not. Embed SourceUnits and retrieve per question."),
    ("Learned thresholds", "Confidence is currently rule-assigned. With feedback on which items the executive actually acted on, it can be calibrated."),
]
text(s, Inches(7.4), Inches(2.25), Inches(5.2), Inches(0.3), [("WHAT I'D BUILD NEXT", 10, EMERALD, True)])
bullets(s, Inches(7.4), Inches(2.62), Inches(5.1), nxt, size=12, gap=11)

box(s, Inches(0.75), Inches(6.35), Inches(11.8), Inches(0.75), fill=CARD2)
text(s, Inches(1.05), Inches(6.5), Inches(11.2), Inches(0.5),
     [("github.com/harshiit-rana/AIONOS-Assignment-1", 13, FG, True, MONO),
      (f"{NAME} · {ROLL} · AIONOS Agentic AI Factory · Assignment 1", 10.5, DIM, False, FONT, 3)])

prs.save(OUT)
print(f"saved: {OUT}")
print(f"slides: {len(prs.slides.__iter__.__self__._sldIdLst)}")
print(f"size: {OUT.stat().st_size/1024:.0f} KB")
