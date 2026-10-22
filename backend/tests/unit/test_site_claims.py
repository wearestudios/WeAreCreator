"""Every promise the public pages make, checked against the product.

A marketing page is the one surface where a sentence can be false without a
single test noticing — nothing calls it, nothing renders it into a response,
and nobody re-reads it after a feature changes underneath it. So each claim
on home, /brands and /creators is pinned here to the code that makes it true.

**And the claims the rewrite's brief asked for that are not true are refused
by name**, so a later copy edit cannot put them back without somebody first
building what they describe:

- "Money is held before the shoot" / "the brand funds it (amount held)" —
  there is no escrow. A payment row is raised at `in_payment`, after the work
  is approved.
- "Reviews cannot stall forever" / "a clock on the review" — the draft
  auto-approval timer is in an unmerged PR, not in this tree.
- "a cap on revisions (1 of 2 used)" — there is no revision cap.
- "an exportable statement" — creators have no statement export.
- "Counter the fee" and offer/counter history — negotiation history is in the
  same unmerged PR; on this tree a creator quotes a rate and the fee is agreed
  and recorded.
- "Run it yourself vs Have us run it" — the product is managed-only.
- "approving drafts stays yours" — on a campaign we run the drafts are our
  manager's to review; what stays the brand's is approving the work.
- "Messaging runs here" — there is no brand-to-creator messaging.
- "this, not follower count, moves you up" — audience size against the brief
  is part of the score.
- "Free to post. You only pay when a collaboration is agreed" — a campaign
  fee can be set on a brief we run.
"""
from __future__ import annotations

import functools
import inspect
import json
import re
import subprocess
from pathlib import Path

import pytest

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend"
CONTENT = FRONTEND / "src" / "content" / "marketing.js"


@functools.lru_cache(maxsize=1)
def content():
    out = subprocess.run(
        ["node", "--input-type=module", "-e",
         CONTENT.read_text() + "\nconsole.log(JSON.stringify({HOME, BRANDS, CREATORS, HERO_SCREENS}));"],
        capture_output=True, text=True, timeout=60,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def _all_text(node):
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        return " ".join(_all_text(v) for v in node.values())
    if isinstance(node, list):
        return " ".join(_all_text(v) for v in node)
    return ""


def _titles(section):
    return [i["title"] for i in section["items"]]


# ---------------------------------------------------------------------------
# Home: the three things the product enforces
# ---------------------------------------------------------------------------


class TestHomePromises:
    def test_the_three_are_the_ones_that_are_true(self):
        assert _titles(content()["HOME"]["promises"]) == [
            "A brand never gets a creator's number",
            "The fee is agreed before anyone shoots",
            "Every creator is checked before they apply",
        ]

    def test_a_brand_never_gets_a_creators_number(self):
        """Every brand-facing creator view is `_brand_visible_creator`, an
        allow-list that carries no contact field; the forbidden list names
        each one and the leak tests search every brand response for them."""
        for field in ("phone", "whatsapp", "email", "full_address"):
            assert field in server.BRAND_FORBIDDEN_CREATOR_FIELDS, field
            assert field not in server._BRAND_VISIBLE_CREATOR_FIELDS, field

    def test_the_fee_is_agreed_before_anyone_shoots(self):
        """The fee step precedes booking on the ladder, and the terms are
        frozen once, at acceptance."""
        order = server.COLLAB_STATE_ORDER
        assert order.index("commercial_agreed") < order.index("slot_booked")
        assert order.index("commercial_agreed") < order.index("attended")
        snapshot = inspect.getsource(server._issue_terms_snapshot)
        assert '"terms": {"$exists": False}' in snapshot

    def test_every_creator_is_checked_before_they_apply(self):
        """Applying needs a verified profile; a creator we have not checked
        yet has their pitch held, not sent."""
        assert "verified" in inspect.getsource(server._why_you_cannot_apply)
        hold = inspect.getsource(server._may_hold_application)
        assert "submitted_for_review_at" in hold and '"pending"' in hold


# ---------------------------------------------------------------------------
# /brands
# ---------------------------------------------------------------------------


class TestBrandPromises:
    def test_the_three_are_the_ones_that_are_true(self):
        assert _titles(content()["BRANDS"]["promises"]) == [
            "Creators are verified before they apply",
            "What you agree stays off public pages",
            "The campaign fee comes back if we can't fill it",
        ]

    def test_an_agreed_fee_is_on_no_public_page(self):
        """The share page renders no agreed amount, a case study forbids
        money in both directions, and the brand page's projection forbids it
        too."""
        assert "agreed_amount" not in inspect.getsource(server.public_campaign_page)
        assert "agreed_amount" in server.CASE_STUDY_FORBIDDEN_FIELDS

    def test_the_refund_rule_is_the_one_on_the_page(self):
        terms = server.REFUND_POLICY_TERMS.lower()
        assert "refund" in terms
        assert "shortlist" in terms
        text = _all_text(content()["BRANDS"]).lower()
        assert "refunded if we cannot fill it, unless you turned down everyone we shortlisted" in text

    def test_our_fee_sits_on_top_of_the_creators(self):
        assert "on top" in server.COMMISSION_TERMS.lower()
        assert "on top of the creator's rate, never taken out of theirs" in _all_text(content()["BRANDS"]).lower()

    def test_the_shortlist_is_scored_with_its_reasons(self):
        """The drawn shortlist shows a match out of 100 and the reasons — which
        is what the suggestions panel ships: a score from a table that sums to
        100, and the components with it."""
        assert sum(server.CREATOR_MATCH_WEIGHTS.values()) == 100
        rows = content()["BRANDS"]["shortlist"]["card"]["rows"]
        for row in rows:
            assert re.fullmatch(r"\d{1,2}%", row["match"]), row
            assert row["reasons"], row

    def test_we_invite_the_creators_a_brand_already_knows(self):
        """"Send us their handles and we'll invite them" — inviting is staff
        work, and the route exists for exactly the staff roles."""
        sig = inspect.signature(server.weare_invite_creators)
        guard = sig.parameters["user"].default.dependency
        assert "weare_team" in inspect.getclosurevars(guard).nonlocals["roles"]
        assert "_invite_creators" in inspect.getsource(server.weare_invite_creators)

    def test_approving_the_work_is_the_brands(self):
        """Content approval is a brand-owned transition, which is what the
        comparison table's sign-off row says in both columns."""
        assert "content_approved" in server._BRAND_OWNED_TRANSITIONS


# ---------------------------------------------------------------------------
# /creators
# ---------------------------------------------------------------------------


class TestCreatorPromises:
    def test_the_money_states_are_the_ones_the_record_moves_through(self):
        states = [s["title"] for s in content()["CREATORS"]["money"]["states"]]
        assert states == ["Agreed", "Delivered", "Paid"]
        order = server.COLLAB_STATE_ORDER
        assert order.index("commercial_agreed") < order.index("content_approved") < order.index("in_payment")

    def test_the_payout_window_drawn_is_the_platforms_default(self):
        """The drawn brief says "Paid within 7 days of approval". That is the
        platform default, so the illustration is a real brief's value rather
        than a nicer number."""
        assert server.CREATOR_PAYOUT_DAYS == 7
        chips = content()["CREATORS"]["brief"]["card"]["chips"]
        assert f"Paid within {server.CREATOR_PAYOUT_DAYS} days of approval" in chips

    def test_every_send_back_needs_a_reason(self):
        for fn in (server.brand_request_changes, server.request_draft_changes):
            src = inspect.getsource(fn)
            assert re.search(r"if not \(payload\.(?:reason|note) or \"\"\)\.strip\(\)|if not note", src), fn.__name__

    def test_a_date_on_the_payment(self):
        assert "content_approved_at" in inspect.getsource(server._payout_due_at)

    def test_pan_and_upi_or_bank(self):
        assert "pan" in inspect.getsource(server.payout_missing).lower()
        assert set(server.PAYOUT_METHOD_FIELDS) == {"upi", "bank"}

    def test_finishing_is_scored_but_follower_count_is_too(self):
        """The record section says finishing counts "not only your follower
        count" — both halves are weights in the shortlist score."""
        w = server.CREATOR_MATCH_WEIGHTS
        assert w["delivery"] > 0 and w["reach_fit"] > 0
        line = content()["CREATORS"]["record"]["line"].lower()
        assert "not only your follower count" in line


# ---------------------------------------------------------------------------
# What the brief asked for that is not true, refused by name
# ---------------------------------------------------------------------------


def _everything():
    c = content()
    return " ".join(_all_text(c[k]) for k in ("HOME", "BRANDS", "CREATORS", "HERO_SCREENS")).lower()


class TestWhatIsNotTrueIsNotSaid:
    def test_no_money_is_held(self):
        """Escrow appears once: the brand's own question, answered "No, and
        there isn't any"."""
        text = _everything()
        for phrase in ("held before", "amount held", "still held", "funds it", "travel on a promise"):
            assert phrase not in text, phrase
        faq = [i for i in content()["BRANDS"]["faq"]["items"] if "escrow" in i["q"].lower()]
        assert len(faq) == 1 and faq[0]["a"].startswith("No, and there isn't any")
        assert text.count("escrow") == 1

    def test_no_review_clock_until_one_exists(self):
        """If `_approve_draft_by_window` lands, this claim can come back."""
        if hasattr(server, "_approve_draft_by_window"):
            pytest.skip("the review timer exists in this tree")
        text = _everything()
        for phrase in ("stall", "clock on the review", "auto-approv", "approved automatically"):
            assert phrase not in text, phrase

    def test_no_revision_cap_and_no_statement_export(self):
        text = _everything()
        for phrase in ("cap on revisions", "1 of 2", "revision cap", "exportable", "statement"):
            assert phrase not in text, phrase

    def test_no_counter_offers_until_negotiation_history_exists(self):
        if hasattr(server, "NEGOTIATION_KINDS"):
            pytest.skip("negotiation history exists in this tree")
        text = _everything()
        for phrase in ("counter the fee", "countered", "offered ₹"):
            assert phrase not in text, phrase

    def test_no_self_serve_and_no_messaging(self):
        text = _everything()
        for phrase in ("run it yourself", "have us run it", "messaging runs here", "approving drafts"):
            assert phrase not in text, phrase

    def test_follower_count_is_not_claimed_to_be_irrelevant(self):
        text = _everything()
        assert "not follower count" not in text

    def test_the_close_does_not_promise_you_only_pay_per_collaboration(self):
        """A campaign fee can be set on a brief we run, so "you only pay when a
        collaboration is agreed" would be false on those briefs."""
        text = _everything()
        assert "only pay when" not in text
        assert content()["HOME"]["close"]["line"] == "Free to post, and no retainer."
