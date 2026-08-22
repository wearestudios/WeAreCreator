"""Taking the sequential waits out, without taking the checks out.

Five of these six changes remove a wait. That is only an improvement if what
was being waited *for* still happens — so most of what is pinned here is the
thing that must not have moved: a held application is on no board, an
unverified brand still cannot publish, a bulk decision is still fifty audited
decisions, and a trusted brand's brief can still be pulled.

The sixth is a fix rather than a change: the two document endpoints existed for
months with no caller, so verification was a judgement made from a filename.
"""

from __future__ import annotations

import asyncio
import inspect
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException
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
        db = AsyncMongoMockClient()["leaner"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return LOOP.run_until_complete(go())


ADMIN = {"_id": str(ObjectId()), "role": "admin", "name": "Admin"}


def _now():
    return datetime.now(timezone.utc)


async def _scene(db, *, creator_status="pending", submitted=True, verified_brand=True,
                 needed=2, requires_slot_confirmation=False):
    brand, creator, campaign = ObjectId(), ObjectId(), ObjectId()
    await db.users.insert_many([
        {"_id": brand, "role": "brand_manager", "name": "Riya", "brand_id": brand,
         "phone": "+919900000004"},
        {"_id": creator, "role": "creator", "name": "Asha", "phone": "+919900000001"},
    ])
    await db.brand_profiles.insert_one(
        {"user_id": brand, "business_name": "Toit", "verified": verified_brand,
         "verified_at": _now() if verified_brand else None,
         "verification_state": "verified" if verified_brand else "pending_verification"}
    )
    await db.creator_profiles.insert_one({
        "user_id": creator, "name": "Asha", "verification_status": creator_status,
        "platforms": ["instagram"],
        **({"submitted_for_review_at": _now() - timedelta(days=1)} if submitted else {}),
        **({"verified_at": _now()} if creator_status == "verified" else {}),
    })
    await db.campaigns.insert_one({
        "_id": campaign, "brand_id": brand, "title": "Tasting", "status": "open",
        "creators_needed": needed, "execution_owner": "brand",
        "requires_slot_confirmation": requires_slot_confirmation,
        "campaign_type": "personal_table",
        "start_date": _now() - timedelta(days=1), "end_date": _now() + timedelta(days=20),
    })
    return {
        "brand_oid": brand, "creator_oid": creator, "campaign_oid": campaign,
        "creator": {"_id": str(creator), "role": "creator", "name": "Asha"},
        "brand": {"_id": str(brand), "role": "brand_manager", "name": "Riya",
                  "brand_id": brand},
        "campaign_id": str(campaign),
    }


# ---------------------------------------------------------------------------
# 1. Documents an admin can actually read
# ---------------------------------------------------------------------------


class TestTheDocumentsAreOnTheScreen:
    """Both endpoints existed and neither had a caller, so an admin verifying
    a brand could see that a GST certificate had been uploaded and could not
    read it."""

    def test_the_page_renders_a_document_panel(self):
        page = no_comments(FRONTEND / "components/admin/BrandDetailPage.jsx")
        assert "<BrandDocuments" in page

    def test_it_fetches_the_file_and_can_review_it(self):
        src = no_comments(FRONTEND / "components/admin/BrandDocuments.jsx")
        assert "/documents/${doc.id}" in src, "no caller for the download route"
        assert "/documents/${doc.id}/review" in src, "no caller for the review route"

    def test_the_bytes_come_through_the_authenticated_client(self):
        """**Not an `<iframe src>` at the API.** The cookie is `SameSite=None`,
        so a bare cross-origin link rides along in production and silently does
        not on a plain-http laptop — the worst kind of difference. Going
        through `api` is the same auth as everything else, and the object URL
        dies with the panel, which is what `Cache-Control: no-store` asked
        for."""
        src = no_comments(FRONTEND / "components/admin/BrandDocuments.jsx")
        assert 'responseType: "blob"' in src
        assert "createObjectURL" in src
        assert "revokeObjectURL" in src, "the bytes would outlive the panel"
        assert "API_BASE" not in src, "a bare cross-origin link is not authenticated"

    def test_both_pdfs_and_images_render_inline(self):
        src = no_comments(FRONTEND / "components/admin/BrandDocuments.jsx")
        assert "<iframe" in src and "<img" in src

    def test_a_rejection_needs_a_note_before_the_button_works(self):
        """The route refuses one without a reason; the button agrees with it
        rather than producing a 422."""
        src = no_comments(FRONTEND / "components/admin/BrandDocuments.jsx")
        assert "!note.trim()" in src

    def test_a_purged_document_says_so_rather_than_reading_as_a_fault(self):
        src = no_comments(FRONTEND / "components/admin/BrandDocuments.jsx")
        assert "410" in src and "retention" in src


# ---------------------------------------------------------------------------
# 2. Applying before verification
# ---------------------------------------------------------------------------


class TestHoldingAnApplication:
    def test_a_submitted_creator_may_pitch_and_it_is_held(self):
        async def body(db):
            s = await _scene(db)
            out = await server.apply_to_campaign(
                s["campaign_id"],
                server.ApplyPayload(pitch="This is exactly my area, happy to.", quoted_rate=5000),
                s["creator"],
            )
            return out, await db.collaborations.count_documents({})

        out, collabs = run(body)
        assert out["held"] is True
        assert collabs == 0, "a held pitch is not a collaboration"

    def test_a_half_finished_profile_still_cannot_pitch(self):
        """Not a wall we removed by accident: a brand reading a shortlist a
        week later should not find somebody who never filled their profile in,
        and holding a pitch for a creator who has not asked to be reviewed is
        holding it forever."""

        async def body(db):
            s = await _scene(db, submitted=False)
            with pytest.raises(HTTPException) as err:
                await server.apply_to_campaign(
                    s["campaign_id"],
                    server.ApplyPayload(pitch="Let me have a go at this one.", quoted_rate=5000),
                    s["creator"],
                )
            return err.value

        assert run(body).status_code == 403

    def test_a_rejected_creator_cannot_pitch(self):
        async def body(db):
            s = await _scene(db, creator_status="rejected")
            with pytest.raises(HTTPException) as err:
                await server.apply_to_campaign(
                    s["campaign_id"],
                    server.ApplyPayload(pitch="Let me have a go at this one.", quoted_rate=5000),
                    s["creator"],
                )
            return err.value

        assert run(body).status_code == 403

    def test_a_suspended_creator_is_refused_rather_than_held(self):
        """Holding a pitch for somebody who is suspended is promising them
        something that is not coming."""

        async def body(db):
            s = await _scene(db)
            await db.users.update_one(
                {"_id": s["creator_oid"]},
                {"$set": {"status": "suspended", "suspension_reason": "No-shows."}},
            )
            with pytest.raises(HTTPException) as err:
                await server.apply_to_campaign(
                    s["campaign_id"],
                    server.ApplyPayload(pitch="Let me have a go at this one.", quoted_rate=5000),
                    s["creator"],
                )
            return err.value

        err = run(body)
        assert err.status_code == 403
        assert err.detail["code"] == "suspended"

    def test_a_held_pitch_is_on_no_board_and_takes_no_seat(self):
        """The whole reason it lives in its own collection: a new state on
        `collaborations` would have to be excluded from forty-five reads, and
        the one that got missed would be an unchecked creator on a brand's
        shortlist."""

        async def body(db):
            s = await _scene(db, needed=1)
            await server.apply_to_campaign(
                s["campaign_id"],
                server.ApplyPayload(pitch="This is exactly my area, happy to.", quoted_rate=5000),
                s["creator"],
            )
            filled = (await server._filled_counts_for([s["campaign_oid"]])).get(
                s["campaign_oid"], 0
            )
            notified = await db.notifications.count_documents({"user_id": s["brand_oid"]})
            return filled, notified

        filled, notified = run(body)
        assert filled == 0, "a held pitch took a seat"
        assert notified == 0, "the brand was told about an unchecked creator"

    def test_pitching_twice_is_refused_the_way_a_duplicate_is(self):
        async def body(db):
            s = await _scene(db)
            payload = server.ApplyPayload(
                pitch="This is exactly my area, happy to.", quoted_rate=5000
            )
            await server.apply_to_campaign(s["campaign_id"], payload, s["creator"])
            with pytest.raises(HTTPException) as err:
                await server.apply_to_campaign(s["campaign_id"], payload, s["creator"])
            return err.value

        err = run(body)
        assert err.status_code == 409
        assert err.detail["code"] == "already_held"


class TestReleasingIt:
    def test_verification_puts_every_held_pitch_in(self):
        async def body(db):
            s = await _scene(db)
            await server.apply_to_campaign(
                s["campaign_id"],
                server.ApplyPayload(pitch="This is exactly my area, happy to.", quoted_rate=5000),
                s["creator"],
            )
            await server._set_creator_verification(
                str(s["creator_oid"]), "verified", ADMIN, None
            )
            collab = await db.collaborations.find_one({})
            held = await db.held_applications.find_one({})
            return collab, held

        collab, held = run(body)
        assert collab and collab["state"] == "applied"
        assert collab["pitch"].startswith("This is exactly"), "the pitch was not carried"
        assert collab["reference"].startswith("COL-")
        assert held["state"] == "released"

    def test_the_release_goes_through_the_one_application_helper(self):
        """A second implementation would be a second definition of what an
        application is — the capacity check, the duplicate refusal and the
        routing are part of that definition, not decoration."""
        assert "_create_application(" in inspect.getsource(
            server._release_held_applications
        )
        assert "_create_application(" in inspect.getsource(server.apply_to_campaign)

    def test_the_brand_is_told_at_release_and_not_before(self):
        async def body(db):
            s = await _scene(db)
            await server.apply_to_campaign(
                s["campaign_id"],
                server.ApplyPayload(pitch="This is exactly my area, happy to.", quoted_rate=5000),
                s["creator"],
            )
            before = await db.notifications.count_documents({"user_id": s["brand_oid"]})
            await server._set_creator_verification(
                str(s["creator_oid"]), "verified", ADMIN, None
            )
            after = await db.notifications.count_documents({"user_id": s["brand_oid"]})
            return before, after

        before, after = run(body)
        assert before == 0 and after == 1

    def test_a_brief_that_filled_while_they_waited_is_said_rather_than_silent(self):
        """The ordinary outcome of having waited, and the honest thing is to
        tell them rather than to fail the verification over it."""

        async def body(db):
            s = await _scene(db, needed=1)
            await server.apply_to_campaign(
                s["campaign_id"],
                server.ApplyPayload(pitch="This is exactly my area, happy to.", quoted_rate=5000),
                s["creator"],
            )
            # Somebody else takes the only seat.
            await db.collaborations.insert_one({
                "campaign_id": s["campaign_oid"], "creator_id": ObjectId(),
                "state": "accepted", "created_at": _now(),
            })
            await server._set_creator_verification(
                str(s["creator_oid"]), "verified", ADMIN, None
            )
            held = await db.held_applications.find_one({})
            told = await db.notifications.find(
                {"user_id": s["creator_oid"], "event": "held_application_withdrawn"}
            ).to_list(length=5)
            return held, told

        held, told = run(body)
        assert held["state"] == "withdrawn"
        assert held["reason"], "no reason on a pitch that did not go in"
        assert told, "the creator was not told"

    def test_a_rejection_takes_the_held_pitches_back(self):
        async def body(db):
            s = await _scene(db)
            await server.apply_to_campaign(
                s["campaign_id"],
                server.ApplyPayload(pitch="This is exactly my area, happy to.", quoted_rate=5000),
                s["creator"],
            )
            await server._set_creator_verification(
                str(s["creator_oid"]), "rejected", ADMIN, "Handle doesn't match the name."
            )
            held = await db.held_applications.find_one({})
            return held, await db.collaborations.count_documents({})

        held, collabs = run(body)
        assert held["state"] == "declined"
        assert "Handle" in (held["reason"] or "")
        assert collabs == 0

    def test_the_creator_can_take_one_back_and_nobody_elses(self):
        async def body(db):
            s = await _scene(db)
            out = await server.apply_to_campaign(
                s["campaign_id"],
                server.ApplyPayload(pitch="This is exactly my area, happy to.", quoted_rate=5000),
                s["creator"],
            )
            stranger = {"_id": str(ObjectId()), "role": "creator", "name": "Someone"}
            with pytest.raises(HTTPException) as err:
                await server.cancel_held_application(out["id"], stranger)
            refusal = err.value
            await server.cancel_held_application(out["id"], s["creator"])
            return refusal, await db.held_applications.find_one({})

        refusal, held = run(body)
        # A 404, never a 403 — the same rule every other ownership refusal here
        # follows.
        assert refusal.status_code == 404
        assert held["state"] == "withdrawn"

    def test_the_creator_is_shown_what_is_outstanding(self):
        block = server._verification_outstanding(
            {"submitted_for_review_at": _now(), "platforms": ["instagram"]}
        )
        assert block["waiting_on"] in ("weare", "you")
        assert block["message"]

    def test_the_panel_is_mounted_and_says_they_need_do_nothing(self):
        page = no_comments(FRONTEND / "pages/Dashboard.jsx")
        assert "<HeldApplications" in page
        panel = no_comments(FRONTEND / "components/creator/HeldApplications.jsx")
        assert "/creator/held-applications/" in panel

    def test_the_campaign_page_reads_both_flags_the_endpoint_sends(self):
        """`apply_holds` and `outstanding` shipped with no caller for a while.

        The endpoint decides both, and the whole value of holding a pitch is
        that the creator is *told* — before pressing Apply, that it will wait
        with us, and afterwards, that they need not send it again. A flag
        nothing renders is the wall back with an extra database collection.
        """
        page = no_comments(FRONTEND / "pages/CampaignDetail.jsx")
        assert "campaign.apply_holds" in page
        assert "detail-apply-holds" in page
        # The applied card has to distinguish held from on-the-board, or it
        # tells somebody their pitch is with the brand when it is with us.
        assert 'application.state === "held"' in page
        assert "outstanding={campaign.outstanding}" in page


# ---------------------------------------------------------------------------
# 3. Drafting before verification
# ---------------------------------------------------------------------------


class TestAnUnverifiedBrandCanBuild:
    def test_a_draft_needs_no_verification_and_a_submission_does(self):
        src = inspect.getsource(server.create_brand_campaign)
        gate = src[src.index("BRAND_SETTABLE_CAMPAIGN_STATUSES"):]
        assert "_verified_brand_or_403" in gate
        # And it is guarded by the status, not applied to every write.
        assert "if payload.status == CAMPAIGN_REVIEW_STATUS:" in gate

    def test_the_form_says_what_is_outstanding_before_the_button_is_pressed(self):
        """The refusal was always correct and always arrived as a toast, after
        the work, naming the state rather than the fix."""
        page = no_comments(FRONTEND / "pages/PostCampaign.jsx")
        assert "<PublishGate" in page
        gate = no_comments(FRONTEND / "components/brand/PublishGate.jsx")
        assert "missing_fields" in gate, "the outstanding fields are not listed"
        for state in ("rejected", "pending_verification"):
            assert state in gate, f"no distinct next step for {state}"

    def test_the_publish_button_is_disabled_rather_than_allowed_and_refused(self):
        page = no_comments(FRONTEND / "pages/PostCampaign.jsx")
        block = page[page.index('data-testid="pc-publish-btn"'):]
        assert 'verification.state !== "verified"' in block[:500]

    def test_saving_a_draft_is_not_disabled_by_it(self):
        """Writing the brief is not the part that has to wait on us."""
        page = no_comments(FRONTEND / "pages/PostCampaign.jsx")
        block = page[page.index('data-testid="pc-save-draft-btn"'):]
        head = block[: block.index("</Button>")]
        assert "verification" not in head


# ---------------------------------------------------------------------------
# 4. Optional slot confirmation
# ---------------------------------------------------------------------------


class TestSlotConfirmationIsOptional:
    def test_absent_means_off(self):
        assert server._requires_slot_confirmation({}) is False
        assert server._requires_slot_confirmation(None) is False
        assert server._requires_slot_confirmation(
            {"requires_slot_confirmation": True}
        ) is True

    def test_a_booking_is_confirmed_immediately_by_default(self):
        async def body(db):
            s = await _scene(db, creator_status="verified")
            collab = ObjectId()
            slot = ObjectId()
            starts = _now() + timedelta(days=3)
            await db.collaborations.insert_one({
                "_id": collab, "campaign_id": s["campaign_oid"],
                "creator_id": s["creator_oid"], "state": "commercial_agreed",
                "agreed_amount": 5000.0,
            })
            await db.campaign_slots.insert_one({
                "_id": slot, "campaign_id": s["campaign_oid"], "starts_at": starts,
                "ends_at": starts + timedelta(hours=2), "capacity": 2, "booked_count": 0,
            })
            campaign = await db.campaigns.find_one({"_id": s["campaign_oid"]})
            out = await server._claim_slot(
                s["creator"],
                await db.collaborations.find_one({"_id": collab}),
                campaign,
                await db.campaign_slots.find_one({"_id": slot}),
            )
            return out, await db.collaborations.find_one({"_id": collab})

        out, collab = run(body)
        assert out["slot_confirmed"] is True
        assert collab["slot_confirmed_at"] is not None
        assert server._slot_confirmed(collab) is True

    def test_with_the_toggle_on_it_still_waits_for_an_answer(self):
        async def body(db):
            s = await _scene(db, creator_status="verified", requires_slot_confirmation=True)
            collab, slot = ObjectId(), ObjectId()
            starts = _now() + timedelta(days=3)
            await db.collaborations.insert_one({
                "_id": collab, "campaign_id": s["campaign_oid"],
                "creator_id": s["creator_oid"], "state": "commercial_agreed",
            })
            await db.campaign_slots.insert_one({
                "_id": slot, "campaign_id": s["campaign_oid"], "starts_at": starts,
                "ends_at": starts + timedelta(hours=2), "capacity": 2, "booked_count": 0,
            })
            out = await server._claim_slot(
                s["creator"],
                await db.collaborations.find_one({"_id": collab}),
                await db.campaigns.find_one({"_id": s["campaign_oid"]}),
                await db.campaign_slots.find_one({"_id": slot}),
            )
            return out, await db.collaborations.find_one({"_id": collab})

        out, collab = run(body)
        assert out["slot_confirmed"] is False
        assert collab["slot_confirmed_at"] is None
        assert server._slot_confirmed(collab) is False

    def test_the_answer_is_written_at_booking_rather_than_read_per_surface(self):
        """Eight surfaces read `_slot_confirmed` and most have no campaign in
        hand. Writing the answer at the one place that does keeps a single
        reader — and makes the record honest: the runner agreed in advance by
        not asking to be asked."""
        assert "campaign" not in inspect.signature(server._slot_confirmed).parameters
        assert "_requires_slot_confirmation" in inspect.getsource(server._claim_slot)

    def test_a_pre_handshake_booking_still_reads_as_confirmed(self):
        """The migration rule that must survive: reopening every old booking
        as pending would put a decision in front of a manager for shoots that
        already happened."""
        assert server._slot_confirmed({}) is True
        assert server._slot_confirmed({"slot_booked_at": _now()}) is False

    def test_the_form_offers_the_toggle(self):
        page = no_comments(FRONTEND / "pages/PostCampaign.jsx")
        assert "requires_slot_confirmation" in page
        assert 'data-testid="pc-slot-confirmation"' in page


# ---------------------------------------------------------------------------
# 5. Trusted brands
# ---------------------------------------------------------------------------


class TestTrustedBrands:
    def test_a_new_brand_is_not_trusted(self):
        async def body(db):
            s = await _scene(db)
            profile = await db.brand_profiles.find_one({"user_id": s["brand_oid"]})
            return await server._brand_is_trusted(profile)

        assert run(body) is False

    def test_enough_clean_approvals_earns_it(self):
        async def body(db):
            s = await _scene(db)
            for _ in range(3):
                await db.audit_log.insert_one(
                    {"action": "campaign.approve", "brand_id": s["brand_oid"]}
                )
            profile = await db.brand_profiles.find_one({"user_id": s["brand_oid"]})
            return await server._brand_is_trusted(profile)

        assert run(body) is True

    def test_a_single_rejection_ends_it(self):
        """Not a ratio. One brief we had to send back is one we are glad we
        read, and "mostly fine" is not the standard for skipping the read."""

        async def body(db):
            s = await _scene(db)
            for _ in range(9):
                await db.audit_log.insert_one(
                    {"action": "campaign.approve", "brand_id": s["brand_oid"]}
                )
            await db.audit_log.insert_one(
                {"action": "campaign.reject", "brand_id": s["brand_oid"]}
            )
            profile = await db.brand_profiles.find_one({"user_id": s["brand_oid"]})
            return await server._brand_is_trusted(profile)

        assert run(body) is False

    def test_an_unverified_brand_is_never_trusted(self):
        async def body(db):
            s = await _scene(db, verified_brand=False)
            for _ in range(9):
                await db.audit_log.insert_one(
                    {"action": "campaign.approve", "brand_id": s["brand_oid"]}
                )
            profile = await db.brand_profiles.find_one({"user_id": s["brand_oid"]})
            return await server._brand_is_trusted(profile)

        assert run(body) is False

    def test_a_revocation_outlives_the_count(self):
        """Trust is otherwise arithmetic, so a revocation the count could
        overturn would be a decision with an expiry date nobody chose."""

        async def body(db):
            s = await _scene(db)
            for _ in range(9):
                await db.audit_log.insert_one(
                    {"action": "campaign.approve", "brand_id": s["brand_oid"]}
                )
            await server.revoke_brand_trust(
                str(s["brand_oid"]),
                server.TrustPayload(reason="Two briefs needed edits after publication."),
                ADMIN,
            )
            profile = await db.brand_profiles.find_one({"user_id": s["brand_oid"]})
            return await server._brand_is_trusted(profile)

        assert run(body) is False

    def test_a_trusted_brands_brief_publishes_on_submission(self):
        async def body(db):
            s = await _scene(db)
            for _ in range(3):
                await db.audit_log.insert_one(
                    {"action": "campaign.approve", "brand_id": s["brand_oid"]}
                )
            out = await server.create_brand_campaign(
                server.PostCampaignPayload(
                    title="Second tasting", brief="B" * 40,
                    deliverable_items=[{"type": "reel", "quantity": 1}],
                    budget_per_creator=8000, category="fnb", area="Indiranagar",
                    creators_needed=2, campaign_type="personal_table",
                    compensation_type="fixed", status="pending_review",
                    start_date=_now() - timedelta(days=1),
                    end_date=_now() + timedelta(days=20),
                ),
                s["brand"],
            )
            doc = await db.campaigns.find_one({"title": "Second tasting"})
            return out, doc

        out, doc = run(body)
        assert doc["status"] == "open", "a trusted brand's brief still waited"
        assert doc["auto_published_at"]
        # And it did *not* claim somebody reviewed it.
        assert not doc.get("reviewed_at")

    def test_an_untrusted_brands_brief_still_waits(self):
        async def body(db):
            s = await _scene(db)
            await server.create_brand_campaign(
                server.PostCampaignPayload(
                    title="First tasting", brief="B" * 40,
                    deliverable_items=[{"type": "reel", "quantity": 1}],
                    budget_per_creator=8000, category="fnb", area="Indiranagar",
                    creators_needed=2, campaign_type="personal_table",
                    compensation_type="fixed", status="pending_review",
                    start_date=_now() - timedelta(days=1),
                    end_date=_now() + timedelta(days=20),
                ),
                s["brand"],
            )
            return await db.campaigns.find_one({"title": "First tasting"})

        assert run(body)["status"] == "pending_review"

    def test_auto_publishing_is_audited_as_itself(self):
        """Not as `campaign.approve`. The trust count reads that line, and a
        brand approving its own campaigns into the count that decides whether
        it may approve its own campaigns is a loop."""
        src = inspect.getsource(server.create_brand_campaign)
        assert '"campaign.auto_publish"' in src
        assert '"campaign.approve"' not in src

    def test_the_spot_check_queue_holds_them_without_blocking(self):
        src = inspect.getsource(server.list_campaigns_for_review)
        assert "auto_published_at" in src and "spot_checked_at" in src
        assert '"auto_published"' in src, "the row cannot tell the two kinds apart"

    def test_a_spot_check_can_pull_a_live_brief(self):
        """The only thing that makes "flagged rather than blocking" a check."""

        async def body(db):
            s = await _scene(db)
            await db.campaigns.update_one(
                {"_id": s["campaign_oid"]},
                {"$set": {"auto_published_at": _now(), "spot_checked_at": None}},
            )
            await server.reject_campaign(
                s["campaign_id"],
                server.DecisionPayload(reason="Off-brief for the platform."),
                ADMIN,
            )
            return await db.campaigns.find_one({"_id": s["campaign_oid"]})

        doc = run(body)
        assert doc["status"] == "draft", "a bad auto-published brief stayed live"
        assert doc["spot_checked_at"], "it would sit in the queue forever"

    def test_clearing_a_spot_check_is_not_approving_a_campaign(self):
        src = inspect.getsource(server.spot_check_campaign)
        assert '"reviewed_at"' not in src
        assert '"campaign.spot_check"' in src

    def test_the_admin_can_see_and_change_it(self):
        page = no_comments(FRONTEND / "components/admin/BrandDetailPage.jsx")
        assert "<BrandTrust" in page
        panel = no_comments(FRONTEND / "components/admin/BrandTrust.jsx")
        assert "/trust/revoke" in panel or "trust/${action}" in panel


# ---------------------------------------------------------------------------
# 6. Bulk actions
# ---------------------------------------------------------------------------


class TestBulkReview:
    def test_a_batch_is_fifty_real_decisions(self):
        """Not one `update_many`. Fifty rows stamped in one write is one audit
        line for fifty decisions, which is a record nobody can answer a
        question from."""

        async def body(db):
            ids = []
            for i in range(4):
                uid = ObjectId()
                await db.users.insert_one({"_id": uid, "role": "creator", "name": f"C{i}"})
                await db.creator_profiles.insert_one({
                    "user_id": uid, "name": f"C{i}", "verification_status": "pending",
                    "submitted_for_review_at": _now(),
                })
                ids.append(str(uid))
            out = await server.bulk_review(
                "creators",
                server.BulkDecisionPayload(ids=ids, action="approve"),
                ADMIN,
            )
            lines = await db.audit_log.find({"action": "creator.verified"}).to_list(50)
            notes = await db.notifications.count_documents({})
            return out, lines, notes

        out, lines, notes = run(body)
        assert len(out["done"]) == 4
        assert len(lines) == 4, "the decisions were not audited individually"
        assert notes == 4, "not everybody was told"

    def test_the_batch_itself_is_audited_too(self):
        async def body(db):
            uid = ObjectId()
            await db.users.insert_one({"_id": uid, "role": "creator", "name": "C"})
            await db.creator_profiles.insert_one(
                {"user_id": uid, "name": "C", "verification_status": "pending"}
            )
            await server.bulk_review(
                "creators",
                server.BulkDecisionPayload(ids=[str(uid)], action="approve"),
                ADMIN,
            )
            return await db.audit_log.find({"action": "bulk.creators_approve"}).to_list(5)

        assert run(body), "nothing records that this was one action"

    def test_one_stale_row_does_not_lose_the_rest(self):
        async def body(db):
            uid = ObjectId()
            await db.users.insert_one({"_id": uid, "role": "creator", "name": "C"})
            await db.creator_profiles.insert_one(
                {"user_id": uid, "name": "C", "verification_status": "pending"}
            )
            return await server.bulk_review(
                "creators",
                server.BulkDecisionPayload(
                    ids=[str(uid), str(ObjectId())], action="approve"
                ),
                ADMIN,
            )

        out = run(body)
        assert len(out["done"]) == 1
        assert len(out["failed"]) == 1
        assert out["failed"][0]["error"], "the failure has nothing to say"

    def test_a_bulk_rejection_needs_a_reason(self):
        async def body(db):
            with pytest.raises(HTTPException) as err:
                await server.bulk_review(
                    "creators",
                    server.BulkDecisionPayload(ids=[str(ObjectId())], action="reject"),
                    ADMIN,
                )
            return err.value

        assert run(body).status_code == 422

    def test_the_role_is_rechecked_by_hand(self):
        """**Calling a route function directly skips its `Depends`**, so the
        `require_roles("admin")` on `approve_creator` does not run. Without the
        check in the bulk route, a scoped console would reach the creator
        directory's decisions through this door."""

        async def body(db):
            team = {"_id": str(ObjectId()), "role": "weare_team", "name": "T",
                    "assigned_brand_ids": []}
            with pytest.raises(HTTPException) as err:
                await server.bulk_review(
                    "creators",
                    server.BulkDecisionPayload(ids=[str(ObjectId())], action="approve"),
                    team,
                )
            return err.value

        assert run(body).status_code == 403
        assert "is_all_access" in inspect.getsource(server.bulk_review)

    def test_an_unknown_queue_is_a_404(self):
        async def body(db):
            with pytest.raises(HTTPException) as err:
                await server.bulk_review(
                    "payments",
                    server.BulkDecisionPayload(ids=[str(ObjectId())], action="approve"),
                    ADMIN,
                )
            return err.value

        assert run(body).status_code == 404

    def test_the_batch_is_capped(self):
        """A queue screen cannot select more than it shows; a client that is
        not the queue screen can."""
        with pytest.raises(Exception):
            server.BulkDecisionPayload(
                ids=[str(ObjectId()) for _ in range(server.MAX_BULK + 1)],
                action="approve",
            )

    def test_all_three_queues_offer_it(self):
        src = no_comments(FRONTEND / "components/admin/Reviews.jsx")
        for kind in ("creators", "campaigns", "brands"):
            assert f'bulkKind: "{kind}"' in src
        assert "/admin/bulk/${config.bulkKind}" in src

    def test_the_confirmation_says_what_will_happen(self):
        """"Are you sure?" over fifty records is a question nobody can
        answer."""
        src = no_comments(FRONTEND / "components/admin/Reviews.jsx")
        assert "selected.size" in src
        assert 'requireReason={bulk === "reject"}' in src

    def test_approving_does_not_demand_a_reason_and_rejecting_does(self):
        dialog = no_comments(FRONTEND / "components/admin/dialogs.jsx")
        assert "requireReason = true" in dialog, "the default must stay strict"
        assert "if (requireReason && reason.trim().length < MIN_REASON)" in dialog
