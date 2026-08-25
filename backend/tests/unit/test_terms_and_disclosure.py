"""What the post must say, what may be done with it, and what was agreed.

Three things that were nowhere, and all three are the same kind of gap: a fact
both sides needed, held in somebody's memory.

- **Disclosure.** ASCI requires a label on content carrying a material
  connection, and the liability sits with the *advertiser* — us and the brand,
  not only the creator. Nothing on the brief said so and nobody confirmed it
  was there.
- **Usage rights.** A creator applied not knowing whether a reel would be
  reposted once or run as a paid ad for a year. Very different pieces of work,
  very different prices, and the most common thing to argue about afterwards.
- **The terms.** Every term lived somewhere editable: deliverables and usage on
  the campaign the brand can edit, the fee on a collaboration a partial
  acceptance rewrites, the cancellation policy in a constant we can change in a
  deploy. So mediation three weeks later had nothing to read.

The tests drive the real handlers and read the database back, for the reason
`test_money_paths.py` sets out: a guard that is present and does nothing keeps
the string and loses the protection.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import server

LOOP = None


def run(body):
    """One loop per call — see the note in `test_money_paths.py`."""
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()

    async def go():
        db = AsyncMongoMockClient()["terms"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return LOOP.run_until_complete(go())


def _now():
    return datetime.now(timezone.utc)


DAY = (_now() + timedelta(days=14)).replace(hour=13, minute=0, second=0, microsecond=0)
ADMIN = {"_id": str(ObjectId()), "role": "admin", "name": "Admin"}


def _body(**over):
    body = {
        "title": "Two reels for the spring range",
        "brief": "Shoot in store, natural light.",
        "deliverable_items": [{"type": "reel", "quantity": 2}],
        "budget_per_creator": 9000,
        "category": "fashion",
        "area": "Indiranagar",
        "creators_needed": 2,
        "campaign_type": "personal_table",
        "start_date": DAY,
        "end_date": DAY + timedelta(days=7),
    }
    body.update(over)
    return body


# ---------------------------------------------------------------------------
# 2. Disclosure
# ---------------------------------------------------------------------------


class TestEveryCampaignCarriesADisclosure:
    def test_absent_reads_as_the_default_rather_than_none(self):
        """**Campaigns predate the field and every one of them still needed a
        label.** Reading absent as "no disclosure required" would quietly
        exempt the entire back catalogue — which is the opposite of what a
        compliance field is for."""
        assert server._required_disclosure({}) == server.DEFAULT_DISCLOSURE
        assert server._required_disclosure(None) == server.DEFAULT_DISCLOSURE
        assert server._disclosure_text({}) in server.DISCLOSURE_LABELS.values()

    def test_an_unrecognised_value_falls_back_rather_than_rendering_itself(self):
        """A label nobody can act on is worse than the default: a reviewer
        confirming "pls mention us" has confirmed nothing."""
        assert server._required_disclosure({"required_disclosure": "whatever"}) == (
            server.DEFAULT_DISCLOSURE
        )

    def test_the_default_is_to_disclose_and_not_to_skip(self):
        assert server.DEFAULT_DISCLOSURE in server.DISCLOSURE_LABELS
        assert "none" not in server.DISCLOSURE_LABELS

    def test_barter_gets_one_too(self):
        """**The deviation, and the reason for it.** The requirement asked for
        this on *paid* campaigns. Restricting it there would leave the
        arrangement that most obviously needs it — a free stay, a meal, a
        product sent over — with no disclosure at all. A gifted post is an ad,
        and ASCI's material-connection test does not care whether money moved.
        """
        assert server._required_disclosure({"compensation_type": "barter"}) == (
            server.DEFAULT_DISCLOSURE
        )

    def test_it_rides_on_every_campaign_shape_including_the_creators(self):
        """It is one of the things somebody has to know *before* applying.
        Shipping it only to the owner would put it in front of the one party
        who already knew."""
        doc = {
            "_id": ObjectId(), "brand_id": ObjectId(), "title": "x",
            "status": "open", "required_disclosure": "ad",
        }
        out = server._serialize_campaign(doc, None)
        assert out["required_disclosure"] == "ad"
        assert out["disclosure_label"] == server.DISCLOSURE_LABELS["ad"]


class TestTheReviewerHasToConfirmIt:
    async def _scene(self, db, *, draft_gate=True, state="draft_submitted"):
        brand_oid, creator_oid = ObjectId(), ObjectId()
        campaign_oid, collab_oid = ObjectId(), ObjectId()
        await db.users.insert_many([
            {"_id": brand_oid, "role": "brand_manager", "name": "Ninth Street",
             "brand_id": brand_oid, "phone": "+919900000001"},
            {"_id": creator_oid, "role": "creator", "name": "Asha",
             "phone": "+919900000002"},
        ])
        await db.brand_profiles.insert_one(
            {"user_id": brand_oid, "business_name": "Ninth Street",
             "verified": True, "verified_at": _now()}
        )
        await db.campaigns.insert_one(
            {"_id": campaign_oid, "brand_id": brand_oid, "title": "Spring range",
             "status": "in_progress", "execution_owner": "brand",
             "compensation_type": "fixed", "budget_per_creator": 9000,
             "required_disclosure": "ad",
             "requires_draft_approval": draft_gate}
        )
        await db.collaborations.insert_one(
            {"_id": collab_oid, "campaign_id": campaign_oid,
             "creator_id": creator_oid, "state": state,
             "agreed_amount": 9000, "state_since": _now(),
             "draft_url": "https://example.com/draft.mp4",
             "draft_submitted_at": _now(),
             "content_url": "https://instagram.com/p/abc/"}
        )
        brand = await db.users.find_one({"_id": brand_oid})
        return {
            "brand": {**brand, "_id": str(brand_oid)},
            "collab_id": str(collab_oid), "collab_oid": collab_oid,
        }

    def test_approving_a_draft_without_confirming_is_refused(self):
        async def body(db):
            s = await self._scene(db)
            with pytest.raises(HTTPException) as err:
                await server.approve_draft(
                    s["collab_id"],
                    server.DisclosureCheckPayload(disclosure_confirmed=False),
                    s["brand"],
                )
            return err.value, await db.collaborations.find_one({"_id": s["collab_oid"]})

        exc, collab = run(body)
        assert exc.status_code == 422
        assert exc.detail["code"] == "disclosure_unconfirmed"
        # The refusal is worth nothing if the state moved anyway.
        assert collab["state"] == "draft_submitted"

    def test_the_refusal_names_the_label_the_reviewer_is_looking_for(self):
        """"Confirm the disclosure" is a checkbox; "confirm it carries #ad" is
        an instruction."""

        async def body(db):
            s = await self._scene(db)
            with pytest.raises(HTTPException) as err:
                await server.approve_draft(
                    s["collab_id"],
                    server.DisclosureCheckPayload(disclosure_confirmed=False),
                    s["brand"],
                )
            return err.value.detail

        detail = run(body)
        assert detail["label"] == server.DISCLOSURE_LABELS["ad"]
        assert "#ad" in detail["message"]

    def test_confirming_records_who_and_when_not_just_a_boolean(self):
        """"The disclosure was confirmed" with nobody's name on it is exactly
        the record that is no use in a complaint."""

        async def body(db):
            s = await self._scene(db)
            await server.approve_draft(
                s["collab_id"],
                server.DisclosureCheckPayload(disclosure_confirmed=True),
                s["brand"],
            )
            return await db.collaborations.find_one({"_id": s["collab_oid"]})

        collab = run(body)
        check = collab["draft_disclosure_check"]
        assert check["confirmed"] is True
        assert check["confirmed_at"] is not None
        assert check["confirmed_by_name"] == "Ninth Street"
        assert check["label"] == server.DISCLOSURE_LABELS["ad"]
        assert collab["state"] == "draft_approved"

    def test_approving_live_content_without_confirming_is_refused(self):
        async def body(db):
            s = await self._scene(db, draft_gate=False, state="content_submitted")
            with pytest.raises(HTTPException) as err:
                await server.brand_approve_content(
                    s["collab_id"],
                    server.DisclosureCheckPayload(disclosure_confirmed=False),
                    s["brand"],
                )
            return err.value, await db.collaborations.find_one({"_id": s["collab_oid"]})

        exc, collab = run(body)
        assert exc.status_code == 422
        assert collab["state"] == "content_submitted"

    def test_the_live_confirmation_is_recorded_separately_from_the_draft_one(self):
        """**Two checkpoints, two records.** A campaign with a draft gate is
        checked twice — once when the label can still be added for free, and
        once against the post a regulator could actually go and look at."""

        async def body(db):
            s = await self._scene(db, draft_gate=False, state="content_submitted")
            await server.brand_approve_content(
                s["collab_id"],
                server.DisclosureCheckPayload(disclosure_confirmed=True),
                s["brand"],
            )
            return await db.collaborations.find_one({"_id": s["collab_oid"]})

        collab = run(body)
        assert collab["content_disclosure_check"]["confirmed"] is True
        assert collab.get("draft_disclosure_check") is None
        assert collab["state"] == "content_approved"

    def test_a_stage_nobody_has_reviewed_serialises_as_none(self):
        """Not-yet-reviewed and reviewed-and-absent are different facts, and a
        red cross on every unreviewed draft is a warning people learn to
        ignore."""
        assert server._serialize_disclosure_check(None) is None
        assert server._serialize_disclosure_check({}) is None

    def test_the_payload_defaults_to_unconfirmed(self):
        """A box that arrives ticked is a box nobody read."""
        assert server.DisclosureCheckPayload().disclosure_confirmed is False


# ---------------------------------------------------------------------------
# 3. Usage rights
# ---------------------------------------------------------------------------


class TestUsageRights:
    def test_absent_grants_the_narrowest_thing(self):
        """**A campaign written before the field granted nothing beyond a
        repost**, because nothing broader was ever agreed. Reading absent as a
        buyout would retroactively hand over every piece of content on the
        platform."""
        assert server._usage_rights({}) == "organic_only"
        assert server._usage_rights(None) == "organic_only"
        assert server.DEFAULT_USAGE_RIGHTS == "organic_only"

    def test_an_unrecognised_grant_falls_back_narrow_too(self):
        assert server._usage_rights({"usage_rights": "everything"}) == "organic_only"

    def test_paid_usage_has_to_carry_a_period(self):
        """Open-ended paid usage is a buyout wearing a smaller name, and a
        creator reading the brief cannot tell the two apart."""
        with pytest.raises(Exception) as err:
            server.PostCampaignPayload(**_body(usage_rights="paid_usage"))
        assert "period" in str(err.value).lower() or "days" in str(err.value).lower()

    @pytest.mark.parametrize("kind", ["organic_only", "full_buyout"])
    def test_the_other_two_refuse_a_period(self, kind):
        """A duration on a repost-only grant is a number describing nothing,
        and it would render on the brief as though it did."""
        with pytest.raises(Exception):
            server.PostCampaignPayload(
                **_body(usage_rights=kind, usage_duration_days=90)
            )

    def test_a_complete_paid_grant_is_accepted(self):
        payload = server.PostCampaignPayload(
            **_body(usage_rights="paid_usage", usage_duration_days=90)
        )
        assert payload.usage_duration_days == 90

    def test_the_duration_is_dropped_on_a_grant_that_has_none(self):
        """Even if a stored document carries a stray one — a campaign edited
        from paid usage down to organic should not keep advertising 90 days."""
        assert server._usage_duration_days(
            {"usage_rights": "organic_only", "usage_duration_days": 90}
        ) is None

    def test_the_sentence_is_built_once_for_every_surface(self):
        """The brief, the application page and the frozen terms all render
        `text`, so the same grant cannot be phrased three ways."""
        assert server._usage_text({"usage_rights": "organic_only"}) == (
            "Organic repost only"
        )
        assert "45 days" in server._usage_text(
            {"usage_rights": "paid_usage", "usage_duration_days": 45}
        )
        assert "months" in server._usage_text(
            {"usage_rights": "paid_usage", "usage_duration_days": 180}
        )
        assert server._usage_text({"usage_rights": "full_buyout"}) == "Full buyout"

    def test_a_paid_grant_with_no_stored_period_says_so(self):
        """The field is required with this option, so this is a campaign
        written before the rule. "Period not recorded" is the honest reading
        and the one a mediator can act on."""
        text = server._usage_text({"usage_rights": "paid_usage"})
        assert "not recorded" in text

    def test_it_rides_on_every_campaign_shape(self):
        doc = {
            "_id": ObjectId(), "brand_id": ObjectId(), "title": "x", "status": "open",
            "usage_rights": "paid_usage", "usage_duration_days": 60,
        }
        block = server._serialize_campaign(doc, None)["usage"]
        assert block["kind"] == "paid_usage"
        assert block["duration_days"] == 60
        # Past 60 days the sentence reads in months, which is how somebody
        # actually thinks about a licence period.
        assert "months" in block["text"]


# ---------------------------------------------------------------------------
# 4. The terms snapshot
# ---------------------------------------------------------------------------


async def _accepted_scene(db, *, compensation="fixed", usage="paid_usage"):
    """A brand, a creator and an application sitting at `verified`."""
    brand_oid, creator_oid = ObjectId(), ObjectId()
    campaign_oid, collab_oid = ObjectId(), ObjectId()
    await db.users.insert_many([
        {"_id": brand_oid, "role": "brand_manager", "name": "Ninth Street",
         "brand_id": brand_oid, "phone": "+919900000001"},
        {"_id": creator_oid, "role": "creator", "name": "Asha",
         "phone": "+919900000002"},
    ])
    await db.brand_profiles.insert_one(
        {"user_id": brand_oid, "business_name": "Ninth Street", "verified": True,
         "verified_at": _now()}
    )
    await db.creator_profiles.insert_one(
        {"user_id": creator_oid, "name": "Asha", "verification_status": "verified"}
    )
    await db.campaigns.insert_one({
        "_id": campaign_oid, "brand_id": brand_oid, "brand_name": "Ninth Street",
        "title": "Spring range", "status": "open", "execution_owner": "brand",
        "compensation_type": compensation, "budget_per_creator": 9000,
        "creators_needed": 3,
        "deliverable_items": [{"type": "reel", "quantity": 2}],
        "campaign_type": "personal_table",
        "start_date": DAY, "end_date": DAY + timedelta(days=7),
        "required_disclosure": "ad",
        "usage_rights": usage,
        **({"usage_duration_days": 90} if usage == "paid_usage" else {}),
        **({"barter_description": "Dinner for two, on the house."}
           if compensation == "barter" else {}),
    })
    await db.collaborations.insert_one(
        {"_id": collab_oid, "campaign_id": campaign_oid, "creator_id": creator_oid,
         "state": "verified", "quoted_rate": 9000, "state_since": _now()}
    )
    brand = await db.users.find_one({"_id": brand_oid})
    return {
        "brand": {**brand, "_id": str(brand_oid)},
        "creator": {"_id": str(creator_oid), "role": "creator", "name": "Asha"},
        "collab_id": str(collab_oid), "collab_oid": collab_oid,
        "campaign_oid": campaign_oid,
    }


class TestTheSnapshotIsTakenAtAcceptance:
    def test_accepting_freezes_every_term(self):
        async def body(db):
            s = await _accepted_scene(db)
            await server.brand_accept_applicant(
                s["collab_id"], server.BrandAcceptPayload(), s["brand"]
            )
            return await db.collaborations.find_one({"_id": s["collab_oid"]})

        terms = run(body)["terms"]
        assert terms["deliverables"] == "2 reels"
        assert terms["money"]["agreed_amount"] == 9000
        assert terms["usage"]["kind"] == "paid_usage"
        assert terms["disclosure"]["label"] == server.DISCLOSURE_LABELS["ad"]
        assert terms["cancellation_terms"] == server.CANCELLATION_TERMS
        assert terms["issued_at"] is not None
        assert terms["accepted_at"] is None

    def test_editing_the_campaign_afterwards_does_not_move_it(self):
        """**The whole point.** Every term lives on something editable, so a
        record that tracked the campaign would be a copy of the campaign —
        which is the thing that was already no use in a dispute."""

        async def body(db):
            s = await _accepted_scene(db)
            await server.brand_accept_applicant(
                s["collab_id"], server.BrandAcceptPayload(), s["brand"]
            )
            # The brand rewrites the brief underneath the arrangement.
            await db.campaigns.update_one(
                {"_id": s["campaign_oid"]},
                {"$set": {
                    "usage_rights": "full_buyout",
                    "usage_duration_days": None,
                    "required_disclosure": "gifted",
                    "deliverable_items": [{"type": "story", "quantity": 9}],
                }},
            )
            collab = await db.collaborations.find_one({"_id": s["collab_oid"]})
            campaign = await db.campaigns.find_one({"_id": s["campaign_oid"]})
            return collab["terms"], campaign

        terms, campaign = run(body)
        assert campaign["usage_rights"] == "full_buyout"
        # And the frozen copy is untouched.
        assert terms["usage"]["kind"] == "paid_usage"
        assert terms["disclosure"]["code"] == "ad"
        assert terms["deliverables"] == "2 reels"

    def test_a_second_issue_cannot_overwrite_an_accepted_snapshot(self):
        """Idempotent by precondition rather than by checking first, so two
        accepts racing produce one snapshot."""

        async def body(db):
            s = await _accepted_scene(db)
            await server.brand_accept_applicant(
                s["collab_id"], server.BrandAcceptPayload(), s["brand"]
            )
            first = (await db.collaborations.find_one({"_id": s["collab_oid"]}))["terms"]
            await server.creator_accept_terms(s["collab_id"], s["creator"])
            collab = await db.collaborations.find_one({"_id": s["collab_oid"]})
            # A re-issue with a rewritten campaign must change nothing.
            await server._issue_terms_snapshot(
                collab, {"title": "Something else", "usage_rights": "full_buyout"}
            )
            return first, await db.collaborations.find_one({"_id": s["collab_oid"]})

        first, after = run(body)
        assert after["terms"]["usage"]["kind"] == first["usage"]["kind"]
        assert after["terms"]["campaign_title"] == first["campaign_title"]
        assert after["terms"]["accepted_at"] is not None

    def test_a_barter_arrangement_records_a_description_and_not_a_zero(self):
        """`0` on a barter row reads as "agreed, nothing" on every surface that
        shows money, which is the one reading that is definitely wrong."""
        money = server._terms_money(
            {"compensation_type": "barter",
             "barter_description": "Dinner for two, on the house."},
            {"agreed_amount": 0},
        )
        assert money["agreed_amount"] is None
        assert "Dinner for two" in money["description"]

    def test_barter_with_no_description_still_says_something_useful(self):
        money = server._terms_money({"compensation_type": "barter"}, {})
        assert money["agreed_amount"] is None
        assert money["description"]


class TestTheCreatorAccepts:
    def test_one_tap_records_a_timestamp(self):
        async def body(db):
            s = await _accepted_scene(db)
            await server.brand_accept_applicant(
                s["collab_id"], server.BrandAcceptPayload(), s["brand"]
            )
            out = await server.creator_accept_terms(s["collab_id"], s["creator"])
            return out, await db.collaborations.find_one({"_id": s["collab_oid"]})

        out, collab = run(body)
        assert out["terms"]["accepted"] is True
        assert collab["terms"]["accepted_at"] is not None
        assert collab["terms"]["accepted_by"] is not None

    def test_accepting_twice_does_not_move_the_timestamp(self):
        """Somebody tapping again on a slow connection must not end up with a
        later acknowledgement than the one they actually made."""

        async def body(db):
            s = await _accepted_scene(db)
            await server.brand_accept_applicant(
                s["collab_id"], server.BrandAcceptPayload(), s["brand"]
            )
            await server.creator_accept_terms(s["collab_id"], s["creator"])
            first = (await db.collaborations.find_one({"_id": s["collab_oid"]}))["terms"][
                "accepted_at"
            ]
            await server.creator_accept_terms(s["collab_id"], s["creator"])
            second = (await db.collaborations.find_one({"_id": s["collab_oid"]}))[
                "terms"
            ]["accepted_at"]
            return first, second

        first, second = run(body)
        assert first == second

    def test_a_stale_read_is_stopped_by_the_precondition_not_the_early_return(self):
        """**Two guards, and only one is exercised by tapping twice.**

        `creator_accept_terms` reads the row, returns early if it is already
        accepted, and only then updates under `terms.accepted_at: None`. The
        sequential test above is answered entirely by the early return —
        delete the precondition and it stays green. The filter exists for the
        case the read cannot see: two requests in flight, the second one's read
        landing before the first one's write.

        `asyncio.gather` will not produce that here (mongomock resolves without
        yielding), so the race is staged directly: the handler is handed a
        stale, unaccepted document while the stored row already carries a
        timestamp. That is exactly what the losing request sees, and the
        precondition is the only thing between it and a later acknowledgement
        overwriting the real one.
        """

        async def body(db):
            s = await _accepted_scene(db)
            await server.brand_accept_applicant(
                s["collab_id"], server.BrandAcceptPayload(), s["brand"]
            )
            await server.creator_accept_terms(s["collab_id"], s["creator"])
            real = await db.collaborations.find_one({"_id": s["collab_oid"]})
            first = real["terms"]["accepted_at"]

            stale = {**real, "terms": {**real["terms"], "accepted_at": None}}
            original = server._own_collab_or_404

            async def hands_back_a_stale_row(collab_id, user):
                return stale

            server._own_collab_or_404 = hands_back_a_stale_row
            try:
                await server.creator_accept_terms(s["collab_id"], s["creator"])
            finally:
                server._own_collab_or_404 = original
            after = await db.collaborations.find_one({"_id": s["collab_oid"]})
            return first, after["terms"]["accepted_at"]

        first, second = run(body)
        assert first == second, "the loser overwrote the real acknowledgement"

    def test_somebody_elses_collaboration_is_a_404(self):
        async def body(db):
            s = await _accepted_scene(db)
            await server.brand_accept_applicant(
                s["collab_id"], server.BrandAcceptPayload(), s["brand"]
            )
            stranger = {"_id": str(ObjectId()), "role": "creator", "name": "Nobody"}
            with pytest.raises(HTTPException) as err:
                await server.creator_accept_terms(s["collab_id"], stranger)
            collab = await db.collaborations.find_one({"_id": s["collab_oid"]})
            return err.value, collab

        exc, collab = run(body)
        assert exc.status_code == 404
        assert collab["terms"]["accepted_at"] is None

    def test_there_is_nothing_to_accept_before_acceptance(self):
        async def body(db):
            s = await _accepted_scene(db)
            with pytest.raises(HTTPException) as err:
                await server.creator_accept_terms(s["collab_id"], s["creator"])
            return err.value

        assert run(body).status_code == 409

    def test_only_a_creator_may_accept(self):
        """The acknowledgement is the creator's. A brand tapping it would be
        the brand agreeing with itself."""
        import inspect
        from fastapi import params

        for p in inspect.signature(server.creator_accept_terms).parameters.values():
            dep = p.default
            if isinstance(dep, params.Depends):
                guard = dep.dependency

                async def go(role):
                    try:
                        await guard({"_id": str(ObjectId()), "role": role})
                        return True
                    except HTTPException:
                        return False

                global LOOP
                if LOOP is None:
                    LOOP = asyncio.new_event_loop()
                assert LOOP.run_until_complete(go("creator")) is True
                for role in ("brand_manager", "admin", "campaign_manager"):
                    assert LOOP.run_until_complete(go(role)) is False, role
                return
        raise AssertionError("no role guard on creator_accept_terms")


class TestMediationReadsTheRecord:
    def test_the_dispute_queue_carries_the_frozen_terms(self):
        """The whole argument for freezing them: this row can carry what was
        agreed, rather than what the campaign says today."""

        async def body(db):
            s = await _accepted_scene(db)
            await server.brand_accept_applicant(
                s["collab_id"], server.BrandAcceptPayload(), s["brand"]
            )
            await db.collaborations.update_one(
                {"_id": s["collab_oid"]}, {"$set": {"state": "content_submitted"}}
            )
            await server.raise_dispute(
                s["collab_id"],
                server.DisputePayload(reason="They want it as an ad for a year."),
                s["creator"],
            )
            return await server.list_disputes("open", ADMIN)

        payload = run(body)
        row = payload["disputes"][0]
        assert row["terms"]["usage"]["kind"] == "paid_usage"
        assert row["terms"]["money"]["agreed_amount"] == 9000
        assert row["terms"]["cancellation_terms"]

    def test_the_snapshot_never_leaks_the_accepting_creators_id(self):
        """`accepted_by` is an internal join, and the dispute queue is a
        brand-visible shape by the same rule as everything else here."""
        served = server._serialize_terms(
            {"terms": {"accepted_by": ObjectId(), "issued_at": _now(),
                       "accepted_at": _now(), "money": {}}}
        )
        assert "accepted_by" not in served
        assert served["accepted"] is True

    def test_no_snapshot_serialises_as_none_rather_than_an_empty_shell(self):
        """Every collaboration that predates this has none, and an empty card
        headed "what was agreed" reads as "nothing was"."""
        assert server._serialize_terms({}) is None
        assert server._serialize_terms(None) is None


class TestTheVocabulariesAgreeWithTheFrontend:
    """Two copies of a vocabulary is how a form offers an option the API
    rejects — the same drift test `followerTiers.js` and `shootWindows.js`
    carry."""

    def _mirror(self):
        path = (
            server.Path(server.__file__).resolve().parents[1]
            if hasattr(server, "Path")
            else None
        )
        from pathlib import Path as P

        return (P(server.__file__).resolve().parents[1] / "frontend" / "src" / "lib"
                / "campaignTerms.js").read_text()

    def test_the_disclosure_labels_match(self):
        js = self._mirror()
        for key, label in server.DISCLOSURE_LABELS.items():
            assert f"{key}:" in js, key
            assert label in js, label

    def test_the_usage_grants_match(self):
        js = self._mirror()
        for key, label in server.USAGE_RIGHTS.items():
            assert f"{key}:" in js, key
            assert label in js, label

    def test_the_defaults_match(self):
        js = self._mirror()
        assert f"DEFAULT_DISCLOSURE = '{server.DEFAULT_DISCLOSURE}'" in js
        assert f"DEFAULT_USAGE_RIGHTS = '{server.DEFAULT_USAGE_RIGHTS}'" in js

    def test_which_grant_needs_a_period_matches(self):
        js = self._mirror()
        for kind in server.USAGE_NEEDS_DURATION:
            assert f"'{kind}'" in js.split("USAGE_NEEDS_DURATION")[1][:120], kind


class TestTheSurfacesExist:
    """A backend flow with no UI is not shipped, whatever the tests say."""

    def _read(self, *parts):
        from pathlib import Path as P

        return (P(server.__file__).resolve().parents[1] / "frontend" / "src"
                / P(*parts)).read_text()

    def test_the_brief_shows_both_before_the_apply_button(self):
        page = self._read("pages", "CampaignDetail.jsx")
        assert "BriefTerms" in page
        assert page.index("BriefTerms") < page.index("detail-apply-btn")

    def test_the_application_page_shows_the_terms_and_the_checks(self):
        page = self._read("components", "application", "ApplicationDetail.jsx")
        assert "TermsCard" in page
        assert "DisclosureChecks" in page

    def test_the_creator_accept_route_has_a_caller(self):
        card = self._read("components", "campaign", "CampaignTerms.jsx")
        assert "/accept-terms" in card

    def test_the_card_is_mounted_where_the_creator_can_actually_reach_it(self):
        """**The gap this nearly shipped with.** The shared application page is
        mounted at /admin, /brand and /manager and at no creator route, so a
        terms card that lived only there would be a card the one party who has
        to accept it can never open — an endpoint with a caller nobody can
        press. Found in a browser, not by a test, which is why there is one
        now.
        """
        creator_card = self._read("components", "creator", "ActiveCampaigns.jsx")
        assert "TermsCard" in creator_card
        assert "can_accept_terms" in creator_card

    def test_the_creators_own_row_carries_the_terms(self):
        """A card mounted on a row that does not carry the data is the same
        absence one level down."""
        import inspect

        src = inspect.getsource(server._serialize_collab_row)
        assert '"terms": _serialize_terms(collab)' in src
        assert '"can_accept_terms"' in src

    def test_both_review_points_send_the_confirmation(self):
        draft = self._read("components", "application", "DraftReview.jsx")
        assert "disclosure_confirmed: true" in draft
        board = self._read("pages", "BrandCampaignApplicants.jsx")
        assert "disclosure_confirmed: true" in board

    def test_the_post_form_asks_for_both(self):
        form = self._read("pages", "PostCampaign.jsx")
        assert "pc-disclosure" in form
        assert "pc-usage" in form
        assert "usage_duration_days" in form
