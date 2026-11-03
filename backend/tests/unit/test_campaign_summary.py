"""The AI campaign summary: grounded or not shown.

Three layers, the order they matter in:

1. **The grounding validator, pure.** Every number the model writes must be in
   the input or the derived set, within display rounding. Planted invented
   numbers — a "3x", a rupee figure nobody computed, a percentage from
   nowhere, a number word — must each be caught, and honest roundings ("1.49L"
   for 1,48,932) must each pass. A validator that rejects everything is as
   useless as one that rejects nothing, so both directions are pinned.
2. **The derived values are Python's**, checked by hand here.
3. **The routes, driven** against a mock database with the fake provider:
   cache and staleness, the five-a-day limit, the three-post floor, the kill
   switch, the summary written on close, no forbidden value reaching the
   provider, and an erasure taking the summary with it.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import re
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId
from fastapi import HTTPException, params
from mongomock_motor import AsyncMongoMockClient

import ai
import campaign_summary as cs
import server
from fake_ai import FakeProvider, ai_on

NOW = datetime.now(timezone.utc)
LOOP = asyncio.new_event_loop()


def run(body):
    async def go():
        db = AsyncMongoMockClient()["summary"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return LOOP.run_until_complete(go())


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    async def boom(self, **_):
        raise AssertionError(f"a test reached the real {self.name} provider")

    monkeypatch.setattr(ai.GeminiProvider, "complete", boom)
    monkeypatch.setattr(ai.AnthropicProvider, "complete", boom)
    monkeypatch.delenv("AI_ENABLED", raising=False)
    yield
    ai.use_provider(None)


def inr(n) -> str:
    """Indian digit grouping: 148932 → 1,48,932."""
    s = str(int(round(n)))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups + [tail])


# ---------------------------------------------------------------------------
# A small, fixed input for the pure tests
# ---------------------------------------------------------------------------


def sample_input(*, measured_all=False, baseline=True):
    analytics = {
        "campaign": {"title": "Weekend tasting 2026", "category": "fnb", "city": "Bengaluru",
                     "campaign_type": "personal_table", "compensation_type": "fixed"},
        "totals": {"total_reach": 148932, "total_impressions": 260000, "total_views": 0,
                   "total_engagements": 6512, "engagement_rate": 4.37, "total_spend": 80000.0,
                   "cost_per_thousand_reach": 537.15, "paid_reach": 148932},
        "creators": [
            {"creator_id": "a", "name": "Aditi Rao", "reach": 68000, "impressions": 120000,
             "engagements": 3400, "engagement_rate": 5.0, "cost": 20000.0,
             "cost_per_thousand_reach": 294.12, "measured": True},
            {"creator_id": "b", "name": "Foodie42", "reach": 48932, "impressions": 90000,
             "engagements": 2112, "engagement_rate": 4.32, "cost": 20000.0,
             "cost_per_thousand_reach": 408.73, "measured": True},
            {"creator_id": "c", "name": "Kiran M", "reach": 32000, "impressions": 50000,
             "engagements": 1000, "engagement_rate": 3.13, "cost": 20000.0,
             "cost_per_thousand_reach": 625.0, "measured": True},
            {"creator_id": "d", "name": "Priya S", "reach": None, "impressions": None,
             "engagements": None, "engagement_rate": None, "cost": 20000.0,
             "cost_per_thousand_reach": None, "measured": False},
        ],
    }
    if measured_all:
        analytics["creators"] = analytics["creators"][:3]
    versus = None
    if baseline:
        versus = {
            "campaigns_before": 2,
            "reach": {"value": 148932, "previous": 98000, "change_percent": 52.0, "better": True},
            "engagement_rate": {"value": 4.37, "previous": 3.9, "change_percent": 12.1, "better": True},
            "cost_per_thousand_reach": {"value": 537.15, "previous": 640.0,
                                        "change_percent": -16.1, "better": True},
        }
    formats = {"a": "1 reel · 2 stories", "b": "1 reel · 2 stories",
               "c": "1 reel · 2 stories", "d": "1 reel · 2 stories"}
    return cs.build_summary_input(analytics, versus, formats, category_label="Food & drink")


def point(text, *evidence):
    return {"text": text, "evidence": list(evidence) or ["totals.reach"]}


def summary(headline, worked, didnt=(), nxt=None):
    return cs.CampaignSummary.model_validate(
        {
            "headline": headline,
            "worked": list(worked),
            "didnt": list(didnt),
            "next": nxt or [point("Book Aditi Rao again for the next tasting.", "creators[0].name")],
        }
    )


GOOD_HEADLINE = "3 of 4 posts measured: 1.49L people reached at ₹537 per 1,000"


def good_summary(data=None):
    return summary(
        GOOD_HEADLINE,
        [
            point("Aditi Rao reached 68,000 people, 45.7% of everyone this campaign reached.",
                  "creators[0].reach", "derived.top_creator_share_of_reach_percent"),
            point("Engagement was 4.37%, up 12.1% on your earlier campaigns.",
                  "totals.engagement_rate", "baseline.engagement_rate.change_percent"),
            point("Reach was 52% higher than your 2 earlier campaigns: 1,48,932 people.",
                  "baseline.reach.change_percent"),
        ],
        [point("One post (Priya S) has no reading yet, so it is not counted.",
               "derived.posts_unmeasured")],
    )


# ---------------------------------------------------------------------------
# 1. Number extraction and normalisation
# ---------------------------------------------------------------------------


class TestExtraction:
    @pytest.mark.parametrize(
        "text,value,kind",
        [
            ("₹1,48,932", 148932, "money"),
            ("Rs. 80,000", 80000, "money"),
            ("INR 537.15", 537.15, "money"),
            ("1.49L people", 149000, "plain"),
            ("1.49 lakh", 149000, "plain"),
            ("38K reach", 38000, "plain"),
            ("2.5M", 2_500_000, "plain"),
            ("1.2 crore", 12_000_000, "plain"),
            ("4.37%", 4.37, "percent"),
            ("12.1 per cent", 12.1, "percent"),
            ("52 percent", 52, "percent"),
            ("1,48,932", 148932, "plain"),
            ("148,932", 148932, "plain"),
        ],
    )
    def test_formats_are_normalised(self, text, value, kind):
        found = [f for f in cs.extract_numbers(text) if f.kind != "ordinal"]
        assert len(found) == 1, found
        assert found[0].value == pytest.approx(value)
        assert found[0].kind == kind

    def test_display_rounding_sets_the_tolerance(self):
        (lakh,) = cs.extract_numbers("1.49L")
        assert lakh.tol == pytest.approx(500)  # anything that displays as 1.49L
        (k,) = cs.extract_numbers("38K")
        assert k.tol == pytest.approx(500)
        (pct,) = cs.extract_numbers("4.4%")
        assert pct.tol == pytest.approx(0.05)

    def test_trailing_zeros_round_but_never_by_more_than_half_a_percent(self):
        (rounded,) = cs.extract_numbers("1,49,000")
        assert rounded.tol == pytest.approx(500)
        (hundred,) = cs.extract_numbers("100 posts")
        assert hundred.tol == pytest.approx(0.5), "100 must not vouch for 60"

    def test_number_words_are_numbers(self):
        assert [f.value for f in cs.extract_numbers("three of four posts")] == [3, 4]

    def test_per_thousand_is_a_unit_not_a_figure(self):
        assert cs.extract_numbers("cost per 1,000 people reached") == []
        assert cs.extract_numbers("₹537 per thousand")[0].value == 537

    def test_a_digit_inside_a_known_name_is_not_a_claim(self):
        assert [f.value for f in cs.extract_numbers("Foodie42 did well", strip=("Foodie42",))] == []

    def test_ordinals_are_positions(self):
        (first,) = cs.extract_numbers("the 2nd creator")
        assert first.kind == "ordinal" and first.value == 2


# ---------------------------------------------------------------------------
# 2. Grounding — pass
# ---------------------------------------------------------------------------


class TestGroundingPasses:
    def test_an_honest_summary_is_grounded(self):
        data = sample_input()
        assert cs.ground(good_summary(), data) == []

    @pytest.mark.parametrize(
        "phrase",
        [
            "1,48,932 people reached",      # exact, Indian commas
            "148,932 people reached",       # exact, western commas
            "1.49L people reached",         # lakh notation
            "1.5 lakh people reached",      # coarser lakh
            "149K people reached",          # thousands
            "about 1,49,000 people",        # rounded to the thousand
            "₹537 per 1,000 people",        # money, rounded
            "₹537.15 per 1,000 people",     # money, exact
            "₹80,000 spent",                # spend
            "engagement of 4.4%",           # percent, rounded
            "16.1% cheaper per 1,000",      # a delta, sign dropped
            "Foodie42 reached 48,932",      # digits in a name
            "the top creator carried 45.7% of reach",
            "2 earlier campaigns",
        ],
    )
    def test_honest_roundings_pass(self, phrase):
        data = sample_input()
        s = summary(GOOD_HEADLINE, [point(phrase, "totals.reach")])
        assert cs.ground(s, data) == [], phrase


# ---------------------------------------------------------------------------
# 3. Grounding — fail, with planted invented numbers
# ---------------------------------------------------------------------------


class TestGroundingRejects:
    @pytest.mark.parametrize(
        "invented",
        [
            "3x the reach of a normal post",        # a multiple nobody computed
            "reached 2,00,000 people",              # a total that is not the total
            "₹99,999 well spent",                   # a rupee figure from nowhere
            "engagement of 7.2%",                   # a percentage from nowhere
            "reach grew 64%",                       # a delta that is not the delta
            "1.8L people reached",                  # lakh, but the wrong lakh
            "seven creators delivered",             # a number word not in the data
            "₹4.37 per post",                       # a rate dressed as money
            "537% cheaper",                         # money dressed as a percent
            "worth 55K in reach",                   # K notation, invented
            "3 times the reach",                    # a multiple spelt out
            "a 2-fold rise",                        # and hyphenated
            "Aditi Rao did 4×",                     # and with the sign
        ],
    )
    def test_a_planted_invented_number_is_rejected(self, invented):
        data = sample_input()
        s = summary(GOOD_HEADLINE, [point(invented, "totals.reach")])
        problems = cs.ground(s, data)
        assert problems, f"{invented!r} was let through"
        assert any("is not in the data" in p for p in problems)

    def test_the_offending_number_is_named_so_the_retry_can_fix_it(self):
        data = sample_input()
        s = summary(GOOD_HEADLINE, [point("3x the reach", "totals.reach")])
        assert any('"3x"' in p for p in cs.ground(s, data))

    def test_an_invented_number_in_the_headline_is_caught_too(self):
        data = sample_input()
        s = summary("3 of 4 posts measured, reaching 9,99,999 people", [point("Fine.")])
        assert any(p.startswith("headline") for p in cs.ground(s, data))

    def test_evidence_must_exist(self):
        data = sample_input()
        for bad in ("totals.sales", "creators[9].reach", "creators[3].reach", "derived.nothing", "totals..reach["):
            s = summary(GOOD_HEADLINE, [point("Reach was strong.", bad)])
            assert any("evidence path" in p for p in cs.ground(s, data)), bad

    def test_unmeasured_posts_must_be_said(self):
        data = sample_input()
        s = summary("1.49L people reached at ₹537 per 1,000", [point("Aditi Rao led.", "creators[0].name")])
        problems = cs.ground(s, data)
        assert any("posts were measured" in p for p in problems)

    def test_with_every_post_measured_there_is_nothing_to_say(self):
        data = sample_input(measured_all=True)
        s = summary("1.49L people reached at ₹537 per 1,000", [point("Aditi Rao led.", "creators[0].name")])
        assert not any("posts were measured" in p for p in cs.ground(s, data))

    @pytest.mark.parametrize(
        "measure",
        ["drove sales", "lifted revenue", "brought footfall", "won new followers",
         "got lots of likes", "many comments", "people clicked through clicks", "great ROI"],
    )
    def test_a_measure_the_input_does_not_carry_is_refused(self, measure):
        data = sample_input()
        s = summary(GOOD_HEADLINE, [point(f"The campaign {measure}.", "totals.reach")])
        assert any("which is not in the data" in p for p in cs.ground(s, data))

    def test_views_are_refused_when_none_were_recorded(self):
        data = sample_input()
        assert "views" not in data["totals"]
        s = summary(GOOD_HEADLINE, [point("Lots of views.", "totals.reach")])
        assert any("views" in p for p in cs.ground(s, data))

    def test_no_comparison_without_a_baseline(self):
        data = sample_input(baseline=False)
        s = summary(GOOD_HEADLINE, [point("Better than your last campaign.", "totals.reach")])
        assert any("earlier campaigns" in p for p in cs.ground(s, data))


# ---------------------------------------------------------------------------
# 4. The input and the derived values
# ---------------------------------------------------------------------------


class TestInput:
    def test_derived_values_are_computed_in_python(self):
        d = sample_input()["derived"]
        assert d["posts_total"] == 4 and d["posts_measured"] == 3 and d["posts_unmeasured"] == 1
        assert d["average_reach_per_measured_post"] == round(148932 / 3)
        assert d["top_creator_share_of_reach_percent"] == round(68000 / 148932 * 100, 1)
        assert d["cost_per_thousand_reach"] == 537.15
        (fmt,) = d["by_format"]
        assert fmt["format"] == "1 reel · 2 stories"
        assert fmt["posts"] == 4 and fmt["posts_measured"] == 3
        assert fmt["average_reach"] == round(148932 / 3)
        assert fmt["engagement_rate"] == round(6512 / 148932 * 100, 2)
        # Over paid, measured posts only, on both sides of the division.
        assert fmt["cost_per_thousand_reach"] == round(60000 / 148932 * 1000, 2)

    def test_formats_are_averaged_separately(self):
        data = sample_input()
        data["creators"][0]["format"] = "1 reel"
        d = cs.derive(data)
        labels = {f["format"]: f for f in d["by_format"]}
        assert labels["1 reel"]["average_reach"] == 68000
        assert labels["1 reel · 2 stories"]["average_reach"] == round((48932 + 32000) / 2)

    def test_absent_is_absent_not_null(self):
        data = sample_input()
        priya = data["creators"][3]
        assert "reach" not in priya and "engagement_rate" not in priya
        assert priya["measured"] is False
        assert "views" not in data["totals"]

    def test_there_is_no_language_average_until_tagging_exists(self):
        assert "by_language" not in sample_input()["derived"]

    def test_the_digest_moves_with_the_data_and_with_the_prompt(self, monkeypatch):
        a, b = sample_input(), sample_input()
        assert cs.input_digest(a) == cs.input_digest(b)
        b["totals"]["reach"] += 1
        assert cs.input_digest(a) != cs.input_digest(b)
        before = cs.input_digest(a)
        monkeypatch.setattr(cs, "PROMPT", cs.ai.Prompt(cs.TASK, "campaign_summary.vX", "x"))
        assert cs.input_digest(a) != before


# ---------------------------------------------------------------------------
# 5. The routes, driven
# ---------------------------------------------------------------------------

PLANTED = {
    "phone": "+919812345678",
    "email": "aditi.private@example.com",
    "full_address": "42 Secret Lane, Indiranagar",
    "location_lat": 12.97161,
    "payout_upi": "aditi@okhdfc",
    "payout_account_number": "918273645500",
    "payout_ifsc": "HDFC0001234",
    "pan": "ABCDE1234F",
}


async def world(db, *, readings=(60000, 45000, 30000, None), status="in_progress",
                earlier=True):
    """A brand, a campaign with four creators (one unmeasured by default), all
    paid, and an earlier campaign for the baseline. Every creator carries the
    planted contact values the leak test searches for."""
    brand = ObjectId()
    await db.users.insert_one({"_id": brand, "role": "brand_manager", "name": "Toit", "brand_id": brand})
    await db.brand_profiles.insert_one({"user_id": brand, "business_name": "Toit", "verified": True,
                                        "contact_phone": "+919000000001",
                                        "contact_email": "owner@toit.example"})

    def campaign(when, st):
        return {
            "_id": ObjectId(), "brand_id": brand, "title": "Tasting", "status": st,
            "created_at": when, "creators_needed": len(readings), "category": "fnb",
            "city": "Bengaluru", "campaign_type": "personal_table",
            "compensation_type": "fixed", "budget_per_creator": 20000,
            "execution_owner": "brand",
            "deliverable_items": [{"type": "reel", "quantity": 1}],
        }

    current = campaign(NOW - timedelta(days=20), status)
    await db.campaigns.insert_one(current)
    names = ["Aditi Rao", "Kiran M", "Priya S", "Rahul T", "Tanvi K"]
    creators = []
    for i, reach in enumerate(readings):
        creator, collab = ObjectId(), ObjectId()
        creators.append(creator)
        await db.users.insert_one({"_id": creator, "role": "creator", "name": names[i],
                                   "phone": PLANTED["phone"], "email": PLANTED["email"]})
        await db.creator_profiles.insert_one(
            {"user_id": creator, "name": names[i], "verification_status": "verified",
             "instagram_handle": f"handle{i}", **PLANTED}
        )
        await db.collaborations.insert_one(
            {"_id": collab, "campaign_id": current["_id"], "creator_id": creator,
             "state": "closed", "agreed_amount": 20000.0, "agreed_at": NOW - timedelta(days=18)}
        )
        await db.payments.insert_one(
            {"_id": ObjectId(), "collaboration_id": collab, "state": "paid",
             "creator_payout": 20000.0, "paid_at": NOW - timedelta(days=10)}
        )
        if reach is not None:
            await db.content_performance.insert_one(
                {"_id": ObjectId(), "collaboration_id": collab, "campaign_id": current["_id"],
                 "reach": reach, "impressions": reach * 2, "likes": reach // 20,
                 "comments": reach // 200, "captured_at": NOW - timedelta(days=9),
                 "note": f"call me on {PLANTED['phone']}"}
            )
    if earlier:
        old = campaign(NOW - timedelta(days=120), "closed")
        await db.campaigns.insert_one(old)
        oc = ObjectId()
        await db.collaborations.insert_one(
            {"_id": oc, "campaign_id": old["_id"], "creator_id": creators[0], "state": "closed",
             "agreed_amount": 20000.0, "agreed_at": NOW - timedelta(days=118)}
        )
        await db.payments.insert_one(
            {"_id": ObjectId(), "collaboration_id": oc, "state": "paid", "creator_payout": 20000.0}
        )
        await db.content_performance.insert_one(
            {"_id": ObjectId(), "collaboration_id": oc, "campaign_id": old["_id"],
             "reach": 40000, "likes": 1000, "comments": 50}
        )
    user = {"_id": str(brand), "role": "brand_manager", "name": "Toit", "brand_id": str(brand)}
    return {"user": user, "brand": brand, "campaign": current, "id": str(current["_id"]),
            "creators": creators}


def _data_from(user_message: str) -> dict:
    body = re.search(r"<<<DATA-\w+>>>\n(.*)\n<<<END-DATA-\w+>>>", user_message, re.S).group(1)
    return json.loads(body)


def grounded_reply(system, user) -> str:
    """What a well-behaved model returns: every number read off the input."""
    data = _data_from(user)
    d, t = data["derived"], data["totals"]
    top = data["creators"][0]
    headline = f"{inr(t['reach'])} people reached at ₹{round(t['cost_per_thousand_reach'])} per 1,000"
    if d["posts_measured"] < d["posts_total"]:
        headline = f"{d['posts_measured']} of {d['posts_total']} posts measured: " + headline
    out = {
        "headline": headline[:110],
        "worked": [
            {"text": f"{top['name']} reached {inr(top['reach'])} people, "
                     f"{d['top_creator_share_of_reach_percent']}% of the total.",
             "evidence": ["creators[0].reach", "derived.top_creator_share_of_reach_percent"]},
            {"text": f"Engagement was {t['engagement_rate']}% across measured posts.",
             "evidence": ["totals.engagement_rate"]},
        ],
        "didnt": [],
        "next": [{"text": f"Book {top['name']} again for the next brief.",
                  "evidence": ["creators[0].name"]}],
    }
    return json.dumps(out, ensure_ascii=False)


def invented_reply(system, user) -> str:
    return json.dumps({
        "headline": "Your campaign tripled footfall",
        "worked": [{"text": "Reach was 3x your usual at ₹12 per 1,000.", "evidence": ["totals.reach"]}],
        "didnt": [],
        "next": [{"text": "Do it again.", "evidence": ["totals.reach"]}],
    })


def get(w):
    return server.brand_campaign_summary(w["id"], w["user"])


def regenerate(w):
    return server.regenerate_campaign_summary(w["id"], w["user"])


class TestRoutes:
    def test_both_routes_are_for_the_brand_and_admin_only(self):
        for fn in (server.brand_campaign_summary, server.regenerate_campaign_summary):
            for p in inspect.signature(fn).parameters.values():
                if isinstance(p.default, params.Depends):
                    guard = p.default.dependency
            for role, allowed in (("brand_manager", True), ("brand", True), ("admin", True),
                                  ("creator", False), ("weare_team", False),
                                  ("campaign_manager", False)):
                async def check():
                    try:
                        await guard({"_id": str(ObjectId()), "role": role})
                        return True
                    except HTTPException:
                        return False
                assert LOOP.run_until_complete(check()) is allowed, (fn.__name__, role)

    def test_switched_off_the_feature_is_a_clean_absence(self):
        async def body(db):
            w = await world(db)
            await db.campaign_summaries.insert_one(
                {"campaign_id": w["campaign"]["_id"], "summary": {"headline": "old"}}
            )
            out = await get(w)
            with pytest.raises(HTTPException) as err:
                await regenerate(w)
            return out, err.value

        out, err = run(body)
        assert out == {"available": False, "campaign_id": out["campaign_id"]}
        assert "old" not in json.dumps(out), "a stale summary must not leak past the switch"
        assert err.status_code == 503 and err.detail["code"] == "ai_unavailable"

    def test_generate_cache_and_stale(self):
        fake = FakeProvider(grounded_reply, grounded_reply)

        async def body(db):
            w = await world(db)
            before = await get(w)
            made = await regenerate(w)
            after = await get(w)
            # Same data again: the cache answers, nobody is called.
            again = await regenerate(w)
            calls_after_cache = len(fake.calls)
            # A reading is corrected: the summary is now stale.
            await db.content_performance.update_one(
                {"campaign_id": w["campaign"]["_id"], "reach": 30000}, {"$set": {"reach": 31000}}
            )
            stale = await get(w)
            fresh = await regenerate(w)
            return before, made, after, again, calls_after_cache, stale, fresh

        with ai_on(fake):
            before, made, after, again, calls_after_cache, stale, fresh = run(body)

        assert before["available"] and before["eligible"] and before["summary"] is None
        assert before["reason"] == "not_generated"
        assert before["posts_measured"] == 3 and before["posts_total"] == 4
        assert made["summary"]["headline"].startswith("3 of 4 posts measured")
        assert made["cached"] is False and made["stale"] is False
        assert after["summary"] == made["summary"] and after["stale"] is False
        assert again["cached"] is True and calls_after_cache == 1
        assert stale["stale"] is True and stale["summary"] == made["summary"], (
            "stale is said, not hidden: the old summary stays readable beside the flag"
        )
        assert fresh["stale"] is False and fresh["cached"] is False
        assert len(fake.calls) == 2
        assert fresh["regenerations_left"] == cs.REGENERATIONS_PER_DAY - 2

    def test_an_ungrounded_summary_is_never_stored(self):
        fake = FakeProvider(invented_reply, invented_reply)

        async def body(db):
            w = await world(db)
            with pytest.raises(HTTPException) as err:
                await regenerate(w)
            stored = await db.campaign_summaries.find_one({"campaign_id": w["campaign"]["_id"]})
            return err.value, stored, await get(w)

        with ai_on(fake):
            err, stored, state = run(body)
        assert err.status_code == 503 and err.detail["code"] == "summary_unavailable"
        assert len(fake.calls) == 2, "one retry, then closed"
        retry = fake.calls[1]["user"]
        assert '"3x"' in retry, "the retry names the offending number"
        assert "footfall" in retry
        assert stored.get("summary") is None and stored["last_error"] == "rejected"
        assert state["summary"] is None and state["reason"] == "unavailable"

    def test_a_retry_that_fixes_the_numbers_is_accepted(self):
        fake = FakeProvider(invented_reply, grounded_reply)

        async def body(db):
            w = await world(db)
            return await regenerate(w)

        with ai_on(fake):
            out = run(body)
        assert out["summary"] and len(fake.calls) == 2

    def test_five_regenerations_a_day_then_no(self):
        fake = FakeProvider(*([invented_reply] * 10))

        async def body(db):
            w = await world(db)
            codes = []
            for _ in range(6):
                try:
                    await regenerate(w)
                    codes.append(200)
                except HTTPException as err:
                    codes.append(err.detail["code"])
            return codes

        with ai_on(fake):
            codes = run(body)
        assert codes == ["summary_unavailable"] * 5 + ["regenerate_limit"]
        assert len(fake.calls) == 10, "the sixth press never reached the provider"

    def test_yesterdays_regenerations_do_not_count(self):
        fake = FakeProvider(grounded_reply)

        async def body(db):
            w = await world(db)
            await db.campaign_summaries.insert_one(
                {"campaign_id": w["campaign"]["_id"],
                 "regenerations": [NOW - timedelta(days=2)] * 5}
            )
            return await regenerate(w)

        with ai_on(fake):
            assert run(body)["summary"]

    def test_fewer_than_three_measured_posts_gets_no_summary(self):
        fake = FakeProvider()

        async def body(db):
            w = await world(db, readings=(60000, 45000, None, None))
            state = await get(w)
            with pytest.raises(HTTPException) as err:
                await regenerate(w)
            return state, err.value

        with ai_on(fake):
            state, err = run(body)
        assert state["eligible"] is False and state["reason"] == "too_few_measured"
        assert state["posts_measured"] == 2
        assert err.status_code == 409 and err.detail["code"] == "too_few_measured"
        assert fake.calls == []

    def test_another_brands_campaign_is_a_404(self):
        async def body(db):
            w = await world(db)
            stranger = {"_id": str(ObjectId()), "role": "brand_manager", "brand_id": str(ObjectId())}
            with pytest.raises(HTTPException) as err:
                await server.brand_campaign_summary(w["id"], stranger)
            return err.value.status_code

        with ai_on(FakeProvider()):
            assert run(body) == 404

    def test_no_forbidden_value_reaches_the_provider_end_to_end(self):
        fake = FakeProvider(grounded_reply)

        async def body(db):
            w = await world(db)
            await regenerate(w)

        with ai_on(fake):
            run(body)
        sent = fake.sent()
        for value in list(PLANTED.values()) + ["+919000000001", "owner@toit.example"]:
            assert str(value) not in sent, value
        for key in set(server.BRAND_FORBIDDEN_CREATOR_FIELDS) | set(server.PUBLIC_BRAND_FORBIDDEN_FIELDS):
            assert f'"{key}"' not in sent, key
        assert "handle0" not in sent, "only the display name travels, not the handle"
        assert '"name": "Aditi Rao"' in sent

    def test_the_summary_is_written_when_the_campaign_closes(self):
        fake = FakeProvider(grounded_reply)

        async def body(db):
            w = await world(db, status="in_progress")
            await server.close_brand_campaign(w["id"], server.DecisionPayload(reason="Done"), w["user"])
            await asyncio.gather(*list(server._SUMMARY_TASKS))
            return await db.campaign_summaries.find_one({"campaign_id": w["campaign"]["_id"]})

        with ai_on(fake):
            doc = run(body)
        assert doc and doc["summary"] and doc["trigger"] == "campaign_closed"
        assert not doc.get("regenerations"), "an automatic summary is not one of the five"

    def test_closing_with_ai_off_schedules_nothing(self):
        async def body(db):
            w = await world(db, status="in_progress")
            await server.close_brand_campaign(w["id"], server.DecisionPayload(reason="Done"), w["user"])
            return len(server._SUMMARY_TASKS), await db.campaign_summaries.count_documents({})

        assert run(body) == (0, 0)

    def test_closing_a_thin_campaign_writes_nothing(self):
        fake = FakeProvider()

        async def body(db):
            w = await world(db, readings=(60000, None, None), status="in_progress")
            await server.close_brand_campaign(w["id"], server.DecisionPayload(reason="Done"), w["user"])
            await asyncio.gather(*list(server._SUMMARY_TASKS))
            return await db.campaign_summaries.count_documents({})

        with ai_on(fake):
            assert run(body) == 0
        assert fake.calls == []

    def test_an_erased_creator_takes_the_summary_with_them(self):
        fake = FakeProvider(grounded_reply)

        async def body(db):
            w = await world(db)
            await regenerate(w)
            account = await db.users.find_one({"_id": w["creators"][0]})
            await server._erase_personal_data(account)
            return await db.campaign_summaries.count_documents({})

        with ai_on(fake):
            assert run(body) == 0

    def test_the_provider_call_is_logged_against_the_brand(self):
        fake = FakeProvider(grounded_reply)

        async def body(db):
            w = await world(db)
            await regenerate(w)
            return w, await db.ai_calls.find().to_list(None)

        with ai_on(fake):
            w, rows = run(body)
        (row,) = rows
        assert row["task"] == cs.TASK and row["prompt_version"] == cs.PROMPT.version
        assert row["account"] == ai.account_hash(str(w["brand"]))
        assert row["ok"] is True

    def test_regenerating_is_audited(self):
        fake = FakeProvider(grounded_reply)

        async def body(db):
            w = await world(db)
            await regenerate(w)
            return await db.audit_log.find({"action": "campaign.summary_regenerated"}).to_list(None)

        with ai_on(fake):
            (line,) = run(body)
        assert line["after"]["produced"] is True


def test_the_summary_module_writes_nothing():
    """Model output never changes state by itself: the engine is pure, and the
    only writes are the summary's own collection, in server.py."""
    import pathlib

    source = pathlib.Path(cs.__file__).read_text()
    assert "db." not in source and "await " not in source


# ---------------------------------------------------------------------------
# 6. The dashboard's derived values, and the one multiple the model may quote
# ---------------------------------------------------------------------------

DASHBOARD = {
    "by_format": [
        {"format": "reel", "posts": 7, "views": 420000},
        {"format": "carousel", "posts": 4, "views": 100000},
    ],
    "versus_last_campaign": {"title": "Diwali menu", "views": 400000, "change_percent": 30.0},
}


def dashboard_input():
    analytics = {
        "campaign": {"title": "Brunch"},
        "totals": {"total_reach": 300000, "total_views": 520000, "total_shares": 2100,
                   "engagement_rate": 4.0},
        "creators": [
            {"creator_id": "a", "name": "Aditi Rao", "views": 312000, "reach": 180000,
             "shares": 1500, "measured": True},
            {"creator_id": "b", "name": "Kiran M", "views": 208000, "reach": 120000,
             "shares": 600, "measured": True},
        ],
    }
    return cs.build_summary_input(analytics, None, {}, dashboard=DASHBOARD)


class TestDashboardDerived:
    def test_each_creators_share_of_views_and_shares_per_thousand(self):
        d = dashboard_input()["derived"]
        aditi, kiran = d["by_creator_views"]
        assert aditi["share_of_views_percent"] == 60.0 and kiran["share_of_views_percent"] == 40.0
        assert aditi["shares_per_thousand_views"] == round(1500 / 312000 * 1000, 1)

    def test_average_views_per_post_by_format_and_the_ratio(self):
        d = dashboard_input()["derived"]
        reel, carousel = d["by_post_format"]
        assert reel["average_views_per_post"] == 60000 and carousel["average_views_per_post"] == 25000
        (ratio,) = d["format_ratios"]
        assert ratio == {"formats": "reel to carousel", "average_views_ratio": 2.4}

    def test_the_delta_against_the_last_campaign(self):
        assert dashboard_input()["derived"]["vs_last_campaign"] == {
            "views_last_campaign": 400000, "views_change_percent": 30.0,
        }

    def test_a_computed_ratio_may_be_quoted_as_a_multiple(self):
        data = dashboard_input()
        s = summary("Reels drew 60,000 views a post", [
            point("Reels averaged 2.4x the views of a carousel.", "derived.format_ratios[0].average_views_ratio"),
            point("Reels averaged 2.4 times a carousel's views.", "derived.format_ratios[0].average_views_ratio"),
        ])
        assert cs.ground(s, data) == []

    def test_a_multiple_that_is_not_the_ratio_is_still_refused(self):
        data = dashboard_input()
        s = summary("Reels drew 60,000 views a post", [point("Reels did 3x better.", "totals.views")])
        assert any('"3x"' in p for p in cs.ground(s, data))

    def test_a_ratio_does_not_vouch_for_a_plain_count_it_shares_digits_with(self):
        """2.4 as a multiple; "2.4%" is a different claim and is not in the data."""
        data = dashboard_input()
        s = summary("Reels drew 60,000 views a post", [point("Shares rose 2.4%.", "totals.views")])
        assert cs.ground(s, data)

    def test_with_no_ratio_field_every_multiple_is_refused(self):
        data = sample_input()
        assert "format_ratios" not in data["derived"]
        s = summary(GOOD_HEADLINE, [point("Aditi did 2.4x.", "totals.reach")])
        assert cs.ground(s, data)
