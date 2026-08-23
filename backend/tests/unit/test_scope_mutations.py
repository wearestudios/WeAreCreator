"""Four roles, and what each of them cannot *change* outside its scope.

`test_access_matrix.py` holds the reads: filtered lists, 404s on detail pages,
and a structural sweep asserting that every console handler taking an id calls
one of the four scoped guards. That sweep is the right shape for catching a new
route written the old way, and it is a substring check — a handler that calls
`_collab_or_404` and then writes to a differently-resolved id still contains
the string.

So this file is the behavioural complement, and it asserts **two** things per
case, because only the second one is about damage:

1. the call is refused, with a 404 rather than a 403 — whether a record we do
   not work with exists is itself what the scope protects; and
2. **the target row is unchanged afterwards.** A refusal raised after the write
   is not a refusal.

Role bars are checked by running the route's real `require_roles` dependency
rather than reading its source for a string. Calling a route function directly
skips `Depends` entirely, so a test that calls the handler with the wrong role
and sees it succeed has proved nothing — that is the trap `bulk_review` has to
re-check by hand, and it is worth a harness that cannot fall into it.
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


def _loop():
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()
    return LOOP


def _now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Running the guard FastAPI would have run
# ---------------------------------------------------------------------------


def role_guard(fn):
    """The `require_roles` dependency the route actually carries."""
    for p in inspect.signature(fn).parameters.values():
        dep = p.default
        if isinstance(dep, params.Depends) and dep.dependency is not None:
            if getattr(dep.dependency, "__name__", "") == "_guard":
                return dep.dependency
    raise AssertionError(f"{fn.__name__} declares no require_roles guard")


def guard_allows(fn, role):
    """Would FastAPI let this role reach the handler at all?"""
    guard = role_guard(fn)

    async def go():
        try:
            await guard({"_id": str(ObjectId()), "role": role})
            return True
        except HTTPException as err:
            assert err.status_code == 403
            return False

    return _loop().run_until_complete(go())


# ---------------------------------------------------------------------------
# Two brands, and the people around them
# ---------------------------------------------------------------------------


class World:
    """Mine and theirs, symmetrically — so "the scope works" and "there was
    nothing there anyway" can never be confused. Every assertion about a
    refusal has a mirror showing the same call succeeds inside the scope."""

    async def build(self, db):
        self.db = db
        server.db = db

        self.mine, self.theirs = ObjectId(), ObjectId()
        self.creator = ObjectId()
        self.team_id, self.manager_id = ObjectId(), ObjectId()

        await db.users.insert_many(
            [
                {"_id": self.mine, "role": "brand_manager", "name": "Toit",
                 "brand_id": self.mine, "phone": "+919900000001"},
                {"_id": self.theirs, "role": "brand_manager", "name": "Blue Tokai",
                 "brand_id": self.theirs, "phone": "+919900000002"},
                {"_id": self.creator, "role": "creator", "name": "Asha",
                 "phone": "+919900000003"},
                {"_id": self.team_id, "role": "weare_team", "name": "Dev",
                 "assigned_brand_ids": [self.mine]},
                {"_id": self.manager_id, "role": "campaign_manager", "name": "Ravi"},
            ]
        )
        for brand in (self.mine, self.theirs):
            await db.brand_profiles.insert_one(
                {"user_id": brand, "business_name": str(brand), "verified": True,
                 "verified_at": _now()}
            )
        await db.creator_profiles.insert_one(
            {"user_id": self.creator, "name": "Asha",
             "verification_status": "verified", "verified_at": _now(),
             "payout_method": "upi", "payout_upi": "asha@okhdfc"}
        )

        self.camp = {}
        self.collab = {}
        self.pay = {}
        for key, brand in (("mine", self.mine), ("theirs", self.theirs)):
            camp_oid, collab_oid, pay_oid = ObjectId(), ObjectId(), ObjectId()
            await db.campaigns.insert_one(
                {"_id": camp_oid, "brand_id": brand, "title": f"{key} brief",
                 "status": "in_progress", "execution_owner": "brand",
                 "compensation_type": "fixed", "budget_per_creator": 12000,
                 # Only the manager's own campaign is assigned to them.
                 **({"manager_id": self.manager_id} if key == "mine" else {})}
            )
            await db.collaborations.insert_one(
                {"_id": collab_oid, "campaign_id": camp_oid,
                 "creator_id": self.creator, "state": "in_payment",
                 "agreed_amount": 12000, "agreed_at": _now(), "state_since": _now()}
            )
            await db.payments.insert_one(
                {"_id": pay_oid, "collaboration_id": collab_oid, "state": "pending",
                 "agreed_amount": 12000, "creator_payout": 12000,
                 "brand_invoice_state": "pending"}
            )
            self.camp[key], self.collab[key], self.pay[key] = (
                camp_oid, collab_oid, pay_oid,
            )

        self.team = {"_id": str(self.team_id), "role": "weare_team", "name": "Dev",
                     "assigned_brand_ids": [self.mine]}
        self.manager = {"_id": str(self.manager_id), "role": "campaign_manager",
                        "name": "Ravi"}
        self.brand_mine = {"_id": str(self.mine), "role": "brand_manager",
                           "name": "Toit", "brand_id": str(self.mine)}
        self.creator_user = {"_id": str(self.creator), "role": "creator",
                             "name": "Asha"}
        self.admin = {"_id": str(ObjectId()), "role": "admin", "name": "Admin"}
        return self


def in_world(body):
    """Build the two brands, run `body(world)`, restore the real db."""

    async def go():
        db = AsyncMongoMockClient()["scope"]
        original = server.db
        world = await World().build(db)
        try:
            return await body(world)
        finally:
            server.db = original

    return _loop().run_until_complete(go())


async def refuses(coro):
    """The HTTPException a call raises, or an assertion if it did not.

    Async, because every caller is already inside `in_world`'s loop and
    `run_until_complete` cannot re-enter a running one.
    """
    try:
        await coro
    except HTTPException as err:
        return err
    raise AssertionError("this was allowed and should not have been")


# ---------------------------------------------------------------------------
# weare_team — the console, ending at the brands they are on
# ---------------------------------------------------------------------------


class TestWeAreTeamCannotMoveAnotherBrandsMoney:
    def test_marking_another_brands_payout_paid_is_refused_and_changes_nothing(self):
        """The strongest single case in this file. A payment reaches a brand
        two joins away — payment → collaboration → campaign → brand — so the
        scope has to be resolved rather than read off the row, and a filter
        applied only to the list is one somebody reaches around by pasting an
        id."""

        async def body(w):
            err = await refuses(
                server.mark_payment_paid(
                    str(w.pay["theirs"]),
                    server.MarkPaidPayload(payment_reference="NEFT-1"),
                    w.team,
                )
            )
            after = await w.db.payments.find_one({"_id": w.pay["theirs"]})
            return err, after

        err, after = in_world(body)
        assert err.status_code == 404
        assert after["state"] == "pending"
        assert after.get("paid_at") is None

    def test_and_their_own_brands_payout_goes_through(self):
        """The mirror. Without it the test above passes on a scope that
        refuses everybody."""

        async def body(w):
            await server.mark_payment_paid(
                str(w.pay["mine"]),
                server.MarkPaidPayload(payment_reference="NEFT-2"),
                w.team,
            )
            return await w.db.payments.find_one({"_id": w.pay["mine"]})

        assert in_world(body)["state"] == "paid"

    def test_refunding_another_brands_payout_is_refused(self):
        async def body(w):
            await w.db.payments.update_one(
                {"_id": w.pay["theirs"]}, {"$set": {"state": "paid"}}
            )
            err = await refuses(
                server.refund_payment(
                    str(w.pay["theirs"]),
                    server.RefundPayload(reason="Undo it.", refund_reference="RV-1"),
                    w.team,
                )
            )
            after = await w.db.payments.find_one({"_id": w.pay["theirs"]})
            return err, after

        err, after = in_world(body)
        assert err.status_code == 404
        assert after["state"] == "paid"
        assert after.get("refunded_at") is None

    def test_invoicing_against_another_brand_is_refused(self):
        async def body(w):
            err = await refuses(
                server.set_brand_invoice_state(
                    str(w.pay["theirs"]),
                    server.InvoiceStatePayload(state="sent"),
                    w.team,
                )
            )
            after = await w.db.payments.find_one({"_id": w.pay["theirs"]})
            return err, after

        err, after = in_world(body)
        assert err.status_code == 404
        assert after["brand_invoice_state"] == "pending"

    def test_cancelling_another_brands_collaboration_is_refused(self):
        async def body(w):
            err = await refuses(
                server.cancel_collaboration(
                    str(w.collab["theirs"]),
                    server.CancelCollabPayload(reason="Off.", kill_fee=5000),
                    w.team,
                )
            )
            return err, await w.db.collaborations.find_one({"_id": w.collab["theirs"]})

        err, after = in_world(body)
        assert err.status_code == 404
        assert after["state"] == "in_payment"
        assert after.get("kill_fee") is None

    def test_advancing_another_brands_collaboration_is_refused(self):
        async def body(w):
            err = await refuses(
                server.advance_collaboration(
                    str(w.collab["theirs"]),
                    server.AdvanceCollabPayload(to_state="closed"),
                    w.team,
                )
            )
            return err, await w.db.collaborations.find_one({"_id": w.collab["theirs"]})

        err, after = in_world(body)
        assert err.status_code == 404
        assert after["state"] == "in_payment"

    def test_somebody_assigned_nothing_reaches_nothing_rather_than_everything(self):
        """`None` means no filter and a list means these brands — an empty
        list reading as "no filter" would hand a new starter the whole platform
        on their first morning."""

        async def body(w):
            fresh = {"_id": str(ObjectId()), "role": "weare_team", "name": "New",
                     "assigned_brand_ids": []}
            err = await refuses(
                server.mark_payment_paid(
                    str(w.pay["mine"]),
                    server.MarkPaidPayload(payment_reference="NEFT-3"),
                    fresh,
                )
            )
            return err, await w.db.payments.find_one({"_id": w.pay["mine"]})

        err, after = in_world(body)
        assert err.status_code == 404
        assert after["state"] == "pending"


class TestWeAreTeamCannotReachThePlatformWideDecisions:
    """A creator works across every brand, so deciding about one is not scoped
    work. These are guard-level bars, so they are checked by running the
    guard."""

    @pytest.mark.parametrize(
        "fn",
        ["approve_creator", "reject_creator", "suspend_creator", "list_audit_log",
         "admin_health", "admin_metrics", "assign_brand_to_team_member"],
    )
    def test_admin_only_and_the_guard_says_so(self, fn):
        handler = getattr(server, fn)
        assert guard_allows(handler, "admin")
        assert not guard_allows(handler, "weare_team"), f"{fn} admits weare_team"

    def test_the_bulk_route_re_checks_the_creator_queue_by_hand(self):
        """The route's own guard is `CONSOLE_ROLES`, because two of the three
        queues are scoped work. The creator queue is not, and calling a route
        function directly skips its `Depends` — so the loop re-checks. Driven
        rather than read, because this is the one place in the codebase where
        the guard genuinely is not FastAPI's."""

        async def body(w):
            err = await refuses(
                server.bulk_review(
                    "creators",
                    server.BulkDecisionPayload(
                        ids=[str(ObjectId())], action="approve", reason=None
                    ),
                    w.team,
                )
            )
            return err

        assert in_world(body).status_code == 403

    def test_but_the_campaign_queue_is_theirs(self):
        async def body(w):
            result = await server.bulk_review(
                "campaigns",
                server.BulkDecisionPayload(
                    ids=[str(w.camp["mine"])], action="approve", reason=None
                ),
                w.team,
            )
            return result

        assert in_world(body)["kind"] == "campaigns"


# ---------------------------------------------------------------------------
# brand_manager — its own brand, and nothing about anybody else's
# ---------------------------------------------------------------------------


class TestBrandManagerStopsAtItsOwnBrand:
    def test_it_cannot_record_a_fee_on_another_brands_collaboration(self):
        async def body(w):
            err = await refuses(
                server.brand_record_agreed_amount(
                    str(w.collab["theirs"]),
                    server.AgreedAmountPayload(agreed_amount=999),
                    w.brand_mine,
                )
            )
            return err, await w.db.collaborations.find_one({"_id": w.collab["theirs"]})

        err, after = in_world(body)
        assert err.status_code == 404
        assert after["agreed_amount"] == 12000

    def test_it_cannot_approve_content_on_another_brands_collaboration(self):
        async def body(w):
            await w.db.collaborations.update_one(
                {"_id": w.collab["theirs"]}, {"$set": {"state": "content_submitted"}}
            )
            err = await refuses(
                server.brand_approve_content(str(w.collab["theirs"]), w.brand_mine)
            )
            return err, await w.db.collaborations.find_one({"_id": w.collab["theirs"]})

        err, after = in_world(body)
        assert err.status_code == 404
        assert after["state"] == "content_submitted"

    def test_it_cannot_read_another_brands_work_notes(self):
        """A 404 behind all three doors, so whether a thread exists on somebody
        else's collaboration is itself not answered."""

        async def body(w):
            return await refuses(
                server._note_readable_collab_or_404(str(w.collab["theirs"]),
                                                    w.brand_mine)
            )

        assert in_world(body).status_code == 404

    def test_the_console_is_closed_to_it_entirely(self):
        for fn in ("admin_health", "mark_payment_paid", "bulk_review"):
            handler = getattr(server, fn)
            assert not guard_allows(handler, "brand_manager"), fn
            assert not guard_allows(handler, "brand"), fn

    def test_the_scope_is_the_brand_rather_than_the_login_row(self):
        """Correct only while the login and the brand are the same row. Routing
        it through one function means a second seat is one edit rather than a
        hunt through forty queries."""
        brand = ObjectId()
        login = ObjectId()
        assert server._brand_scope(
            {"_id": str(login), "brand_id": str(brand)}
        ) == brand


# ---------------------------------------------------------------------------
# campaign_manager — the campaigns they are actually on
# ---------------------------------------------------------------------------


class TestCampaignManagerStopsAtAssignedCampaigns:
    def test_an_unassigned_campaign_is_a_404(self):
        async def body(w):
            return await refuses(
                server._managed_campaign_or_404(str(w.camp["theirs"]), w.manager)
            )

        assert in_world(body).status_code == 404

    def test_and_the_assigned_one_resolves(self):
        async def body(w):
            return await server._managed_campaign_or_404(str(w.camp["mine"]), w.manager)

        assert in_world(body)["_id"] is not None

    def test_the_daysheet_is_closed_to_the_brands_own_person(self):
        """Campaigns default their manager to the brand's own person, so
        `_managed_campaign_or_404` would pass a brand manager on ownership
        alone. **The role guard is the only thing keeping them out** — and out
        of the CSV, which carries creators' phone numbers by design."""
        for fn_name in ("manager_campaign_roster", "manager_daysheet_csv"):
            fn = getattr(server, fn_name, None)
            if fn is None:
                continue
            assert guard_allows(fn, "campaign_manager"), fn_name
            assert guard_allows(fn, "admin"), fn_name
            for role in ("brand_manager", "brand", "weare_team", "creator"):
                assert not guard_allows(fn, role), f"{fn_name} admits {role}"

    def test_it_cannot_touch_the_console_payment_routes(self):
        for fn in ("mark_payment_paid", "refund_payment", "set_brand_invoice_state"):
            assert not guard_allows(getattr(server, fn), "campaign_manager"), fn


# ---------------------------------------------------------------------------
# creator — their own row and nobody else's
# ---------------------------------------------------------------------------


class TestCreatorStopsAtTheirOwnRow:
    def test_they_cannot_withdraw_somebody_elses_application(self):
        async def body(w):
            await w.db.collaborations.update_one(
                {"_id": w.collab["theirs"]}, {"$set": {"state": "applied"}}
            )
            stranger = {"_id": str(ObjectId()), "role": "creator", "name": "Nobody"}
            err = await refuses(
                server.withdraw_application(
                    str(w.collab["theirs"]),
                    server.ReasonPayload(reason="Not mine."),
                    stranger,
                )
            )
            return err, await w.db.collaborations.find_one({"_id": w.collab["theirs"]})

        err, after = in_world(body)
        assert err.status_code == 404
        assert after["state"] == "applied"

    def test_they_cannot_reach_the_money_routes_at_all(self):
        for fn in ("mark_payment_paid", "refund_payment", "cancel_collaboration",
                   "resolve_dispute", "bulk_review"):
            assert not guard_allows(getattr(server, fn), "creator"), fn

    def test_work_notes_do_not_accept_the_role_at_all(self):
        """Not "a creator gets an empty list" — the route does not admit them.
        Offline negotiation is the model and this is the internal paper trail."""
        for fn in ("add_collab_note", "list_collab_notes"):
            handler = getattr(server, fn, None)
            if handler is None:
                continue
            assert not guard_allows(handler, "creator"), fn

    def test_a_creator_cannot_raise_a_dispute_on_a_stranger_s_collaboration(self):
        async def body(w):
            stranger = {"_id": str(ObjectId()), "role": "creator", "name": "Nobody"}
            err = await refuses(
                server.raise_dispute(
                    str(w.collab["theirs"]),
                    server.DisputePayload(reason="I want in on this."),
                    stranger,
                )
            )
            return err, await w.db.collaborations.find_one({"_id": w.collab["theirs"]})

        err, after = in_world(body)
        assert err.status_code == 404
        assert after.get("dispute") is None


# ---------------------------------------------------------------------------
# The shape of a refusal, across every role
# ---------------------------------------------------------------------------


class TestARefusalNeverLeaksWhetherTheRecordExists:
    def test_every_cross_scope_refusal_is_a_404_and_never_a_403(self):
        """A 403 says "this exists and you may not have it", which is the half
        the scope is protecting. Gathered in one place so a new guard returning
        the wrong code is visible as a pattern break rather than as one odd
        test."""

        async def body(w):
            calls = [
                server.mark_payment_paid(
                    str(w.pay["theirs"]),
                    server.MarkPaidPayload(payment_reference="X"),
                    w.team,
                ),
                server._collab_or_404(str(w.collab["theirs"]), w.team),
                server._admin_campaign_or_404(str(w.camp["theirs"]), w.team),
                server._console_brand_or_404(str(w.theirs), w.team),
                server._managed_campaign_or_404(str(w.camp["theirs"]), w.manager),
            ]
            return [(await refuses(call)).status_code for call in calls]

        assert in_world(body) == [404, 404, 404, 404, 404]

    def test_an_id_that_is_not_an_id_is_also_a_404_and_not_a_500(self):
        """A pasted fragment is the ordinary way these ids arrive."""

        async def body(w):
            calls = [
                server._collab_or_404("not-an-objectid", w.team),
                server._console_payment_or_404("../../etc/passwd", w.team),
            ]
            return [(await refuses(call)).status_code for call in calls]

        assert in_world(body) == [404, 404]
