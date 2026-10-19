"""The dispute freeze, derived from the routes and driven rather than read.

This replaces a test that listed eleven handler names by hand and grepped each
one's source for the string `_refuse_if_disputed`. It had two blind spots, and
both turned out to be occupied:

- **A hand-written list cannot see a route nobody added to it.** The four
  draft routes moved state on a frozen collaboration for as long as the draft
  gate has existed, and so did a second booking route and the creator's own QR
  check-in. None of them was on the list, so none of them was checked.
- **A source grep cannot tell a guard that runs from one that is present and
  does nothing** — called on the wrong document, or after the write it was
  meant to stop.

So the set of routes is computed: every registered route that can reach an
update to a collaboration document, followed through the helpers it calls.
Each one is then either **driven** — a frozen collaboration is seeded, the real
handler is called, and the stored document is read back — or **exempt**, with
the reason beside it. A route in neither table fails, which is what makes the
next route written the old way fail here on the day it ships.

Every driver also runs a **control**: the same call on the same row with no
dispute must change the stored document. Without it, a driver that never
reached the guard — a wrong state, a wrong role, a missing slot — would report
"refused" for a reason that has nothing to do with the freeze.
"""

from __future__ import annotations

import ast
import asyncio
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException
from fastapi.routing import APIRoute
from mongomock_motor import AsyncMongoMockClient

import server

LOOP = None
_UPLOADS = Path(tempfile.mkdtemp(prefix="freeze-uploads-"))


def run(body):
    """One loop for the module, the arrangement `test_money_paths.py` uses —
    `asyncio.run` closes the loop mongomock's cursors were built on."""
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()

    async def go():
        db = AsyncMongoMockClient()["dispute_freeze"]
        original_db, original_dir = server.db, server.PRIVATE_UPLOAD_DIR
        server.db, server.PRIVATE_UPLOAD_DIR = db, _UPLOADS
        server._SLA_CACHE.clear()
        try:
            return await body(db)
        finally:
            server.db, server.PRIVATE_UPLOAD_DIR = original_db, original_dir
            server._SLA_CACHE.clear()

    return LOOP.run_until_complete(go())


def _now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Which routes can move a collaboration
# ---------------------------------------------------------------------------

_WRITES = {"update_one", "update_many", "find_one_and_update", "replace_one", "find_one_and_replace"}
_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


def _module_functions():
    tree = ast.parse(Path(server.__file__).read_text())
    return {
        n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _updates_a_collaboration(fn) -> bool:
    """`db.collaborations.<update>(...)` anywhere in the body. Inserts are left
    out on purpose: a row that did not exist a moment ago cannot be under
    dispute."""
    return any(
        isinstance(c, ast.Call)
        and isinstance(c.func, ast.Attribute)
        and c.func.attr in _WRITES
        and isinstance(c.func.value, ast.Attribute)
        and c.func.value.attr == "collaborations"
        for c in ast.walk(fn)
    )


def _collaboration_writing_routes() -> dict:
    """`{endpoint name: path}` for every registered mutating route whose call
    closure reaches an update to a collaboration.

    Walked from `app.routes`, never from the decorators: a route declared after
    its router was included is not a route, whatever the source says, and the
    first version of this test found two of those.
    """
    funcs = _module_functions()
    memo: dict = {}

    def reaches(name, seen=()):
        if name in memo:
            return memo[name]
        if name in seen:
            return False
        fn = funcs[name]
        hit = _updates_a_collaboration(fn) or any(
            reaches(c.func.id, seen + (name,))
            for c in ast.walk(fn)
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id in funcs
        )
        memo[name] = hit
        return hit

    out = {}
    for r in server.app.routes:
        if not isinstance(r, APIRoute) or not (r.methods & _MUTATING):
            continue
        name = r.endpoint.__name__
        if name in funcs and reaches(name):
            out[name] = r.path
    return out


def _registered_endpoints() -> set:
    return {r.endpoint.__name__ for r in server.app.routes if isinstance(r, APIRoute)}


# ---------------------------------------------------------------------------
# The scene
# ---------------------------------------------------------------------------

_IN_A_WEEK = _now() + timedelta(days=7)


async def _scene(
    db,
    state,
    *,
    campaign_type="personal_table",
    execution_owner="brand",
    with_slot=False,
    payment_state=None,
    deliverable_items=None,
    requires_draft_approval=True,
    disputed=False,
    **collab_extra,
):
    """A brand, a creator, an assigned manager, a campaign and one
    collaboration, written the way the app writes them."""
    brand_oid, creator_oid, manager_oid = ObjectId(), ObjectId(), ObjectId()
    campaign_oid, collab_oid, slot_oid = ObjectId(), ObjectId(), ObjectId()
    await db.users.insert_many(
        [
            {"_id": brand_oid, "role": "brand_manager", "name": "Toit", "brand_id": brand_oid},
            {"_id": creator_oid, "role": "creator", "name": "Asha", "status": "active"},
            {"_id": manager_oid, "role": "campaign_manager", "name": "Meera"},
        ]
    )
    await db.brand_profiles.insert_one(
        {"user_id": brand_oid, "business_name": "Toit", "verified": True,
         "verification_state": "verified", "verified_at": _now()}
    )
    await db.creator_profiles.insert_one(
        {"user_id": creator_oid, "name": "Asha", "verification_status": "verified",
         "verified_at": _now(), "payout_method": "upi", "payout_upi": "asha@okhdfc",
         "pan": "ABCDE1234F", "full_address": "12 Main Rd, Indiranagar"}
    )
    await db.campaigns.insert_one(
        {"_id": campaign_oid, "brand_id": brand_oid, "title": "Tasting",
         "status": "in_progress", "campaign_type": campaign_type,
         "execution_owner": execution_owner, "manager_id": manager_oid,
         "compensation_type": "fixed", "budget_per_creator": 12000,
         "creators_needed": 5, "requires_draft_approval": requires_draft_approval,
         "requires_slot_confirmation": True,
         "start_date": _now() - timedelta(days=30), "end_date": _now() + timedelta(days=30),
         **({"deliverable_items": deliverable_items} if deliverable_items else {})}
    )
    collab = {
        "_id": collab_oid, "campaign_id": campaign_oid, "creator_id": creator_oid,
        "state": state, "state_since": _now() - timedelta(days=30),
        "updated_at": _now() - timedelta(days=30),
        "agreed_amount": 12000, "agreed_at": _now() - timedelta(days=40),
        "quoted_rate": 12000, "active": True,
        **collab_extra,
    }
    if with_slot:
        await db.campaign_slots.insert_many(
            [
                {"_id": slot_oid, "campaign_id": campaign_oid, "starts_at": _IN_A_WEEK,
                 "ends_at": _IN_A_WEEK + timedelta(hours=2), "capacity": 4,
                 "booked_count": 1 if state != "commercial_agreed" else 0},
                {"_id": ObjectId(), "campaign_id": campaign_oid,
                 "starts_at": _IN_A_WEEK + timedelta(days=1),
                 "ends_at": _IN_A_WEEK + timedelta(days=1, hours=2), "capacity": 4,
                 "booked_count": 0},
            ]
        )
        if state != "commercial_agreed":
            collab.update(slot_id=slot_oid, scheduled_at=_IN_A_WEEK,
                          slot_booked_at=_now() - timedelta(days=2))
    if disputed:
        collab["dispute"] = {"state": "open", "raised_by_role": "creator",
                             "raised_at": _now(), "reason": "The fee changed after the shoot."}
    await db.collaborations.insert_one(collab)

    payment_oid = None
    if payment_state:
        payment_oid = ObjectId()
        await db.payments.insert_one(
            {"_id": payment_oid, "collaboration_id": collab_oid, "state": payment_state,
             "agreed_amount": 12000, "platform_fee": 0.0, "fee_percent": 0.0,
             "creator_payout": 12000, "brand_invoice_amount": 12000,
             "brand_invoice_state": "pending", "created_at": _now(),
             **({"paid_at": _now()} if payment_state == "paid" else {})}
        )

    def as_user(oid, role, name):
        return {"_id": str(oid), "role": role, "name": name,
                **({"brand_id": oid} if role == "brand_manager" else {})}

    return {
        "collab_id": str(collab_oid), "collab_oid": collab_oid,
        "campaign_id": str(campaign_oid), "campaign_oid": campaign_oid,
        "slot_id": str(slot_oid), "slot_oid": slot_oid,
        "payment_id": str(payment_oid) if payment_oid else None,
        "brand": as_user(brand_oid, "brand_manager", "Toit"),
        "creator": as_user(creator_oid, "creator", "Asha"),
        "manager": as_user(manager_oid, "campaign_manager", "Meera"),
        "admin": {"_id": str(ObjectId()), "role": "admin", "name": "Admin"},
    }


class _Upload:
    """The slice of `UploadFile` the private-upload path touches."""

    def __init__(self, data: bytes, filename: str):
        self._data, self._read, self.filename = data, False, filename

    async def read(self, n=-1):
        if self._read:
            return b""
        self._read = True
        return self._data

    async def close(self):
        return None


def _png():
    return _Upload(b"\x89PNG\r\n\x1a\n" + b"0" * 64, "story.png")


# ---------------------------------------------------------------------------
# One driver per route: the state the route acts from, how to build the scene,
# and how to call the real handler.
# ---------------------------------------------------------------------------


class Driver:
    def __init__(self, state, call, *, prepare=None, **scene):
        self.state, self.call, self.prepare, self.scene = state, call, prepare, scene


async def _second_slot(db, s):
    other = await db.campaign_slots.find_one(
        {"campaign_id": s["campaign_oid"], "_id": {"$ne": s["slot_oid"]}}
    )
    return str(other["_id"])


async def _proof_on_record(db, s):
    """A screenshot already attached, so there is something to remove."""
    await server.add_content_proof(s["collab_id"], _png(), "Story one", s["creator"])
    row = await db.collaborations.find_one({"_id": s["collab_oid"]})
    return row["content_proofs"][0]["id"]


async def _terms_on_record(db, s):
    await db.collaborations.update_one(
        {"_id": s["collab_oid"]},
        {"$set": {"terms": {"issued_at": _now(), "accepted_at": None, "agreed_amount": 12000}}},
    )


async def _checkin_code(db, s):
    slot = await db.campaign_slots.find_one({"_id": s["slot_oid"]})
    await db.campaign_slots.update_one(
        {"_id": s["slot_oid"]}, {"$set": {"starts_at": _now(), "ends_at": _now() + timedelta(hours=2)}}
    )
    await db.collaborations.update_one(
        {"_id": s["collab_oid"]}, {"$set": {"scheduled_at": _now(), "slot_confirmed_at": _now()}}
    )
    campaign = await db.campaigns.find_one({"_id": s["campaign_oid"]})
    slot = await db.campaign_slots.find_one({"_id": s["slot_oid"]})
    return server._mint_checkin_code(slot, campaign)["code"]


_STORY = [{"type": "story", "quantity": 1}]

DRIVERS = {
    # --- the creator ------------------------------------------------------
    "submit_collab_content": Driver(
        "attended",
        lambda db, s, _: server.submit_collab_content(
            s["collab_id"], server.SubmitContentPayload(content_urls=["https://instagram.com/p/x"]),
            s["creator"]),
        requires_draft_approval=False,
    ),
    "add_content_proof": Driver(
        "attended",
        lambda db, s, _: server.add_content_proof(s["collab_id"], _png(), "Story", s["creator"]),
        deliverable_items=_STORY, requires_draft_approval=False,
    ),
    "remove_content_proof": Driver(
        "attended",
        lambda db, s, proof_id: server.remove_content_proof(s["collab_id"], proof_id, s["creator"]),
        prepare=_proof_on_record,
        deliverable_items=_STORY, requires_draft_approval=False,
    ),
    "creator_accept_terms": Driver(
        "commercial_agreed",
        lambda db, s, _: server.creator_accept_terms(s["collab_id"], s["creator"]),
        prepare=_terms_on_record,
    ),
    "creator_book_slot": Driver(
        "commercial_agreed",
        lambda db, s, _: server.creator_book_slot(
            s["collab_id"],
            server.CreatorBookSlotPayload(slot_id=s["slot_id"], preferred_time=_IN_A_WEEK + timedelta(minutes=30)),
            s["creator"]),
        with_slot=True,
    ),
    "book_slot": Driver(
        "commercial_agreed",
        lambda db, s, _: server.book_slot(s["slot_id"], s["creator"]),
        with_slot=True, campaign_type="group_event",
    ),
    "creator_self_check_in": Driver(
        "slot_booked",
        lambda db, s, code: server.creator_self_check_in(server.CheckInCodePayload(code=code), s["creator"]),
        prepare=_checkin_code,
        with_slot=True,
    ),
    "creator_confirm_delivery_address": Driver(
        "commercial_agreed",
        lambda db, s, _: server.creator_confirm_delivery_address(
            s["collab_id"], server.ConfirmDeliveryAddressPayload(), s["creator"]),
        campaign_type="delivery",
    ),
    "creator_confirm_delivery_received": Driver(
        "dispatched",
        lambda db, s, _: server.creator_confirm_delivery_received(
            s["collab_id"], server.ConfirmDeliveryReceivedPayload(), s["creator"]),
        campaign_type="delivery",
    ),
    "withdraw_application": Driver(
        "verified",
        lambda db, s, _: server.withdraw_application(
            s["collab_id"], server.ReasonPayload(reason="Changed my mind"), s["creator"]),
    ),
    "creator_cancel_slot": Driver(
        "slot_booked",
        lambda db, s, _: server.creator_cancel_slot(
            s["collab_id"], server.CreatorCancelSlotPayload(reason="Clash"), s["creator"]),
        with_slot=True,
    ),
    "submit_draft_file": Driver(
        "attended",
        lambda db, s, _: server.submit_draft_file(
            s["collab_id"], _Upload(b"\x00\x00\x00\x18ftypmp42" + b"0" * 64, "cut.mp4"), None,
            s["creator"]),
    ),
    "submit_draft_link": Driver(
        "attended",
        lambda db, s, _: server.submit_draft_link(
            s["collab_id"], server.DraftLinkPayload(draft_url="https://drive.example.com/cut"),
            s["creator"]),
    ),
    # --- whoever runs it --------------------------------------------------
    "brand_accept_applicant": Driver(
        "verified",
        lambda db, s, _: server.brand_accept_applicant(
            s["collab_id"], server.BrandAcceptPayload(), s["brand"]),
        agreed_at=None, agreed_amount=None,
    ),
    "brand_decline_applicant": Driver(
        "verified",
        lambda db, s, _: server.brand_decline_applicant(
            s["collab_id"], server.DecisionPayload(reason="Not this time"), s["brand"]),
    ),
    "brand_record_agreed_amount": Driver(
        "accepted",
        lambda db, s, _: server.brand_record_agreed_amount(
            s["collab_id"], server.AgreedAmountPayload(agreed_amount=12000), s["brand"]),
        agreed_at=None,
    ),
    "brand_approve_content": Driver(
        "content_submitted",
        lambda db, s, _: server.brand_approve_content(
            s["collab_id"], server.DisclosureCheckPayload(disclosure_confirmed=True), s["brand"]),
        content_urls=["https://instagram.com/p/x"],
    ),
    "brand_request_changes": Driver(
        "content_submitted",
        lambda db, s, _: server.brand_request_changes(
            s["collab_id"], server.DecisionPayload(reason="Tag the venue please"), s["brand"]),
        content_urls=["https://instagram.com/p/x"],
    ),
    "accept_partial_delivery": Driver(
        "content_submitted",
        lambda db, s, _: server.accept_partial_delivery(
            s["collab_id"],
            server.PartialDeliveryPayload(delivered={"story": 1}, agreed_amount=12000,
                                          note="One of two stories went up"),
            s["brand"]),
        content_urls=["https://instagram.com/p/x"],
        deliverable_items=[{"type": "story", "quantity": 2}],
    ),
    "brand_confirm_slot": Driver(
        "slot_booked",
        lambda db, s, _: server.brand_confirm_slot(s["collab_id"], s["brand"]),
        with_slot=True, slot_confirmed_at=None,
    ),
    "brand_decline_slot": Driver(
        "slot_booked",
        lambda db, s, _: server.brand_decline_slot(
            s["collab_id"], server.ReasonPayload(reason="Kitchen closed"), s["brand"]),
        with_slot=True, slot_confirmed_at=None,
    ),
    "brand_check_in_creator": Driver(
        "slot_booked",
        lambda db, s, _: server.brand_check_in_creator(s["collab_id"], s["brand"]),
        with_slot=True, slot_confirmed_at=_now(),
    ),
    "approve_draft": Driver(
        "draft_submitted",
        lambda db, s, _: server.approve_draft(
            s["collab_id"], server.DisclosureCheckPayload(disclosure_confirmed=True), s["brand"]),
        draft={"kind": "link", "draft_url": "https://drive.example.com/cut", "submitted_at": _now()},
    ),
    "request_draft_changes": Driver(
        "draft_submitted",
        lambda db, s, _: server.request_draft_changes(
            s["collab_id"], server.DraftDecisionPayload(note="Show the menu"), s["brand"]),
        draft={"kind": "link", "draft_url": "https://drive.example.com/cut", "submitted_at": _now()},
    ),
    "dispatch_delivery": Driver(
        "address_confirmed",
        lambda db, s, _: server.dispatch_delivery(
            s["collab_id"], server.DispatchDeliveryPayload(tracking_reference="AWB123"), s["admin"]),
        campaign_type="delivery",
    ),
    # --- the WeAre manager --------------------------------------------------
    "manager_confirm_slot": Driver(
        "slot_booked",
        lambda db, s, _: server.manager_confirm_slot(s["collab_id"], s["manager"]),
        with_slot=True, slot_confirmed_at=None, execution_owner="weare",
    ),
    "manager_decline_slot": Driver(
        "slot_booked",
        lambda db, s, _: server.manager_decline_slot(
            s["collab_id"], server.ReasonPayload(reason="Kitchen closed"), s["manager"]),
        with_slot=True, slot_confirmed_at=None, execution_owner="weare",
    ),
    "check_in_creator": Driver(
        "slot_booked",
        lambda db, s, _: server.check_in_creator(s["collab_id"], s["manager"]),
        with_slot=True, slot_confirmed_at=_now(), execution_owner="weare",
    ),
    "mark_no_show": Driver(
        "slot_booked",
        lambda db, s, _: server.mark_no_show(
            s["collab_id"], server.NoShowPayload(note="Never arrived"), s["manager"]),
        with_slot=True, slot_confirmed_at=_now(), execution_owner="weare",
    ),
    "reschedule_creator": Driver(
        "slot_booked",
        lambda db, s, other: server.reschedule_creator(
            s["collab_id"], server.ReschedulePayload(slot_id=other, reason="Asked to move"),
            s["manager"]),
        prepare=_second_slot,
        with_slot=True, slot_confirmed_at=_now(), execution_owner="weare",
    ),
    "update_slot": Driver(
        "slot_booked",
        lambda db, s, _: server.update_slot(
            s["slot_id"],
            server.UpdateSlotPayload(starts_at=_IN_A_WEEK + timedelta(hours=1),
                                     ends_at=_IN_A_WEEK + timedelta(hours=3)),
            s["manager"]),
        with_slot=True, slot_confirmed_at=_now(), execution_owner="weare",
    ),
    # --- the console ------------------------------------------------------
    "advance_collaboration": Driver(
        "attended",
        lambda db, s, _: server.advance_collaboration(
            s["collab_id"], server.AdvanceCollabPayload(from_state="attended"), s["admin"]),
        requires_draft_approval=False,
    ),
    "revert_collaboration": Driver(
        "attended",
        lambda db, s, _: server.revert_collaboration(
            s["collab_id"], server.ReasonPayload(reason="Marked by mistake"), s["admin"]),
        with_slot=True,
    ),
    "decline_applicant": Driver(
        "verified",
        lambda db, s, _: server.decline_applicant(
            s["collab_id"], server.ReasonPayload(reason="Not this time"), s["admin"]),
    ),
    "mark_payment_paid": Driver(
        "in_payment",
        lambda db, s, _: server.mark_payment_paid(
            s["payment_id"], server.MarkPaidPayload(payment_reference="NEFT-1"), s["admin"]),
        payment_state="pending",
    ),
    "refund_payment": Driver(
        "closed",
        lambda db, s, _: server.refund_payment(
            s["payment_id"], server.RefundPayload(reason="Clawed back"), s["admin"]),
        payment_state="paid",
    ),
    "run_lifecycle_job": Driver(
        "attended",
        lambda db, s, _: server.run_lifecycle_job(s["admin"]),
    ),
}

# Routes that write to a collaboration and are deliberately not frozen.
EXEMPT = {
    # The freeze itself: raising sets it and withdrawing lifts it. A guard on
    # either would make a dispute impossible to open or to take back.
    "raise_dispute": "opens the freeze",
    "withdraw_dispute": "the side that raised it lifting it",
    # The mediator's decision is what ends the freeze; it cannot be behind it.
    "resolve_dispute": "the decision that ends the freeze",
    # A post that is legally problematic has to come down whether or not there
    # is an argument about the money — those are different questions.
    "request_takedown": "a live post can need taking down mid-dispute",
    "respond_to_takedown": "the creator's answer to a takedown is not frozen either",
}

# Routes that only ever act on states earlier than any dispute can be raised
# in. Asserted against `DISPUTABLE_STATES` rather than trusted, so widening
# that tuple backwards turns these into drivers that are missing.
BEFORE_ANY_DISPUTE = {
    "close_brand_campaign": ("applied", "verified"),
    "admin_close_campaign": ("applied", "verified"),
}

# Driven, and currently moving a frozen collaboration. Each entry is a finding,
# reported rather than fixed. `strict` so that the day a guard lands the entry
# XPASSes and has to be taken off this list.
KNOWN_UNFROZEN = {
    "book_slot": "the second booking route reaches `_claim_slot` without the guard `creator_book_slot` has",
    "creator_self_check_in": "QR check-in moves slot_booked → attended; the manual check-ins are guarded",
    "creator_accept_terms": "accepting the terms snapshot the mediator is reading",
    "update_slot": "editing a slot reschedules every creator booked on it",
    "refund_payment": "cancels the collaboration under an open dispute",
    "run_lifecycle_job": "chases a frozen creator and stamps `content_overdue` on them",
}


# ---------------------------------------------------------------------------
# The tables are complete
# ---------------------------------------------------------------------------


def test_every_route_that_writes_a_collaboration_is_driven_or_exempt():
    routes = _collaboration_writing_routes()
    accounted = set(DRIVERS) | set(EXEMPT) | set(BEFORE_ANY_DISPUTE)
    missing = {name: path for name, path in routes.items() if name not in accounted}
    assert not missing, (
        "These routes write to a collaboration and nothing says whether the "
        f"dispute freeze applies: {missing}. Add a driver, or an exemption with "
        "the reason."
    )


def test_every_driver_is_a_route_that_writes_a_collaboration():
    """The other direction: a driver for a route that no longer writes, or no
    longer exists, is a test of nothing."""
    routes = _collaboration_writing_routes()
    stale = sorted(set(DRIVERS) - set(routes))
    assert not stale, f"no longer a collaboration-writing route: {stale}"


@pytest.mark.parametrize("name", sorted(EXEMPT))
def test_every_exemption_is_a_registered_route(name):
    """An exemption for a route that is not served is a hole in the table
    rather than a decision. This is how `resolve_dispute` was found: declared
    on `admin_router` below the line that includes it, so never registered."""
    if name == "resolve_dispute":
        pytest.xfail("declared after `api_router.include_router(admin_router)` — never served")
    assert name in _registered_endpoints()


def test_the_pre_dispute_routes_really_are_before_any_dispute():
    for name, states in BEFORE_ANY_DISPUTE.items():
        assert not set(states) & set(server.DISPUTABLE_STATES), (
            f"{name} acts on {states}, and a dispute can now be open there — "
            "give it a driver"
        )


def test_the_known_gaps_are_drivers():
    assert set(KNOWN_UNFROZEN) <= set(DRIVERS)


# ---------------------------------------------------------------------------
# Each route refuses, and its control moves
# ---------------------------------------------------------------------------


def _drive(name, *, disputed):
    d = DRIVERS[name]

    async def body(db):
        s = await _scene(db, d.state, disputed=False, **d.scene)
        extra = await d.prepare(db, s) if d.prepare else None
        if disputed:
            await db.collaborations.update_one(
                {"_id": s["collab_oid"]},
                {"$set": {"dispute": {"state": "open", "raised_by_role": "creator",
                                      "raised_at": _now(), "reason": "The fee changed."}}},
            )
        before = await db.collaborations.find_one({"_id": s["collab_oid"]})
        error = None
        try:
            await d.call(db, s, extra)
        except HTTPException as exc:
            error = exc
        after = await db.collaborations.find_one({"_id": s["collab_oid"]})
        return before, after, error

    return run(body)


@pytest.mark.parametrize("name", sorted(DRIVERS))
def test_the_control_moves_the_collaboration(name):
    """Without a dispute the same call changes the stored row. If it does not,
    the driver never reached the guard and the frozen run below proves
    nothing."""
    before, after, error = _drive(name, disputed=False)
    assert before != after, f"{name} did not move the collaboration: {error and error.detail}"


@pytest.mark.parametrize(
    "name",
    [
        pytest.param(n, marks=pytest.mark.xfail(reason=KNOWN_UNFROZEN[n], strict=True))
        if n in KNOWN_UNFROZEN
        else n
        for n in sorted(DRIVERS)
    ],
)
def test_a_frozen_collaboration_does_not_move(name):
    before, after, error = _drive(name, disputed=True)
    assert after == before, f"{name} moved a frozen collaboration"
    assert error is not None and error.status_code == 409, (
        f"{name} left the row alone but did not refuse"
    )
    assert isinstance(error.detail, dict) and error.detail.get("code") == "disputed"


def test_notes_and_ratings_are_not_on_the_collaboration():
    """The paper trail stays open during a mediation, and it can: notes and
    ratings live in their own collections, so neither route is in the set
    above at all."""
    routes = _collaboration_writing_routes()
    assert "add_collaboration_note" not in routes
    assert "rate_collaboration" not in routes
