"""Tests written against the traps in the data pack.

Each test names the behaviour the assignment brief asks for, so a reviewer can
read this file as a checklist of requirements rather than as unit tests.

Run: pytest -q
"""
from datetime import datetime

import pytest

from app.agent.dates import resolve_due
from app.agent.extract import extract_mentions
from app.agent.ingest import load_sources, sources_upto
from app.agent.qa import answer
from app.agent.resolve import (DONE, DUE_TODAY, MINE, OVERDUE, UNOWNED,
                               WAITING, resolve_commitments)

WED = datetime.fromisoformat("2026-09-23T09:00")
THU = datetime.fromisoformat("2026-09-24T17:00")
MON = datetime.fromisoformat("2026-09-21T18:00")


def brief_at(as_of):
    return resolve_commitments(extract_mentions(sources_upto(as_of)), as_of)


def find(cs, cid):
    return next(c for c in cs if c.id == cid)


# --- Requirement: deduplicate the same action across sources ---------------
def test_vendor_list_is_one_commitment_not_seven():
    """Transcript + 5 emails + voice note all describe the SAME obligation."""
    c = find(brief_at(WED), "vendor_list")
    ids = {e.source_id for e in c.evidence}
    assert {"TR-03", "VN-01"} <= ids
    assert len([i for i in ids if i.startswith("EM-T1")]) == 5
    assert len([x for x in brief_at(WED) if x.id == "vendor_list"]) == 1


def test_total_commitments_is_five_not_thirty_seven():
    """37 raw mentions collapse to 5 real commitments."""
    units = sources_upto(datetime.fromisoformat("2026-09-25T23:59"))
    assert len(extract_mentions(units)) > 30
    assert len(resolve_commitments(extract_mentions(units), THU)) == 5


# --- Requirement: identify commitments made by the executive ---------------
def test_separates_my_actions_from_waiting_on_others():
    cs = brief_at(WED)
    assert find(cs, "vendor_list").direction == MINE
    assert find(cs, "meridian_call").direction == MINE
    assert find(cs, "expense_variance").direction == WAITING
    assert find(cs, "campaign_deck").direction == WAITING


def test_owner_of_delegated_work_is_the_delegate_not_arjun():
    """Arjun ASKED Divya for the report -- Divya owns it, not Arjun."""
    c = find(brief_at(WED), "expense_variance")
    assert c.owner == "divya"
    assert c.counterparty == "arjun"


# --- Requirement: detect deadlines and overdue items -----------------------
def test_deadline_supersession_latest_statement_wins():
    """Deck review: Wednesday -> Thursday 09:30. The last word counts."""
    c = find(brief_at(THU), "campaign_deck")
    assert c.due_at.startswith("2026-09-24")
    assert c.slip_count >= 1


def test_report_deadline_pulled_earlier_not_later():
    """Divya said Thursday; Arjun pulled it to Wednesday evening."""
    c = find(brief_at(WED), "expense_variance")
    assert c.due_at == "2026-09-23T20:00"


def test_vendor_list_slipped_three_times_and_goes_overdue():
    wed = find(brief_at(WED), "vendor_list")
    assert wed.slip_count == 3, "Mon EOD-tomorrow -> Tue AM -> Wed AM"
    assert wed.status == DUE_TODAY
    assert find(brief_at(THU), "vendor_list").status == OVERDUE


def test_contrasted_weekday_resolves_to_the_correction():
    """'Thursday morning instead of Wednesday' means Thursday."""
    r = resolve_due("shifting the review to Thursday morning instead of Wednesday",
                    datetime.fromisoformat("2026-09-22T16:15"))
    assert r.due_at.date().isoformat() == "2026-09-24"


def test_relative_dates_anchor_to_their_own_source():
    """'tomorrow' on Monday and 'tomorrow' on Tuesday are different days."""
    mon = resolve_due("will send first thing tomorrow morning",
                      datetime.fromisoformat("2026-09-21T17:40"))
    tue = resolve_due("will send by tomorrow morning for sure",
                      datetime.fromisoformat("2026-09-22T18:30"))
    assert mon.due_at.date().isoformat() == "2026-09-22"
    assert tue.due_at.date().isoformat() == "2026-09-23"


# --- Requirement: flag unclear ownership rather than inventing it ----------
def test_mumbai_lease_is_never_assigned_to_anyone():
    """The whole point: nobody accepted it, so the agent must not guess."""
    for as_of in (MON, WED, THU):
        c = find(brief_at(as_of), "mumbai_lease")
        assert c.owner == "UNCLEAR"
        assert c.direction == UNOWNED
        assert c.needs_escalation is True
        assert c.owner != "arjun"
        assert c.confidence <= 0.45


def test_unowned_item_is_never_marked_done():
    """A chase containing the word 'confirmed' must not close the item."""
    assert find(brief_at(THU), "mumbai_lease").status != DONE


def test_facilities_is_recorded_as_a_suggestion_not_an_owner():
    c = find(brief_at(WED), "mumbai_lease")
    assert "facilities" in c.ownership_note.lower()
    assert c.owner == "UNCLEAR"


# --- Requirement: closed items stop nagging --------------------------------
def test_delivered_work_is_marked_done():
    cs = brief_at(THU)
    assert find(cs, "expense_variance").status == DONE   # report attached Wed 18:00
    assert find(cs, "meridian_call").status == DONE      # call confirmed
    assert find(cs, "campaign_deck").status == DONE      # deck delivered Thu 08:00


def test_nothing_is_done_before_it_was_delivered():
    """On Wednesday morning the report had not arrived yet."""
    assert find(brief_at(WED), "expense_variance").status != DONE


# --- Requirement: the agent only knows what it could have known ------------
def test_time_travel_hides_future_sources():
    assert len(sources_upto(MON)) < len(sources_upto(WED)) < len(load_sources())


def test_monday_brief_has_no_overdue_items():
    assert all(c.status != OVERDUE for c in brief_at(MON))


# --- Requirement: answer questions -----------------------------------------
def test_what_did_i_promise_raghav():
    r = answer("What did I promise Raghav?", brief_at(WED), WED)
    assert r["intent"] == "promises_to_person"
    assert "vendor list" in r["answer"].lower()
    assert "TR-03" in r["citations"]


def test_what_needs_action_today():
    r = answer("What needs action today?", brief_at(WED), WED)
    assert r["intent"] == "today"
    assert "vendor list" in r["answer"].lower()
    # It must surface the unowned item as needing a decision.
    assert "no owner" in r["answer"].lower() or "mumbai" in r["answer"].lower()


def test_answers_are_always_cited():
    for q in ["What did I promise Raghav?", "What is overdue?",
              "Who owns the Mumbai lease renewal?"]:
        r = answer(q, brief_at(THU), THU)
        assert r["grounded"] is False or r["citations"]


def test_refuses_questions_outside_the_data_pack():
    r = answer("What is our revenue forecast for Q4 in Singapore?", brief_at(WED), WED)
    assert r["grounded"] is False
    assert "only answer" in r["answer"].lower()


@pytest.mark.parametrize("question", [
    "what am I waiting on?", "what is overdue?", "what has been completed?",
])
def test_qa_never_crashes(question):
    assert answer(question, brief_at(THU), THU)["answer"]
