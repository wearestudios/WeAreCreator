"""Was this campaign worth it, and is the business healthy.

Two audiences, two questions, and they are not the same question wearing
different clothes. A brand asks whether to run another one, which is answered
by comparing this campaign to *their own* previous ones — an industry
benchmark they cannot verify is a number they ignore. The business asks
whether the marketplace works, which is answered by four ratios with
denominators somebody would argue about.

**The arithmetic is pure and tested without a database.** `_repeat_rate`,
`_fill_outcome`, `_fill_rate`, `_campaign_margin`, `_first_payment_rate` and
`_supply_and_demand` take counts and return numbers — the same arrangement
`_refund_reckoning` and `_weare_run_reason` use, and for the same reason: a
rule that can be read in one screen and checked without fixtures is a rule
people trust enough to act on. The aggregations that feed them are driven
separately, against a real mock database, and read back.

**The PII half is a leak test, not a key check.** It plants a phone number, an
email, an address, a map pin, a UPI id, an account number, an IFSC and a PAN
on the profile, then searches the bytes of every brand-facing analytics
payload and CSV — the arrangement `test_exports.py` uses. Reading the source
for a key name catches the mistake somebody makes on purpose; running it
catches the one where a field arrives through a `**spread` from a document
nobody remembered had one.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException, params
from mongomock_motor import AsyncMongoMockClient

import server

FRONTEND = Path(__file__).resolve().parents[3] / "frontend" / "src"

LOOP = None


def _loop():
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()
    return LOOP


def run(body):
    async def go():
        db = AsyncMongoMockClient()["analytics"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return _loop().run_until_complete(go())


def guard_allows(fn, role):
    for p in inspect.signature(fn).parameters.values():
        dep = p.default
        if isinstance(dep, params.Depends) and dep.dependency is not None:
            if getattr(dep.dependency, "__name__", "") == "_guard":
                guard = dep.dependency
                break
    else:
        raise AssertionError(f"{fn.__name__} declares no require_roles guard")

    async def go():
        try:
            await guard({"_id": str(ObjectId()), "role": role})
            return True
        except HTTPException as err:
            assert err.status_code == 403
            return False

    return _loop().run_until_complete(go())


NOW = datetime.now(timezone.utc)


def ago(days):
    return NOW - timedelta(days=days)


# ---------------------------------------------------------------------------
# 1. Brand repeat rate — the most important number here
# ---------------------------------------------------------------------------


class TestRepeatRate:
    def test_a_brand_that_posted_again_inside_the_window_counts(self):
        rate = server._repeat_rate([(ago(200), ago(160), True)])
        assert rate["repeated"] == 1 and rate["rate"] == 100.0

    def test_a_brand_that_never_came_back_counts_against_it(self):
        rate = server._repeat_rate([(ago(200), None, True)])
        assert rate["repeated"] == 0 and rate["rate"] == 0.0

    def test_a_brand_whose_window_has_not_closed_is_not_in_the_denominator(self):
        """**The classic way this metric lies.** A brand that posted its first
        brief last Tuesday cannot have repeated yet, and counting it as a
        failure means a good month of acquisition *lowers* the repeat rate —
        the number moves the wrong way in response to the thing going right.
        """
        cohort = [
            (ago(200), ago(150), True),   # came back
            (ago(200), None, True),       # did not
            (ago(10), None, False),       # too soon to say
            (ago(3), None, False),        # too soon to say
        ]
        rate = server._repeat_rate(cohort)

        assert rate["eligible"] == 2, "only the closed windows are judged"
        assert rate["rate"] == 50.0
        # And the same cohort scored naively would report half that.
        naive = len([c for c in cohort if c[1]]) / len(cohort) * 100
        assert naive == 25.0

    def test_the_denominator_travels_with_the_rate(self):
        """50% over four brands is not the same fact as 50% over four hundred,
        and a headline without its denominator is a headline somebody quotes
        in a deck."""
        rate = server._repeat_rate([(ago(200), ago(150), True), (ago(200), None, True)])
        assert rate["eligible"] == 2 and rate["repeated"] == 1

    def test_nobody_eligible_reads_as_unknown_rather_than_zero(self):
        """"0% came back" and "nobody has had the chance yet" are different
        facts, and only one of them is bad news."""
        assert server._repeat_rate([])["rate"] is None
        assert server._repeat_rate([(ago(5), None, False)])["rate"] is None

    def test_a_brand_that_came_back_too_late_is_not_a_repeat(self):
        """They did come back, and not in a way this window can claim. The
        constant is what the window means, and it travels with the answer."""
        rate = server._repeat_rate([(ago(300), None, True)])
        assert rate["rate"] == 0.0
        assert rate["window_days"] == server.REPEAT_WINDOW_DAYS == 90

    def test_it_is_computed_end_to_end_and_trended_by_arrival_cohort(self):
        """Driven rather than asserted: two brands, one of which came back.

        Trended by the month the brand *first* posted, which is the only
        honest axis — a cohort's repeat rate is a fact about when they
        arrived, and plotting it by calendar month would move every past
        point every time somebody came back.
        """

        async def body(db):
            came_back, never = ObjectId(), ObjectId()
            # Both first posted 150 days ago: inside the 180-day trend window,
            # and far enough back that their 90-day repeat window has closed.
            await db.campaigns.insert_many(
                [
                    {"_id": ObjectId(), "brand_id": came_back, "created_at": ago(150),
                     "status": "closed", "creators_needed": 2},
                    {"_id": ObjectId(), "brand_id": came_back, "created_at": ago(100),
                     "status": "closed", "creators_needed": 2},
                    {"_id": ObjectId(), "brand_id": never, "created_at": ago(150),
                     "status": "closed", "creators_needed": 2},
                ]
            )
            return await server._compute_admin_analytics()

        data = run(body)
        assert data["repeat_rate"]["eligible"] == 2
        assert data["repeat_rate"]["repeated"] == 1
        assert data["repeat_rate"]["rate"] == 50.0
        assert data["repeat_rate_trend"], "the trend is not computed"


# ---------------------------------------------------------------------------
# 2. Fill rate
# ---------------------------------------------------------------------------


class TestFillRate:
    def test_late_is_its_own_outcome_and_not_a_kind_of_underfill(self):
        """A brief that got its six creators a fortnight after the shoot is a
        different operational story from one that only ever found four, and
        rolling them together hides which of the two is happening."""
        assert server._fill_outcome(6, 6, True) == "filled"
        assert server._fill_outcome(6, 6, False) == "late"
        assert server._fill_outcome(6, 4, True) == "underfilled"

    def test_a_brief_with_no_headcount_is_not_scored(self):
        """It cannot have missed a target it never set, and scoring it as a
        failure would punish a brief for a field it was not asked to fill."""
        assert server._fill_outcome(None, 3, True) is None
        assert server._fill_outcome(0, 0, True) is None

    def test_overfilling_still_counts_as_filled(self):
        assert server._fill_outcome(3, 4, True) == "filled"

    def test_the_rate_is_filled_over_everything_judged(self):
        rate = server._fill_rate(["filled", "filled", "late", "underfilled", None])
        assert rate["campaigns"] == 4
        assert rate["filled"] == 2 and rate["late"] == 1 and rate["underfilled"] == 1
        assert rate["rate"] == 50.0

    def test_it_breaks_down_by_category_and_city(self):
        """The breakdown is what makes it actionable: a platform-wide 70% is a
        number to worry about, and "40% in beauty, in Pune" is a number to do
        something about."""

        async def body(db):
            brand = ObjectId()
            full, short = ObjectId(), ObjectId()
            await db.campaigns.insert_many(
                [
                    {"_id": full, "brand_id": brand, "created_at": ago(40),
                     "status": "closed", "creators_needed": 1,
                     "category": "fnb", "city": "Bengaluru", "start_date": ago(30)},
                    {"_id": short, "brand_id": brand, "created_at": ago(40),
                     "status": "closed", "creators_needed": 4,
                     "category": "beauty", "city": "Mumbai", "start_date": ago(30)},
                ]
            )
            await db.collaborations.insert_one(
                {"_id": ObjectId(), "campaign_id": full, "creator_id": ObjectId(),
                 "state": "closed"}
            )
            return await server._compute_admin_analytics()

        fill = run(body)["fill_rate"]
        by_cat = {r["key"]: r for r in fill["by_category"]}
        by_city = {r["key"]: r for r in fill["by_city"]}
        assert by_cat["fnb"]["filled"] == 1
        assert by_cat["beauty"]["underfilled"] == 1
        assert by_city["Mumbai"]["rate"] == 0.0


# ---------------------------------------------------------------------------
# 3. Margin per campaign
# ---------------------------------------------------------------------------


class TestMargin:
    def test_revenue_is_the_fee_plus_the_commission_and_nothing_else(self):
        """**The creator's own fee is neither side of this.** It passes
        through — the brand pays it, the creator receives it, and the whole
        arrangement this platform sells on is that we take no cut of it. On
        either side it would report a margin the business does not earn."""
        m = server._campaign_margin(40000, 18000, 12000)
        assert m["revenue"] == 58000
        assert m["margin"] == 46000

    def test_an_unrecorded_cost_makes_it_revenue_rather_than_margin(self):
        """A margin computed with no recorded cost is a gross figure wearing a
        net figure's name. `complete` is what stops a table mixing the two."""
        m = server._campaign_margin(40000, 18000, None)
        assert m["complete"] is False
        assert m["delivery_cost"] is None
        assert m["margin_percent"] is None
        # The number is still there and still right — it is just revenue.
        assert m["margin"] == m["revenue"] == 58000

    def test_zero_cost_is_a_claim_and_absent_is_not(self):
        """Somebody typing 0 has said it cost nothing to run. Nobody typing
        anything has said nothing at all."""
        assert server._campaign_margin(10000, 0, 0)["complete"] is True
        assert server._campaign_margin(10000, 0, None)["complete"] is False

    def test_the_average_skips_briefs_whose_cost_nobody_recorded(self):
        """Averaging a gross figure in with net ones overstates the business by
        exactly the amount nobody has measured."""

        async def body(db):
            brand = ObjectId()
            measured, unmeasured = ObjectId(), ObjectId()
            await db.campaigns.insert_many(
                [
                    {"_id": measured, "brand_id": brand, "created_at": ago(40),
                     "status": "closed", "creators_needed": 1, "campaign_type": "launch",
                     "campaign_fee": 50000, "delivery_cost": 20000},
                    {"_id": unmeasured, "brand_id": brand, "created_at": ago(40),
                     "status": "closed", "creators_needed": 1, "campaign_type": "launch",
                     "campaign_fee": 50000},
                ]
            )
            return await server._compute_admin_analytics()

        margin = run(body)["margin"]
        assert margin["campaigns"] == 2
        assert margin["with_recorded_cost"] == 1
        assert margin["average_margin"] == 30000.0, "the unmeasured brief is excluded"
        assert margin["revenue"] == 100000.0, "revenue still counts both"

    def test_the_cost_is_recorded_rather_than_inferred(self):
        """Nothing in this system knows what a manager's evening at a venue
        cost. A formula that guessed would put a guess in a board pack, so
        there is a route that records it and no arithmetic that invents it."""
        src = inspect.getsource(server.set_campaign_delivery_cost)
        assert "delivery_cost" in src and "audit(" in src
        # Old value and new, like the commission change: "set to 40,000"
        # cannot say whether that was a correction or a first estimate.
        assert 'before={"delivery_cost": before}' in src
        assert guard_allows(server.set_campaign_delivery_cost, "creator") is False
        assert guard_allows(server.set_campaign_delivery_cost, "weare_team") is True


# ---------------------------------------------------------------------------
# 4. Creator first-payment rate
# ---------------------------------------------------------------------------


class TestFirstPayment:
    def test_it_counts_creators_who_ever_got_paid(self):
        rate = server._first_payment_rate(
            [(ago(100), ago(80)), (ago(100), None), (ago(100), ago(60)), (ago(100), None)]
        )
        assert rate["verified"] == 4 and rate["paid"] == 2 and rate["rate"] == 50.0

    def test_the_median_not_the_mean(self):
        """One creator who took eleven months because they went travelling
        should not move the headline — and with the numbers a young
        marketplace has, the mean is mostly that one person."""
        rate = server._first_payment_rate(
            [
                (ago(400), ago(390)),   # 10 days
                (ago(400), ago(388)),   # 12 days
                (ago(400), ago(386)),   # 14 days
                (ago(400), ago(70)),    # 330 days
            ]
        )
        assert rate["median_days_to_first_payment"] == 13.0
        mean = (10 + 12 + 14 + 330) / 4
        assert mean > 90, "the mean would report a wildly different operation"

    def test_the_spread_travels_with_it(self):
        """"Median 12 days" over a range of 2-160 is a different operation
        from the same median over 9-15."""
        rate = server._first_payment_rate([(ago(100), ago(98)), (ago(100), ago(40))])
        assert rate["fastest_days"] == 2 and rate["slowest_days"] == 60

    def test_an_unverified_creator_is_not_in_the_denominator(self):
        assert server._first_payment_rate([(None, None)])["verified"] == 0
        assert server._first_payment_rate([(None, None)])["rate"] is None


# ---------------------------------------------------------------------------
# Supply against demand
# ---------------------------------------------------------------------------


class TestSupplyAndDemand:
    def test_it_names_where_we_have_creators_and_no_briefs(self):
        """**Sell into these.** A table of counts is something somebody reads
        and nods at; a list is something a salesperson works."""
        out = server._supply_and_demand(
            {("beauty", "Mumbai"): 14, ("fnb", "Bengaluru"): 30},
            {("fnb", "Bengaluru"): 6},
        )
        assert [r["category"] for r in out["sell_into"]] == ["beauty"]
        assert out["sell_into"][0]["creators"] == 14

    def test_it_orders_the_sell_into_list_by_how_much_supply_is_idle(self):
        out = server._supply_and_demand(
            {("beauty", "Mumbai"): 4, ("tech", "Pune"): 21}, {}
        )
        assert [r["category"] for r in out["sell_into"]] == ["tech", "beauty"]

    def test_creators_per_campaign_is_absent_rather_than_infinite(self):
        """No briefs is not a ratio — it is the sell-into case, which has its
        own list."""
        out = server._supply_and_demand({("beauty", "Mumbai"): 9}, {})
        assert out["rows"][0]["creators_per_campaign"] is None

    def test_recruit_for_comes_from_the_fill_outcome_rather_than_a_second_rule(self):
        """"Could not fill" has one definition in this file, and it is
        `_fill_outcome`. A second judgement here would be a second answer."""
        assert server._supply_and_demand({}, {})["recruit_for"] == []
        src = inspect.getsource(server._compute_admin_analytics)
        assert 'supply["recruit_for"]' in src
        assert "_fill_outcome(" in src

    def test_it_surfaces_both_lists_end_to_end(self):
        async def body(db):
            brand = ObjectId()
            await db.creator_profiles.insert_many(
                [
                    {"user_id": ObjectId(), "verification_status": "verified",
                     "city": "Mumbai", "niches": ["skincare"], "verified_at": ago(100)},
                    {"user_id": ObjectId(), "verification_status": "verified",
                     "city": "Bengaluru", "niches": ["cafe"], "verified_at": ago(100)},
                ]
            )
            await db.campaigns.insert_one(
                {"_id": ObjectId(), "brand_id": brand, "created_at": ago(40),
                 "status": "closed", "creators_needed": 5,
                 "category": "fnb", "city": "Bengaluru", "start_date": ago(30)}
            )
            return await server._compute_admin_analytics()

        supply = run(body)["supply_and_demand"]
        # Beauty supply in Mumbai with nothing briefed against it.
        assert any(r["city"] == "Mumbai" for r in supply["sell_into"])
        # And a brief in Bengaluru we could not fill.
        assert any(r["city"] == "Bengaluru" for r in supply["recruit_for"])

    def test_a_creators_words_reach_a_category_through_the_one_bridge(self):
        """Nobody writes "fnb" about themselves. `CAMPAIGN_CATEGORY_SYNONYMS`
        is the table that knows both vocabularies, and a second mapping here
        would put a creator in a different category on this screen from the
        one the suggestions panel puts them in."""
        assert "fnb" in server._creator_categories({"niches": ["cafe"]})
        assert server._creator_categories({"niches": []}) == []
        assert "CAMPAIGN_CATEGORY_SYNONYMS" in inspect.getsource(server._creator_categories)


# ---------------------------------------------------------------------------
# The brand's own numbers
# ---------------------------------------------------------------------------


async def _brand_world(db, *, reach=50000, spend=20000.0, second_campaign=False):
    """A brand, a creator who delivered, and a paid payment."""
    brand, creator = ObjectId(), ObjectId()
    await db.users.insert_many(
        [
            {"_id": brand, "role": "brand_manager", "name": "Toit", "brand_id": brand},
            {"_id": creator, "role": "creator", "name": "Aditi Rao"},
        ]
    )
    await db.brand_profiles.insert_one(
        {"user_id": brand, "business_name": "Toit", "verified": True}
    )
    # **Every value here is planted to be searched for.** See the leak test.
    await db.creator_profiles.insert_one(
        {
            "user_id": creator, "name": "Aditi Rao",
            "verification_status": "verified",
            "instagram_handle": "aditi.shoots", "follower_count": 24800,
            "phone": "+919812345678",
            "email": "aditi.private@example.com",
            "full_address": "42 Secret Lane, Indiranagar",
            "location_lat": 12.9716, "location_lng": 77.5946,
            "payout_upi": "aditi@okhdfc",
            "payout_account_number": "918273645500",
            "payout_ifsc": "HDFC0001234",
            "pan": "ABCDE1234F",
        }
    )

    def _campaign(when, fee=20000):
        cid = ObjectId()
        return cid, {
            "_id": cid, "brand_id": brand, "title": "Tasting", "status": "closed",
            "created_at": when, "creators_needed": 1, "category": "fnb",
            "city": "Bengaluru", "campaign_type": "personal_table",
            "compensation_type": "fixed", "budget_per_creator": fee,
            "total_budget": 60000.0,
            "deliverable_items": [{"type": "reel", "quantity": 1},
                                  {"type": "story", "quantity": 2}],
            "start_date": when, "end_date": when,
        }

    cid, doc = _campaign(ago(30))
    await db.campaigns.insert_one(doc)
    collab = ObjectId()
    await db.collaborations.insert_one(
        {"_id": collab, "campaign_id": cid, "creator_id": creator, "state": "closed",
         "agreed_amount": spend, "agreed_at": ago(28),
         "delivered_items": {"reel": 1, "story": 2}}
    )
    await db.payments.insert_one(
        {"_id": ObjectId(), "collaboration_id": collab, "state": "paid",
         "creator_payout": spend, "platform_fee": 3000.0, "paid_at": ago(20)}
    )
    await db.content_performance.insert_one(
        {"_id": ObjectId(), "collaboration_id": collab, "campaign_id": cid,
         "reach": reach, "impressions": reach * 2, "likes": 2000, "comments": 120,
         "captured_at": ago(18)}
    )

    if second_campaign:
        cid2, doc2 = _campaign(ago(120))
        await db.campaigns.insert_one(doc2)
        collab2 = ObjectId()
        await db.collaborations.insert_one(
            {"_id": collab2, "campaign_id": cid2, "creator_id": creator,
             "state": "closed", "agreed_amount": 20000.0, "agreed_at": ago(118)}
        )
        await db.payments.insert_one(
            {"_id": ObjectId(), "collaboration_id": collab2, "state": "paid",
             "creator_payout": 20000.0, "platform_fee": 3000.0, "paid_at": ago(110)}
        )
        await db.content_performance.insert_one(
            {"_id": ObjectId(), "collaboration_id": collab2, "campaign_id": cid2,
             "reach": 10000, "likes": 300, "comments": 20, "captured_at": ago(108)}
        )

    user = {"_id": str(brand), "role": "brand_manager", "name": "Toit"}
    return {"user": user, "brand": brand, "campaign": str(cid), "creator": creator}


class TestBrandCampaignAnalytics:
    def test_it_answers_reach_cost_and_cost_per_thousand(self):
        async def body(db):
            w = await _brand_world(db, reach=50000, spend=20000.0)
            return await server.brand_campaign_analytics(w["campaign"], w["user"])

        out = run(body)
        assert out["totals"]["total_reach"] == 50000
        assert out["totals"]["total_spend"] == 20000.0
        # ₹20,000 over 50,000 people reached.
        assert out["totals"]["cost_per_thousand_reach"] == 400.0

    def test_the_per_creator_table_says_who_performed(self):
        async def body(db):
            w = await _brand_world(db)
            return await server.brand_campaign_analytics(w["campaign"], w["user"])

        rows = run(body)["creators"]
        assert len(rows) == 1
        row = rows[0]
        assert row["name"] == "Aditi Rao"
        assert row["reach"] == 50000
        assert row["cost"] == 20000.0
        assert row["cost_per_thousand_reach"] == 400.0
        assert row["engagement_rate"] is not None

    def test_an_unmeasured_creator_has_no_cost_per_thousand_rather_than_zero(self):
        """A collaboration nobody measured did not reach zero people. Every
        surface draws unknown as an em dash and this is what lets it."""
        row = server._analytics_creator_row({"name": "X"}, None, 5000)
        assert row["reach"] is None
        assert row["cost_per_thousand_reach"] is None
        assert row["measured"] is False

    def test_promised_against_delivered_is_counted_per_creator_taken_on(self):
        """A brief that asked for six people and filled four promised four
        people's worth of content. Holding it to six would report a shortfall
        against creators who were never booked — that is an underfill, and it
        already has its own number."""
        async def body(db):
            w = await _brand_world(db)
            return await server.brand_campaign_analytics(w["campaign"], w["user"])

        d = run(body)["deliverables"]
        assert d["counted"] is True
        assert d["creators_taken"] == 1
        assert d["promised"] == 3, "one reel and two stories, for one creator"
        assert d["delivered"] == 3

    def test_a_brief_with_no_structured_ask_is_not_counted(self):
        """The same line `_delivery_shortfall` draws: a campaign nobody
        counted has no shortfall, and reporting one would be a claim about
        work that was never measured."""
        out = server._promised_versus_delivered({"deliverables": "a few stories"}, [])
        assert out["counted"] is False
        assert out["promised"] is None

    def test_spend_committed_against_budget_remaining(self):
        async def body(db):
            w = await _brand_world(db, spend=20000.0)
            return await server.brand_campaign_analytics(w["campaign"], w["user"])

        budget = run(body)["budget"]
        assert budget["total"] == 60000.0
        assert budget["committed"] == 20000.0
        assert budget["remaining"] == 40000.0

    def test_another_brands_campaign_is_a_404(self):
        """Ownership before anything else, as everywhere — a 403 would say
        which ids exist."""

        async def body(db):
            w = await _brand_world(db)
            stranger = {"_id": str(ObjectId()), "role": "brand_manager", "name": "Other"}
            with pytest.raises(HTTPException) as exc:
                await server.brand_campaign_analytics(w["campaign"], stranger)
            return exc.value

        assert run(body).status_code == 404


class TestAgainstTheirOwnHistory:
    def test_the_comparison_is_absent_on_a_first_campaign(self):
        """Said rather than shown as 0%. "No change" is a claim about a
        comparison that does not exist."""

        async def body(db):
            w = await _brand_world(db)
            return await server.brand_campaign_analytics(w["campaign"], w["user"])

        assert run(body)["versus_their_own_history"] is None

    def test_a_second_campaign_is_measured_against_the_first(self):
        """**The comparison that makes a third campaign feel obvious.** A
        brand cannot check an industry benchmark; it can check its own last
        brief, and that is the number it will act on."""

        async def body(db):
            w = await _brand_world(db, reach=50000, second_campaign=True)
            return await server.brand_campaign_analytics(w["campaign"], w["user"])

        cmp = run(body)["versus_their_own_history"]
        assert cmp is not None
        assert cmp["campaigns_before"] == 1
        assert cmp["reach"]["previous"] == 10000
        assert cmp["reach"]["value"] == 50000
        assert cmp["reach"]["better"] is True

    def test_a_falling_cost_per_thousand_is_the_good_direction(self):
        """A chart that coloured every fall red would tell a brand its best
        campaign went badly. Said once, here, rather than at three call
        sites."""
        cmp = server._against_their_own_history(
            {"totals": {"total_reach": 100, "engagement_rate": 2.0,
                        "cost_per_thousand_reach": 200.0}},
            [{"totals": {"total_reach": 100, "total_spend": 100.0, "paid_reach": 250,
                         "total_engagements": 2, "engagement_rate": 2.0,
                         "cost_per_thousand_reach": 400.0, "creators_delivered": 1}}],
        )
        assert cmp["cost_per_thousand_reach"]["change_percent"] == -50.0
        assert cmp["cost_per_thousand_reach"]["better"] is True

    def test_the_rollup_divides_totals_rather_than_averaging_rates(self):
        """Those two differ whenever the campaigns differ in size, and the
        mean of the rates lets one small brief with a freak number move the
        headline — the same arithmetic, and the same reason, as
        `_rollup_performance`'s engagement rate."""
        rollup = server._brand_rollup(
            [
                {"totals": {"total_spend": 1000.0, "total_reach": 100000,
                            "paid_reach": 100000, "total_engagements": 1000,
                            "creators_delivered": 1}},
                {"totals": {"total_spend": 1000.0, "total_reach": 1000,
                            "paid_reach": 1000, "total_engagements": 500,
                            "creators_delivered": 1}},
            ]
        )
        # Aggregate: 1,500 engagements over 101,000 reach.
        assert rollup["engagement_rate"] == 1.49
        # The mean of the two rates would be 26.0 — off by a factor of 17.
        assert round((1.0 + 50.0) / 2, 2) == 25.5


class TestBrandRollup:
    def test_it_totals_every_campaign_the_brand_has_run(self):
        async def body(db):
            w = await _brand_world(db, second_campaign=True)
            return await server.brand_analytics(w["user"])

        out = run(body)
        assert out["rollup"]["campaigns"] == 2
        assert out["rollup"]["total_spend"] == 40000.0
        assert out["rollup"]["total_reach"] == 60000
        assert out["latest_versus_history"] is not None

    def test_a_brand_with_nothing_run_gets_an_empty_rollup_not_an_error(self):
        async def body(db):
            brand = ObjectId()
            await db.users.insert_one(
                {"_id": brand, "role": "brand_manager", "name": "New", "brand_id": brand}
            )
            await db.brand_profiles.insert_one({"user_id": brand, "business_name": "New"})
            return await server.brand_analytics(
                {"_id": str(brand), "role": "brand_manager", "name": "New"}
            )

        out = run(body)
        assert out["rollup"]["campaigns"] == 0
        assert out["latest_versus_history"] is None


# ---------------------------------------------------------------------------
# The rule that matters most: no creator PII, anywhere brand-facing
# ---------------------------------------------------------------------------


# Planted on the profile in `_brand_world`, then searched for in the bytes.
LEAKS = {
    "phone": "+919812345678",
    "email": "aditi.private@example.com",
    "address": "42 Secret Lane",
    "map pin latitude": "12.9716",
    "map pin longitude": "77.5946",
    "UPI id": "aditi@okhdfc",
    "account number": "918273645500",
    "IFSC": "HDFC0001234",
    "PAN": "ABCDE1234F",
}


def _search(blob: str):
    return sorted(label for label, value in LEAKS.items() if value in blob)


class TestNoCreatorPiiInAnalytics:
    def test_the_per_campaign_payload_carries_none_of_it(self):
        """**Run, not read.** Searching the real output catches the case where
        a field arrives through a `**spread` from a document nobody remembered
        had one — which reading the source for a key name would miss."""

        async def body(db):
            w = await _brand_world(db)
            return await server.brand_campaign_analytics(w["campaign"], w["user"])

        found = _search(json.dumps(run(body), default=str))
        assert not found, f"creator PII in the campaign analytics payload: {found}"

    def test_the_brand_rollup_carries_none_of_it(self):
        async def body(db):
            w = await _brand_world(db, second_campaign=True)
            return await server.brand_analytics(w["user"])

        found = _search(json.dumps(run(body), default=str))
        assert not found, f"creator PII in the brand analytics payload: {found}"

    def test_the_per_campaign_csv_carries_none_of_it(self):
        async def body(db):
            w = await _brand_world(db)
            return await server.export_brand_analytics(w["user"], campaign_id=w["campaign"])

        response = run(body)
        found = _search(response.body.decode())
        assert not found, f"creator PII in the analytics CSV: {found}"
        # And it really did produce the rows, or the check above is vacuous.
        assert "Aditi Rao" in response.body.decode()

    def test_the_rollup_csv_carries_none_of_it(self):
        async def body(db):
            w = await _brand_world(db, second_campaign=True)
            return await server.export_brand_analytics(w["user"])

        found = _search(run(body).body.decode())
        assert not found, f"creator PII in the rollup CSV: {found}"

    def test_the_leak_test_can_actually_fail(self):
        """A test that cannot fail is worse than no test. If the projection
        were bypassed, this is the shape the output would take."""
        assert _search('{"name": "Aditi Rao", "phone": "+919812345678"}') == ["phone"]
        assert _search('{"name": "Aditi Rao"}') == []

    def test_the_row_is_built_off_the_projection_rather_than_the_profile(self):
        """**The safety property is structural.** A phone number cannot appear
        because there is no phone number in the input, and a field added to
        `creator_profiles` next month cannot leak because this cannot see
        it."""
        src = inspect.getsource(server._campaign_analytics)
        assert "_brand_visible_creator(" in src
        # And the row builder takes the projected creator, never a profile.
        assert "visible" in inspect.signature(server._analytics_creator_row).parameters

    def test_the_row_names_every_key_rather_than_spreading_the_input(self):
        """**Two defences, and this is the one the leak test cannot see.**

        Break-testing found that pointing `_campaign_analytics` at the raw
        profile still leaks nothing, because the row builder picks keys by
        name — so the leak test above passed with the projection removed. That
        is a good property and a bad test, so this pins the second defence
        directly: a `**visible` here would make the projection the only thing
        standing between a phone number and a chart, and the leak test would
        then be the only alarm.
        """
        src = inspect.getsource(server._analytics_creator_row)
        assert "**visible" not in src and "**performance" not in src
        # Every key it emits, written out. Adding one is a decision somebody
        # makes on purpose rather than a field arriving on its own.
        emitted = {
            line.split('"')[1]
            for line in src.splitlines()
            if line.strip().startswith('"') and ":" in line
        }
        forbidden = {
            "phone", "whatsapp", "email", "full_address", "address",
            "location_lat", "location_lng", "location_place_id",
            "payout_upi", "payout_account_number", "payout_account_name",
            "payout_ifsc", "pan", "gstin",
        }
        assert not emitted & forbidden, f"the row emits {sorted(emitted & forbidden)}"

    def test_the_forbidden_list_is_the_one_the_rest_of_the_product_uses(self):
        """Not a list typed here. `BRAND_FORBIDDEN_CREATOR_FIELDS` is what the
        applicant board, the exports and the campaign report are all held to,
        and a second list would drift from it the first time one was
        extended."""
        for field in ("phone", "full_address", "location_lat", "pan"):
            assert field in server.BRAND_FORBIDDEN_CREATOR_FIELDS, field

    def test_no_forbidden_field_reaches_the_payload_by_any_route(self):
        """The whole projection, checked by key as well as by value — because
        a field could be present and empty on this fixture and still be a leak
        on somebody's real record."""

        async def body(db):
            w = await _brand_world(db)
            return await server.brand_campaign_analytics(w["campaign"], w["user"])

        blob = json.dumps(run(body), default=str)
        present = sorted(
            f for f in server.BRAND_FORBIDDEN_CREATOR_FIELDS if f'"{f}"' in blob
        )
        assert not present, f"forbidden keys in the analytics payload: {present}"

    def test_the_shortlist_gate_applies_here_too(self):
        """A brand that never saw an application does not meet the creator
        through a chart. `_brand_sees_collab` is the same reader the applicant
        board uses."""
        assert "_brand_sees_collab(" in inspect.getsource(server._campaign_analytics)


# ---------------------------------------------------------------------------
# Caching, and who may read the platform's own numbers
# ---------------------------------------------------------------------------


class TestCachingAndAccess:
    def test_the_platform_metrics_are_admin_only(self):
        """The same split every platform-wide instrument makes. A repeat rate
        across every brand is a fact about the business, not about the brands
        a scoped team member works on — answering it for them would be the
        scope leaking through a chart."""
        for fn in (server.admin_analytics, server.export_admin_analytics):
            assert guard_allows(fn, "admin") is True
            assert guard_allows(fn, "weare_team") is False
            assert guard_allows(fn, "brand_manager") is False

    def test_a_second_read_comes_from_the_cache(self):
        """The honest version of this scans most of the database. Recomputing
        it per request is how an analytics page becomes the slowest screen in
        the product and then stops being opened."""

        async def body(db):
            admin = {"_id": str(ObjectId()), "role": "admin", "name": "A"}
            first = await server.admin_analytics(admin)
            second = await server.admin_analytics(admin)
            stored = await db.analytics_cache.find_one({"_id": server.ANALYTICS_CACHE_ID})
            return first, second, stored

        first, second, stored = run(body)
        assert first["cached"] is False
        assert second["cached"] is True
        assert stored is not None, "nothing was written to analytics_cache"

    def test_it_lives_in_its_own_collection(self):
        """Not a row in `platform_settings`, which holds what an operator
        typed and is one bad `_id` away from being overwritten by a job — the
        same separation `leaderboard_cache` makes."""
        src = inspect.getsource(server.refresh_admin_analytics)
        assert "analytics_cache" in src
        assert "platform_settings" not in src

    def test_a_forced_refresh_recomputes(self):
        async def body(db):
            admin = {"_id": str(ObjectId()), "role": "admin", "name": "A"}
            await server.admin_analytics(admin)
            return await server.admin_analytics(admin, refresh=True)

        assert run(body)["cached"] is False

    def test_the_age_travels_with_it(self):
        """A dashboard that looks live and is an hour old is worse than one
        that says so."""

        async def body(db):
            admin = {"_id": str(ObjectId()), "role": "admin", "name": "A"}
            await server.admin_analytics(admin)
            return await server.admin_analytics(admin)

        assert "age_seconds" in run(body)

    def test_the_job_and_the_loop_call_the_same_function(self):
        """A number somebody forced and a number the schedule produced must
        not be able to differ."""
        assert "refresh_admin_analytics()" in inspect.getsource(server.run_analytics_refresh)
        assert "refresh_admin_analytics()" in inspect.getsource(server._analytics_loop)

    def test_the_loop_is_started_and_can_be_turned_off(self):
        src = inspect.getsource(server._startup)
        assert "_analytics_loop()" in src
        assert "_analytics_interval_seconds() > 0" in src

    @pytest.mark.parametrize("kind", ["supply", "fill", "margin", "repeat"])
    def test_every_export_kind_produces_a_csv(self, kind):
        async def body(db):
            admin = {"_id": str(ObjectId()), "role": "admin", "name": "A"}
            return await server.export_admin_analytics(kind, admin)

        response = run(body)
        assert response.headers["content-type"].startswith("text/csv")
        assert response.headers["cache-control"] == "no-store"

    def test_an_unknown_export_kind_is_refused(self):
        async def body(db):
            admin = {"_id": str(ObjectId()), "role": "admin", "name": "A"}
            with pytest.raises(HTTPException) as exc:
                await server.export_admin_analytics("everything", admin)
            return exc.value

        assert run(body).status_code == 422


# ---------------------------------------------------------------------------
# 8. The date range
# ---------------------------------------------------------------------------


class TestTheDateRange:
    """Choosing a window, and what is allowed to be cached under one.

    The trap this exists for is a cache that answers every window with the
    numbers from one of them. `ANALYTICS_CACHE_ID` is a single document, so the
    default window is the only one it can hold — and a route that served it for
    `days=30` would report six months of business under a 30-day heading, which
    is the shape of wrong that nobody catches by reading a chart.
    """

    def test_the_default_window_is_served_from_the_cache(self):
        async def body(db):
            admin = {"_id": str(ObjectId()), "role": "admin", "name": "A"}
            await server.admin_analytics(admin)  # primes it
            return await server.admin_analytics(admin)

        out = run(body)
        assert out["cached"] is True
        assert out["window_days"] == server.ANALYTICS_DEFAULT_DAYS

    def test_a_narrower_window_is_never_served_from_the_cache(self):
        """The cache holds one window. Serving it for another would answer the
        wrong question with a number that looks right."""

        async def body(db):
            admin = {"_id": str(ObjectId()), "role": "admin", "name": "A"}
            await server.admin_analytics(admin)  # primes the default
            return await server.admin_analytics(admin, days=30)

        out = run(body)
        assert out["cached"] is False
        assert out["window_days"] == 30

    def test_priming_a_narrow_window_does_not_write_the_cache(self):
        """Or the next reader of the default window gets 30 days of business
        under a six-month heading — the same confusion, arriving later and
        without anybody having asked for it."""

        async def body(db):
            admin = {"_id": str(ObjectId()), "role": "admin", "name": "A"}
            await server.admin_analytics(admin, days=30)
            return await db.analytics_cache.find_one({"_id": server.ANALYTICS_CACHE_ID})

        assert run(body) is None

    @pytest.mark.parametrize("days", list(server.ANALYTICS_WINDOWS))
    def test_every_offered_window_is_accepted(self, days):
        async def body(db):
            admin = {"_id": str(ObjectId()), "role": "admin", "name": "A"}
            return await server.admin_analytics(admin, days=days)

        assert run(body)["window_days"] == days

    def test_a_window_outside_the_set_is_refused(self):
        """An open integer would let one request scan the whole history, and
        the picker offers four."""

        async def body(db):
            admin = {"_id": str(ObjectId()), "role": "admin", "name": "A"}
            with pytest.raises(HTTPException) as exc:
                await server.admin_analytics(admin, days=9999)
            return exc.value

        err = run(body)
        assert err.status_code == 422
        assert "180" in err.detail

    def test_the_admin_export_honours_the_window(self):
        """A spreadsheet that disagrees with the screen it came from is worse
        than no spreadsheet — and the export is the easiest place to forget."""
        src = inspect.getsource(server.export_admin_analytics)
        assert "days=days" in src

    def test_a_brand_defaults_to_its_whole_history(self):
        """Not the admin panel's default with a different number. The argument
        for a second campaign is the first one, and windowing by default would
        hide it the day it turned six months old."""

        async def body(db):
            w = await _brand_world(db, second_campaign=True)
            return await server.brand_analytics(w["user"])

        out = run(body)
        assert out["window_days"] is None
        assert out["rollup"]["campaigns"] == 2

    def test_a_brand_can_narrow_and_the_older_campaign_drops_out(self):
        async def body(db):
            w = await _brand_world(db, second_campaign=True)
            return await server.brand_analytics(w["user"], days=90)

        out = run(body)
        # The second campaign is 120 days old; the first is 30.
        assert out["rollup"]["campaigns"] == 1
        assert out["window_days"] == 90

    def test_an_empty_window_is_an_empty_rollup_rather_than_a_refusal(self):
        """"Nothing ran in these 90 days" is an answer. A 404 would read as the
        analytics being broken."""

        async def body(db):
            w = await _brand_world(db)
            # The only campaign is 30 days old, so ask for a window it predates
            # by moving the campaign instead.
            await db.campaigns.update_many({}, {"$set": {"created_at": ago(300)}})
            return await server.brand_analytics(w["user"], days=90)

        out = run(body)
        assert out["rollup"]["campaigns"] == 0
        assert out["latest_versus_history"] is None

    def test_a_brand_window_outside_the_set_is_refused(self):
        async def body(db):
            w = await _brand_world(db)
            with pytest.raises(HTTPException) as exc:
                await server.brand_analytics(w["user"], days=7)
            return exc.value

        assert run(body).status_code == 422

    def test_the_brand_export_honours_the_window(self):
        src = inspect.getsource(server.export_brand_analytics)
        assert "days=days" in src

    def test_the_picker_offers_exactly_what_the_route_accepts(self):
        """`WINDOWS` in `Analytics.jsx` mirrors `ANALYTICS_WINDOWS`. A fifth
        option on the picker is a 422, not a longer view — the same drift test
        `followerTiers.js` and `shootWindows.js` carry."""
        src = (FRONTEND / "components" / "admin" / "Analytics.jsx").read_text()
        block = src.split("export const WINDOWS = [", 1)[1].split("];", 1)[0]
        offered = sorted(int(n) for n in re.findall(r"days:\s*(\d+)", block))
        assert offered == sorted(server.ANALYTICS_WINDOWS)


# ---------------------------------------------------------------------------
# 9. Every surface is actually mounted
# ---------------------------------------------------------------------------


class TestTheSurfacesExist:
    """A caller with no mount is as unreachable as a route with no caller.

    This is the failure `test_manager_experience.py` was written for and the
    one the terms card nearly shipped with: a component holding the only call
    to an endpoint, rendered by nothing. Grepping the repository for the URL
    stays green in exactly that case, so these ask which *page* renders it.
    """

    def _read(self, *parts):
        return (FRONTEND.joinpath(*parts)).read_text()

    def test_the_admin_console_routes_to_the_analytics_section(self):
        sidebar = self._read("components", "admin", "console", "Sidebar.jsx")
        assert '"analytics"' in sidebar
        assert "AnalyticsRoute" in self._read("App.js")

    def test_the_brand_dashboard_renders_the_rollup(self):
        page = self._read("pages", "BrandDashboardView.jsx")
        assert "BrandAnalyticsSummary" in page
        assert "<BrandAnalyticsSummary />" in page

    def test_the_applicant_board_renders_the_campaign_panel(self):
        page = self._read("pages", "BrandCampaignApplicants.jsx")
        assert "<CampaignAnalytics" in page

    @pytest.mark.parametrize(
        "page,element",
        [
            ("BrandDashboardView.jsx", "<BrandAnalyticsSummary"),
            ("BrandCampaignApplicants.jsx", "<CampaignAnalytics"),
        ],
    )
    def test_both_brand_surfaces_are_inside_a_section_boundary(self, page, element):
        """A panel that throws must not take the dashboard down with it.

        The rule `SafeSection` exists for, and analytics is exactly the kind of
        panel it was written for: it reads a shape nobody has on a brand new
        account. Checked as the opening tag immediately above the element
        rather than as the word appearing anywhere in the file — both of these
        pages already use `SafeSection` elsewhere, so the loose version passes
        with the boundary deleted.
        """
        src = self._read("pages", page)
        before = src.split(element, 1)[0]
        opened = before.rfind("<SafeSection")
        closed = before.rfind("</SafeSection>")
        assert opened > closed, f"{element} in {page} is outside any SafeSection"

    def test_the_brand_panels_never_ask_what_role_is_looking(self):
        """The same rule the shared application screen holds: what a brand may
        do arrives from the server. An admin opening a brand's board reads the
        brand's numbers, not a different set."""
        src = self._read("components", "brand", "CampaignAnalytics.jsx")
        for banned in ('role ===', 'role !==', 'isAdmin', '"admin"'):
            assert banned not in src, banned
