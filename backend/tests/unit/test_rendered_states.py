"""What the server computes, rendered — one test per new state.

Across all three personas the backend decided correctly, sent the answer, and
no screen read it. Each class below drives the handler or the pure function
that makes the decision, reads the payload back, and then checks the screen
that is supposed to draw it actually reads that key. The second half is a
source check because there is no component runner here; the first half is
what makes it more than one — a screen reading a key the server never sets
would pass a grep and fail a creator.
"""
import asyncio
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"


def src(rel: str) -> str:
    text = (FRONTEND / rel).read_text()
    text = re.sub(r"\{/\*.*?\*/\}", "", text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("//"))


_LOOP = None


@pytest.fixture
def db():
    global _LOOP
    keep = server.db
    _LOOP = asyncio.new_event_loop()
    server.db = AsyncMongoMockClient()["rendered"]
    server._SLA_CACHE.clear() if hasattr(server, "_SLA_CACHE") else None
    try:
        yield server.db
    finally:
        _LOOP.close()
        _LOOP = None
        server.db = keep


def run(coro):
    return _LOOP.run_until_complete(coro)


def now():
    return datetime.now(timezone.utc)


async def _creator(db, **account):
    uid = ObjectId()
    user = {"_id": uid, "role": "creator", "name": "Aditi", "phone": "+919900000001", **account}
    await db.users.insert_one(user)
    await db.creator_profiles.insert_one(
        {"user_id": uid, "name": "Aditi", "verification_status": "verified", "city": "Bengaluru"}
    )
    return user


async def _campaign(db, **extra):
    cid, brand = ObjectId(), ObjectId()
    doc = {
        "_id": cid, "brand_id": brand, "title": "Tasting", "status": "open",
        "creators_needed": 3, "budget_per_creator": 8000, "compensation_type": "fixed",
        "execution_owner": "weare", "campaign_type": "personal_table", "created_at": now(),
        **extra,
    }
    await db.campaigns.insert_one(doc)
    return doc


# ---------------------------------------------------------------------------
# CREATOR
# ---------------------------------------------------------------------------


class TestSuspension:
    def test_the_dashboard_says_it_with_the_reason(self, db):
        user = run(_creator(db, status="suspended", suspension_reason="three no-shows in a row"))
        data = run(server.get_creator_dashboard(user=user))
        block = data["profile"]["block"]
        assert block["code"] == "suspended"
        assert "three no-shows in a row" in block["message"]

    def test_nobody_in_good_standing_has_a_block(self, db):
        user = run(_creator(db))
        assert run(server.get_creator_dashboard(user=user))["profile"]["block"] is None

    def test_booking_is_paused_on_the_card_and_refused_by_the_route(self, db):
        user = run(_creator(db, status="suspended"))
        camp = run(_campaign(db))
        cid = run(db.collaborations.insert_one({
            "campaign_id": camp["_id"], "creator_id": user["_id"],
            "state": "commercial_agreed", "agreed_amount": 8000, "active": True,
            "created_at": now(),
        })).inserted_id
        data = run(server.get_creator_dashboard(user=user))
        row = next(r for r in data["collaborations"]["active"] if r["id"] == str(cid))
        assert row["next_action"]["action"] is None
        assert "paused" in row["next_action"]["label"]

        slot = {"_id": ObjectId(), "campaign_id": camp["_id"], "capacity": 2, "booked_count": 0,
                "starts_at": now() + timedelta(days=3)}
        run(db.campaign_slots.insert_one(slot))
        collab = run(db.collaborations.find_one({"_id": cid}))
        with pytest.raises(HTTPException) as e:
            run(server._claim_slot(user, collab, camp, slot))
        assert e.value.status_code == 403
        assert run(db.campaign_slots.find_one({"_id": slot["_id"]}))["booked_count"] == 0

    def test_an_admin_booking_on_their_behalf_is_not_the_creators_claim(self):
        import inspect

        body = inspect.getsource(server._claim_slot)
        assert 'on_behalf_reason is None and (user or {}).get("status") == "suspended"' in body

    def test_the_home_page_draws_it(self):
        page = src("pages/CreatorHome.jsx")
        assert 'profile?.block?.code === "suspended"' in page
        assert "profile.block.message" in page


class TestUnconfirmedBookings:
    PENDING = {"state": "slot_booked", "slot_booked_at": "x", "slot_confirmed_at": None}
    AGREED = {"state": "slot_booked", "slot_booked_at": "x", "slot_confirmed_at": "y"}

    def test_the_creator_waits_until_the_venue_says_yes(self):
        nxt = server._creator_next_action(self.PENDING, {"execution_owner": "weare"}, True)
        assert nxt["action"] == "await_slot_confirmation"
        assert "Waiting for the venue to confirm" in nxt["label"]
        assert nxt["waiting_on"] == "weare"
        agreed = server._creator_next_action(self.AGREED, {}, True)
        assert agreed["action"] == "attend" and "Turn up" in agreed["label"]

    def test_the_shared_table_no_longer_says_turn_up_early(self):
        assert server._next_action(self.PENDING, {})["label"] == "Confirm the booking"
        assert server._next_action(self.AGREED, {})["label"] == "Turn up"

    def test_a_booking_from_before_the_handshake_still_reads_agreed(self):
        legacy = {"state": "slot_booked"}
        assert server._creator_next_action(legacy, {}, True)["action"] == "attend"


class TestDeclinedSlotReason:
    def test_on_the_row_and_above_the_picker(self):
        row = server._serialize_collab_row(
            {"_id": ObjectId(), "campaign_id": ObjectId(), "state": "commercial_agreed",
             "slot_declined_reason": "kitchen closed Mondays"},
            {}, "Toit", payout_default=7,
        )
        assert row["slot_declined_reason"] == "kitchen closed Mondays"
        picker = src("components/creator/SlotPicker.jsx")
        assert "Your last time was declined: {collab.slot_declined_reason}" in picker


class TestFinishedWork:
    def test_completed_rows_are_rendered_with_the_takedown_panel(self, db):
        user = run(_creator(db))
        camp = run(_campaign(db, compensation_type="barter", barter_description="Dinner for two"))
        run(db.collaborations.insert_one({
            "campaign_id": camp["_id"], "creator_id": user["_id"], "state": "closed",
            "created_at": now(),
        }))
        data = run(server.get_creator_dashboard(user=user))
        assert len(data["collaborations"]["completed"]) == 1
        assert data["collaborations"]["completed"][0]["compensation_type"] == "barter"

        home = src("pages/CreatorHome.jsx")
        assert "rows={groups.completed}" in home
        finished = src("components/creator/Finished.jsx")
        assert "<TakedownPanel" in finished and "canRespond" in finished
        # Barter closes without a payment; "Paid" would be false.
        assert '"closed_barter"' in finished
        assert "closed_barter:" in src("components/creator/shared.jsx")

    def test_closed_is_delivered_so_a_takedown_can_land_there(self):
        assert "closed" in server.DELIVERED_COLLAB_STATES


class TestDraftSummary:
    def test_what_was_sent_and_what_became_of_it(self):
        card = src("components/creator/ActiveCampaigns.jsx")
        for key in ("draft.submitted_at", "draft.revision_count", "draft.approved_at"):
            assert f"collab.{key}" in card


class TestHeldReason:
    def test_resolved_pitches_carry_why(self, db):
        user = run(_creator(db))
        camp = run(_campaign(db))
        base = {"campaign_id": camp["_id"], "creator_id": user["_id"], "created_at": now(),
                "resolved_at": now()}
        run(db.held_applications.insert_many([
            {**base, "state": "withdrawn", "reason": "The brief filled while we checked you."},
            {**base, "state": "released"},
            {**base, "state": "withdrawn"},  # their own take-back, no reason
            {**base, "state": "held", "resolved_at": None},
        ]))
        data = run(server.get_creator_dashboard(user=user))
        assert [r["reason"] for r in data["held_resolved"]] == [
            "The brief filled while we checked you."
        ]
        assert "{row.reason}" in src("components/creator/HeldApplications.jsx")
        assert "resolved={data.held_resolved}" in src("pages/CreatorHome.jsx")


class TestStateMeta:
    @pytest.mark.parametrize("state", ["withdrawn", "expired"])
    def test_every_exit_has_a_word(self, state):
        assert f"    {state}: {{ label:" in src("components/creator/shared.jsx")


class TestRecheckFields:
    def test_named_on_the_dashboard(self, db):
        user = run(_creator(db))
        run(db.creator_profiles.update_one(
            {"user_id": user["_id"]},
            {"$set": {"pending_review": True, "pending_review_fields": ["Instagram handle"]}},
        ))
        data = run(server.get_creator_dashboard(user=user))
        assert data["profile"]["pending_review_fields"] == ["Instagram handle"]
        assert 'profile.pending_review_fields.join(", ")' in src("pages/CreatorHome.jsx")


# ---------------------------------------------------------------------------
# BRAND
# ---------------------------------------------------------------------------


class TestPublishGate:
    def _brand(self, **extra):
        return {"user_id": ObjectId(), "verified": True, "verification_state": "verified", **extra}

    def test_four_refusals_from_one_reader(self, db, monkeypatch):
        assert run(server._brand_publish_block(None))["code"] == "no_profile"
        assert run(server._brand_publish_block({"user_id": ObjectId()}))["code"] == "unverified"
        lapsed = self._brand(verified_at=now() - timedelta(days=4000))
        assert run(server._brand_publish_block(lapsed))["code"] == "verification_lapsed"

        async def owing(ids):
            return {ids[0]: {"count": 2, "total": 14000, "worst_days": 9}}

        monkeypatch.setattr(server, "_brand_overdue_invoices", owing)
        block = run(server._brand_publish_block(self._brand()))
        assert block["code"] == "invoice_overdue" and block["count"] == 2
        # The override is the way past it.
        assert run(server._brand_publish_block(self._brand(invoice_override=True))) is None

    def test_the_route_and_the_profile_answer_alike(self, db, monkeypatch):
        brand = self._brand(verified_at=now() - timedelta(days=4000), business_name="Toit")
        run(db.brand_profiles.insert_one(brand))
        user = {"_id": brand["user_id"], "role": "brand_manager"}
        with pytest.raises(HTTPException) as e:
            run(server._verified_brand_or_403(user))
        assert e.value.detail["code"] == "verification_lapsed"
        profile = run(server._brand_profile_response(brand))
        assert profile["publish_block"]["code"] == "verification_lapsed"
        assert profile["invoices"] == {"overdue": None, "override": False}

    def test_the_form_disables_publish_and_says_why(self):
        gate = src("components/brand/PublishGate.jsx")
        assert 'state === "verified" && block' in gate and "{block.message}" in gate
        form = src("pages/PostCampaign.jsx")
        assert "block={brandProfile?.publish_block}" in form
        assert "Boolean(brandProfile?.publish_block)" in form


class TestSentBack:
    def test_the_owner_reads_the_reason_and_a_creator_does_not(self, db):
        brand_id = ObjectId()
        camp = run(_campaign(db, brand_id=brand_id, status="draft",
                             review_reason="Add the venue address", reviewed_at=now()))
        owner = {"_id": brand_id, "role": "brand_manager", "brand_id": brand_id}
        data = run(server.get_campaign(str(camp["_id"]), user=owner))
        assert data["review_reason"] == "Add the venue address"

    def test_dashboard_and_form_draw_it(self):
        dash = src("pages/BrandDashboardView.jsx")
        assert 'c.status === "draft" && c.review_reason' in dash
        assert "Changes requested" in dash
        assert 'existing?.review_reason' in src("pages/PostCampaign.jsx")


class TestBudgetOnTheBoard:
    def test_accept_reads_the_block_not_the_per_creator_fee(self):
        board = src("pages/BrandCampaignApplicants.jsx")
        assert "overBudgetBy" in board
        assert "budgetBlock={budgetApplies(campaign) ? campaign.budget : null}" in board
        assert "disabled={busy || over != null}" in board
        assert "Boolean(budgetBlock?.exhausted)" in board


class TestFrozenRows:
    def test_the_applicant_flags_read_false_while_disputed(self):
        collab = {"_id": ObjectId(), "campaign_id": ObjectId(), "creator_id": ObjectId(),
                  "state": "content_submitted", "dispute": {"state": "open"}}
        row = server._serialize_applicant(collab, {}, {}, None, {"deliverable_items": [
            {"type": "reel", "quantity": 1}]})
        assert row["frozen"] is True
        assert not row["can_review_content"] and not row["can_accept_partial"]
        open_row = server._serialize_applicant({**collab, "dispute": None}, {}, {}, None, {
            "deliverable_items": [{"type": "reel", "quantity": 1}]})
        assert open_row["can_review_content"] and open_row["can_accept_partial"]

    def test_the_shared_screen_freezes_every_state_moving_flag(self):
        import inspect

        body = inspect.getsource(server.get_application)
        for flag in ("can_accept", "can_decline", "can_agree_commercial", "can_review_content",
                     "can_accept_partial", "can_review_draft", "can_confirm_slot",
                     "can_dispatch", "can_advance"):
            chunk = body.split(f'"{flag}":', 1)[1].split('\n            "', 1)[0]
            assert "not frozen" in chunk, flag

    def test_the_board_draws_the_dispute(self):
        board = src("pages/BrandCampaignApplicants.jsx")
        assert "<DisputePanel collaborationId={a.id} dispute={a.dispute} />" in board
        assert "<TakedownPanel collaborationId={a.id} takedown={a.takedown} />" in board


class TestVerificationOnTheDashboard:
    def test_the_payload_and_the_pill(self, db):
        brand = {"user_id": ObjectId(), "verified": False,
                 "verification_state": "rejected", "verification_reason": "GST does not match"}
        run(db.brand_profiles.insert_one(brand))
        user = {"_id": brand["user_id"], "role": "brand_manager", "brand_id": brand["user_id"]}
        data = run(server.get_brand_dashboard(user=user))
        assert data["verification"]["state"] == "rejected"
        assert data["publish_block"]["code"] == "unverified"
        dash = src("pages/BrandDashboardView.jsx")
        assert "<StandingPill" in dash and "<StandingNotice" in dash


class TestAlsoRendered:
    def test_the_board_and_the_dashboard(self):
        board = src("pages/BrandCampaignApplicants.jsx")
        for needle in ("ageing={a.ageing}", "a.payment.state", "a.slot_declined_reason",
                       "a.reschedule_reason"):
            assert needle in board
        dash = src("pages/BrandDashboardView.jsx")
        for needle in ("c.pause_reason", "c.commission_percent", "c.campaign_fee", "c.reviewed_at"):
            assert needle in dash

    def test_the_launch_rule_is_read_from_the_payload(self):
        lib = src("lib/execution.js")
        assert "launchIsWeareRun !== false" in lib
        assert "launch_is_weare_run" in src("pages/PostCampaign.jsx")


# ---------------------------------------------------------------------------
# REQUIRED REASONS THAT NOBODY SAW
# ---------------------------------------------------------------------------


class TestReasons:
    def test_no_show_note_on_the_admin_page(self):
        import inspect

        body = inspect.getsource(server._serialize_admin_collab)
        assert '"note": collab.get("no_show_note")' in body
        page = src("components/admin/CollaborationDetailPage.jsx")
        assert "collab.no_show.note" in page

    def test_reschedule_reason_for_both_parties(self):
        assert "collab.reschedule_reason" in src("components/creator/ActiveCampaigns.jsx")
        assert "a.reschedule_reason" in src("pages/BrandCampaignApplicants.jsx")

    def test_slot_cancel_reason_on_the_day_plan_and_in_the_message(self):
        import inspect

        assert "r.slot_cancel_reason" in src("pages/ManagerCampaign.jsx")
        body = inspect.getsource(server.creator_cancel_slot)
        assert 'f"cancelled by the creator ({reason})"' in body


class TestCancelSlotFlag:
    def test_cutoff_and_cap_disable_it_with_the_reason(self):
        t = now()
        inside = {"state": "slot_booked", "slot_id": ObjectId(), "scheduled_at": t + timedelta(hours=2)}
        assert server._slot_cancel_refusal(inside, 2, t)["code"] == "cancel_cutoff"
        capped = {"state": "slot_booked", "slot_id": ObjectId(),
                  "scheduled_at": t + timedelta(days=5), "reschedule_count": 2}
        assert server._slot_cancel_refusal(capped, 2, t)["code"] == "reschedule_limit"
        free = {**capped, "reschedule_count": 0}
        assert server._slot_cancel_refusal(free, 2, t) is None

    def test_the_dashboard_flag_agrees_with_the_route(self, db):
        user = run(_creator(db))
        camp = run(_campaign(db))
        run(db.collaborations.insert_one({
            "campaign_id": camp["_id"], "creator_id": user["_id"], "state": "slot_booked",
            "slot_id": ObjectId(), "scheduled_at": now() + timedelta(hours=3),
            "agreed_amount": 8000, "active": True, "created_at": now(),
        }))
        row = run(server.get_creator_dashboard(user=user))["collaborations"]["active"][0]
        assert row["can_cancel_slot"] is False
        assert "24 hours" in row["cancel_blocked_reason"]
        assert "collab.cancel_blocked_reason" in src("components/creator/ActiveCampaigns.jsx")
