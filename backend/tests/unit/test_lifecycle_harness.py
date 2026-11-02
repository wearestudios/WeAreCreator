"""Every ladder, walked through the real handlers, with both kinds of money.

`tests/test_lifecycle_walk.py` is the integration version of this and it is the
one that proves the whole stack, but it needs a live server behind TLS and so
it cannot gate a pull request. This file is the half that can. It drives the
same steps through the same route functions against mongomock, and after
**every** step it reads the collaboration back and asks each of the three
parties what they are supposed to do next.

That second half is the point. The ladders below existed and every state on
them was reachable one at a time; what nobody had checked was that the screens
agreed with the ladder at each rung:

- a **barter** collaboration could never leave `content_approved`, because the
  only next rung was `in_payment` and the console refuses `in_payment` with no
  agreed amount — which a barter brief never has, on purpose;
- a **delivery** collaboration at `commercial_agreed` told the creator to book a
  slot on a brief with no venue;
- a dispute resolved as a **refund** cancelled the payment and left the
  collaboration standing on `content_approved`, so the creator's card said
  "Payment is being processed" about money that had just been refunded.

Each of those is a case here, by name. Run the suite on the commit before the
fixes and these are the tests that fail.

Calling a route function directly skips its `Depends`, which is right here —
the roles are pinned elsewhere (`test_on_behalf_overrides.py`,
`test_scope_mutations.py`) and this file is about the state machine.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId
from mongomock_motor import AsyncMongoMockClient

import server

LOOP = None


def run(body):
    """One loop, kept in a module global — see `test_money_paths.run`."""
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()

    async def go():
        db = AsyncMongoMockClient()["lifecycle_harness"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return LOOP.run_until_complete(go())


def _now():
    return datetime.now(timezone.utc)


ADMIN = {"_id": str(ObjectId()), "role": "admin", "name": "Priya"}

# The four shapes a campaign walks. Two independent substitutions, the same
# way `_collab_ladder` composes them: the draft gate, and venue versus delivery.
LADDERS = {
    "venue": dict(campaign_type="group_event", requires_draft_approval=False),
    "venue+draft": dict(campaign_type="group_event", requires_draft_approval=True),
    "delivery": dict(campaign_type="delivery", requires_draft_approval=False),
    "delivery+draft": dict(campaign_type="delivery", requires_draft_approval=True),
}

COMPENSATION = {
    "paid": dict(compensation_type="fixed", budget_per_creator=12000),
    "barter": dict(
        compensation_type="barter",
        budget_per_creator=12000,  # vestigial, the way a converted brief keeps it
        barter_description="Dinner for two and a bottle of the house wine",
    ),
}

CASES = [(ladder, money) for ladder in LADDERS for money in COMPENSATION]


async def _world(db, *, ladder: str, money: str, total_budget=100000):
    """A verified brand running its own brief, one verified creator, one slot,
    and a fresh application at `applied`.

    **Brand-run**, so every brand-owned step is taken by the brand itself
    rather than by the console standing in for it — that is the ordinary path,
    and the overrides have their own file.
    """
    brand_oid, creator_oid = ObjectId(), ObjectId()
    campaign_oid, collab_oid, slot_oid = ObjectId(), ObjectId(), ObjectId()
    await db.users.insert_many(
        [
            {"_id": brand_oid, "role": "brand_manager", "name": "Toit",
             "brand_id": brand_oid, "phone": "+919900000101"},
            {"_id": creator_oid, "role": "creator", "name": "Asha",
             "phone": "+919900000102"},
        ]
    )
    await db.brand_profiles.insert_one(
        {"user_id": brand_oid, "business_name": "Toit", "verified": True,
         "verification_state": "verified", "verified_at": _now()}
    )
    await db.creator_profiles.insert_one(
        {"user_id": creator_oid, "name": "Asha", "verification_status": "verified",
         "verified_at": _now(), "full_address": "12 MG Road, Bengaluru",
         "payout_method": "upi", "payout_upi": "asha@okhdfc", "pan": "ABCDE1234F"}
    )
    shape = LADDERS[ladder]
    await db.campaigns.insert_one(
        {"_id": campaign_oid, "brand_id": brand_oid, "title": "Tasting night",
         "status": "open", "execution_owner": "brand",
         "creators_needed": 3, "total_budget": total_budget,
         "start_date": _now() - timedelta(days=1),
         "end_date": _now() + timedelta(days=30),
         "event_date": _now() + timedelta(days=5),
         "required_disclosure": "paid_partnership",
         **shape, **COMPENSATION[money]}
    )
    await db.campaign_slots.insert_one(
        {"_id": slot_oid, "campaign_id": campaign_oid,
         "starts_at": _now() + timedelta(days=5),
         "ends_at": _now() + timedelta(days=5, hours=2),
         "capacity": 3, "booked_count": 0}
    )
    await db.collaborations.insert_one(
        {"_id": collab_oid, "campaign_id": campaign_oid, "creator_id": creator_oid,
         "state": "applied", "quoted_rate": 12000, "active": True,
         "created_at": _now(), "state_since": _now(), "updated_at": _now()}
    )
    return {
        "brand": {"_id": str(brand_oid), "role": "brand_manager", "name": "Toit",
                  "brand_id": brand_oid},
        "creator": {"_id": str(creator_oid), "role": "creator", "name": "Asha"},
        "collab_id": str(collab_oid), "collab_oid": collab_oid,
        "campaign_oid": campaign_oid, "slot_id": str(slot_oid),
        "brand_oid": brand_oid, "creator_oid": creator_oid,
    }


# --- the steps, each through the route its owner actually calls ------------


async def _advance(w, frm, **extra):
    return await server.advance_collaboration(
        w["collab_id"], server.AdvanceCollabPayload(from_state=frm, **extra), ADMIN
    )


async def step(db, w, state, money):
    """Take the step out of `state`, as the party who owns it."""
    cid = w["collab_id"]
    if state == "applied":
        await _advance(w, "applied")
    elif state == "verified":
        await server.brand_accept_applicant(cid, server.BrandAcceptPayload(), w["brand"])
    elif state == "accepted":
        await _advance(w, "accepted", agreed_amount=12000 if money == "paid" else None)
    elif state == "commercial_agreed":
        campaign = await db.campaigns.find_one({"_id": w["campaign_oid"]})
        if server._is_delivery(campaign):
            await server.creator_confirm_delivery_address(
                cid, server.ConfirmDeliveryAddressPayload(), w["creator"]
            )
        else:
            await server.creator_book_slot(
                cid, server.CreatorBookSlotPayload(slot_id=w["slot_id"]), w["creator"]
            )
    elif state == "slot_booked":
        await _advance(w, "slot_booked")
    elif state == "address_confirmed":
        await server.dispatch_delivery(
            cid, server.DispatchDeliveryPayload(tracking_reference="DTDC-77"), w["brand"]
        )
    elif state == "dispatched":
        await server.creator_confirm_delivery_received(
            cid, server.ConfirmDeliveryReceivedPayload(), w["creator"]
        )
    elif state in ("attended", "received"):
        campaign = await db.campaigns.find_one({"_id": w["campaign_oid"]})
        if server._requires_draft_approval(campaign):
            await server.submit_draft_link(
                cid, server.DraftLinkPayload(draft_url="https://drive.example/draft"),
                w["creator"],
            )
        else:
            await server.submit_collab_content(
                cid, server.SubmitContentPayload(
                    content_urls=["https://www.instagram.com/reel/abc123/"]
                ), w["creator"],
            )
    elif state == "draft_submitted":
        await server.approve_draft(
            cid, server.DisclosureCheckPayload(disclosure_confirmed=True), w["brand"]
        )
    elif state == "draft_approved":
        await server.submit_collab_content(
            cid, server.SubmitContentPayload(
                content_urls=["https://www.instagram.com/reel/abc123/"]
            ), w["creator"],
        )
    elif state == "content_submitted":
        await server.brand_approve_content(
            cid, server.DisclosureCheckPayload(disclosure_confirmed=True), w["brand"]
        )
    elif state == "content_approved":
        # The console's one button here: into payment on a paid brief, and
        # straight to the end on a barter one.
        await _advance(w, "content_approved")
    elif state == "in_payment":
        payment = await db.payments.find_one({"collaboration_id": w["collab_oid"]})
        await server.mark_payment_paid(
            str(payment["_id"]), server.MarkPaidPayload(payment_reference="NEFT-1"), ADMIN
        )
    else:  # pragma: no cover - a state with no step is a bug in this table
        raise AssertionError(f"no step out of {state}")


def expected_ladder(ladder: str, money: str) -> list:
    """The rungs, written out by hand rather than read from `_collab_ladder` —
    a harness that asks the code what the answer is cannot disagree with it."""
    states = ["applied", "verified", "accepted", "commercial_agreed"]
    if ladder.startswith("delivery"):
        states += ["address_confirmed", "dispatched", "received"]
    else:
        states += ["slot_booked", "attended"]
    if ladder.endswith("+draft"):
        states += ["draft_submitted", "draft_approved"]
    states += ["content_submitted", "content_approved"]
    if money == "paid":
        states += ["in_payment"]
    return states + ["closed"]


# What the creator's own card says to do, rung by rung. `None` is a wait.
def creator_action(state, ladder, money):
    draft = ladder.endswith("+draft")
    return {
        "applied": None,
        "verified": None,
        "accepted": None,
        "commercial_agreed": "confirm_address" if ladder.startswith("delivery") else "book_slot",
        "slot_booked": "attend",
        "attended": "submit_draft" if draft else "submit_content",
        "address_confirmed": "await_dispatch",
        "dispatched": "confirm_received",
        "received": "submit_draft" if draft else "submit_content",
        "draft_submitted": "resubmit_draft",
        "draft_approved": "submit_content",
        "content_submitted": "resubmit_content",
        "content_approved": None,
        "in_payment": None,
        "closed": None,
    }[state]


# Who the process flow says is being waited on. `brand` is the runner here.
OWNER = {
    "applied": "admin",
    "verified": "brand",
    "accepted": "admin",
    "commercial_agreed": "creator",
    "slot_booked": "creator",
    "attended": "creator",
    "address_confirmed": "brand",
    "dispatched": "creator",
    "received": "creator",
    "draft_submitted": "brand",
    "draft_approved": "creator",
    "content_submitted": "brand",
    "content_approved": "admin",
    "in_payment": "admin",
    "closed": None,
}

_MONEY_WORDS = ("pay", "payout", "₹")


def check_personas(collab, campaign, ladder, money):
    """Ask all three parties what happens next, and check the answers agree
    with the rung — and with the money."""
    state = collab["state"]
    delivery = ladder.startswith("delivery")
    barter = money == "barter"

    # The creator's card.
    mine = server._creator_next_action(collab, campaign, True)
    assert mine["action"] == creator_action(state, ladder, money), (state, mine)
    if barter and mine.get("label"):
        assert not any(w in mine["label"].lower() for w in _MONEY_WORDS), (
            f"{state}: a barter creator is told about money — {mine['label']!r}"
        )
    if delivery and mine.get("label"):
        assert "slot" not in mine["label"].lower(), (state, mine["label"])

    # The ladder every console draws, and the one table they all read.
    nxt = server._next_action(collab, campaign)
    lifecycle = server._lifecycle_for(collab, campaign)
    rungs = [s["state"] for s in lifecycle["steps"]]
    assert rungs == expected_ladder(ladder, money), rungs
    if barter:
        assert "in_payment" not in rungs
        assert not any(w in (nxt["label"] or "").lower() for w in ("payment", "payout")), (
            f"{state}: the admin's next step on a barter brief mentions payment — "
            f"{nxt['label']!r}"
        )
    if delivery and state == "commercial_agreed":
        assert "slot" not in nxt["label"].lower(), nxt

    # The eight-stage flow, in all three voices.
    for side, viewer in (
        ("creator", {"role": "creator"}),
        ("brand", {"role": "brand_manager"}),
        ("admin", {"role": "admin"}),
    ):
        flow = server._process_flow(collab, campaign, viewer=viewer)
        line = flow["next_action"]
        if OWNER[state] is None:
            assert line is None or line["owner"] is None, (state, side, line)
            continue
        assert line["owner"] == OWNER[state], (state, side, line)
        label = line["label"].lower()
        if barter:
            assert not any(w in label for w in ("payout", "payment", "paid")), (
                f"{state}/{side}: {line['label']!r} on a barter brief"
            )
        if delivery:
            assert "slot" not in label, (state, side, line["label"])
        if barter:
            assert flow["stages"][-1]["label"] != "Payment", flow["stages"][-1]


@pytest.mark.parametrize("ladder,money", CASES, ids=[f"{l}-{m}" for l, m in CASES])
def test_a_collaboration_walks_every_rung_to_closed(ladder, money):
    """Applied to closed, one owner's step at a time, reading the row back."""

    async def body(db):
        w = await _world(db, ladder=ladder, money=money)
        rungs = expected_ladder(ladder, money)
        seen = []
        for i, state in enumerate(rungs):
            collab = await db.collaborations.find_one({"_id": w["collab_oid"]})
            campaign = await db.campaigns.find_one({"_id": w["campaign_oid"]})
            assert collab["state"] == state, (
                f"expected to stand on {state}, found {collab['state']} after {seen}"
            )
            check_personas(collab, campaign, ladder, money)
            seen.append(state)
            if state == "closed":
                break
            await step(db, w, state, money)
            after = await db.collaborations.find_one({"_id": w["collab_oid"]})
            assert after["state"] == rungs[i + 1], (
                f"{state} stepped to {after['state']}, not {rungs[i + 1]}"
            )
        final = await db.collaborations.find_one({"_id": w["collab_oid"]})
        payment = await db.payments.find_one({"collaboration_id": w["collab_oid"]})
        return final, payment

    final, payment = run(body)
    assert final["state"] == "closed"
    if money == "paid":
        assert payment["state"] == "paid"
        assert final["agreed_amount"] == 12000
    else:
        # No money moved, so no payment was ever raised, and the fee is absent
        # rather than zero.
        assert payment is None
        assert final.get("agreed_amount") is None


# --- disputes that end the arrangement --------------------------------------

DISPUTE_CASES = [
    ("venue", "paid", "content_approved"),
    ("venue", "paid", "in_payment"),
    ("venue", "barter", "content_approved"),
    ("delivery", "paid", "received"),
    ("delivery+draft", "barter", "draft_submitted"),
]


async def _walk_to(db, w, target, ladder, money):
    for state in expected_ladder(ladder, money):
        if state == target:
            return
        await step(db, w, state, money)
    raise AssertionError(f"{target} is not on the {ladder}/{money} ladder")


@pytest.mark.parametrize("resolution", ["refund", "cancelled"])
@pytest.mark.parametrize(
    "ladder,money,at", DISPUTE_CASES, ids=[f"{l}-{m}-{a}" for l, m, a in DISPUTE_CASES]
)
def test_a_dispute_that_ends_it_leaves_a_terminal_record(ladder, money, at, resolution):
    """Refund and call-off both end the arrangement — the row, the money, the
    budget and both parties have to agree that it has ended.

    The refund branch used to cancel the payment and leave the collaboration
    on the rung it was frozen on, so every screen went on describing a live
    collaboration whose money had just gone back.
    """

    async def body(db):
        w = await _world(db, ladder=ladder, money=money)
        await _walk_to(db, w, at, ladder, money)
        campaign = await db.campaigns.find_one({"_id": w["campaign_oid"]})
        committed_before = (await server._campaign_budget(campaign))["committed"]

        await server.raise_dispute(
            w["collab_id"],
            server.DisputePayload(reason="The brand never answered about the reshoot."),
            w["creator"],
        )
        await server.resolve_dispute(
            w["collab_id"],
            server.DisputeResolutionPayload(
                resolution=resolution, note="Neither side can deliver on this now."
            ),
            ADMIN,
        )
        collab = await db.collaborations.find_one({"_id": w["collab_oid"]})
        payment = await db.payments.find_one({"collaboration_id": w["collab_oid"]})
        campaign = await db.campaigns.find_one({"_id": w["campaign_oid"]})
        budget = await server._campaign_budget(campaign)
        told = {
            n["user_id"]
            for n in await db.notifications.find({"event": "dispute_resolved"}).to_list(None)
        }
        return w, collab, payment, committed_before, budget, told, campaign

    w, collab, payment, committed_before, budget, told, campaign = run(body)

    assert collab["state"] in server.TERMINAL_COLLAB_STATES
    assert collab["state"] == "cancelled"
    assert collab["active"] is False
    assert collab["cancellation_type"] == (
        "dispute_refund" if resolution == "refund" else "dispute"
    )
    assert collab["exit_reason"] == "Neither side can deliver on this now."
    assert collab["dispute"]["state"] == "resolved"
    assert collab["dispute"]["resolution"] == resolution
    if payment is not None:
        assert payment["state"] == "cancelled"
        assert payment.get("frozen") is False

    # The money comes back to the brief the moment the row leaves the
    # committed set — derived, so nothing had to remember to give it back.
    if money == "paid":
        assert committed_before == 12000
    assert budget["committed"] == 0

    # Both sides heard.
    assert w["creator_oid"] in told
    assert w["brand_oid"] in told

    # And nobody is told to do anything next: an exit is a banner, not a step.
    flow = server._process_flow(collab, campaign, viewer={"role": "creator"})
    assert flow["banner"] and flow["banner"]["tone"] == "ended"
    mine = server._creator_next_action(collab, campaign, True)
    assert mine["action"] is None
    assert not mine.get("label") or "payment" not in mine["label"].lower()
