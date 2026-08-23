"""Money and the exits, driven rather than read.

There are already tests for all of this. Most of them assert the *shape* of
the code — that `mark_payment_paid` contains the string `_refuse_if_disputed`,
that the resolution table has four keys, that a helper returns the right
number. That catches a guard somebody forgot to add and it is worth keeping.

What it cannot catch is the guard that is present and does nothing: called on
the wrong document, called after the write it was meant to prevent, or called
and its result dropped on the floor. `_refuse_if_disputed` *returns* rather
than raising in one of its two uses, so "the name appears in this function" and
"this function refuses" are genuinely different claims — and the second is the
one anybody actually cares about when the money is in the room.

So these tests build the row, call the real handler, and then **read the
database back**. Every one of them asserts on stored state after the call, not
just on the exception: a 409 raised after the payout landed is not a refusal,
it is a bug with an apology attached.

Companion to `test_unhappy_paths.py` (which holds the shapes) and
`test_money_and_exits.py` (which holds the arithmetic).
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId
from fastapi import HTTPException, params
from mongomock_motor import AsyncMongoMockClient

import server

LOOP = None


def role_guard(fn):
    """The `require_roles` guard the route actually carries, ready to call.

    **Calling a route function directly skips its `Depends`**, which is the
    trap `bulk_review` had to re-check by hand. So a test that calls
    `raise_dispute(..., admin_user)` proves nothing about whether an admin may
    raise one — FastAPI would have refused before the body ran.

    Reading the source for `require_roles("admin")` is the existing way round
    that and it is a string match. This pulls the real dependency object off
    the signature and runs it, so a guard that is present but lists the wrong
    roles fails here.
    """
    for p in inspect.signature(fn).parameters.values():
        dep = p.default
        if isinstance(dep, params.Depends) and dep.dependency is not None:
            if getattr(dep.dependency, "__name__", "") == "_guard":
                return dep.dependency
    raise AssertionError(f"{fn.__name__} declares no require_roles guard")


def guard_allows(fn, role):
    """Would FastAPI let this role through to the handler?"""
    guard = role_guard(fn)

    async def go():
        try:
            await guard({"_id": str(ObjectId()), "role": role})
            return True
        except HTTPException as err:
            assert err.status_code == 403
            return False

    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()
    return LOOP.run_until_complete(go())


def run(body):
    """One loop per call, kept in a module global.

    `asyncio.get_event_loop` fails inside a pytest-xdist worker thread, and
    `asyncio.run` closes the loop mongomock's cursors were built on.
    """
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()

    async def go():
        db = AsyncMongoMockClient()["money_paths"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return LOOP.run_until_complete(go())


def _now():
    return datetime.now(timezone.utc)


ADMIN = {"_id": str(ObjectId()), "role": "admin", "name": "Admin"}


async def _scene(
    db,
    *,
    state="in_payment",
    payment_state="pending",
    execution_owner="brand",
    scheduled_at=None,
    with_payment=True,
    deliverable_items=None,
):
    """A brand, a creator, a campaign, a collaboration, and usually a payment.

    Deliberately written the way the app writes these rows — `no_show_reported`
    absent rather than `False`, no `frozen` key until a dispute sets one — so a
    test cannot pass against a fixture the product would never produce.
    """
    brand_oid, creator_oid = ObjectId(), ObjectId()
    campaign_oid, collab_oid = ObjectId(), ObjectId()

    await db.users.insert_many(
        [
            {"_id": brand_oid, "role": "brand_manager", "name": "Toit",
             "brand_id": brand_oid, "phone": "+919900000001"},
            {"_id": creator_oid, "role": "creator", "name": "Asha",
             "phone": "+919900000002"},
        ]
    )
    await db.brand_profiles.insert_one(
        {"user_id": brand_oid, "business_name": "Toit", "verified": True,
         "verified_at": _now()}
    )
    await db.creator_profiles.insert_one(
        {"user_id": creator_oid, "name": "Asha", "verification_status": "verified",
         "verified_at": _now(), "payout_method": "upi",
         "payout_upi": "asha@okhdfc", "pan": "ABCDE1234F"}
    )
    await db.campaigns.insert_one(
        {"_id": campaign_oid, "brand_id": brand_oid, "title": "Tasting",
         "status": "in_progress", "execution_owner": execution_owner,
         "compensation_type": "fixed", "budget_per_creator": 12000,
         **({"deliverable_items": deliverable_items} if deliverable_items else {})}
    )
    await db.collaborations.insert_one(
        {"_id": collab_oid, "campaign_id": campaign_oid, "creator_id": creator_oid,
         "state": state, "agreed_amount": 12000, "agreed_at": _now(),
         "state_since": _now(),
         **({"scheduled_at": scheduled_at} if scheduled_at else {})}
    )
    payment_oid = None
    if with_payment:
        payment_oid = ObjectId()
        await db.payments.insert_one(
            {"_id": payment_oid, "collaboration_id": collab_oid,
             "state": payment_state, "agreed_amount": 12000,
             "platform_fee": 0.0, "fee_percent": 0.0, "creator_payout": 12000,
             "brand_invoice_amount": 14160, "brand_invoice_state": "pending",
             "created_at": _now()}
        )

    brand_user = await db.users.find_one({"_id": brand_oid})
    creator_user = await db.users.find_one({"_id": creator_oid})
    return {
        "brand": {**brand_user, "_id": str(brand_oid)},
        "creator": {**creator_user, "_id": str(creator_oid)},
        "collab_id": str(collab_oid), "collab_oid": collab_oid,
        "campaign_oid": campaign_oid,
        "brand_oid": brand_oid, "creator_oid": creator_oid,
        "payment_id": str(payment_oid) if payment_oid else None,
        "payment_oid": payment_oid,
    }


def _paid(reference="NEFT-11821", tds_applicable=None, tds_amount=None):
    return server.MarkPaidPayload(
        payment_reference=reference,
        tds_applicable=tds_applicable,
        tds_amount=tds_amount,
    )


# ---------------------------------------------------------------------------
# 1. Payouts, and every state a payment can be in
# ---------------------------------------------------------------------------


class TestMarkingAPayoutPaid:
    def test_it_records_the_reference_and_closes_the_collaboration(self):
        """The happy path, asserted on the stored row rather than the return
        value — the response is built by hand and could agree with itself while
        disagreeing with the database."""

        async def body(db):
            s = await _scene(db)
            await server.mark_payment_paid(s["payment_id"], _paid(), ADMIN)
            return (
                await db.payments.find_one({"_id": s["payment_oid"]}),
                await db.collaborations.find_one({"_id": s["collab_oid"]}),
            )

        payment, collab = run(body)
        assert payment["state"] == "paid"
        assert payment["payment_reference"] == "NEFT-11821"
        assert payment["paid_at"] is not None
        assert collab["state"] == "closed"

    def test_paying_twice_is_refused_and_does_not_restate_the_reference(self):
        """A double-click on a payout screen. The precondition on the update is
        what makes the second call a no-op, and the assertion that matters is
        that the *first* reference survives — a second write would relabel a
        payout somebody has already reconciled."""

        async def body(db):
            s = await _scene(db)
            await server.mark_payment_paid(s["payment_id"], _paid("NEFT-11821"), ADMIN)
            with pytest.raises(HTTPException) as err:
                await server.mark_payment_paid(
                    s["payment_id"], _paid("NEFT-99999"), ADMIN
                )
            return err.value, await db.payments.find_one({"_id": s["payment_oid"]})

        exc, payment = run(body)
        assert exc.status_code == 409
        assert payment["payment_reference"] == "NEFT-11821"

    def test_a_stale_read_is_stopped_by_the_precondition_and_not_by_the_check(self):
        """**Two guards, and only one of them is tested by calling twice.**

        `mark_payment_paid` reads the row, refuses if it says `paid`, and only
        then updates under `{"_id": pid, "state": "pending"}`. In the
        sequential test above the early read does all the work — delete the
        precondition and that test stays green. The precondition exists for the
        case the read cannot see: two requests in flight, the second one's read
        landing before the first one's write.

        `asyncio.gather` will not produce that here (mongomock resolves without
        yielding), so the race is staged directly: the handler is handed a
        stale `pending` document while the stored row has already been paid.
        That is exactly what the losing request sees, and the update filter is
        the only thing left between it and paying somebody twice.
        """

        async def body(db):
            s = await _scene(db)
            await server.mark_payment_paid(s["payment_id"], _paid("NEFT-A"), ADMIN)
            stale = {"_id": s["payment_oid"], "collaboration_id": s["collab_oid"],
                     "state": "pending", "creator_payout": 12000}

            real_guard = server._console_payment_or_404

            async def hands_back_a_stale_row(payment_id, user):
                return stale

            server._console_payment_or_404 = hands_back_a_stale_row
            try:
                with pytest.raises(HTTPException) as err:
                    await server.mark_payment_paid(
                        s["payment_id"], _paid("NEFT-B"), ADMIN
                    )
            finally:
                server._console_payment_or_404 = real_guard
            return err.value, await db.payments.find_one({"_id": s["payment_oid"]})

        exc, payment = run(body)
        assert exc.status_code == 409
        # The first reference stands; the loser did not overwrite it.
        assert payment["payment_reference"] == "NEFT-A"

    def test_net_paid_is_the_payout_less_the_withholding(self):
        async def body(db):
            s = await _scene(db)
            await server.mark_payment_paid(
                s["payment_id"], _paid(tds_applicable=True, tds_amount=1200), ADMIN
            )
            return await db.payments.find_one({"_id": s["payment_oid"]})

        payment = run(body)
        assert payment["tds_applicable"] is True
        assert payment["tds_amount"] == 1200
        assert payment["net_paid"] == 10800

    def test_nobody_having_said_is_stored_as_nobody_having_said(self):
        """**Three states, not two.** `None` is "nobody has said", which the
        export prints as blank; `False` is a claim that no withholding applied.
        Defaulting one to the other invents a statement we never made."""

        async def body(db):
            s = await _scene(db)
            await server.mark_payment_paid(s["payment_id"], _paid(), ADMIN)
            return await db.payments.find_one({"_id": s["payment_oid"]})

        payment = run(body)
        assert payment["tds_applicable"] is None
        assert payment["tds_amount"] is None
        assert payment["net_paid"] == 12000

    def test_the_incoherent_withholding_pairs_are_refused_by_the_model(self):
        """Caught before a handler sees it, because a payment record that says
        "no withholding, ₹1,200 withheld" is the shape an accountant finds a
        year later."""
        with pytest.raises(Exception):
            server.MarkPaidPayload(
                payment_reference="X", tds_applicable=False, tds_amount=900
            )
        with pytest.raises(Exception):
            server.MarkPaidPayload(
                payment_reference="X", tds_applicable=True, tds_amount=None
            )

    def test_a_cancelled_payment_cannot_be_paid(self):
        async def body(db):
            s = await _scene(db, payment_state="cancelled")
            with pytest.raises(HTTPException) as err:
                await server.mark_payment_paid(s["payment_id"], _paid(), ADMIN)
            return err.value, await db.payments.find_one({"_id": s["payment_oid"]})

        exc, payment = run(body)
        assert exc.status_code == 409
        assert payment["state"] == "cancelled"
        assert payment.get("paid_at") is None


class TestRefunding:
    def test_a_paid_payout_refunds_and_the_collaboration_unwinds(self):
        async def body(db):
            s = await _scene(db, payment_state="paid")
            await server.refund_payment(
                s["payment_id"],
                server.RefundPayload(reason="Post came down the same night.",
                                     refund_reference="RV-3311"),
                ADMIN,
            )
            return await db.payments.find_one({"_id": s["payment_oid"]})

        payment = run(body)
        assert payment["state"] == "refunded"
        assert payment["refund_reference"] == "RV-3311"
        assert payment["refunded_at"] is not None

    def test_refunding_twice_is_refused(self):
        async def body(db):
            s = await _scene(db, payment_state="paid")
            p = server.RefundPayload(reason="Wrong account.", refund_reference="RV-1")
            await server.refund_payment(s["payment_id"], p, ADMIN)
            with pytest.raises(HTTPException) as err:
                await server.refund_payment(
                    s["payment_id"],
                    server.RefundPayload(reason="Again.", refund_reference="RV-2"),
                    ADMIN,
                )
            return err.value, await db.payments.find_one({"_id": s["payment_oid"]})

        exc, payment = run(body)
        assert exc.status_code == 409
        assert payment["refund_reference"] == "RV-1"

    def test_a_pending_payout_cannot_be_refunded(self):
        """Nothing left the bank, so there is nothing to bring back — and the
        refusal points at cancellation, which is the move that actually
        applies."""

        async def body(db):
            s = await _scene(db, payment_state="pending")
            with pytest.raises(HTTPException) as err:
                await server.refund_payment(
                    s["payment_id"],
                    server.RefundPayload(reason="Changed our minds.",
                                         refund_reference="RV-9"),
                    ADMIN,
                )
            return err.value, await db.payments.find_one({"_id": s["payment_oid"]})

        exc, payment = run(body)
        assert exc.status_code == 409
        assert "cancel" in str(exc.detail).lower()
        assert payment["state"] == "pending"

    def test_a_settled_invoice_is_flagged_rather_than_quietly_voided(self):
        """We already took the brand's money, so a refund leaves us holding it.
        That is a decision with an invoice attached, not something to resolve by
        setting a field to `void`."""

        async def body(db):
            s = await _scene(db, payment_state="paid")
            await db.payments.update_one(
                {"_id": s["payment_oid"]}, {"$set": {"brand_invoice_state": "settled"}}
            )
            await server.refund_payment(
                s["payment_id"],
                server.RefundPayload(reason="Content removed.", refund_reference="RV-7"),
                ADMIN,
            )
            return await db.payments.find_one({"_id": s["payment_oid"]})

        payment = run(body)
        assert payment["brand_refund_due"] is True
        assert payment["brand_invoice_state"] == "settled"

    def test_an_unsettled_invoice_is_voided_and_nothing_is_owed_back(self):
        async def body(db):
            s = await _scene(db, payment_state="paid")
            await db.payments.update_one(
                {"_id": s["payment_oid"]}, {"$set": {"brand_invoice_state": "sent"}}
            )
            await server.refund_payment(
                s["payment_id"],
                server.RefundPayload(reason="Cancelled.", refund_reference="RV-8"),
                ADMIN,
            )
            return await db.payments.find_one({"_id": s["payment_oid"]})

        payment = run(body)
        assert payment["brand_invoice_state"] == "void"
        assert payment["brand_refund_due"] is False


class TestTheBrandInvoice:
    def test_issuing_stamps_a_due_date_from_the_terms(self):
        async def body(db):
            s = await _scene(db)
            await server.set_brand_invoice_state(
                s["payment_id"], server.InvoiceStatePayload(state="sent"), ADMIN
            )
            return await db.payments.find_one({"_id": s["payment_oid"]})

        payment = run(body)
        assert payment["brand_invoice_state"] == "sent"
        assert payment.get("invoice_due_at") is not None

    def test_shortening_the_terms_does_not_backdate_an_invoice_already_out(self):
        """The stored date wins. A brand told it had a fortnight must not become
        overdue because somebody edited a setting."""

        async def body(db):
            s = await _scene(db)
            await server.set_brand_invoice_state(
                s["payment_id"], server.InvoiceStatePayload(state="sent"), ADMIN
            )
            issued = await db.payments.find_one({"_id": s["payment_oid"]})
            due_before = issued["invoice_due_at"]
            await db.platform_settings.update_one(
                {"_id": "payment_terms"}, {"$set": {"days": 1}}, upsert=True
            )
            return due_before, server._invoice_due_at(issued)

        due_before, read_back = run(body)
        # `_invoice_due_at` stamps the zone on a value BSON gave back naive, so
        # the two are the same instant described two ways. What matters is that
        # the reader did not recompute it from the new one-day terms.
        if due_before.tzinfo is None:
            due_before = due_before.replace(tzinfo=timezone.utc)
        assert read_back == due_before
        assert (read_back - _now()).days >= 7

    def test_void_cannot_be_set_by_hand(self):
        """Typing `void` on a live invoice is how a debt disappears with no
        record of who decided that. Only the refund path writes it."""

        async def body(db):
            s = await _scene(db)
            with pytest.raises(Exception):
                await server.set_brand_invoice_state(
                    s["payment_id"], server.InvoiceStatePayload(state="void"), ADMIN
                )
            return await db.payments.find_one({"_id": s["payment_oid"]})

        payment = run(body)
        assert payment["brand_invoice_state"] == "pending"


# ---------------------------------------------------------------------------
# 2. Disputes — and that the freeze actually holds the money
# ---------------------------------------------------------------------------


class TestTheFreezeStopsTheMoney:
    """The existing test asserts `_refuse_if_disputed` *appears in the source*
    of each handler that moves a collaboration. That is a real check and it
    misses a real failure: a guard called on a stale document, or after the
    write, or whose return value is discarded, all keep the string and lose the
    protection. These call the handler on a genuinely disputed row and then
    read the database back."""

    def test_a_frozen_payment_cannot_be_marked_paid(self):
        async def body(db):
            s = await _scene(db)
            await server.raise_dispute(
                s["collab_id"],
                server.DisputePayload(reason="They approved it and won't pay."),
                s["creator"],
            )
            with pytest.raises(HTTPException) as err:
                await server.mark_payment_paid(s["payment_id"], _paid(), ADMIN)
            return err.value, await db.payments.find_one({"_id": s["payment_oid"]})

        exc, payment = run(body)
        assert exc.status_code == 409
        # The refusal is worth nothing if the row moved anyway.
        assert payment["state"] == "pending"
        assert payment.get("paid_at") is None
        assert payment["frozen"] is True

    def test_a_frozen_collaboration_cannot_be_cancelled(self):
        """**The move the freeze exists to stop.** Cancelling ends the argument
        by ending the arrangement, before anybody neutral has decided anything.
        `cancelled` is one of the four outcomes a mediator can pick, and going
        through them is the only route to it."""

        async def body(db):
            s = await _scene(db, state="content_submitted")
            await server.raise_dispute(
                s["collab_id"],
                server.DisputePayload(reason="The reel was never posted."),
                s["brand"],
            )
            with pytest.raises(HTTPException) as err:
                await server.cancel_collaboration(
                    s["collab_id"],
                    server.CancelCollabPayload(reason="Calling it off."),
                    ADMIN,
                )
            return err.value, await db.collaborations.find_one({"_id": s["collab_oid"]})

        exc, collab = run(body)
        assert exc.status_code == 409
        assert collab["state"] == "content_submitted"
        assert collab.get("cancelled_at") is None

    def test_a_frozen_collaboration_cannot_be_advanced(self):
        async def body(db):
            s = await _scene(db, state="content_submitted")
            await server.raise_dispute(
                s["collab_id"],
                server.DisputePayload(reason="Not what we briefed."),
                s["brand"],
            )
            with pytest.raises(HTTPException) as err:
                await server.advance_collaboration(
                    s["collab_id"],
                    server.AdvanceCollabPayload(to_state="content_approved"),
                    ADMIN,
                )
            return err.value, await db.collaborations.find_one({"_id": s["collab_oid"]})

        exc, collab = run(body)
        assert exc.status_code == 409
        assert collab["state"] == "content_submitted"

    def test_the_freeze_lifts_when_the_dispute_is_resolved(self):
        """A freeze that outlived its dispute would be a second way to strand a
        payout, which is the thing being protected against."""

        async def body(db):
            s = await _scene(db)
            await server.raise_dispute(
                s["collab_id"],
                server.DisputePayload(reason="Short by one story."),
                s["creator"],
            )
            await server.resolve_dispute(
                s["collab_id"],
                server.DisputeResolutionPayload(
                    resolution="release", note="Checked the posts; all three are up."
                ),
                ADMIN,
            )
            await server.mark_payment_paid(s["payment_id"], _paid(), ADMIN)
            return await db.payments.find_one({"_id": s["payment_oid"]})

        payment = run(body)
        assert payment["frozen"] is False
        assert payment["state"] == "paid"


class TestWhoMayRaiseAndWhoMayDecide:
    def test_an_admin_cannot_raise_one(self):
        """A mediator who opened the case is not a mediator.

        Asserted on the route's own guard rather than by calling the handler:
        the refusal lives in `Depends(require_roles(...))`, which a direct call
        skips entirely — so calling `raise_dispute` with an admin would succeed
        here and prove nothing about what happens over HTTP.
        """
        assert not guard_allows(server.raise_dispute, "admin")
        assert guard_allows(server.raise_dispute, "creator")
        assert guard_allows(server.raise_dispute, "brand_manager")

    def test_and_only_an_admin_may_resolve_one(self):
        assert guard_allows(server.resolve_dispute, "admin")
        for role in ("creator", "brand_manager", "campaign_manager", "weare_team"):
            assert not guard_allows(server.resolve_dispute, role), role

    def test_a_brand_on_a_weare_run_brief_gets_a_404_not_a_403(self):
        """They are not the runner. A 403 would confirm the collaboration
        exists, which is what every other refusal here is careful not to do."""

        async def body(db):
            s = await _scene(db, execution_owner="weare")
            with pytest.raises(HTTPException) as err:
                await server.raise_dispute(
                    s["collab_id"],
                    server.DisputePayload(reason="Unhappy with the reel."),
                    s["brand"],
                )
            return err.value

        assert run(body).status_code == 404

    def test_the_side_that_raised_it_may_withdraw_it_and_the_money_unfreezes(self):
        """**Both halves.** A withdrawal that lifted the case and left the
        payment frozen would strand a payout with no dispute to point at and
        nothing left to resolve — found by deleting the unfreeze and watching
        this file stay green, which it did until this test existed."""

        async def body(db):
            s = await _scene(db)
            await server.raise_dispute(
                s["collab_id"],
                server.DisputePayload(reason="Thought they hadn't paid."),
                s["creator"],
            )
            frozen_while_open = (
                await db.payments.find_one({"_id": s["payment_oid"]})
            )["frozen"]
            await server.withdraw_dispute(s["collab_id"], s["creator"])
            return (
                frozen_while_open,
                await db.collaborations.find_one({"_id": s["collab_oid"]}),
                await db.payments.find_one({"_id": s["payment_oid"]}),
            )

        frozen_while_open, collab, payment = run(body)
        assert frozen_while_open is True
        assert collab["dispute"]["state"] == "withdrawn"
        assert payment["frozen"] is False

    def test_and_the_payout_can_then_be_made(self):
        """The end-to-end version of the same rule: unfrozen has to mean the
        money can actually move, not just that a flag flipped."""

        async def body(db):
            s = await _scene(db)
            await server.raise_dispute(
                s["collab_id"],
                server.DisputePayload(reason="Raised this by mistake."),
                s["creator"],
            )
            await server.withdraw_dispute(s["collab_id"], s["creator"])
            await server.mark_payment_paid(s["payment_id"], _paid(), ADMIN)
            return await db.payments.find_one({"_id": s["payment_oid"]})

        assert run(body)["state"] == "paid"

    def test_only_the_side_that_raised_it_may_withdraw_it(self):
        """The other side making a dispute vanish would mean the freeze
        protected nobody."""

        async def body(db):
            s = await _scene(db)
            await server.raise_dispute(
                s["collab_id"],
                server.DisputePayload(reason="They have not paid."),
                s["creator"],
            )
            with pytest.raises(HTTPException) as err:
                await server.withdraw_dispute(s["collab_id"], s["brand"])
            collab = await db.collaborations.find_one({"_id": s["collab_oid"]})
            payment = await db.payments.find_one({"_id": s["payment_oid"]})
            return err.value, collab, payment

        exc, collab, payment = run(body)
        assert exc.status_code in (403, 404, 409)
        assert collab["dispute"]["state"] == "open"
        assert payment["frozen"] is True


class TestMediationOutcomes:
    @pytest.mark.parametrize("resolution", sorted(server.DISPUTE_RESOLUTIONS))
    def test_every_outcome_records_a_note_and_lifts_the_freeze(self, resolution):
        """All four, including `cancelled` — sometimes the honest answer is
        that the arrangement should not have happened, and forcing a mediator
        to pick "release" or "refund" records the decision as something it was
        not."""

        async def body(db):
            s = await _scene(db)
            await server.raise_dispute(
                s["collab_id"],
                server.DisputePayload(reason="Disagreement about the delivery."),
                s["creator"],
            )
            await server.resolve_dispute(
                s["collab_id"],
                server.DisputeResolutionPayload(
                    resolution=resolution,
                    note="Read the thread and the posts; decided on that.",
                    amount=6000 if resolution == "partial_release" else None,
                ),
                ADMIN,
            )
            return (
                await db.collaborations.find_one({"_id": s["collab_oid"]}),
                await db.payments.find_one({"_id": s["payment_oid"]}),
            )

        collab, payment = run(body)
        assert collab["dispute"]["state"] == "resolved"
        assert collab["dispute"]["resolution"] == resolution
        assert collab["dispute"]["resolution_note"]
        assert payment["frozen"] is False

    def test_a_partial_release_without_an_amount_is_refused(self):
        """"Pay them part of it" with no number is not a decision anybody can
        act on."""

        async def body(db):
            s = await _scene(db)
            await server.raise_dispute(
                s["collab_id"],
                server.DisputePayload(reason="Two of three."),
                s["creator"],
            )
            with pytest.raises(Exception):
                await server.resolve_dispute(
                    s["collab_id"],
                    server.DisputeResolutionPayload(
                        resolution="partial_release",
                        note="Splitting it.",
                        amount=None,
                    ),
                    ADMIN,
                )
            return await db.collaborations.find_one({"_id": s["collab_oid"]})

        collab = run(body)
        assert collab["dispute"]["state"] == "open"

    def test_cancelling_through_mediation_does_reach_cancelled(self):
        """The freeze blocks the cancel *route*; it must not block the outcome,
        or a mediator would have one of the four decisions they cannot carry
        out."""

        async def body(db):
            s = await _scene(db, state="content_submitted")
            await server.raise_dispute(
                s["collab_id"],
                server.DisputePayload(reason="Never happened."),
                s["creator"],
            )
            await server.resolve_dispute(
                s["collab_id"],
                server.DisputeResolutionPayload(
                    resolution="cancelled",
                    note="Venue closed that week; nobody is at fault.",
                ),
                ADMIN,
            )
            return await db.collaborations.find_one({"_id": s["collab_oid"]})

        collab = run(body)
        assert collab["state"] == "cancelled"


# ---------------------------------------------------------------------------
# 3. Cancellation, kill fees, and withdrawal
# ---------------------------------------------------------------------------


class TestCancellingWithAKillFee:
    def test_a_kill_fee_keeps_the_payment_row_payable(self):
        """Money is owed. A cancelled payment is a row no payout run looks at
        again, so a kill fee recorded that way is money nobody chases."""

        async def body(db):
            s = await _scene(db)
            await server.cancel_collaboration(
                s["collab_id"],
                server.CancelCollabPayload(
                    reason="Venue pulled out two days before.",
                    cancellation_type="brand_cancelled",
                    kill_fee=4000,
                ),
                ADMIN,
            )
            return await db.payments.find_one({"_id": s["payment_oid"]})

        payment = run(body)
        assert payment["state"] == "pending"
        assert payment["kill_fee"] == 4000
        # The payout shrinks to what is now owed; the original stays beside it.
        assert payment["creator_payout"] == 4000
        assert payment["agreed_amount"] == 12000

    def test_no_kill_fee_cancels_the_payment_outright(self):
        async def body(db):
            s = await _scene(db)
            await server.cancel_collaboration(
                s["collab_id"],
                server.CancelCollabPayload(reason="Creator went quiet."),
                ADMIN,
            )
            return await db.payments.find_one({"_id": s["payment_oid"]})

        payment = run(body)
        assert payment["state"] == "cancelled"
        assert payment.get("kill_fee") is None

    def test_a_kill_fee_with_no_payment_row_gets_one_of_its_own(self):
        """A payment row is only raised at `in_payment`, so cancelling earlier
        leaves the fee with nowhere to live — and money owed that exists only in
        a cancellation reason is money nobody reconciles against."""

        async def body(db):
            s = await _scene(db, state="slot_booked", with_payment=False)
            await server.cancel_collaboration(
                s["collab_id"],
                server.CancelCollabPayload(
                    reason="Cancelled the morning of the shoot.", kill_fee=2500
                ),
                ADMIN,
            )
            return await db.payments.find_one({"collaboration_id": s["collab_oid"]})

        payment = run(body)
        assert payment is not None
        assert payment["is_kill_fee"] is True
        assert payment["state"] == "pending"
        assert payment["creator_payout"] == 2500
        # Who bears a kill fee is a conversation, not a formula.
        assert payment["brand_invoice_amount"] is None

    def test_the_notice_is_recorded_and_can_be_negative(self):
        """A shoot cancelled after the fact is a real thing that happens, and
        rounding it to zero would hide it. The record carries the number; the
        judgement about whether it was enough is left to whoever reads it."""

        async def body(db):
            s = await _scene(db, scheduled_at=_now() - timedelta(days=2))
            await server.cancel_collaboration(
                s["collab_id"],
                server.CancelCollabPayload(reason="Nobody turned up; sorting it after."),
                ADMIN,
            )
            return await db.collaborations.find_one({"_id": s["collab_oid"]})

        collab = run(body)
        assert collab["cancellation_notice_days"] == -2

    def test_who_cancelled_is_on_the_record_not_only_in_the_audit_log(self):
        """"The brand cancelled" and "we cancelled" are different facts about
        the same row, and an audit line does not travel with the
        collaboration."""

        async def body(db):
            s = await _scene(db)
            await server.cancel_collaboration(
                s["collab_id"],
                server.CancelCollabPayload(
                    reason="Client changed the campaign.",
                    cancellation_type="brand_cancelled",
                ),
                ADMIN,
            )
            return await db.collaborations.find_one({"_id": s["collab_oid"]})

        collab = run(body)
        assert collab["state"] == "cancelled"
        assert collab["cancelled_by_role"] == "admin"
        assert collab["cancellation_type"] == "brand_cancelled"
        assert collab["exit_reason"]

    def test_a_paid_out_collaboration_cannot_be_cancelled(self):
        """The money left the bank. Refund is the route, and the refusal says
        so rather than leaving somebody to guess."""

        async def body(db):
            s = await _scene(db, payment_state="paid")
            with pytest.raises(HTTPException) as err:
                await server.cancel_collaboration(
                    s["collab_id"],
                    server.CancelCollabPayload(reason="Undo it."),
                    ADMIN,
                )
            return err.value, await db.collaborations.find_one({"_id": s["collab_oid"]})

        exc, collab = run(body)
        assert exc.status_code == 409
        assert collab["state"] == "in_payment"

    def test_cancelling_twice_is_refused(self):
        async def body(db):
            s = await _scene(db)
            p = server.CancelCollabPayload(reason="Off.")
            await server.cancel_collaboration(s["collab_id"], p, ADMIN)
            with pytest.raises(HTTPException) as err:
                await server.cancel_collaboration(s["collab_id"], p, ADMIN)
            return err.value

        assert run(body).status_code == 409


class TestWithdrawing:
    @pytest.mark.parametrize("state", server.WITHDRAWABLE_COLLAB_STATES)
    def test_a_creator_may_take_a_pitch_back_before_acceptance(self, state):
        async def body(db):
            s = await _scene(db, state=state, with_payment=False)
            await server.withdraw_application(
                s["collab_id"],
                server.ReasonPayload(reason="Double-booked that weekend."),
                s["creator"],
            )
            return await db.collaborations.find_one({"_id": s["collab_oid"]})

        collab = run(body)
        assert collab["state"] == "withdrawn"
        assert collab["exit_reason"]

    def test_after_acceptance_it_is_a_cancellation_and_the_refusal_says_so(self):
        """Somebody has committed to them by then. Taking it back unilaterally
        is a different event with a notice period attached."""

        async def body(db):
            s = await _scene(db, state="accepted", with_payment=False)
            with pytest.raises(HTTPException) as err:
                await server.withdraw_application(
                    s["collab_id"],
                    server.ReasonPayload(reason="Changed my mind."),
                    s["creator"],
                )
            return err.value, await db.collaborations.find_one({"_id": s["collab_oid"]})

        exc, collab = run(body)
        assert exc.status_code == 409
        assert collab["state"] == "accepted"

    def test_somebody_elses_application_is_a_404(self):
        async def body(db):
            s = await _scene(db, state="applied", with_payment=False)
            stranger = {"_id": str(ObjectId()), "role": "creator", "name": "Nobody"}
            with pytest.raises(HTTPException) as err:
                await server.withdraw_application(
                    s["collab_id"],
                    server.ReasonPayload(reason="Not mine."),
                    stranger,
                )
            return err.value, await db.collaborations.find_one({"_id": s["collab_oid"]})

        exc, collab = run(body)
        assert exc.status_code == 404
        assert collab["state"] == "applied"

    def test_withdrawn_is_its_own_terminal_state_and_not_a_cancellation(self):
        """A withdrawal happens before anybody is committed and is the
        creator's to make. Drawing it as a cancellation puts a black mark where
        there is none."""
        assert "withdrawn" in server.TERMINAL_COLLAB_STATES
        assert "withdrawn" in server.COLLAB_GROUP_ENDED
        assert server._NEXT_ACTION.get("withdrawn") != server._NEXT_ACTION.get(
            "cancelled"
        )
