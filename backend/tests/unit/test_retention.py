"""The two retention leaks: repeat work, and signal that never accumulated.

A brand's second campaign was as much work as its first — every field went back
in by hand, including the twelve that were identical. And a creator who was
excellent on three shoots read identically to one who no-showed twice, because
nothing anybody thought about either of them was ever written down.

These tests hold the shapes that fix both, and the lines that must not move:
what a duplicate carries, what a brand may see about somebody's record, and
what "partially delivered" is allowed to mean.
"""

from __future__ import annotations

import asyncio
import inspect
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from mongomock_motor import AsyncMongoMockClient

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"

LOOP = None


def no_comments(path: Path) -> str:
    src = re.sub(r"\{/\*.*?\*/\}", "", path.read_text(), flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


def run(body):
    """One loop per call, kept in a module global — `asyncio.get_event_loop`
    fails inside a pytest-xdist worker thread, and `asyncio.run` closes the loop
    mongomock's cursors were built on."""
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()

    async def go():
        db = AsyncMongoMockClient()["retention"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return LOOP.run_until_complete(go())


ADMIN = {"_id": str(ObjectId()), "role": "admin", "name": "Admin"}


def _campaign(**over):
    doc = {
        "brand_id": ObjectId(),
        "title": "Monthly tasting",
        "brief": "Come and eat.",
        "deliverable_items": [
            {"type": "reel", "quantity": 1},
            {"type": "story", "quantity": 3},
        ],
        "deliverables": "1 reel · 3 stories",
        "budget_per_creator": 9000.0,
        "category": "fnb",
        "area": "Indiranagar",
        "city": "Bengaluru",
        "creators_needed": 4,
        "campaign_type": "personal_table",
        "compensation_type": "fixed",
        "execution_owner": "brand",
        "visibility": "public",
        "requires_draft_approval": True,
        "venue_address": "12 12th Main",
        "status": "completed",
        "start_date": datetime.now(timezone.utc) - timedelta(days=40),
        "end_date": datetime.now(timezone.utc) - timedelta(days=30),
        "reference": "CMP-0099",
        "manager_id": ObjectId(),
        "showcase": True,
    }
    doc.update(over)
    return doc


# ---------------------------------------------------------------------------
# Doing it again
# ---------------------------------------------------------------------------


class TestDuplication:
    def test_a_copy_carries_the_brief_and_not_the_dates(self):
        """**The whole point of the exercise.** A duplicate that carried its
        dates would be a brief for a day that has passed; the reason to
        duplicate is that the brief is the same and the day is different."""

        async def body(db):
            source = _campaign()
            source["_id"] = (await db.campaigns.insert_one(source)).inserted_id
            return await server._duplicate_campaign(source, ADMIN)

        copy = run(body)
        for field in ("title", "brief", "budget_per_creator", "category", "area",
                      "venue_address", "deliverable_items", "requires_draft_approval"):
            assert field in copy, field
        for absent in ("start_date", "end_date", "event_date"):
            assert absent not in copy, f"a copy carried {absent}"

    def test_a_copy_is_a_draft_whoever_makes_it(self):
        """An admin can publish directly elsewhere, but a duplicate is by
        definition unreviewed against the dates it does not yet have."""

        async def body(db):
            source = _campaign(status="open")
            source["_id"] = (await db.campaigns.insert_one(source)).inserted_id
            return await server._duplicate_campaign(source, ADMIN)

        copy = run(body)
        assert copy["status"] == "draft"
        # And it carries the clock, like every other state write here.
        assert "state_since" in copy

    def test_a_copy_gets_its_own_reference_and_remembers_its_parent(self):
        async def body(db):
            source = _campaign()
            source["_id"] = (await db.campaigns.insert_one(source)).inserted_id
            copy = await server._duplicate_campaign(source, ADMIN)
            return source, copy

        source, copy = run(body)
        assert copy["reference"] != source["reference"]
        assert copy["duplicated_from"] == source["_id"]

    def test_a_copy_carries_none_of_the_run_it_came_from(self):
        """Applicants, slots, review notes and the assigned manager all belong
        to the run rather than to the brief. **`manager_id` especially** —
        inheriting it would quietly assign somebody to work they have not been
        told about."""

        async def body(db):
            source = _campaign(
                review_reason="Fix the fee",
                reviewed_at=datetime.now(timezone.utc),
                submitted_for_review_at=datetime.now(timezone.utc),
            )
            source["_id"] = (await db.campaigns.insert_one(source)).inserted_id
            return await server._duplicate_campaign(source, ADMIN)

        copy = run(body)
        # `status` and `reference` are reset rather than dropped — a copy is a
        # draft with a number of its own, which the test above pins.
        for field in server._CAMPAIGN_NOT_COPIED:
            if field in ("status", "reference"):
                continue
            assert field not in copy, f"a copy carried {field}"

    def test_the_two_field_lists_do_not_overlap(self):
        """**This is the test that actually keeps the dates off a copy.**

        `_brief_fields_of` is an allow-list, so `_CAMPAIGN_NOT_COPIED` does not
        block anything by itself — it documents the intent. What makes it
        enforcement is this: adding a date to the brief list to "carry a bit
        more" trips here rather than silently shipping a duplicate that briefs
        a day which has already passed. Verified by trying exactly that.
        """
        assert not (set(server._CAMPAIGN_BRIEF_FIELDS) & set(server._CAMPAIGN_NOT_COPIED))

    def test_a_template_and_a_duplicate_copy_the_same_thing(self):
        """**One list, three readers.** Three copies is how a field added to
        the form next month ends up carried by duplication and silently dropped
        by templates."""
        for fn in (server._duplicate_campaign, server.save_campaign_as_template):
            assert "_brief_fields_of(" in inspect.getsource(fn), fn.__name__

    def test_a_field_the_template_never_had_is_absent_not_null(self):
        """A template saved before a field existed must not blank that field on
        every campaign made from it. "The template does not mention this" is a
        different thing from "the template says leave it empty"."""
        fields = server._brief_fields_of({"title": "x", "venue_address": None})
        assert fields == {"title": "x"}

    def test_applying_a_template_is_a_prefill_and_not_a_second_creation_path(self):
        """The campaign is created by the ordinary POST, with the ordinary
        validation behind it. Minting one from a template would be a second
        idea of what a valid brief is, and the two would drift."""
        src = inspect.getsource(server.mark_template_used)
        assert "campaigns.insert_one" not in src
        assert "used_count" in src


# ---------------------------------------------------------------------------
# What somebody is like to work with
# ---------------------------------------------------------------------------


class TestReliability:
    def test_no_history_is_neutral_and_never_a_low_band(self):
        """**The rule that decides whether this feature helps or hurts.** A
        creator on their first brief has no history, which is the ordinary
        state of everybody the platform is trying to bring in. Sorting them
        below somebody with one late delivery would make the directory a
        ranking of who got here first."""
        for stats in (None, {}, {"completed": 0, "on_time_rate": None}):
            band = server._reliability_band(stats)
            assert band["band"] == "new"
            assert band["enough_history"] is False
            assert "most people at the start" in band["blurb"]

    def test_a_tiny_sample_does_not_earn_a_verdict(self):
        """One campaign delivered on time is not "consistently delivers"."""
        band = server._reliability_band({"completed": 1, "on_time_rate": 1.0})
        assert band["band"] == "new"

    @pytest.mark.parametrize(
        "rate,expected",
        [(1.0, "strong"), (0.96, "strong"), (0.85, "steady"), (0.5, "mixed"), (0.0, "mixed")],
    )
    def test_the_bands_are_the_boundaries_they_say(self, rate, expected):
        band = server._reliability_band({"completed": 10, "on_time_rate": rate})
        assert band["band"] == expected

    def test_an_unknown_rate_is_none_and_never_zero(self):
        """A creator with no finished campaigns has an unknown on-time rate,
        not a 0% one, and every surface draws unknown as an em dash rather than
        as a failure."""

        async def body(db):
            creator = ObjectId()
            await db.collaborations.insert_one(
                {"creator_id": creator, "campaign_id": ObjectId(), "state": "applied"}
            )
            return (await server._reliability_for([creator]))[creator]

        stats = run(body)
        assert stats["completed"] == 0
        assert stats["on_time_rate"] is None

    def test_it_counts_the_things_that_actually_happened(self):
        async def body(db):
            creator = ObjectId()
            campaign = ObjectId()
            rows = [
                {"state": "closed"},
                {"state": "closed", "content_overdue": True},
                {"state": "closed", "no_show_reported": True},
                {"state": "cancelled", "cancelled_by_role": "creator"},
                {"state": "cancelled", "cancelled_by_role": "brand_manager"},
                {"state": "withdrawn"},
                {"state": "slot_booked", "reschedule_count": 3},
                {"state": "closed", "draft_revision_count": 2},
                {"state": "closed", "draft_revision_count": 0},
            ]
            for row in rows:
                await db.collaborations.insert_one(
                    {"creator_id": creator, "campaign_id": campaign, **row}
                )
            return (await server._reliability_for([creator]))[creator]

        stats = run(body)
        assert stats["completed"] == 5  # every `closed`
        assert stats["late_deliveries"] == 1
        assert stats["no_shows"] == 1
        # **Only the cancellations they caused.** A brand pulling out is not a
        # fact about the creator, and counting it against them would put a mark
        # on somebody for being let down.
        assert stats["cancellations"] == 1
        assert stats["withdrawals"] == 1
        assert stats["reschedules"] == 3
        # Averaged over the drafts that existed, not over every collaboration:
        # a campaign with no draft gate has no revisions to have.
        assert stats["avg_revisions"] == 1.0

    def test_a_brand_gets_the_band_and_never_the_counts(self):
        """"2 no-shows" against forty campaigns is a good record read as a bad
        one, and a brand has no denominator to hand."""
        row = server._brand_visible_creator(
            {"name": "Aditi", "user_id": ObjectId()},
            {},
            reliability={"completed": 10, "on_time_rate": 0.5, "no_shows": 4},
        )
        assert row["reliability"]["band"] == "mixed"
        for leaked in ("no_shows", "completed", "on_time_rate"):
            assert leaked not in row["reliability"]
            assert leaked not in row

    def test_a_surface_that_did_not_fetch_history_says_nothing(self):
        """Omitted rather than an empty band: "we did not look" and "they have
        no history" are different, and only one of them belongs on a card."""
        row = server._brand_visible_creator({"name": "Aditi"}, {})
        assert "reliability" not in row

    def test_the_band_is_on_the_allow_list(self):
        assert "reliability" in server._BRAND_VISIBLE_CREATOR_FIELDS

    def test_the_counts_never_reach_a_brand_through_the_application_page(self):
        """The staff block is gated on the role; the creator block carries the
        band. A brand reading the page gets one and not the other."""
        src = inspect.getsource(server.get_application)
        assert '"reliability": reliability_stats if is_staff_side else None' in src


class TestRatingsFeedRanking:
    def test_a_rating_rides_in_on_the_existing_delivery_weight(self):
        """**Not a new weight.** A rating and an on-time rate measure the same
        thing at different grains, and a tenth weight would mean re-tuning a
        table that sums to 100 and silently changing what everything else is
        worth."""
        assert sum(server.CREATOR_MATCH_WEIGHTS.values()) == 100
        assert "rating" not in server.CREATOR_MATCH_WEIGHTS

    def test_no_signal_at_all_is_unknown_rather_than_bad(self):
        assert server._reliability_signal(None) is None
        assert server._reliability_signal({"on_time_rate": None, "rating_avg": None}) is None

    def test_a_middling_rating_sits_exactly_where_an_unknown_would(self):
        """3 out of 5 maps to 0.5, which is `_UNKNOWN_SIGNAL` — the honest
        relationship between "they were fine" and "we do not know"."""
        assert server._reliability_signal({"rating_avg": 3.0}) == server._UNKNOWN_SIGNAL

    def test_each_half_is_used_only_when_it_exists(self):
        assert server._reliability_signal({"on_time_rate": 1.0}) == 1.0
        assert server._reliability_signal({"rating_avg": 5.0}) == 1.0
        assert server._reliability_signal({"on_time_rate": 1.0, "rating_avg": 1.0}) == 0.5

    def test_the_scorer_still_works_with_nothing_but_a_count(self):
        """The blended signal is what the pipeline passes; the raw rate is the
        fallback that keeps this function readable and testable on its own."""
        result = server.score_creator_for_campaign(
            {"niches": ["food"], "city": "Bengaluru"},
            _campaign(),
            delivery={"completed": 4, "on_time": 2},
        )
        assert 0 <= result["score"] <= 100


class TestRatingsAreOursAlone:
    def test_they_are_on_no_brand_facing_shape(self):
        """Private to WeAre is the decision to revisit, not the one to quietly
        extend. A public average turns a considered three into a reputational
        act."""
        row = server._brand_visible_creator(
            {"name": "Aditi"}, {}, reliability={"completed": 9, "rating_avg": 4.5}
        )
        assert "rating_avg" not in str(row)

    def test_rating_opens_only_once_it_closes(self):
        """A score sitting on the record while the person being scored still
        has to be worked with is leverage rather than a record."""
        src = inspect.getsource(server._rateable_collab_or_404)
        assert 'collab.get("state") != "closed"' in src
        assert '"code": "not_closed"' in src

    def test_each_side_sees_its_own_and_never_the_other(self):
        """A runner reading the creator's score before writing their own is an
        anchoring problem the whole point of collecting both is to avoid."""
        src = inspect.getsource(server.get_collaboration_ratings)
        assert "visible = RATING_SIDES if all_access else ([side] if side else [])" in src

    def test_which_side_follows_execution_owner_not_the_role(self):
        """A weare-run brief is rated by our manager and a brand-run one by the
        brand — in both cases the person who was actually there."""
        assert "_question_staff_may_see(campaign, user)" in inspect.getsource(
            server._rating_side_for
        )

    def test_one_rating_per_side_however_many_taps(self):
        src = inspect.getsource(server.rate_collaboration)
        assert "upsert=True" in src
        assert '{"collaboration_id": collab["_id"], "side": side}' in src


# ---------------------------------------------------------------------------
# When some of it arrives
# ---------------------------------------------------------------------------


class TestPartialDelivery:
    CAMPAIGN = {
        "deliverable_items": [
            {"type": "reel", "quantity": 1},
            {"type": "story", "quantity": 3},
        ]
    }

    def test_a_brief_with_no_counted_ask_has_no_shortfall(self):
        """**`None`, not an empty shortfall.** An empty one means "all of it
        arrived", and saying that about a campaign nobody counted would be a
        claim we cannot support."""
        assert server._delivery_shortfall({"deliverables": "a reel and some stories"}, {}) is None

    def test_a_collaboration_nobody_counted_is_unknown_not_complete(self):
        assert server._delivery_shortfall(self.CAMPAIGN, {}) is None

    def test_it_counts_what_is_short(self):
        got = server._delivery_shortfall(
            self.CAMPAIGN, {"delivered_items": {"reel": 1, "story": 2}}
        )
        assert got["asked_total"] == 4
        assert got["delivered_total"] == 3
        assert got["complete"] is False
        assert got["missing"] == [
            {"type": "story", "label": "Story", "asked": 3, "delivered": 2, "short": 1}
        ]
        assert "1 story short" in got["summary"]

    def test_everything_arriving_reads_complete(self):
        got = server._delivery_shortfall(
            self.CAMPAIGN, {"delivered_items": {"reel": 1, "story": 3}}
        )
        assert got["complete"] is True
        assert got["missing"] == []

    def test_more_than_asked_is_clamped_rather_than_counted(self):
        """Four stories where three were asked is a miscount, not 133%."""
        got = server._delivery_shortfall(
            self.CAMPAIGN, {"delivered_items": {"reel": 1, "story": 9}}
        )
        assert got["delivered_total"] == 4
        assert got["complete"] is True

    def test_the_pro_rata_is_a_suggestion_and_the_amount_is_typed(self):
        """Two of three stories is not two-thirds of the value when the reel
        was the point. The same rule the withholding field holds: this records
        what somebody decided, it does not decide."""
        got = server._delivery_shortfall(
            self.CAMPAIGN, {"delivered_items": {"reel": 1, "story": 2}}
        )
        assert got["pro_rata_fraction"] == 0.75
        src = inspect.getsource(server.accept_partial_delivery)
        # The fee comes from the payload through the shared resolver, never
        # from the fraction above.
        assert "_resolve_agreed_amount(campaign, payload.agreed_amount)" in src
        assert "pro_rata" not in src.split("_resolve_agreed_amount")[1]

    def test_it_is_not_a_new_state(self):
        """What happens next — payment — is the same, so it lands on
        `content_approved` exactly like a full approval. A ninth state would
        put a fork in a ladder that already works."""
        src = inspect.getsource(server.accept_partial_delivery)
        assert '_state_stamp("content_approved"' in src
        assert "partial" not in server.COLLAB_STATE_ORDER

    def test_accepting_everything_through_this_route_is_not_flagged_as_partial(self):
        """A runner who opens the dialog and finds everything did arrive should
        leave an ordinary approval behind, not a record flagged as partial on
        somebody's reliability history."""
        src = inspect.getsource(server.accept_partial_delivery)
        assert '"partial_delivery": bool(shortfall and not shortfall["complete"])' in src

    def test_a_brief_with_no_structure_refuses_rather_than_guessing(self):
        src = inspect.getsource(server.accept_partial_delivery)
        assert '"code": "no_structured_ask"' in src

    def test_the_note_is_required(self):
        """"Accepted partial" with no reason is a decision somebody has to
        reconstruct from a payment figure a year later."""
        assert server.PartialDeliveryPayload.model_fields["note"].is_required()


# ---------------------------------------------------------------------------
# Moving a booking
# ---------------------------------------------------------------------------


class TestRescheduleLimit:
    def test_absent_is_zero_moves(self):
        """Nothing recorded is nothing we can hold against anybody."""
        assert server._reschedule_count({}) == 0
        assert server._reschedule_count(None) == 0
        assert server._reschedule_count({"reschedule_count": 4}) == 4

    def test_the_default_is_two(self):
        async def body(db):
            return await server.reschedule_limit()

        assert run(body) == server.RESCHEDULE_LIMIT_DEFAULT == 2

    def test_a_stored_limit_wins(self):
        async def body(db):
            await db.platform_settings.insert_one(
                {"_id": server._RESCHEDULE_SETTINGS_ID, "limit": 5}
            )
            return await server.reschedule_limit()

        assert run(body) == 5

    def test_nonsense_falls_back_to_the_default(self):
        async def body(db):
            await db.platform_settings.insert_one(
                {"_id": server._RESCHEDULE_SETTINGS_ID, "limit": "loads"}
            )
            return await server.reschedule_limit()

        assert run(body) == server.RESCHEDULE_LIMIT_DEFAULT

    def test_zero_is_a_real_answer(self):
        """"No self-service moves at all" is a policy somebody might want, so
        the floor is zero rather than one."""
        assert server.RescheduleLimitPayload(limit=0).limit == 0

    def test_the_cap_is_on_the_creator_and_the_runner_is_the_way_through(self):
        """A cap on both sides would be a cap with no way through it. The
        refusal names the number and points at the person who can still do it,
        because "no" with no next step is how somebody just stops turning up.
        """
        creator_side = inspect.getsource(server.creator_cancel_slot)
        assert "await reschedule_limit()" in creator_side
        assert '"code": "reschedule_limit"' in creator_side
        assert "campaign" in creator_side.split('"code": "reschedule_limit"')[0][-400:]

        runner_side = inspect.getsource(server.reschedule_creator)
        assert "reschedule_limit()" not in runner_side, (
            "the runner is the override — capping them too leaves no way through"
        )

    def test_both_moves_are_counted(self):
        """The runner's is usually made on the creator's behalf and past their
        own limit; a count that recorded only the allowed ones would understate
        exactly the creator it exists to describe."""
        for fn in (server.creator_cancel_slot, server.reschedule_creator):
            assert '"$inc": {"reschedule_count": 1}' in inspect.getsource(fn), fn.__name__


# ---------------------------------------------------------------------------
# Lists, and who has gone quiet
# ---------------------------------------------------------------------------


class TestCreatorLists:
    def test_a_brands_lists_belong_to_the_brand_not_the_login(self):
        """So the manager leaving does not take them."""
        src = inspect.getsource(server._list_owner_for)
        assert "_brand_scope(user)" in src
        assert "_WEARE_LIST_OWNER" in src

    def test_weare_lists_are_shared_rather_than_personal(self):
        """"Creators who are good at launch nights" is operational knowledge,
        not a personal note."""
        assert server._WEARE_LIST_OWNER == "weare"
        assert server._list_owner_for({"role": "weare_team"}) == "weare"
        assert server._list_owner_for({"role": "admin"}) == "weare"

    def test_a_brand_facing_list_goes_through_the_allow_list(self):
        """A saved list is not a way around the contact rule."""
        assert "_brand_visible_creator(" in inspect.getsource(server._serialize_creator_list)

    def test_inviting_a_list_goes_through_the_one_invite_implementation(self):
        """A second invite path would be a second definition of what an
        invitation is — the verification gate, the duplicate refusal and the
        fact that a number is read and never returned all live in one place."""
        src = inspect.getsource(server.invite_creator_list)
        assert "await _invite_creators(" in src
        assert "campaign_invitations.insert_one" not in src

    def test_ownership_is_checked_before_verification(self):
        """The other order turns another brand's campaign from a 404 into a
        403, which leaks which ids exist."""
        src = inspect.getsource(server.invite_creator_list)
        assert src.index("_own_campaign_or_404") < src.index("_verified_brand_or_403")

    def test_somebody_elses_list_is_a_404(self):
        assert 'status_code=404' in inspect.getsource(server._own_creator_list_or_404)


class TestDormancy:
    def test_never_active_sorts_first_not_last(self):
        """A brand we verified and never heard from again got stuck somewhere
        and nobody found out — the strongest signal on the list rather than the
        weakest, which is the opposite of how an unknown sorts in a column."""

        async def body(db):
            long_ago = datetime.now(timezone.utc) - timedelta(days=200)
            quiet, never = ObjectId(), ObjectId()
            await db.brand_profiles.insert_many(
                [
                    {"user_id": quiet, "business_name": "Quiet", "verified": True},
                    {"user_id": never, "business_name": "Never", "verified": True},
                ]
            )
            await db.campaigns.insert_one(
                {"brand_id": quiet, "title": "Old one", "created_at": long_ago}
            )
            return await server.admin_dormant(kind="brands", user=ADMIN)

        rows = run(body)["brands"]
        assert [r["name"] for r in rows] == ["Never", "Quiet"]
        assert rows[0]["never_active"] is True
        assert rows[0]["days_quiet"] is None

    def test_somebody_active_is_not_on_it(self):
        async def body(db):
            active = ObjectId()
            await db.brand_profiles.insert_one(
                {"user_id": active, "business_name": "Busy", "verified": True}
            )
            await db.campaigns.insert_one(
                {
                    "brand_id": active,
                    "title": "Last week",
                    "created_at": datetime.now(timezone.utc) - timedelta(days=3),
                }
            )
            return await server.admin_dormant(kind="brands", user=ADMIN)

        assert run(body)["brands"] == []

    def test_a_half_finished_creator_is_not_dormant(self):
        """They are unfinished, not quiet — and `nudge_stale_creator_profiles`
        already chases them, so listing them here is a second chase from a
        different screen."""
        src = inspect.getsource(server.admin_dormant)
        assert '{"verification_status": "verified"}' in src

    def test_every_row_carries_the_date_and_a_way_in(self):
        """"48 dormant creators" is a fact you cannot act on."""

        async def body(db):
            uid = ObjectId()
            await db.creator_profiles.insert_one(
                {"user_id": uid, "name": "Aditi", "verification_status": "verified"}
            )
            return await server.admin_dormant(kind="creators", user=ADMIN)

        row = run(body)["creators"][0]
        assert "last_active_at" in row and row["href"].startswith("/admin/creators/")


# ---------------------------------------------------------------------------
# Nothing shipped without a way in
# ---------------------------------------------------------------------------


class TestEveryRouteHasACaller:
    """A backend flow with no UI is not shipped, whatever the tests say — the
    rule this repository learned from four verification endpoints that had no
    caller anywhere in the frontend for months."""

    @pytest.mark.parametrize(
        "method,path",
        [
            ("post", "/brand/campaigns/{id}/duplicate"),
            ("post", "/brand/campaigns/{id}/save-as-template"),
            ("get", "/brand/campaign-templates"),
            ("post", "/brand/campaign-templates/{id}/used"),
            ("delete", "/brand/campaign-templates/{id}"),
            ("get", "/brand/creator-lists"),
            ("post", "/brand/creator-lists"),
            ("delete", "/brand/creator-lists/{id}"),
            ("post", "/brand/campaigns/{id}/invite-list/{list}"),
            ("post", "/brand/collaborations/{id}/accept-partial"),
            ("get", "/ratings/{id}"),
            ("post", "/ratings/{id}"),
            ("get", "/admin/dormant"),
        ],
    )
    def test_the_frontend_calls_it(self, method, path):
        """Matched on the literal segments either side of each `{hole}`.

        A caller writes `` api.post(`/brand/campaigns/${id}/duplicate`) `` —
        the parameters are interpolated, so what survives verbatim are the
        fixed halves of the path. Requiring all of them inside one `api.<verb>`
        call is specific enough to catch a typo and loose enough to survive
        somebody renaming a variable.
        """
        segments = [seg for seg in re.split(r"\{[a-z]+\}", path) if seg]
        call = re.compile(rf"api\.{method}\((.{{0,160}}?)\)", re.S)
        # **The second shape, which is not a loophole.** Several screens post
        # through one dispatcher — `api.post(`${base}/${action}`, body)` — so
        # the verb never appears inside the call. Requiring the dispatcher's
        # fixed prefix *and* the verb as a literal in the same file is what
        # actually proves the route is reachable; matching the path alone
        # would report the applicant board as having no caller for half its
        # own actions.
        tail = segments[-1].strip("/") if segments else ""
        prefix = "".join(segments[:-1]) if len(segments) > 1 else ""

        def calls_it(source: str) -> bool:
            for m in call.finditer(source):
                if all(seg in m.group(1) for seg in segments):
                    return True
                if (
                    prefix
                    and tail
                    and prefix in m.group(1)
                    and "${" in m.group(1)
                    and f'"{tail}"' in source
                ):
                    return True
            return False

        hits = [
            f.name
            for pattern in ("*.jsx", "*.js")
            for f in FRONTEND.rglob(pattern)
            if calls_it(no_comments(f))
        ]
        assert hits, f"{method.upper()} {path} has no caller in the frontend"

    def test_the_new_panels_are_actually_mounted(self):
        """A caller with no mount is as unreachable as a route with no caller —
        deleting a component from a page leaves the route-has-a-caller check
        green, because the component file still holds the only call."""
        mounts = {
            "CampaignTemplates": ("pages/PostCampaign.jsx",),
            "SaveAsTemplate": ("pages/BrandDashboardView.jsx",),
            "CreatorLists": ("pages/BrandCampaignApplicants.jsx",),
            "PartialDeliveryDialog": ("pages/BrandCampaignApplicants.jsx",),
            "RateCollaboration": ("components/application/ApplicationDetail.jsx",),
            "ReliabilityPanel": (
                "components/application/ApplicationDetail.jsx",
                "components/admin/CreatorDetailPage.jsx",
            ),
            "Shortfall": (
                "components/application/ApplicationDetail.jsx",
                "components/creator/Applications.jsx",
            ),
            "AdminDormant": ("components/admin/routes.jsx",),
        }
        for component, pages in mounts.items():
            for page in pages:
                src = no_comments(FRONTEND / page)
                assert f"<{component}" in src or f"{component} />" in src or (
                    component == "AdminDormant" and component in src
                ), f"{component} is never rendered by {page}"

    def test_the_dormancy_section_is_in_the_navigation(self):
        sidebar = no_comments(FRONTEND / "components/admin/console/Sidebar.jsx")
        assert 'key: "dormant"' in sidebar
        app = no_comments(FRONTEND / "App.js")
        assert 'path="dormant"' in app
