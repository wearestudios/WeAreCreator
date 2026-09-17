"""Campaigns where something is sent rather than somewhere gone.

All three existing campaign types are a place a creator turns up to, which
meant a product-seeding or shipped-sample brief could not be posted at all —
on a platform whose creator taxonomy is fifteen groups precisely because it
takes every category. A skincare brand sending twenty creators a bottle had to
describe it as a personal table at an address nobody was going to visit, and
then every downstream screen asked when the shoot was and which weekdays the
venue was closed.

`delivery` is the fourth type. Booking a slot and being marked present are
replaced by three states: the creator confirms where it goes, the runner sends
it with an optional tracking reference, the creator says it arrived.

The same instrument as `test_money_paths.py`: every case builds the rows,
calls the **real handler** and reads the database back. Two rules it holds
itself to, both learned here rather than inherited —

- **Assert on stored state, not only on the exception.** A 409 raised after
  the write is not a refusal.
- **Run the guard rather than grepping for it.** Calling a route function
  directly skips its `Depends` entirely, so `guard_allows` pulls the real
  `require_roles` dependency off the signature and calls it.
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException, params
from mongomock_motor import AsyncMongoMockClient

import server

LOOP = None
FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"


def _loop():
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()
    return LOOP


def run(body):
    async def go():
        db = AsyncMongoMockClient()["delivery"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return _loop().run_until_complete(go())


def guard_allows(fn, role):
    """Would FastAPI let this role through to the handler?"""
    for p in inspect.signature(fn).parameters.values():
        dep = p.default
        if isinstance(dep, params.Depends) and dep.dependency is not None:
            if getattr(dep.dependency, "__name__", "") == "_guard":
                guard = dep.dependency
                break
    else:
        raise AssertionError(f"{fn.__name__} declares no require_roles guard")

    async def go():
        try:
            await guard({"_id": str(ObjectId()), "role": role})
            return True
        except HTTPException as err:
            assert err.status_code == 403
            return False

    return _loop().run_until_complete(go())


def _now():
    return datetime.now(timezone.utc)


ADMIN = {"_id": str(ObjectId()), "role": "admin", "name": "Admin"}


async def _world(db, *, campaign_type="delivery", state="commercial_agreed", address="12 MG Road"):
    """A brand, a creator with a delivery address, and one collaboration."""
    brand_oid, creator_oid, camp_oid, collab_oid = (
        ObjectId(),
        ObjectId(),
        ObjectId(),
        ObjectId(),
    )
    await db.users.insert_many(
        [
            {"_id": brand_oid, "role": "brand_manager", "name": "Blume",
             "brand_id": brand_oid, "phone": "+919900000001"},
            {"_id": creator_oid, "role": "creator", "name": "Asha",
             "phone": "+919900000002"},
        ]
    )
    await db.brand_profiles.insert_one(
        {"user_id": brand_oid, "business_name": "Blume", "verified": True}
    )
    await db.creator_profiles.insert_one(
        {
            "user_id": creator_oid,
            "name": "Asha",
            "verification_status": "verified",
            **({"full_address": address} if address else {}),
        }
    )
    await db.campaigns.insert_one(
        {
            "_id": camp_oid, "brand_id": brand_oid, "title": "Sample box",
            "status": "in_progress", "campaign_type": campaign_type,
            "compensation_type": "fixed", "budget_per_creator": 18000,
            "creators_needed": 3, "execution_owner": "brand",
            "start_date": _now(), "end_date": _now(),
        }
    )
    await db.collaborations.insert_one(
        {
            "_id": collab_oid, "campaign_id": camp_oid, "creator_id": creator_oid,
            "state": state, "state_since": _now(), "created_at": _now(),
            "agreed_amount": 18000.0, "agreed_at": _now(),
        }
    )
    return {
        "brand": {"_id": str(brand_oid), "role": "brand_manager", "name": "Blume"},
        "creator": {"_id": str(creator_oid), "role": "creator", "name": "Asha"},
        "campaign_id": camp_oid,
        "collab": str(collab_oid),
        "collab_oid": collab_oid,
    }


# ---------------------------------------------------------------------------
# The type, and the scheduling it does not have
# ---------------------------------------------------------------------------


class TestTheTypeItself:
    def test_it_is_a_real_campaign_type(self):
        assert "delivery" in server.CampaignType.__args__
        assert server.DELIVERY_CAMPAIGN_TYPE == "delivery"

    def test_the_reader_never_returns_none(self):
        """Every surface that asks this branches on it and has to get one of
        two answers — the shape `_execution_owner` and `_compensation_type`
        hold."""
        assert server._is_delivery({"campaign_type": "delivery"}) is True
        assert server._is_delivery({"campaign_type": "launch"}) is False
        assert server._is_delivery({}) is False
        assert server._is_delivery(None) is False

    def test_a_campaign_written_before_the_type_is_not_a_delivery(self):
        """Campaigns predate types, and every one of them was a venue brief.
        Reading absent as a delivery would take the slot off a live campaign
        somebody is booked on."""
        assert server._is_delivery({"title": "written before types"}) is False

    @pytest.mark.parametrize("field", ["restricted_days", "shoot_windows", "sittings"])
    def test_the_venue_scheduling_fields_are_refused(self, field):
        """A courier is not a kitchen. "Not during service" and "afternoons
        only" have no answer on a brief with nowhere to go, and a form that
        asks looks like a form that needs an answer."""
        refusal = server._scheduling_refusal("delivery", {"start_date", "end_date", field})
        assert refusal is not None
        # And it names the control on the screen, not the field.
        assert server._SCHEDULING_LABELS[field] in refusal

    def test_a_window_is_required_so_dispatch_has_a_clock(self):
        assert server._scheduling_refusal("delivery", set()) is not None
        assert server._scheduling_refusal("delivery", {"start_date", "end_date"}) is None

    def test_the_frontend_mirrors_the_shape(self):
        """Two copies is how a form asks for a field the server refuses, which
        is a 422 the person filling it in cannot do anything about."""
        src = (FRONTEND / "lib" / "schedulingShape.js").read_text()
        assert "delivery: ['start_date', 'end_date']" in src


# ---------------------------------------------------------------------------
# The ladder
# ---------------------------------------------------------------------------


class TestTheLadder:
    def test_booking_and_attendance_are_replaced_not_added_to(self):
        ladder = server._collab_ladder({"campaign_type": "delivery"})
        assert [s for s in ladder if s in server.DELIVERY_STATES] == list(
            server.DELIVERY_STATES
        )
        assert not [s for s in ladder if s in server.VENUE_ATTENDANCE_STATES]

    def test_the_delivery_states_sit_where_booking_used_to(self):
        """Between the fee and the content, which is the whole point — the
        three steps answer "how does the creator come to have the thing they
        are shooting", exactly as the two they replace did."""
        ladder = server._collab_ladder({"campaign_type": "delivery"})
        assert ladder.index("commercial_agreed") < ladder.index("address_confirmed")
        assert ladder.index("received") < ladder.index("content_submitted")

    def test_every_delivery_state_is_ongoing_rather_than_uncounted(self):
        """Every state belongs to exactly one group, so a collaboration
        waiting on a courier cannot silently vanish from a creator's record —
        or, because `_COMMITTED_COLLAB_STATES` is built from that tuple, from
        the money a brief has spoken for."""
        for state in server.DELIVERY_STATES:
            assert state in server.COLLAB_GROUP_ONGOING
            assert state in server._COMMITTED_COLLAB_STATES

    def test_a_delivery_brief_commits_its_budget_like_any_other(self):
        """The consequence of the above, driven rather than inferred: a brand
        that has sent three boxes has spoken for three fees."""

        async def body(db):
            w = await _world(db, state="dispatched")
            await db.campaigns.update_one(
                {"_id": w["campaign_id"]}, {"$set": {"total_budget": 60000.0}}
            )
            campaign = await db.campaigns.find_one({"_id": w["campaign_id"]})
            return await server._campaign_budget(campaign)

        budget = run(body)
        assert budget["committed"] == 18000.0
        assert budget["remaining"] == 42000.0

    def test_delivered_states_are_unchanged(self):
        """`received` is not a delivery in the content sense — somebody has a
        parcel, and there is no link yet and so nothing to measure. Putting it
        in `DELIVERED_COLLAB_STATES` would have a report describing posts that
        do not exist."""
        assert not set(server.DELIVERY_STATES) & set(server.DELIVERED_COLLAB_STATES)


# ---------------------------------------------------------------------------
# Confirming the address
# ---------------------------------------------------------------------------


class TestConfirmingTheAddress:
    def test_it_moves_the_state_and_stamps_the_clock(self):
        async def body(db):
            w = await _world(db)
            await server.creator_confirm_delivery_address(
                w["collab"], server.ConfirmDeliveryAddressPayload(note="Second floor"),
                w["creator"],
            )
            return await db.collaborations.find_one({"_id": w["collab_oid"]})

        row = run(body)
        assert row["state"] == "address_confirmed"
        assert row["state_since"] is not None
        assert row["delivery"]["address_note"] == "Second floor"
        assert row["delivery"]["address_confirmed_at"] is not None

    def test_the_address_itself_is_never_copied_onto_the_collaboration(self):
        """**The profile is the record.** It is the one the creator maintains,
        the one the map pin belongs to, and the one an erasure removes — a
        copy taken here would outlive all three, in a collaboration row nobody
        would think to erase."""

        async def body(db):
            w = await _world(db, address="12 MG Road, Bengaluru")
            await server.creator_confirm_delivery_address(
                w["collab"], server.ConfirmDeliveryAddressPayload(), w["creator"]
            )
            return await db.collaborations.find_one({"_id": w["collab_oid"]})

        row = run(body)
        assert "12 MG Road" not in str(row)
        # And the payload has no field to put one in.
        assert "address" not in server.ConfirmDeliveryAddressPayload.model_fields

    def test_a_creator_with_no_address_is_told_which_field(self):
        """"Add your delivery address" is something somebody can go and fix.
        A bare 422 is a support ticket."""

        async def body(db):
            w = await _world(db, address=None)
            with pytest.raises(HTTPException) as exc:
                await server.creator_confirm_delivery_address(
                    w["collab"], server.ConfirmDeliveryAddressPayload(), w["creator"]
                )
            row = await db.collaborations.find_one({"_id": w["collab_oid"]})
            return exc.value, row

        err, row = run(body)
        assert err.status_code == 422
        assert err.detail["code"] == "no_delivery_address"
        assert err.detail["missing_fields"] == ["full_address"]
        # The refusal is a refusal: nothing moved.
        assert row["state"] == "commercial_agreed"

    def test_it_is_refused_on_a_campaign_with_a_venue(self):
        async def body(db):
            w = await _world(db, campaign_type="personal_table")
            with pytest.raises(HTTPException) as exc:
                await server.creator_confirm_delivery_address(
                    w["collab"], server.ConfirmDeliveryAddressPayload(), w["creator"]
                )
            row = await db.collaborations.find_one({"_id": w["collab_oid"]})
            return exc.value, row

        err, row = run(body)
        assert err.status_code == 409
        assert "book a slot" in err.detail
        assert row["state"] == "commercial_agreed"

    def test_confirming_twice_says_so_rather_than_refusing_blankly(self):
        """A creator who taps twice on a slow connection should read "you
        already told us" rather than a bare wrong-state error."""

        async def body(db):
            w = await _world(db, state="address_confirmed")
            with pytest.raises(HTTPException) as exc:
                await server.creator_confirm_delivery_address(
                    w["collab"], server.ConfirmDeliveryAddressPayload(), w["creator"]
                )
            return exc.value

        err = run(body)
        assert err.status_code == 409
        assert "already confirmed your address" in err.detail

    def test_somebody_elses_collaboration_is_a_404(self):
        async def body(db):
            w = await _world(db)
            stranger = {"_id": str(ObjectId()), "role": "creator", "name": "Not them"}
            with pytest.raises(HTTPException) as exc:
                await server.creator_confirm_delivery_address(
                    w["collab"], server.ConfirmDeliveryAddressPayload(), stranger
                )
            return exc.value

        assert run(body).status_code == 404

    def test_only_a_creator_reaches_it(self):
        assert guard_allows(server.creator_confirm_delivery_address, "creator") is True
        for role in ("admin", "brand_manager", "weare_team", "campaign_manager"):
            assert guard_allows(server.creator_confirm_delivery_address, role) is False


# ---------------------------------------------------------------------------
# Dispatching
# ---------------------------------------------------------------------------


class TestDispatching:
    def test_it_records_the_tracking_and_tells_the_creator(self):
        async def body(db):
            w = await _world(db, state="address_confirmed")
            await server.dispatch_delivery(
                w["collab"],
                server.DispatchDeliveryPayload(
                    tracking_reference="DL-8841", courier="Delhivery"
                ),
                w["brand"],
            )
            row = await db.collaborations.find_one({"_id": w["collab_oid"]})
            note = await db.notifications.find_one({"event": "delivery_dispatched"})
            return row, note

        row, note = run(body)
        assert row["state"] == "dispatched"
        assert row["delivery"]["tracking_reference"] == "DL-8841"
        assert row["delivery"]["courier"] == "Delhivery"
        assert row["delivery"]["dispatched_by_name"] == "Blume"
        # The message that stops a creator wondering, and the one they check
        # against the parcel when it turns up.
        assert note is not None and "DL-8841" in note["body"]

    def test_the_tracking_reference_is_optional(self):
        """Half of what this operation sends goes by a local courier with a
        WhatsApp photo of a docket rather than a scannable number. A required
        field there is a field filled in with "sent"."""

        async def body(db):
            w = await _world(db, state="address_confirmed")
            await server.dispatch_delivery(
                w["collab"], server.DispatchDeliveryPayload(), w["brand"]
            )
            return await db.collaborations.find_one({"_id": w["collab_oid"]})

        row = run(body)
        assert row["state"] == "dispatched"
        assert row["delivery"]["tracking_reference"] is None

    def test_it_will_not_send_before_an_address_is_confirmed(self):
        async def body(db):
            w = await _world(db)  # still at commercial_agreed
            with pytest.raises(HTTPException) as exc:
                await server.dispatch_delivery(
                    w["collab"], server.DispatchDeliveryPayload(), w["brand"]
                )
            row = await db.collaborations.find_one({"_id": w["collab_oid"]})
            return exc.value, row

        err, row = run(body)
        assert err.status_code == 409
        assert "hasn't confirmed their address" in err.detail
        assert row["state"] == "commercial_agreed"

    def test_a_creator_cannot_dispatch_to_themselves(self):
        assert guard_allows(server.dispatch_delivery, "creator") is False
        for role in ("admin", "weare_team", "brand_manager"):
            assert guard_allows(server.dispatch_delivery, role) is True

    def test_a_frozen_collaboration_cannot_be_dispatched(self):
        """`_refuse_if_disputed` is on every door that moves a collaboration,
        and a new door is not an exception to that."""
        assert "_refuse_if_disputed" in inspect.getsource(server.dispatch_delivery)

        async def body(db):
            w = await _world(db, state="address_confirmed")
            await db.collaborations.update_one(
                {"_id": w["collab_oid"]},
                {"$set": {"dispute": {"state": "open", "reason": "x"}}},
            )
            with pytest.raises(HTTPException) as exc:
                await server.dispatch_delivery(
                    w["collab"], server.DispatchDeliveryPayload(), w["brand"]
                )
            row = await db.collaborations.find_one({"_id": w["collab_oid"]})
            return exc.value, row

        err, row = run(body)
        assert err.status_code == 409
        assert row["state"] == "address_confirmed"


# ---------------------------------------------------------------------------
# Confirming it arrived
# ---------------------------------------------------------------------------


class TestConfirmingArrival:
    def test_it_moves_to_received_and_starts_the_content_clock(self):
        """`received` carries the `content_submission` target the same way
        `attended` does — which is why it is the creator's to write rather
        than something inferred from a courier's API. A parcel marked
        delivered and never actually received would otherwise put somebody
        overdue for work they cannot start."""

        async def body(db):
            w = await _world(db, state="dispatched")
            await server.creator_confirm_delivery_received(
                w["collab"], server.ConfirmDeliveryReceivedPayload(), w["creator"]
            )
            return await db.collaborations.find_one({"_id": w["collab_oid"]})

        row = run(body)
        assert row["state"] == "received"
        assert row["delivery"]["received_at"] is not None
        assert server._SLA_BY_COLLAB_STATE["received"] == "content_submission"

    def test_a_parcel_in_transit_has_no_clock(self):
        """It is waiting on a courier, not on a person here. A target on it
        would go red about somebody who has already done everything asked of
        them — the same reasoning that keeps `slot_booked` off the table."""
        assert "dispatched" not in server._SLA_BY_COLLAB_STATE
        assert "slot_booked" not in server._SLA_BY_COLLAB_STATE

    def test_it_will_not_confirm_before_anything_was_sent(self):
        async def body(db):
            w = await _world(db, state="address_confirmed")
            with pytest.raises(HTTPException) as exc:
                await server.creator_confirm_delivery_received(
                    w["collab"], server.ConfirmDeliveryReceivedPayload(), w["creator"]
                )
            row = await db.collaborations.find_one({"_id": w["collab_oid"]})
            return exc.value, row

        err, row = run(body)
        assert err.status_code == 409
        assert "hasn't been sent yet" in err.detail
        assert row["state"] == "address_confirmed"


# ---------------------------------------------------------------------------
# Who may write what
# ---------------------------------------------------------------------------


class TestNobodyWritesOnSomebodyElsesBehalf:
    @pytest.mark.parametrize("state", ["address_confirmed", "received"])
    def test_an_admin_cannot_advance_into_a_creator_owned_step(self, state):
        """An address is theirs to check and an arrival is theirs to report.
        Writing either from the console records a confirmation nobody gave,
        about a parcel the console cannot see.
        """
        assert state in server._CREATOR_OWNED_TRANSITIONS

        async def body(db):
            before = {"address_confirmed": "commercial_agreed", "received": "dispatched"}[state]
            w = await _world(db, state=before)
            with pytest.raises(HTTPException) as exc:
                await server.advance_collaboration(
                    w["collab"], server.AdvanceCollabPayload(from_state=before), ADMIN
                )
            row = await db.collaborations.find_one({"_id": w["collab_oid"]})
            return exc.value, row

        err, row = run(body)
        assert err.status_code == 409
        assert "Only the creator" in err.detail
        # Assert on stored state: a 409 raised after the write is not a refusal.
        assert row["state"] != state

    def test_dispatch_is_not_an_advance_either(self):
        """It carries a tracking reference and a message to the creator, both
        of which live on its own route. Advancing blind would record a send
        with nothing anybody can follow."""

        async def body(db):
            w = await _world(db, state="address_confirmed")
            with pytest.raises(HTTPException) as exc:
                await server.advance_collaboration(
                    w["collab"],
                    server.AdvanceCollabPayload(from_state="address_confirmed"),
                    ADMIN,
                )
            row = await db.collaborations.find_one({"_id": w["collab_oid"]})
            return exc.value, row

        err, row = run(body)
        assert err.status_code == 409
        assert "tracking reference" in err.detail
        assert row["state"] == "address_confirmed"


# ---------------------------------------------------------------------------
# What every surface reads
# ---------------------------------------------------------------------------


class TestTheDeliveryBlock:
    def test_it_carries_no_address_and_no_map_pin(self):
        """**This block rides on brand-facing payloads.** A coordinate on
        somebody's front door is their home address to five decimal places;
        both it and the address are off `_BRAND_VISIBLE_CREATOR_FIELDS` for
        that reason, and a new block is not a way around it. What a brand
        needs is that the address is confirmed, not what it says."""
        block = server._delivery_block(
            {
                "delivery": {
                    "address_confirmed_at": _now(),
                    "tracking_reference": "DL-1",
                }
            }
        )
        for forbidden in ("full_address", "location_lat", "location_lng", "address"):
            assert forbidden not in block

    def test_it_is_absent_on_a_venue_brief_rather_than_empty(self):
        """A surface reads absent as "draw no tracking row at all". An empty
        one would render a heading about a delivery on a campaign where
        everybody turned up to a bar."""
        assert server._delivery_block({}) is None
        assert server._delivery_block(None) is None

    def test_it_reaches_the_creators_own_row(self):
        """The party it is about. Finding out where your own parcel is from a
        brand's screen and not your own would be the wrong way round."""
        src = inspect.getsource(server._serialize_collab_row)
        assert "_delivery_block(collab)" in src


# ---------------------------------------------------------------------------
# The screens
# ---------------------------------------------------------------------------


class TestItIsActuallyReachable:
    """A route with no caller is unreachable, and a caller with no mount is as
    unreachable as a route with no caller — the rule
    `test_manager_experience.py` already holds the manager's screens to."""

    @pytest.mark.parametrize(
        "path", ["confirm-address", "confirm-received", "/dispatch"]
    )
    def test_every_delivery_route_has_a_caller(self, path):
        hits = [
            f
            for f in FRONTEND.rglob("*.jsx")
            if path in f.read_text()
        ]
        assert hits, f"no frontend caller for {path}"

    def test_the_creator_card_offers_both_of_their_steps(self):
        src = (FRONTEND / "components" / "creator" / "ActiveCampaigns.jsx").read_text()
        assert "confirm_address" in src and "confirm_received" in src

    def test_the_dispatch_panel_is_mounted_on_the_shared_screen(self):
        src = (
            FRONTEND / "components" / "application" / "ApplicationDetail.jsx"
        ).read_text()
        assert "can_dispatch" in src
        assert "/dispatch" in src

    def test_the_shared_screen_still_never_asks_what_role_is_looking(self):
        """`can_dispatch` is decided server-side like every other action
        there, so a brand on a brief we run never sees the control."""
        src = (
            FRONTEND / "components" / "application" / "ApplicationDetail.jsx"
        ).read_text()
        panel = src[src.index("can_dispatch") : src.index("can_confirm_slot")]
        for role_check in ('role === "admin"', 'role === "brand', "isAdmin"):
            assert role_check not in panel

    def test_the_post_form_hides_venue_scheduling_on_a_delivery(self):
        """The form agreeing with the API rather than deciding on its own —
        and absent rather than disabled, because greyed boxes headed "The
        venue" read as fields somebody has not got to yet."""
        src = (FRONTEND / "pages" / "PostCampaign.jsx").read_text()
        assert "const isDelivery = campaignType ===" in src
        # ShootPreferences stays on the one type where those questions have an
        # answer, which is what it already did.
        block = src[src.index("{campaignType === \"personal_table\" && (") :][:400]
        assert "ShootPreferences" in block
        # And the venue section is branched away entirely.
        assert "pc-delivery-note" in src

    def test_the_post_form_offers_the_type(self):
        src = (FRONTEND / "pages" / "PostCampaign.jsx").read_text()
        assert 'value: "delivery"' in src
