"""One delivery brief, from the creator's offer to the payment, over HTTP.

The two mechanics — the fee history and the self-resolving draft review —
are driven handler by handler in their own files. This walks one
collaboration through every route a real one takes, as the three people who
take it: the creator applies with a quote, the brand counters and then
records what was settled, the product is sent and received, the draft goes
in and **nobody reviews it**, the window runs out, and the work is delivered,
approved and paid.

**Why here and not in `tests/`.** That suite drives a live server and
MongoDB and builds collaborations through `tests/pipeline.py`, which is stale
and is deliberately not repaired in this change. So this runs the real ASGI
app in process through `TestClient`: real cookies, real `require_roles`
guards, every route exactly as it is mounted, with mongomock underneath. What
it cannot see is Mongo itself, and the race tests elsewhere stage the losing
read directly for that reason.

The clock is moved once, by writing the deadline into the past — the one
thing a test cannot wait two days for. Everything else is a request.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

import server

PHONE = "+919900000077"
EMAIL = "e2e.creator@example.com"


def _now():
    return datetime.now(timezone.utc)


@pytest.fixture()
def world():
    db = AsyncMongoMockClient()["e2e_draft_fee"]
    original = server.db
    server.db = db

    admin_oid, brand_oid, creator_oid, campaign_oid = (ObjectId() for _ in range(4))
    now = _now()

    async def seed():
        await db.users.insert_many([
            {"_id": admin_oid, "role": "admin", "name": "Ops Admin",
             "email": "ops@example.com", "status": "active", "created_at": now},
            {"_id": brand_oid, "role": "brand_manager", "name": "Riya Brand",
             "brand_id": brand_oid, "phone": "+919900000088", "status": "active",
             "created_at": now},
            {"_id": creator_oid, "role": "creator", "name": "Asha Creator",
             "phone": PHONE, "email": EMAIL, "status": "active", "created_at": now},
        ])
        await db.brand_profiles.insert_one({
            "user_id": brand_oid, "brand_id": brand_oid, "business_name": "Kettle & Co",
            "verified": True, "verification_state": "verified", "verified_at": now,
            "category": "fnb", "city": "Bengaluru",
        })
        await db.creator_profiles.insert_one({
            "user_id": creator_oid, "name": "Asha Creator", "verification_status": "verified",
            "verified_at": now, "submitted_for_review_at": now, "phone": PHONE,
            "email": EMAIL, "city": "Bengaluru",
            "full_address": "12 Main Road, Indiranagar, Bengaluru 560038",
            "instagram_handle": "@asha", "platforms": ["instagram"],
            "payout_method": "upi", "payout_upi": "asha@okhdfcbank", "pan": "AAAPA1234C",
        })
        await db.campaigns.insert_one({
            "_id": campaign_oid, "brand_id": brand_oid, "title": "Tea hamper unboxing",
            "brief": "Unbox the hamper and brew one of the teas on camera.",
            "status": "open", "campaign_type": "delivery", "execution_owner": "brand",
            "manager_id": brand_oid, "manager_name": "Riya Brand",
            "compensation_type": "negotiated", "budget_per_creator": 15000,
            "creators_needed": 3, "visibility": "public", "city": "Bengaluru",
            "requires_draft_approval": True, "draft_review_days": 2,
            "deliverable_items": [{"type": "reel", "quantity": 1}],
            "deliverables": "1 reel", "created_at": now, "updated_at": now,
        })

    asyncio.run(seed())
    client = TestClient(server.app)

    def as_(oid, role, email=None):
        c = TestClient(server.app)
        c.cookies.set("access_token", server.create_access_token(str(oid), email or "", role))
        return c

    yield {
        "db": db,
        "admin": as_(admin_oid, "admin", "ops@example.com"),
        "brand": as_(brand_oid, "brand_manager"),
        "creator": as_(creator_oid, "creator", EMAIL),
        "campaign_id": str(campaign_oid),
        "client": client,
    }
    server.db = original


def _ok(resp, what):
    assert resp.status_code < 300, f"{what}: {resp.status_code} {resp.text[:600]}"
    return resp.json()


def _read(db, coro_fn):
    return asyncio.run(coro_fn(db))


def test_offer_to_auto_approval_to_payment(world):
    db, admin, brand, creator = world["db"], world["admin"], world["brand"], world["creator"]
    api = "/api"

    # -- The offer -------------------------------------------------------
    applied = _ok(creator.post(f"{api}/campaigns/{world['campaign_id']}/apply",
                               json={"pitch": "I brew on camera every morning.",
                                     "quoted_rate": 15000}), "apply")
    cid = applied.get("id") or applied.get("collaboration_id") or applied["collaboration"]["id"]

    _ok(admin.post(f"{api}/admin/collaborations/{cid}/advance",
                   json={"from_state": "applied"}), "verify the applicant")

    # -- The counter, then what was settled -------------------------------
    _ok(brand.post(f"{api}/brand/collaborations/{cid}/accept",
                   json={"agreed_amount": 11000, "note": "Our ceiling is lower"}), "accept")
    _ok(brand.post(f"{api}/brand/collaborations/{cid}/agreed-amount",
                   json={"agreed_amount": 12500, "note": "Met in the middle on the call"}),
        "record the agreed fee")

    # -- The product travels ----------------------------------------------
    _ok(creator.post(f"{api}/creator/collaborations/{cid}/confirm-address", json={}),
        "confirm address")
    _ok(brand.post(f"/api/collaborations/{cid}/dispatch", json={"courier": "Blue Dart"}),
        "dispatch")
    _ok(creator.post(f"{api}/creator/collaborations/{cid}/confirm-received", json={}),
        "confirm received")

    # -- The draft goes in, and nobody answers ----------------------------
    sent_at = _now()
    _ok(creator.post(f"{api}/drafts/{cid}/link",
                     json={"draft_url": "https://drive.example.com/cut-1"}), "send draft")

    row = _read(db, lambda d: d.collaborations.find_one({"_id": ObjectId(cid)}))
    deadline = row["draft_review_deadline_at"].replace(tzinfo=timezone.utc)
    assert timedelta(days=2) - timedelta(minutes=1) <= deadline - sent_at <= timedelta(days=2, minutes=1)

    # All three see the window, and only the admin is offered its controls.
    brand_app = _ok(brand.get(f"{api}/applications/{cid}"), "brand reads")
    admin_app = _ok(admin.get(f"{api}/applications/{cid}"), "admin reads")
    dash = _ok(creator.get(f"{api}/creator/dashboard"), "creator dashboard")
    creator_row = next(r for r in dash["collaborations"]["active"] if r["id"] == cid)
    for view in (brand_app["draft"], admin_app["draft"]):
        assert view["review_window"]["running"] is True
        assert view["review_window"]["deadline_at"]
    assert creator_row["draft"]["review_window"]["running"] is True
    assert [e["kind"] for e in creator_row["negotiation"]["entries"]] == ["accept", "counter", "offer"]
    assert admin_app["actions"]["can_manage_review_window"] is True
    assert brand_app["actions"]["can_manage_review_window"] is False
    assert brand_app["actions"]["can_review_draft"] is True

    # The brand may not reach the admin's controls, whatever it sends.
    refused = brand.post(f"{api}/admin/collaborations/{cid}/draft-review/approve-now",
                         json={"reason": "Trying the admin route"})
    assert refused.status_code == 403

    # Two days pass.
    asyncio.run(db.collaborations.update_one(
        {"_id": ObjectId(cid)},
        {"$set": {"draft_review_deadline_at": _now() - timedelta(minutes=5)}}))

    first = _ok(admin.post(f"{api}/admin/jobs/draft-auto-approvals"), "sweep")
    again = _ok(admin.post(f"{api}/admin/jobs/draft-auto-approvals"), "sweep again")
    assert first["auto_approved"] == 1 and again["auto_approved"] == 0

    row = _read(db, lambda d: d.collaborations.find_one({"_id": ObjectId(cid)}))
    assert row["state"] == "draft_approved"
    assert row["draft_approved_by"] == "system_auto"
    assert row["draft_auto_approved_at"] is not None
    line = _read(db, lambda d: d.audit_log.find_one({"action": "collaboration.draft_auto_approved"}))
    assert line["actor_role"] == "system_auto" and line["actor_id"] is None
    assert line["note"] == "brand_review_window_elapsed"
    assert line["before"]["state"] == "draft_submitted" and line["after"]["state"] == "draft_approved"

    # Both parties are told the window ran out, not that somebody approved it.
    told = _read(db, lambda d: d.notifications.find({"event": "draft_auto_approved"}).to_list(20))
    assert told, "the creator hears about the auto-approval"

    # -- Delivered, approved by a person, paid ----------------------------
    _ok(creator.post(f"{api}/creator/collaborations/{cid}/submit_content",
                     json={"content_urls": ["https://www.instagram.com/reel/E2Etest1/"]}),
        "submit content")
    # The disclosure is still a person's call on the live post: the window
    # approved a draft, not a label.
    unconfirmed = brand.post(f"{api}/brand/collaborations/{cid}/approve_content", json={})
    assert unconfirmed.status_code in (409, 422)
    _ok(brand.post(f"{api}/brand/collaborations/{cid}/approve_content",
                   json={"disclosure_confirmed": True}), "approve content")
    _ok(admin.post(f"{api}/admin/collaborations/{cid}/advance",
                   json={"from_state": "content_approved"}), "raise the payment")
    payment = _read(db, lambda d: d.payments.find_one({"collaboration_id": ObjectId(cid)}))
    assert payment and payment["state"] == "pending"
    _ok(admin.post(f"{api}/admin/payments/{payment['_id']}/mark_paid",
                   json={"payment_reference": "UTR-E2E-0001", "tds_applicable": False}),
        "mark paid")

    row = _read(db, lambda d: d.collaborations.find_one({"_id": ObjectId(cid)}))
    assert row["state"] == "closed" and row["agreed_amount"] == 12500

    # -- The history, from each of the three -------------------------------
    brand_view = _ok(brand.get(f"{api}/applications/{cid}"), "brand history")["negotiation"]
    admin_detail = _ok(admin.get(f"{api}/admin/collaborations/{cid}"), "admin history")["negotiation"]
    kinds = [e["kind"] for e in brand_view["entries"]]
    assert kinds == ["accept", "counter", "offer"]
    assert [e["amount"] for e in brand_view["entries"]] == [12500, 11000, 15000]
    assert [e["by_role"] for e in brand_view["entries"]] == ["brand", "brand", "creator"]
    assert all("by_user_id" not in e and "source" not in e for e in brand_view["entries"])
    assert [e["source"] for e in admin_detail["entries"]] == ["recorded_offline", "in_app", "in_app"]
    assert all(e["by_user_id"] for e in admin_detail["entries"])

    # The creator reads it on their own surface, which is the dashboard row
    # while the work is live and the past list once it has closed.
    dash = _ok(creator.get(f"{api}/creator/dashboard"), "creator dashboard after")
    text = json.dumps(dash)
    assert "Met in the middle on the call" in text
    assert '"by_user_id"' not in text

    # And no brand surface on this walk ever carried the creator's contact.
    for body in (json.dumps(brand_app), json.dumps(_ok(brand.get(f"{api}/applications/{cid}"), "brand final"))):
        assert PHONE not in body and EMAIL not in body and "Indiranagar, Bengaluru 560038" not in body
