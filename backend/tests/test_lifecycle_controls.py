"""Backend tests for the ways a collaboration goes backwards or wrong.

The pipeline used to only go forwards: a fee agreed at the wrong number had no
fix short of cancelling, a payout that went out could not come back, and a live
campaign could not be stopped. These cover the reversals, the exits, the refund
and the campaign controls — plus the audit trail that has to record all of it.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

import pipeline  # tests/ is on sys.path (no __init__.py, pytest prepend mode)

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "creators@wearemonk.in")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "WeAreMonk@2026")


def _register(session, role):
    email = f"test_{role}-{uuid.uuid4().hex[:10]}@example.com"
    r = session.post(f"{BASE_URL}/auth/register", json={
        "email": email, "password": "Password123!", "name": f"Test {role.title()}", "role": role,
    })
    assert r.status_code == 200, r.text
    return email, r.json()


@pytest.fixture
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture
def anon():
    return requests.Session()


@pytest.fixture
def brand():
    s = requests.Session()
    _register(s, "brand")
    return s


@pytest.fixture
def creator():
    s = requests.Session()
    _, user = _register(s, "creator")
    return s, user["id"]


@pytest.fixture
def collab(admin, brand, creator):
    """A factory for a collaboration parked in whatever state a test needs."""
    cs, cuid = creator

    def _make(state="applied", **kwargs):
        return pipeline.make_collab_in_state(
            admin, brand, cs, cuid, state, **kwargs
        )

    return _make


def _state(admin, collab_id):
    return pipeline.current_state(admin, collab_id)


def _payment_for(admin, collab_id):
    board = admin.get(f"{BASE_URL}/admin/collaborations").json()["by_state"]
    for rows in board.values():
        for row in rows:
            if row["id"] == collab_id:
                return row.get("payment")
    return None


# ---------- 1. Reversal ----------

class TestRevert:
    def test_admin_only(self, anon, brand, creator, collab):
        cs, _ = creator
        cid, _ = collab("commercial_agreed")
        path = f"{BASE_URL}/admin/collaborations/{cid}/revert"
        body = {"reason": "wrong number"}
        assert anon.post(path, json=body).status_code == 401
        assert cs.post(path, json=body).status_code == 403
        assert brand.post(path, json=body).status_code == 403

    def test_it_moves_back_exactly_one_step(self, admin, collab):
        cid, _ = collab("slot_booked")
        r = admin.post(f"{BASE_URL}/admin/collaborations/{cid}/revert",
                       json={"reason": "Booked the wrong day"})
        assert r.status_code == 200, r.text
        assert r.json()["state"] == "commercial_agreed"
        assert r.json()["reverted_from"] == "slot_booked"
        assert _state(admin, cid) == "commercial_agreed"

    def test_a_reason_is_required(self, admin, collab):
        cid, _ = collab("commercial_agreed")
        assert admin.post(
            f"{BASE_URL}/admin/collaborations/{cid}/revert", json={}
        ).status_code == 422
        assert admin.post(
            f"{BASE_URL}/admin/collaborations/{cid}/revert", json={"reason": ""}
        ).status_code == 422

    def test_reverting_then_re_advancing_writes_the_corrected_number(self, admin, brand, collab):
        cid, _ = collab("commercial_agreed")
        admin.post(f"{BASE_URL}/admin/collaborations/{cid}/revert",
                   json={"reason": "Agreed the wrong fee"})
        pipeline.step(admin, brand, cid, "commercial_agreed", agreed_amount=12345)
        board = admin.get(f"{BASE_URL}/admin/collaborations").json()["by_state"]
        row = next(r for r in board["commercial_agreed"] if r["id"] == cid)
        assert row["agreed_amount"] == 12345

    def test_it_cannot_walk_off_the_bottom(self, admin, collab):
        cid, _ = collab("applied")
        r = admin.post(f"{BASE_URL}/admin/collaborations/{cid}/revert",
                       json={"reason": "Nothing behind this one"})
        assert r.status_code == 409, r.text

    def test_closed_cannot_be_reverted(self, admin, brand, creator, collab):
        cid, _ = collab("closed")
        r = admin.post(f"{BASE_URL}/admin/collaborations/{cid}/revert",
                       json={"reason": "Paid the wrong person"})
        assert r.status_code == 409, r.text
        assert "refund" in r.text.lower() or "closed" in r.text.lower()
        assert _state(admin, cid) == "closed"

    @pytest.mark.parametrize("exit_path,body", [
        ("cancel", {"reason": "Venue closed", "cancellation_type": "brand_cancelled"}),
        ("decline", {"reason": "Not the right fit"}),
    ])
    def test_an_exit_is_not_a_step_you_can_walk_back(self, admin, collab, exit_path, body):
        cid, _ = collab("applied" if exit_path == "decline" else "slot_booked")
        assert admin.post(
            f"{BASE_URL}/admin/collaborations/{cid}/{exit_path}", json=body
        ).status_code == 200
        r = admin.post(f"{BASE_URL}/admin/collaborations/{cid}/revert",
                       json={"reason": "changed my mind"})
        assert r.status_code == 409, r.text

    def test_stepping_back_out_of_payment_voids_the_payable(self, admin, collab):
        cid, _ = collab("in_payment")
        assert _payment_for(admin, cid), "there should be a payment to void"

        r = admin.post(f"{BASE_URL}/admin/collaborations/{cid}/revert",
                       json={"reason": "Payout details were wrong"})
        assert r.status_code == 200, r.text
        assert r.json()["payment_voided"] is True
        assert _state(admin, cid) == "content_approved"

    def test_and_a_fresh_payable_is_created_on_the_way_forward_again(self, admin, brand, collab):
        # The unique index on collaboration_id makes this the failure mode:
        # a voided row left behind would block the new one.
        cid, _ = collab("in_payment")
        admin.post(f"{BASE_URL}/admin/collaborations/{cid}/revert",
                   json={"reason": "Payout details were wrong"})
        pipeline.step(admin, brand, cid, "in_payment")
        assert _state(admin, cid) == "in_payment"
        assert _payment_for(admin, cid), "re-advancing must produce a payable again"

    def test_reverting_below_accepted_frees_the_slot(self, admin, brand, creator, collab):
        cid, campaign_id = collab("accepted", creators_needed=1)
        listing = admin.get(f"{BASE_URL}/admin/campaigns",
                            params={"page_size": 100}).json()["campaigns"]
        before = next(c for c in listing if c["id"] == campaign_id)["filled_slots"]

        admin.post(f"{BASE_URL}/admin/collaborations/{cid}/revert",
                   json={"reason": "Accepted the wrong creator"})

        listing = admin.get(f"{BASE_URL}/admin/campaigns",
                            params={"page_size": 100}).json()["campaigns"]
        after = next(c for c in listing if c["id"] == campaign_id)["filled_slots"]
        assert after == before - 1

    def test_unknown_collaboration_is_404(self, admin):
        for cid in ("507f1f77bcf86cd799439011", "not-an-id"):
            assert admin.post(f"{BASE_URL}/admin/collaborations/{cid}/revert",
                              json={"reason": "x y z"}).status_code == 404


# ---------- 2. Failure paths ----------

class TestDecline:
    def test_an_applicant_can_be_turned_down_directly(self, admin, collab):
        cid, _ = collab("applied")
        r = admin.post(f"{BASE_URL}/admin/collaborations/{cid}/decline",
                       json={"reason": "Not the right fit for this brief"})
        assert r.status_code == 200, r.text
        assert r.json()["state"] == "declined"
        assert _state(admin, cid) == "declined"

    def test_the_creator_is_told_why(self, admin, creator, collab):
        cs, _ = creator
        cid, _ = collab("applied")
        admin.post(f"{BASE_URL}/admin/collaborations/{cid}/decline",
                   json={"reason": "Looking for a different niche"})
        row = next(a for a in cs.get(f"{BASE_URL}/creator/dashboard").json()["applications"]
                   if a["id"] == cid)
        assert row["state"] == "declined"
        assert "niche" in row["exit_reason"]

    def test_declining_needs_a_reason(self, admin, collab):
        cid, _ = collab("applied")
        assert admin.post(
            f"{BASE_URL}/admin/collaborations/{cid}/decline", json={}
        ).status_code == 422

    def test_past_acceptance_it_is_a_cancellation_not_a_decline(self, admin, collab):
        cid, _ = collab("accepted")
        r = admin.post(f"{BASE_URL}/admin/collaborations/{cid}/decline",
                       json={"reason": "Too late for this"})
        assert r.status_code == 409, r.text
        assert "cancel" in r.text.lower()

    def test_declining_frees_the_slot_and_re_application_is_possible(self, admin, creator, collab):
        cs, _ = creator
        cid, campaign_id = collab("applied")
        admin.post(f"{BASE_URL}/admin/collaborations/{cid}/decline",
                   json={"reason": "Not this time"})
        # The partial-unique index is on active=true, so a declined creator may
        # come back to the same brief.
        again = cs.post(f"{BASE_URL}/campaigns/{campaign_id}/apply",
                        json={"pitch": "second time lucky please", "quoted_rate": 5000})
        assert again.status_code in (200, 201), again.text


class TestCancel:
    def test_it_records_how_it_failed(self, admin, collab):
        cid, _ = collab("slot_booked")
        r = admin.post(f"{BASE_URL}/admin/collaborations/{cid}/cancel", json={
            "reason": "Creator never turned up", "cancellation_type": "creator_no_show",
        })
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["state"] == "cancelled"
        assert out["cancellation_type"] == "creator_no_show"
        assert out["cancelled_from_state"] == "slot_booked"

    def test_an_unattributed_cancellation_is_ours(self, admin, collab):
        cid, _ = collab("slot_booked")
        out = admin.post(f"{BASE_URL}/admin/collaborations/{cid}/cancel",
                         json={"reason": "Campaign pulled"}).json()
        assert out["cancellation_type"] == "admin_cancelled"

    def test_an_invented_type_is_refused(self, admin, collab):
        cid, _ = collab("slot_booked")
        assert admin.post(f"{BASE_URL}/admin/collaborations/{cid}/cancel", json={
            "reason": "whatever", "cancellation_type": "vibes",
        }).status_code == 422

    def test_a_cancellation_needs_a_reason(self, admin, collab):
        cid, _ = collab("slot_booked")
        assert admin.post(
            f"{BASE_URL}/admin/collaborations/{cid}/cancel",
            json={"cancellation_type": "brand_cancelled"},
        ).status_code == 422

    def test_cancelling_after_the_fee_was_agreed_keeps_the_number(self, admin, collab):
        # No payment row exists yet, so the agreed figure would otherwise vanish
        # when the collaboration leaves the "ongoing" group it was counted in.
        cid, _ = collab("commercial_agreed")
        out = admin.post(f"{BASE_URL}/admin/collaborations/{cid}/cancel", json={
            "reason": "Brand pulled the shoot", "cancellation_type": "brand_cancelled",
        }).json()
        assert out["agreed_amount_at_cancellation"] is not None
        # Nothing was shot, so there is nothing to settle.
        assert out["settlement_review_needed"] is False

    def test_cancelling_after_the_creator_turned_up_is_flagged(self, admin, collab):
        cid, _ = collab("attended")
        out = admin.post(f"{BASE_URL}/admin/collaborations/{cid}/cancel", json={
            "reason": "Brand pulled it after the shoot", "cancellation_type": "brand_cancelled",
        }).json()
        assert out["settlement_review_needed"] is True, (
            "the creator did agreed work — somebody has to decide what they're owed"
        )

    def test_a_no_show_is_not_a_settlement_question(self, admin, collab):
        cid, _ = collab("attended")
        out = admin.post(f"{BASE_URL}/admin/collaborations/{cid}/cancel", json={
            "reason": "Marked attended in error, they never came",
            "cancellation_type": "creator_no_show",
        }).json()
        assert out["settlement_review_needed"] is False

    def test_cancelling_before_a_fee_leaves_no_commitment(self, admin, collab):
        cid, _ = collab("accepted")
        out = admin.post(f"{BASE_URL}/admin/collaborations/{cid}/cancel",
                         json={"reason": "Fell through early"}).json()
        assert out["agreed_amount_at_cancellation"] is None

    def test_a_pending_payable_goes_with_it(self, admin, collab):
        cid, _ = collab("in_payment")
        assert admin.post(f"{BASE_URL}/admin/collaborations/{cid}/cancel",
                          json={"reason": "Content was taken down"}).status_code == 200
        payment = _payment_for(admin, cid)
        assert payment is None or payment["state"] == "cancelled"

    def test_a_paid_collaboration_points_at_refund_instead(self, admin, collab):
        cid, _ = collab("closed")
        r = admin.post(f"{BASE_URL}/admin/collaborations/{cid}/cancel",
                       json={"reason": "Should not have paid"})
        assert r.status_code == 409, r.text
        assert "refund" in r.text.lower()

    def test_cancelling_twice_is_refused(self, admin, collab):
        cid, _ = collab("slot_booked")
        admin.post(f"{BASE_URL}/admin/collaborations/{cid}/cancel",
                   json={"reason": "Called off"})
        assert admin.post(f"{BASE_URL}/admin/collaborations/{cid}/cancel",
                          json={"reason": "Called off again"}).status_code == 409


# ---------- 3. Refunds ----------

class TestRefund:
    def _paid(self, admin, collab):
        cid, campaign_id = collab("in_payment")
        payment = _payment_for(admin, cid)
        r = admin.post(f"{BASE_URL}/admin/payments/{payment['id']}/mark_paid",
                       json={"payment_reference": f"UTR{uuid.uuid4().hex[:10].upper()}"})
        assert r.status_code == 200, r.text
        return cid, campaign_id, payment["id"]

    def test_admin_only(self, anon, brand, creator, admin, collab):
        cs, _ = creator
        _, _, pid = self._paid(admin, collab)
        path = f"{BASE_URL}/admin/payments/{pid}/refund"
        body = {"reason": "Paid the wrong account"}
        assert anon.post(path, json=body).status_code == 401
        assert cs.post(path, json=body).status_code == 403
        assert brand.post(path, json=body).status_code == 403

    def test_it_refunds_and_cancels_the_collaboration(self, admin, collab):
        cid, _, pid = self._paid(admin, collab)
        assert _state(admin, cid) == "closed"

        r = admin.post(f"{BASE_URL}/admin/payments/{pid}/refund", json={
            "reason": "Paid the wrong account", "refund_reference": "RFND-001",
        })
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["state"] == "refunded"
        assert out["collaboration_state"] == "cancelled"
        assert out["refund_reference"] == "RFND-001"
        assert _state(admin, cid) == "cancelled"

    def test_a_refund_needs_a_reason(self, admin, collab):
        _, _, pid = self._paid(admin, collab)
        assert admin.post(f"{BASE_URL}/admin/payments/{pid}/refund",
                          json={}).status_code == 422

    def test_refunding_twice_is_refused(self, admin, collab):
        _, _, pid = self._paid(admin, collab)
        assert admin.post(f"{BASE_URL}/admin/payments/{pid}/refund",
                          json={"reason": "Wrong account"}).status_code == 200
        second = admin.post(f"{BASE_URL}/admin/payments/{pid}/refund",
                            json={"reason": "Wrong account again"})
        assert second.status_code == 409, second.text

    def test_an_unpaid_payout_has_nothing_to_refund(self, admin, collab):
        cid, _ = collab("in_payment")
        payment = _payment_for(admin, cid)
        r = admin.post(f"{BASE_URL}/admin/payments/{payment['id']}/refund",
                       json={"reason": "Never went out"})
        assert r.status_code == 409, r.text
        assert "cancel" in r.text.lower()

    def test_refunded_money_stops_counting_as_revenue(self, admin, collab):
        before = admin.get(f"{BASE_URL}/admin/metrics").json()
        cid, _, pid = self._paid(admin, collab)
        mid = admin.get(f"{BASE_URL}/admin/metrics").json()
        assert mid["total_paid_out"] > before["total_paid_out"]

        admin.post(f"{BASE_URL}/admin/payments/{pid}/refund",
                   json={"reason": "Clawed back"})
        after = admin.get(f"{BASE_URL}/admin/metrics").json()
        assert after["total_paid_out"] == pytest.approx(before["total_paid_out"], abs=0.01)
        assert after["gmv"] == pytest.approx(before["gmv"], abs=0.01)

    def test_a_settled_brand_invoice_is_flagged_as_money_we_hold(self, admin, collab):
        _, _, pid = self._paid(admin, collab)
        assert admin.post(f"{BASE_URL}/admin/payments/{pid}/invoice_state",
                          json={"state": "settled"}).status_code == 200

        out = admin.post(f"{BASE_URL}/admin/payments/{pid}/refund",
                         json={"reason": "Campaign was never delivered"}).json()
        assert out["brand_refund_due"] is True

    def test_an_unsettled_invoice_is_simply_void(self, admin, collab):
        _, _, pid = self._paid(admin, collab)
        out = admin.post(f"{BASE_URL}/admin/payments/{pid}/refund",
                         json={"reason": "Never delivered"}).json()
        assert out["brand_refund_due"] is False

    def test_unknown_payment_is_404(self, admin):
        for pid in ("507f1f77bcf86cd799439011", "not-an-id"):
            assert admin.post(f"{BASE_URL}/admin/payments/{pid}/refund",
                              json={"reason": "x y z"}).status_code == 404


# ---------- 4. Campaign controls ----------

class TestCampaignControls:
    def _live(self, admin, brand):
        return pipeline.seed_open_campaign(brand, admin, creators_needed=2)

    def _status(self, admin, campaign_id):
        rows = admin.get(f"{BASE_URL}/admin/campaigns",
                         params={"page_size": 100}).json()["campaigns"]
        return next(c for c in rows if c["id"] == campaign_id)["status"]

    def test_admin_only(self, anon, brand, creator, admin):
        cid = self._live(admin, brand)
        cs, _ = creator
        for path, body in (
            (f"/admin/campaigns/{cid}/pause", {"reason": "hold it"}),
            (f"/admin/campaigns/{cid}/close", {"reason": "stop it"}),
        ):
            assert anon.post(f"{BASE_URL}{path}", json=body).status_code == 401
            assert cs.post(f"{BASE_URL}{path}", json=body).status_code == 403
            assert brand.post(f"{BASE_URL}{path}", json=body).status_code == 403
        assert anon.patch(f"{BASE_URL}/admin/campaigns/{cid}",
                          json={"title": "x"}).status_code == 401
        assert brand.patch(f"{BASE_URL}/admin/campaigns/{cid}",
                           json={"title": "x"}).status_code == 403

    def test_pausing_takes_it_off_the_feed(self, admin, brand, creator):
        cid = self._live(admin, brand)
        cs, cuid = creator
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, cuid)
        assert cid in {c["id"] for c in cs.get(f"{BASE_URL}/campaigns").json()}

        r = admin.post(f"{BASE_URL}/admin/campaigns/{cid}/pause",
                       json={"reason": "Brand asked us to hold"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "paused"
        assert cid not in {c["id"] for c in cs.get(f"{BASE_URL}/campaigns").json()}

    def test_nobody_can_apply_to_a_paused_campaign(self, admin, brand, creator):
        cid = self._live(admin, brand)
        cs, cuid = creator
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, cuid)
        admin.post(f"{BASE_URL}/admin/campaigns/{cid}/pause", json={"reason": "Hold"})

        r = cs.post(f"{BASE_URL}/campaigns/{cid}/apply",
                    json={"pitch": "still keen on this", "quoted_rate": 5000})
        assert r.status_code == 404

    def test_pausing_does_not_touch_work_already_under_way(self, admin, brand, creator):
        cs, cuid = creator
        collab_id, campaign_id = pipeline.make_collab_in_state(
            admin, brand, cs, cuid, "slot_booked"
        )
        admin.post(f"{BASE_URL}/admin/campaigns/{campaign_id}/pause",
                   json={"reason": "Paused mid-flight"})
        assert _state(admin, collab_id) == "slot_booked"

    def test_resuming_puts_it_back_where_it_was(self, admin, brand):
        cid = self._live(admin, brand)
        before = self._status(admin, cid)
        admin.post(f"{BASE_URL}/admin/campaigns/{cid}/pause", json={"reason": "Hold"})
        r = admin.post(f"{BASE_URL}/admin/campaigns/{cid}/resume", json={})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == before

    def test_pausing_twice_is_refused(self, admin, brand):
        cid = self._live(admin, brand)
        admin.post(f"{BASE_URL}/admin/campaigns/{cid}/pause", json={"reason": "Hold"})
        assert admin.post(f"{BASE_URL}/admin/campaigns/{cid}/pause",
                          json={"reason": "Hold again"}).status_code == 409

    def test_resuming_something_that_is_not_paused_is_refused(self, admin, brand):
        cid = self._live(admin, brand)
        assert admin.post(f"{BASE_URL}/admin/campaigns/{cid}/resume",
                          json={}).status_code == 409

    def test_a_draft_has_nothing_to_pause(self, admin, brand):
        pipeline.setup_brand(brand, admin)
        r = brand.post(f"{BASE_URL}/brand/campaigns", json={
            "title": f"D-{uuid.uuid4().hex[:6]}", "brief": "b", "deliverables": "d",
            "budget_per_creator": 100, "category": "fnb", "area": "Indiranagar",
            "creators_needed": 1, "status": "draft",
            "campaign_type": "personal_table", "start_date": "2025-06-01T00:00:00Z", "end_date": "2027-06-01T00:00:00Z",
        })
        assert admin.post(f"{BASE_URL}/admin/campaigns/{r.json()['id']}/pause",
                          json={"reason": "Hold"}).status_code == 409

    def test_closing_answers_everyone_still_waiting(self, admin, brand, creator):
        cs, cuid = creator
        collab_id, campaign_id = pipeline.make_collab_in_state(
            admin, brand, cs, cuid, "applied"
        )
        r = admin.post(f"{BASE_URL}/admin/campaigns/{campaign_id}/close",
                       json={"reason": "Brand went out of business"})
        assert r.status_code == 200, r.text
        assert r.json()["applications_closed"] == 1
        assert _state(admin, collab_id) == "declined"

    def test_closing_leaves_work_under_way_alone(self, admin, brand, creator):
        cs, cuid = creator
        collab_id, campaign_id = pipeline.make_collab_in_state(
            admin, brand, cs, cuid, "slot_booked"
        )
        admin.post(f"{BASE_URL}/admin/campaigns/{campaign_id}/close",
                   json={"reason": "No more applications wanted"})
        assert _state(admin, collab_id) == "slot_booked"

    def test_closing_twice_is_refused(self, admin, brand):
        cid = self._live(admin, brand)
        admin.post(f"{BASE_URL}/admin/campaigns/{cid}/close", json={"reason": "Done"})
        assert admin.post(f"{BASE_URL}/admin/campaigns/{cid}/close",
                          json={"reason": "Done again"}).status_code == 409

    def test_stopping_a_campaign_needs_a_reason(self, admin, brand):
        cid = self._live(admin, brand)
        assert admin.post(f"{BASE_URL}/admin/campaigns/{cid}/pause", json={}).status_code == 422
        assert admin.post(f"{BASE_URL}/admin/campaigns/{cid}/close", json={}).status_code == 422

    def test_an_admin_can_correct_a_live_campaign(self, admin, brand):
        cid = self._live(admin, brand)
        r = admin.patch(f"{BASE_URL}/admin/campaigns/{cid}", json={
            "title": "Corrected title", "budget_per_creator": 9999,
        })
        assert r.status_code == 200, r.text
        assert r.json()["title"] == "Corrected title"
        assert r.json()["budget_per_creator"] == 9999

    def test_an_edit_cannot_shrink_below_the_creators_already_on_it(self, admin, brand, creator):
        cs, cuid = creator
        _, campaign_id = pipeline.make_collab_in_state(
            admin, brand, cs, cuid, "accepted", creators_needed=2
        )
        r = admin.patch(f"{BASE_URL}/admin/campaigns/{campaign_id}",
                        json={"creators_needed": 0})
        # 0 is refused by the schema; 1 would be refused by the floor. Either
        # way the brief cannot end up smaller than what is committed.
        assert r.status_code in (409, 422), r.text

    def test_an_empty_edit_is_refused(self, admin, brand):
        cid = self._live(admin, brand)
        assert admin.patch(f"{BASE_URL}/admin/campaigns/{cid}", json={}).status_code == 422

    def test_a_closed_campaign_can_no_longer_be_edited(self, admin, brand):
        cid = self._live(admin, brand)
        admin.post(f"{BASE_URL}/admin/campaigns/{cid}/close", json={"reason": "Over"})
        assert admin.patch(f"{BASE_URL}/admin/campaigns/{cid}",
                           json={"title": "Too late"}).status_code == 409

    def test_unknown_campaign_is_404(self, admin):
        for cid in ("507f1f77bcf86cd799439011", "not-an-id"):
            assert admin.post(f"{BASE_URL}/admin/campaigns/{cid}/pause",
                              json={"reason": "x y z"}).status_code == 404
            assert admin.patch(f"{BASE_URL}/admin/campaigns/{cid}",
                               json={"title": "x"}).status_code == 404


# ---------- 5. Audit log ----------

class TestAuditLog:
    def _entries(self, admin, **params):
        r = admin.get(f"{BASE_URL}/admin/audit", params={"limit": 200, **params})
        assert r.status_code == 200, r.text
        return r.json()

    def test_admin_only(self, anon, brand, creator):
        cs, _ = creator
        assert anon.get(f"{BASE_URL}/admin/audit").status_code == 401
        assert cs.get(f"{BASE_URL}/admin/audit").status_code == 403
        assert brand.get(f"{BASE_URL}/admin/audit").status_code == 403

    def test_every_entry_carries_who_what_and_when(self, admin, collab):
        cid, _ = collab("commercial_agreed")
        rows = self._entries(admin, subject_id=cid)
        assert rows, "advancing a collaboration has to leave a trace"
        for row in rows:
            for field in ("actor_id", "actor_name", "action", "subject_type",
                          "subject_id", "created_at"):
                assert row.get(field) is not None, f"{field} missing from {row}"

    def test_it_records_the_before_and_after(self, admin, collab):
        cid, _ = collab("slot_booked")
        admin.post(f"{BASE_URL}/admin/collaborations/{cid}/revert",
                   json={"reason": "Wrong day booked"})
        row = next(r for r in self._entries(admin, subject_id=cid)
                   if r["action"] == "collaboration.revert")
        assert row["before"]["state"] == "slot_booked"
        assert row["after"]["state"] == "commercial_agreed"
        assert row["note"] == "Wrong day booked"

    @pytest.mark.parametrize("action", [
        "collaboration.advance", "collaboration.revert", "collaboration.cancel",
    ])
    def test_each_kind_of_action_is_named(self, admin, collab, action):
        cid, _ = collab("slot_booked")
        admin.post(f"{BASE_URL}/admin/collaborations/{cid}/revert",
                   json={"reason": "Rebooking this one"})
        admin.post(f"{BASE_URL}/admin/collaborations/{cid}/cancel",
                   json={"reason": "Called off", "cancellation_type": "brand_cancelled"})
        actions = {r["action"] for r in self._entries(admin, subject_id=cid)}
        assert action in actions

    def test_filter_by_action_family(self, admin, collab):
        cid, _ = collab("in_payment")
        payment = _payment_for(admin, cid)
        admin.post(f"{BASE_URL}/admin/payments/{payment['id']}/mark_paid",
                   json={"payment_reference": f"UTR{uuid.uuid4().hex[:8].upper()}"})

        rows = self._entries(admin, action="payment")
        assert rows, "a bare family name has to match everything under it"
        assert all(r["action"].startswith("payment.") for r in rows)

    def test_filter_by_exact_action(self, admin, collab):
        cid, _ = collab("applied")
        admin.post(f"{BASE_URL}/admin/collaborations/{cid}/decline",
                   json={"reason": "Not this time"})
        rows = self._entries(admin, action="collaboration.decline")
        assert rows
        assert all(r["action"] == "collaboration.decline" for r in rows)
        assert any(r["subject_id"] == cid for r in rows)

    def test_filter_by_actor(self, admin, collab):
        collab("commercial_agreed")
        me = admin.get(f"{BASE_URL}/auth/me").json()["id"]
        rows = self._entries(admin, actor_id=me)
        assert rows
        assert all(r["actor_id"] == me for r in rows)

    def test_a_bad_actor_id_is_a_422_not_a_500(self, admin):
        assert admin.get(f"{BASE_URL}/admin/audit",
                         params={"actor_id": "nonsense"}).status_code == 422

    def test_filter_by_date_range(self, admin, collab):
        cid, _ = collab("commercial_agreed")
        now = datetime.now(timezone.utc)

        recent = self._entries(admin, date_from=(now - timedelta(hours=1)).isoformat())
        assert any(r["subject_id"] == cid for r in recent)

        old = self._entries(admin, date_to=(now - timedelta(days=365)).isoformat())
        assert not any(r["subject_id"] == cid for r in old)

    def test_newest_first(self, admin, collab):
        collab("commercial_agreed")
        stamps = [r["created_at"] for r in self._entries(admin)]
        assert stamps == sorted(stamps, reverse=True)

    def test_the_money_endpoints_are_all_in_the_log(self, admin, collab):
        cid, _ = collab("in_payment")
        payment = _payment_for(admin, cid)
        admin.post(f"{BASE_URL}/admin/payments/{payment['id']}/mark_paid",
                   json={"payment_reference": f"UTR{uuid.uuid4().hex[:8].upper()}"})
        admin.post(f"{BASE_URL}/admin/payments/{payment['id']}/refund",
                   json={"reason": "Sent to the wrong account"})

        actions = {r["action"] for r in self._entries(admin, subject_id=payment["id"])}
        assert {"payment.mark_paid", "payment.refund"} <= actions

    def test_campaign_controls_are_in_the_log(self, admin, brand):
        cid = pipeline.seed_open_campaign(brand, admin)
        admin.post(f"{BASE_URL}/admin/campaigns/{cid}/pause", json={"reason": "Hold"})
        admin.post(f"{BASE_URL}/admin/campaigns/{cid}/resume", json={})
        admin.patch(f"{BASE_URL}/admin/campaigns/{cid}", json={"title": "Edited"})
        admin.post(f"{BASE_URL}/admin/campaigns/{cid}/close", json={"reason": "Over"})

        actions = {r["action"] for r in self._entries(admin, subject_id=cid)}
        assert {"campaign.pause", "campaign.resume",
                "campaign.update", "campaign.close"} <= actions
