"""Every promise the public pages make, checked against the product.

A marketing page is the one surface where a sentence can be false without a
single test noticing — nothing calls it, nothing renders it into a response,
and nobody re-reads it after a feature changes underneath it. So each claim
on home, /for-brands and /for-creators is pinned here to the code that makes
it true.

**And the claims the rewrite's brief asked for that are not true are refused
by name**, so a later copy edit cannot put them back without somebody first
building what they describe:

- "Money is held before the shoot" / "the brand funds it (held)" / "you never
  travel on a promise" — there is no escrow. A payment row is raised at
  `in_payment`, after the work is approved.
- "Reviews cannot stall forever" / "a clock on the review" / "clears anyway"
  — the draft auto-approval timer is in an unmerged PR, not in this tree.
- "a cap on revisions (1 of 2 used)" — there is no revision cap.
- "an exportable statement", "with a receipt" — creators have neither.
- "Counter the fee" and offer/counter history — negotiation history is in the
  same unmerged PR; on this tree a creator quotes a rate and the fee is
  agreed and recorded.
- "ID-verified" — a person reviews each profile; no ID document is collected.
- "Payouts arrive … automatically" — a payout is marked paid by a person.
- "Run it yourself vs Have us run it" as a comparison — managed-only.
- "Messaging runs here" — there is no brand-to-creator messaging.
- "ranked by whether they finish — not by follower count" — follower fit is
  weighted above delivery in the score.
- "no other brand sees your rates" — a public brief shows its budget.
- "money leaves only when you approve" — a kill fee is owed without one.
- "you only pay when a deal/collaboration is agreed" — a campaign fee can be
  set on a brief we run.
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
         CONTENT.read_text() + "\nconsole.log(JSON.stringify({HOME, BRANDS, CREATORS, ASK, FACTS, WHATSAPP_HREF}));"],
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


def _everything():
    c = content()
    return " ".join(_all_text(c[k]) for k in ("HOME", "BRANDS", "CREATORS", "ASK")).lower()


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

    def test_the_hero_card_shows_the_history_this_product_keeps(self):
        """A budget on the brief, the creator's quote, the fee agreed, both
        sides on the frozen terms — the four things a collaboration here
        records — with the brief's own figures."""
        rows = content()["HOME"]["card"]["rows"]
        assert [r["who"] for r in rows] == [
            "Budget on the brief", "Kiran quoted", "Fee agreed", "Both accepted · terms frozen",
        ]
        assert [r["amount"] for r in rows] == ["₹11,000", "₹14,000", "₹12,500", "₹12,500"]
        assert [r.get("final", False) for r in rows] == [False, False, False, True]

    def test_the_steps_you_touch_are_the_brands_own_transitions(self):
        """"You only touch two": posting the brief, and approving the work —
        `content_approved` is brand-owned. Agreeing is ours on a brief we run
        (`agreed_at` is the moment we finish it) and the shoot is ours."""
        how = content()["HOME"]["how"]["items"]
        assert [i["key"] for i in how if i["yours"]] == ["offer", "paid"]
        assert "content_approved" in server._BRAND_OWNED_TRANSITIONS
        assert server.NEW_CAMPAIGN_EXECUTION_OWNER == "weare"


# ---------------------------------------------------------------------------
# /for-brands
# ---------------------------------------------------------------------------


class TestBrandPromises:
    def test_the_three_are_the_ones_that_are_true(self):
        assert _titles(content()["BRANDS"]["promises"]) == [
            "Creators are checked before they apply",
            "The fee you agree is never published",
            "The campaign fee comes back if we can't fill it",
        ]

    def test_an_agreed_fee_is_on_no_public_page(self):
        """The share page renders no agreed amount and a case study forbids
        money in both directions."""
        assert "agreed_amount" not in inspect.getsource(server.public_campaign_page)
        assert "agreed_amount" in server.CASE_STUDY_FORBIDDEN_FIELDS

    def test_the_refund_rule_is_the_one_on_the_page(self):
        terms = server.REFUND_POLICY_TERMS.lower()
        assert "refund" in terms and "shortlist" in terms
        text = _all_text(content()["BRANDS"]).lower()
        assert "unless you turned down everyone we shortlisted" in text

    def test_our_fee_sits_on_top_of_the_creators(self):
        assert "on top" in server.COMMISSION_TERMS.lower()
        assert "creators keep 100% of their fee — ours is separate" in _all_text(content()["BRANDS"]).lower()

    def test_the_shortlist_is_scored_with_its_reasons(self):
        """The drawn shortlist shows a match out of 100 and the reasons — what
        the suggestions panel ships: a score from a table that sums to 100,
        and the components with it."""
        assert sum(server.CREATOR_MATCH_WEIGHTS.values()) == 100
        for row in content()["BRANDS"]["shortlist"]["card"]["rows"]:
            assert re.fullmatch(r"\d{1,2}%", row["match"]), row
            assert row["reasons"], row

    def test_the_report_shows_only_what_is_measured(self):
        """"Never display a metric the app does not collect": every figure on
        the example report is one `PERFORMANCE_METRICS` records or the rollup
        derives (engagements, the rate over reach, cost per thousand reached)."""
        labels = [t["label"] for t in content()["BRANDS"]["report"]["card"]["totals"]]
        derivable = {
            "Reach": "reach", "Views": "views", "Impressions": "impressions",
            "Engagements": "total_engagements", "Engagement rate": "engagement_rate",
            "Cost per 1,000 reached": "cost_per_thousand_reach",
        }
        rollup = inspect.getsource(server._rollup_performance)
        for label in labels:
            assert label in derivable, label
            key = derivable[label]
            assert key in server.PERFORMANCE_METRICS or f'"{key}"' in rollup, label
        assert set(server.ENGAGEMENT_METRICS) == {"likes", "comments", "saves"}

    def test_we_invite_the_creators_a_brand_already_knows(self):
        """"Send us their handles and we'll invite them" — inviting is staff
        work, and the route exists for exactly the staff roles."""
        sig = inspect.signature(server.weare_invite_creators)
        guard = sig.parameters["user"].default.dependency
        assert "weare_team" in inspect.getclosurevars(guard).nonlocals["roles"]
        assert "_invite_creators" in inspect.getsource(server.weare_invite_creators)

    def test_launch_nights_are_ours(self):
        """"We run it, guest list to the night itself": a launch is weare-run
        whatever the brand picks."""
        reason = server._weare_run_reason("launch", 3, 15)
        assert reason and reason[0] == "launch"


# ---------------------------------------------------------------------------
# /for-creators
# ---------------------------------------------------------------------------


class TestCreatorPromises:
    def test_the_money_states_are_the_ones_the_record_moves_through(self):
        states = [s["title"] for s in content()["CREATORS"]["money"]["states"]]
        assert states == ["Agreed", "Delivered", "Paid"]
        order = server.COLLAB_STATE_ORDER
        assert order.index("commercial_agreed") < order.index("content_approved") < order.index("in_payment")

    def test_seven_days_is_the_platform_default(self):
        """"Paid within 7 days of approval" is now a public promise. It is the
        platform default. (A brief can carry its own window — see the PR's
        payout finding — so the copy promises the default.)"""
        assert server.CREATOR_PAYOUT_DAYS == 7
        assert f"Paid within {server.CREATOR_PAYOUT_DAYS} days of approval" in content()["CREATORS"]["hero"]["chips"]
        assert f"Paid within {server.CREATOR_PAYOUT_DAYS} days of approval" in content()["HOME"]["card"]["chips"]

    def test_creators_sign_in_with_whatsapp(self):
        """"Sign in with WhatsApp" / "a code sent to your WhatsApp": creators
        are not on the password allow-list, and the OTP form says WhatsApp."""
        login = inspect.getsource(server.login)
        assert 'if user.get("role") not in ("admin", "campaign_manager", "weare_team"):' in login
        form = (FRONTEND / "src" / "components" / "OtpForm.jsx").read_text()
        assert "WhatsApp" in form
        assert "Sign in with WhatsApp" in content()["CREATORS"]["hero"]["chips"]

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
        assert "not only your follower count" in content()["CREATORS"]["record"]["lead"].lower()

    def test_the_record_band_is_the_one_a_brand_would_see(self):
        """19 of 20 finished is the top band, and the card prints its label."""
        assert "Consistently delivers" in [b[2] for b in server.RELIABILITY_BANDS]
        assert content()["CREATORS"]["record"]["card"]["band"] == "Consistently delivers"


# ---------------------------------------------------------------------------
# The real names, and the one WhatsApp door
# ---------------------------------------------------------------------------


class TestNames:
    def test_drawn_ui_uses_invented_names_only(self):
        """Real client names belong in "who built it" and nowhere else."""
        drawn = _all_text(content()["HOME"]["card"]) + _all_text(content()["HOME"]["swap"])
        drawn += _all_text(content()["BRANDS"]["shortlist"]) + _all_text(content()["CREATORS"]["briefs"])
        for real in content()["FACTS"]["confirmedClients"]:
            assert real not in drawn, real
        for invented in ("Kiran", "Priya", "Rahul", "Tanvi"):
            assert invented in drawn, invented

    def test_no_team_member_is_named(self):
        """The contact page names the two partners; the three rebuilt pages
        and their copy name nobody from WeAre Studios."""
        site = (FRONTEND / "src" / "lib" / "siteNav.js").read_text()
        people = re.findall(r'name: "([^"]+)"', site[site.index("CONTACT_PEOPLE"):site.index("];", site.index("CONTACT_PEOPLE"))])
        assert people
        text = _everything()
        for person in people:
            for part in person.lower().split():
                assert part not in text.split(), person

    def test_the_whatsapp_door_is_a_number_on_the_contact_page(self):
        """One number, the same one the contact page lists — not a second
        spelling kept beside the first."""
        site = (FRONTEND / "src" / "lib" / "siteNav.js").read_text()
        phones = [p.lstrip("+") for p in re.findall(r'phone: "(\+\d+)"', site)]
        href = content()["WHATSAPP_HREF"]
        assert re.match(r"https://wa\.me/(\d+)\?text=", href)
        assert re.match(r"https://wa\.me/(\d+)", href).group(1) in phones
        assert content()["ASK"]["talkWhatsapp"]["href"] == href


# ---------------------------------------------------------------------------
# What the brief asked for that is not true, refused by name
# ---------------------------------------------------------------------------


class TestWhatIsNotTrueIsNotSaid:
    def test_no_money_is_held(self):
        """Escrow appears once: the brand's own question, answered "No, and
        there isn't any"."""
        text = _everything()
        for phrase in ("held before", "money is held", "still held", "funds it", "travel on a promise"):
            assert phrase not in text, phrase
        faq = [i for i in content()["BRANDS"]["faq"]["items"] if "escrow" in i["q"].lower()]
        assert len(faq) == 1 and faq[0]["a"].startswith("No, and there isn't any")
        assert text.count("escrow") == 1

    def test_no_review_clock_until_one_exists(self):
        """If `_approve_draft_by_window` lands, this claim can come back."""
        if hasattr(server, "_approve_draft_by_window"):
            pytest.skip("the review timer exists in this tree")
        text = _everything()
        for phrase in ("stall", "clock on the review", "auto-approv", "approved automatically", "clears anyway"):
            assert phrase not in text, phrase

    def test_no_revision_cap_no_statement_no_receipt(self):
        text = _everything()
        for phrase in ("cap on revisions", "1 of 2", "revision cap", "exportable", "statement", "receipt"):
            assert phrase not in text, phrase

    def test_no_counter_offers_until_negotiation_history_exists(self):
        if hasattr(server, "NEGOTIATION_KINDS"):
            pytest.skip("negotiation history exists in this tree")
        text = _everything()
        for phrase in ("counter the fee", "countered", "you offered"):
            assert phrase not in text, phrase

    def test_no_id_check_is_claimed(self):
        text = _everything()
        assert "id-verified" not in text and "id verified" not in text

    def test_no_payout_is_claimed_to_be_automatic(self):
        assert "automatically" not in _everything()

    def test_no_self_serve_column_and_no_messaging(self):
        """"Have us run it" survives as the label of a WhatsApp button on
        home; as a column against "Run it yourself" it does not."""
        text = _everything()
        for phrase in ("run it yourself", "self-serve", "messaging runs here", "approving drafts"):
            assert phrase not in text, phrase
        assert content()["BRANDS"]["compare"]["columns"][1] == "Over DMs and a spreadsheet"

    def test_follower_count_is_not_claimed_to_be_irrelevant(self):
        text = _everything()
        assert "not follower count" not in text
        assert "by whether they finish" not in text

    def test_rates_and_approvals_are_not_overclaimed(self):
        text = _everything()
        assert "no other brand sees your rates" not in text
        assert "money leaves only when you approve" not in text

    def test_nothing_promises_you_only_pay_per_deal(self):
        """A campaign fee can be set on a brief we run, so "you only pay when
        a deal is agreed" would be false on those briefs."""
        text = _everything()
        assert "only pay when" not in text
        assert content()["HOME"]["close"]["line"] == "Free to post, and no retainer."
        assert content()["HOME"]["hero"]["note"] == "Free to post · no retainer"
