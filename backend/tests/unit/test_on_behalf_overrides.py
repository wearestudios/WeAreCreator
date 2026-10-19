"""Doing the creator's step for them, on the record.

`advance_collaboration` refuses the three creator-owned transitions —
`slot_booked`, `address_confirmed`, `received` — and this change leaves that
refusal exactly as it was. What it adds is a separate, audited **override**
for the first two: admin-only, a reason required, its own audit action with
the state at the moment of the decision, a marker on the row so every surface
reads "booked by WeAre on their behalf" rather than "booked", and a message to
the creator every time. `received` has no override at all, on purpose.

The same instrument as `test_delivery_campaigns.py`: build the rows, call the
**real handler**, read the database back. Two rules carried over —

- **Assert on stored state, not only on the exception.** A 409 raised after
  the write is not a refusal.
- **Run the guard rather than grepping for it.** `guard_allows` pulls the real
  `require_roles` dependency off the signature and calls it.
"""

from __future__ import annotations

import asyncio
import inspect
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException, params
from pydantic import ValidationError
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
        db = AsyncMongoMockClient()["on_behalf"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return _loop().run_until_complete(go())


def guard_allows(fn, role):
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


ADMIN = {"_id": str(ObjectId()), "role": "admin", "name": "Priya"}
REASON = "You asked us on the phone to put you down for Saturday."


async def _world(
    db,
    *,
    campaign_type="group_event",
    state="commercial_agreed",
    address="12 MG Road",
    requires_slot_confirmation=False,
):
    """A brand, a creator, one campaign of the given type with one slot, and
    one collaboration standing at `state`."""
    brand_oid, creator_oid, camp_oid, collab_oid, slot_oid = (
        ObjectId(), ObjectId(), ObjectId(), ObjectId(), ObjectId(),
    )
    await db.users.insert_many([
        {"_id": brand_oid, "role": "brand_manager", "name": "Blume",
         "brand_id": brand_oid, "phone": "+919900000001"},
        {"_id": creator_oid, "role": "creator", "name": "Asha",
         "phone": "+919900000002"},
        # The campaign is weare-run with nobody assigned, so "whoever runs
        # it" resolves to every admin — there has to be one to be told.
        {"_id": ObjectId(ADMIN["_id"]), "role": "admin", "name": ADMIN["name"],
         "email": "priya@example.test"},
    ])
    await db.brand_profiles.insert_one(
        {"user_id": brand_oid, "business_name": "Blume", "verified": True}
    )
    await db.creator_profiles.insert_one({
        "user_id": creator_oid, "name": "Asha", "verification_status": "verified",
        **({"full_address": address} if address else {}),
    })
    starts = _now() + timedelta(days=3)
    await db.campaigns.insert_one({
        "_id": camp_oid, "brand_id": brand_oid, "title": "Sample box",
        "status": "in_progress", "campaign_type": campaign_type,
        "compensation_type": "fixed", "budget_per_creator": 18000,
        "creators_needed": 3, "execution_owner": "weare",
        "requires_slot_confirmation": requires_slot_confirmation,
        "start_date": _now(), "end_date": starts + timedelta(days=4),
        "event_date": starts,
    })
    await db.campaign_slots.insert_one({
        "_id": slot_oid, "campaign_id": camp_oid, "starts_at": starts,
        "ends_at": starts + timedelta(hours=2), "capacity": 2, "booked_count": 0,
    })
    await db.collaborations.insert_one({
        "_id": collab_oid, "campaign_id": camp_oid, "creator_id": creator_oid,
        "state": state, "state_since": _now(), "created_at": _now(),
        "agreed_amount": 18000.0, "agreed_at": _now(), "active": True,
    })
    return {
        "creator": {"_id": str(creator_oid), "role": "creator", "name": "Asha"},
        "creator_oid": creator_oid,
        "campaign_id": camp_oid,
        "collab": str(collab_oid),
        "collab_oid": collab_oid,
        "slot": str(slot_oid),
        "slot_oid": slot_oid,
    }


def _book(w, reason=REASON, slot=None, preferred_time=None):
    return server.book_slot_on_behalf(
        w["collab"],
        server.BookSlotOnBehalfPayload(
            slot_id=slot or w["slot"], preferred_time=preferred_time, reason=reason
        ),
        ADMIN,
    )


def _confirm_address(w, reason=REASON):
    return server.confirm_address_on_behalf(
        w["collab"], server.OnBehalfPayload(reason=reason), ADMIN
    )


# ---------------------------------------------------------------------------
# The ordinary path is untouched
# ---------------------------------------------------------------------------


class TestAdvanceStillRefusesAllThree:
    """**The override is a separate route, not a relaxation.** An admin
    advancing into any of the three from the console still gets the same 409
    it always did, and the row does not move."""

    @pytest.mark.parametrize(
        "state,before,campaign_type",
        [
            ("slot_booked", "commercial_agreed", "group_event"),
            ("address_confirmed", "commercial_agreed", "delivery"),
            ("received", "dispatched", "delivery"),
        ],
    )
    def test_the_ordinary_advance_refuses_it(self, state, before, campaign_type):
        assert state in server._CREATOR_OWNED_TRANSITIONS

        async def body(db):
            w = await _world(db, campaign_type=campaign_type, state=before)
            with pytest.raises(HTTPException) as exc:
                await server.advance_collaboration(
                    w["collab"], server.AdvanceCollabPayload(from_state=before), ADMIN
                )
            return exc.value, await db.collaborations.find_one({"_id": w["collab_oid"]})

        err, row = run(body)
        assert err.status_code == 409
        assert "Only the creator" in err.detail
        assert row["state"] == before

    def test_the_set_of_creator_owned_steps_did_not_shrink(self):
        assert server._CREATOR_OWNED_TRANSITIONS == {
            "slot_booked", "address_confirmed", "received",
        }

    def test_received_has_no_override(self):
        """An admin asserting a parcel arrived at somebody's door is the one
        of the three with no honest basis, and a required reason would only
        record the guess. Deliberately left out, and said so beside the list."""
        assert "received" not in server.ON_BEHALF_STEPS
        assert set(server.ON_BEHALF_STEPS) == {"slot_booked", "address_confirmed"}
        paths = [
            r.path for r in server.admin_router.routes if "on-behalf" in getattr(r, "path", "")
        ]
        assert paths, "the override routes are missing"
        assert not any("received" in p for p in paths)
        # And the reasoning is written where the next person will look.
        src = server.__file__
        text = Path(src).read_text()
        head = text[text.index("ON_BEHALF_STEPS = ") - 600 : text.index("ON_BEHALF_STEPS = ")]
        assert "received" in head and "guess" in head


# ---------------------------------------------------------------------------
# Booking on their behalf
# ---------------------------------------------------------------------------


class TestBookingOnBehalf:
    def test_it_is_admin_only(self):
        assert guard_allows(server.book_slot_on_behalf, "admin")
        for role in ("weare_team", "campaign_manager", "brand_manager", "creator"):
            assert not guard_allows(server.book_slot_on_behalf, role), role

    def test_the_row_carries_who_when_why_and_that_it_was_an_override(self):
        async def body(db):
            w = await _world(db)
            out = await _book(w)
            return (
                out,
                await db.collaborations.find_one({"_id": w["collab_oid"]}),
                await db.campaign_slots.find_one({"_id": w["slot_oid"]}),
            )

        out, row, slot = run(body)
        assert row["state"] == "slot_booked"
        marker = row["slot_booked_on_behalf"]
        assert marker["reason"] == REASON
        assert marker["by_name"] == "Priya"
        assert str(marker["by_id"]) == ADMIN["_id"]
        assert isinstance(marker["at"], datetime)
        # The seat is a real one, claimed the same way the creator's is.
        assert slot["booked_count"] == 1
        assert row["slot_id"] == slot["_id"]
        # The handshake is untouched: no confirmation asked, so confirmed now.
        assert row["slot_confirmed_at"] is not None
        # And the response says so, like every other surface.
        assert out["on_behalf"]["slot_booked"]["reason"] == REASON

    def test_it_audits_as_its_own_action_with_the_reason_and_the_state_before(self):
        async def body(db):
            w = await _world(db)
            await _book(w)
            return await db.audit_log.find_one(
                {"subject_id": w["collab_oid"], "action": "collaboration.book_slot_on_behalf"}
            ), await db.audit_log.find_one(
                {"subject_id": w["collab_oid"], "action": "collaboration.book_slot"}
            )

        line, plain = run(body)
        assert line is not None, "the override must audit under its own action"
        assert plain is None, "an override must not also read as the creator's own booking"
        assert line["note"] == REASON
        assert line["before"]["state"] == "commercial_agreed"
        assert line["after"]["state"] == "slot_booked"
        assert line["after"]["on_behalf"] is True
        assert line["after"]["booked_by"] == "Priya"
        assert line["actor_role"] == "admin"

    def test_the_creator_is_told_by_name_with_the_reason(self):
        async def body(db):
            w = await _world(db)
            await _book(w)
            return await db.notifications.find_one(
                {"user_id": w["creator_oid"], "event": "slot_booked_for_you"}
            ), await db.notifications.find_one(
                {"user_id": w["creator_oid"], "event": {"$in": ["slot_confirmed", "slot_requested"]}}
            )

        note, plain = run(body)
        assert note is not None
        assert plain is None, "the creator must hear it was done for them, not that they booked"
        assert "Priya" in note["body"]
        assert REASON in note["body"]
        assert "release it" in note["body"]

    def test_a_campaign_that_asks_for_confirmation_still_waits(self):
        """The override is of the creator's half, not the runner's."""

        async def body(db):
            w = await _world(db, requires_slot_confirmation=True)
            out = await _book(w)
            return (
                out,
                await db.collaborations.find_one({"_id": w["collab_oid"]}),
                await db.notifications.find_one(
                    {"user_id": w["creator_oid"], "event": "slot_booked_for_you"}
                ),
            )

        out, row, note = run(body)
        assert out["slot_confirmed"] is False
        assert row["slot_confirmed_at"] is None
        assert server._slot_confirmed(row) is False
        assert "confirmed" in note["body"]

    def test_a_reason_is_required(self):
        with pytest.raises(ValidationError):
            server.BookSlotOnBehalfPayload(slot_id=str(ObjectId()), reason="")
        with pytest.raises(ValidationError):
            server.BookSlotOnBehalfPayload(slot_id=str(ObjectId()), reason="ok")

    def test_a_blank_reason_is_refused_at_the_route_and_nothing_moves(self):
        """Whitespace passes a length floor; the route strips and refuses."""

        async def body(db):
            w = await _world(db)
            with pytest.raises(HTTPException) as exc:
                await _book(w, reason="    ")
            return (
                exc.value,
                await db.collaborations.find_one({"_id": w["collab_oid"]}),
                await db.campaign_slots.find_one({"_id": w["slot_oid"]}),
            )

        err, row, slot = run(body)
        assert err.status_code == 422
        assert row["state"] == "commercial_agreed"
        assert slot["booked_count"] == 0

    def test_another_campaigns_slot_is_not_a_slot(self):
        async def body(db):
            w = await _world(db)
            stray = ObjectId()
            await db.campaign_slots.insert_one({
                "_id": stray, "campaign_id": ObjectId(), "starts_at": _now(),
                "ends_at": _now(), "capacity": 2, "booked_count": 0,
            })
            with pytest.raises(HTTPException) as exc:
                await _book(w, slot=str(stray))
            return exc.value, await db.collaborations.find_one({"_id": w["collab_oid"]})

        err, row = run(body)
        assert err.status_code == 404
        assert row["state"] == "commercial_agreed"

    def test_a_delivery_brief_has_no_slot_to_book(self):
        async def body(db):
            w = await _world(db, campaign_type="delivery")
            with pytest.raises(HTTPException) as exc:
                await _book(w)
            return exc.value, await db.collaborations.find_one({"_id": w["collab_oid"]})

        err, row = run(body)
        assert err.status_code == 409
        assert "address" in err.detail
        assert row["state"] == "commercial_agreed"

    def test_a_frozen_collaboration_is_not_booked(self):
        async def body(db):
            w = await _world(db)
            await db.collaborations.update_one(
                {"_id": w["collab_oid"]},
                {"$set": {"dispute": {"state": "open", "raised_by_role": "creator"}}},
            )
            with pytest.raises(HTTPException):
                await _book(w)
            return await db.collaborations.find_one({"_id": w["collab_oid"]})

        row = run(body)
        assert row["state"] == "commercial_agreed"

    def test_declining_the_override_clears_the_marker_and_a_rebook_is_their_own(self):
        """A declined override is no longer a booking at all, so it is no
        longer one WeAre made — and the creator's own re-booking must not
        inherit the marker."""

        async def body(db):
            w = await _world(db, requires_slot_confirmation=True)
            await _book(w)
            collab = await db.collaborations.find_one({"_id": w["collab_oid"]})
            campaign = await db.campaigns.find_one({"_id": w["campaign_id"]})
            await server._answer_slot_request(
                collab, campaign, ADMIN, confirm=False, reason="Venue shut that day"
            )
            after_decline = await db.collaborations.find_one({"_id": w["collab_oid"]})
            await server._claim_slot(
                w["creator"],
                after_decline,
                campaign,
                await db.campaign_slots.find_one({"_id": w["slot_oid"]}),
            )
            return after_decline, await db.collaborations.find_one({"_id": w["collab_oid"]})

        after_decline, rebooked = run(body)
        assert "slot_booked_on_behalf" not in after_decline
        assert server._on_behalf_block(after_decline) is None
        assert rebooked["state"] == "slot_booked"
        assert rebooked["slot_booked_on_behalf"] is None
        assert server._on_behalf_block(rebooked) is None

    def test_the_creators_own_booking_writes_no_marker(self):
        async def body(db):
            w = await _world(db)
            await server._claim_slot(
                w["creator"],
                await db.collaborations.find_one({"_id": w["collab_oid"]}),
                await db.campaigns.find_one({"_id": w["campaign_id"]}),
                await db.campaign_slots.find_one({"_id": w["slot_oid"]}),
            )
            return (
                await db.collaborations.find_one({"_id": w["collab_oid"]}),
                await db.audit_log.find_one({"subject_id": w["collab_oid"]}),
                await db.notifications.find_one({"user_id": w["creator_oid"]}),
            )

        row, line, note = run(body)
        assert server._on_behalf_block(row) is None
        assert line["action"] == "collaboration.book_slot"
        assert line.get("note") in (None, "")
        assert note["event"] == "slot_confirmed"


# ---------------------------------------------------------------------------
# Confirming the address on their behalf
# ---------------------------------------------------------------------------


class TestConfirmingAddressOnBehalf:
    def test_it_is_admin_only(self):
        assert guard_allows(server.confirm_address_on_behalf, "admin")
        for role in ("weare_team", "campaign_manager", "brand_manager", "creator"):
            assert not guard_allows(server.confirm_address_on_behalf, role), role

    def test_the_row_carries_the_marker_and_the_state_moves(self):
        async def body(db):
            w = await _world(db, campaign_type="delivery")
            out = await _confirm_address(w)
            return out, await db.collaborations.find_one({"_id": w["collab_oid"]})

        out, row = run(body)
        assert row["state"] == "address_confirmed"
        assert row["state_since"] is not None
        marker = row["delivery"]["address_confirmed_on_behalf"]
        assert marker["reason"] == REASON
        assert marker["by_name"] == "Priya"
        assert row["delivery"]["address_confirmed_at"] is not None
        assert out["on_behalf"]["address_confirmed"]["reason"] == REASON
        # And `_delivery_block` is still the delivery block.
        assert out["address_confirmed_at"] is not None

    def test_it_audits_as_its_own_action(self):
        async def body(db):
            w = await _world(db, campaign_type="delivery")
            await _confirm_address(w)
            return await db.audit_log.find_one({"subject_id": w["collab_oid"]})

        line = run(body)
        assert line["action"] == "collaboration.delivery_address_confirmed_on_behalf"
        assert line["note"] == REASON
        assert line["before"]["state"] == "commercial_agreed"
        assert line["after"]["state"] == "address_confirmed"
        assert line["after"]["on_behalf"] is True
        assert line["campaign_id"] is not None

    def test_the_creator_is_told_and_told_what_to_do_if_it_is_wrong(self):
        async def body(db):
            w = await _world(db, campaign_type="delivery")
            await _confirm_address(w)
            return await db.notifications.find_one(
                {"user_id": w["creator_oid"], "event": "address_confirmed_for_you"}
            )

        note = run(body)
        assert note is not None
        assert REASON in note["body"]
        assert "wrong" in note["body"]

    def test_whoever_runs_it_is_told_it_was_done_for_them(self):
        """Routed like the creator's own confirmation — the parcel still has
        to be packed by somebody — and the message says who confirmed."""

        async def body(db):
            w = await _world(db, campaign_type="delivery")
            await _confirm_address(w)
            return await db.notifications.find(
                {"event": "delivery_address_confirmed"}
            ).to_list(length=10)

        notes = run(body)
        assert notes, "the runner was not told"
        assert all("on their behalf" in n["body"] for n in notes)

    def test_no_address_on_the_profile_is_refused(self):
        """An admin confirming a blank would be confirming nothing — the
        parcel would still have nowhere to go."""

        async def body(db):
            w = await _world(db, campaign_type="delivery", address=None)
            with pytest.raises(HTTPException) as exc:
                await _confirm_address(w)
            return exc.value, await db.collaborations.find_one({"_id": w["collab_oid"]})

        err, row = run(body)
        assert err.status_code == 422
        assert err.detail["code"] == "no_delivery_address"
        assert row["state"] == "commercial_agreed"
        assert "delivery" not in row

    def test_a_venue_brief_has_no_address_to_confirm(self):
        async def body(db):
            w = await _world(db, campaign_type="group_event")
            with pytest.raises(HTTPException) as exc:
                await _confirm_address(w)
            return exc.value, await db.collaborations.find_one({"_id": w["collab_oid"]})

        err, row = run(body)
        assert err.status_code == 409
        assert row["state"] == "commercial_agreed"

    def test_only_from_commercial_agreed(self):
        async def body(db):
            w = await _world(db, campaign_type="delivery", state="dispatched")
            with pytest.raises(HTTPException) as exc:
                await _confirm_address(w)
            return exc.value, await db.collaborations.find_one({"_id": w["collab_oid"]})

        err, row = run(body)
        assert err.status_code == 409
        assert row["state"] == "dispatched"

    def test_a_reason_is_required(self):
        with pytest.raises(ValidationError):
            server.OnBehalfPayload(reason="")

        async def body(db):
            w = await _world(db, campaign_type="delivery")
            with pytest.raises(HTTPException) as exc:
                await _confirm_address(w, reason="   ")
            return exc.value, await db.collaborations.find_one({"_id": w["collab_oid"]})

        err, row = run(body)
        assert err.status_code == 422
        assert row["state"] == "commercial_agreed"

    def test_a_frozen_collaboration_is_not_confirmed(self):
        async def body(db):
            w = await _world(db, campaign_type="delivery")
            await db.collaborations.update_one(
                {"_id": w["collab_oid"]},
                {"$set": {"dispute": {"state": "open", "raised_by_role": "creator"}}},
            )
            with pytest.raises(HTTPException):
                await _confirm_address(w)
            return await db.collaborations.find_one({"_id": w["collab_oid"]})

        assert run(body)["state"] == "commercial_agreed"


# ---------------------------------------------------------------------------
# Every surface says so
# ---------------------------------------------------------------------------


def _marked(step="slot_booked"):
    record = {"by_id": ObjectId(), "by_name": "Priya", "at": _now(), "reason": REASON}
    if step == "slot_booked":
        return {
            "state": "slot_booked", "slot_booked_at": _now(),
            "slot_confirmed_at": _now(), "slot_booked_on_behalf": record,
        }
    return {
        "state": "address_confirmed",
        "delivery": {"address_confirmed_at": _now(), "address_confirmed_on_behalf": record},
    }


class TestTheReader:
    def test_absent_means_the_creator_did_it(self):
        assert server._on_behalf_block({}) is None
        assert server._on_behalf_block(None) is None
        assert server._on_behalf_block({"state": "slot_booked", "slot_booked_at": _now()}) is None
        # The creator's own booking writes `None` explicitly; that is absent too.
        assert server._on_behalf_block({"slot_booked_on_behalf": None}) is None

    def test_a_marked_row_names_the_step_who_when_and_why(self):
        block = server._on_behalf_block(_marked())
        assert set(block) == {"slot_booked"}
        assert block["slot_booked"]["by_name"] == "Priya"
        assert block["slot_booked"]["reason"] == REASON
        assert block["slot_booked"]["at"]
        assert "by_id" not in block["slot_booked"]
        assert set(server._on_behalf_block(_marked("address_confirmed"))) == {"address_confirmed"}


class TestEverySurfaceRendersItAsAnOverride:
    """**If the only visible difference were in the audit log, this would have
    failed.** The creator's own card, the shared application screen, the admin
    collaboration page and the manager's roster each carry the block and each
    draws it."""

    def test_the_process_flow_never_says_a_bare_booked(self):
        campaign = {"campaign_type": "group_event", "execution_owner": "weare"}
        for viewer in ({"role": "creator"}, {"role": "admin"}, {"role": "brand_manager"}):
            label = server._process_flow(_marked(), campaign, viewer=viewer)["next_action"]["label"]
            assert "WeAre" in label, (viewer, label)
            assert "behalf" in label or "for you" in label, (viewer, label)
        plain = {"state": "slot_booked", "slot_booked_at": _now(), "slot_confirmed_at": _now()}
        assert "WeAre" not in server._process_flow(plain, campaign, viewer={"role": "creator"})["next_action"]["label"]

    def test_the_process_flow_says_so_on_a_pending_override_too(self):
        campaign = {"campaign_type": "group_event", "requires_slot_confirmation": True}
        row = {**_marked(), "slot_confirmed_at": None}
        label = server._process_flow(row, campaign, viewer={"role": "creator"})["next_action"]["label"]
        assert "WeAre" in label and "confirmed" in label

    def test_the_process_flow_says_so_on_a_confirmed_address(self):
        campaign = {"campaign_type": "delivery", "execution_owner": "weare"}
        label = server._process_flow(_marked("address_confirmed"), campaign, viewer={"role": "creator"})["next_action"]["label"]
        assert "WeAre" in label

    def test_the_creators_next_line_says_who_booked_it(self):
        label = server._creator_next_action(_marked(), {"campaign_type": "group_event"}, True)["label"]
        assert "WeAre booked this slot for you" in label
        label = server._creator_next_action(_marked("address_confirmed"), {"campaign_type": "delivery"}, True)["label"]
        assert "WeAre confirmed" in label

    def test_the_creators_own_row_carries_the_block(self):
        row = server._serialize_collab_row(
            {**_marked(), "_id": ObjectId(), "campaign_id": ObjectId()},
            {"title": "x"}, "Blume", payout_default=7,
        )
        assert row["on_behalf"]["slot_booked"]["reason"] == REASON

    def test_the_rosters_row_carries_the_block(self):
        async def body(db):
            w = await _world(db)
            await _book(w)
            campaign = await db.campaigns.find_one({"_id": w["campaign_id"]})
            return await server._roster_rows(campaign)

        rows = run(body)
        assert rows[0]["on_behalf"]["slot_booked"]["by_name"] == "Priya"

    def test_the_shared_application_screen_carries_the_block_and_the_flags(self):
        async def body(db):
            w = await _world(db)
            before = await server.get_application(w["collab"], ADMIN)
            await _book(w)
            after = await server.get_application(w["collab"], ADMIN)
            return before, after

        before, after = run(body)
        assert before["on_behalf"] is None
        assert before["actions"]["can_book_on_behalf"] is True
        assert before["actions"]["can_confirm_address_on_behalf"] is False
        assert after["on_behalf"]["slot_booked"]["reason"] == REASON
        assert after["actions"]["can_book_on_behalf"] is False

    def test_a_delivery_brief_offers_the_other_flag(self):
        async def body(db):
            w = await _world(db, campaign_type="delivery")
            return await server.get_application(w["collab"], ADMIN)

        out = run(body)
        assert out["actions"]["can_confirm_address_on_behalf"] is True
        assert out["actions"]["can_book_on_behalf"] is False

    def test_the_flags_are_never_offered_to_a_brand(self):
        async def body(db):
            w = await _world(db)
            brand = await db.users.find_one({"role": "brand_manager"})
            await db.campaigns.update_one(
                {"_id": w["campaign_id"]}, {"$set": {"execution_owner": "brand"}}
            )
            user = {"_id": str(brand["_id"]), "role": "brand_manager", "name": "Blume",
                    "brand_id": brand["_id"]}
            return await server.get_application(w["collab"], user)

        out = run(body)
        assert out["actions"]["can_book_on_behalf"] is False
        assert out["actions"]["can_confirm_address_on_behalf"] is False

    def test_the_admin_collaboration_page_carries_the_block_and_the_flags(self):
        async def body(db):
            w = await _world(db)
            before = await server.get_admin_collaboration_detail(w["collab"], ADMIN)
            await _book(w)
            after = await server.get_admin_collaboration_detail(w["collab"], ADMIN)
            return before["collaboration"], after["collaboration"]

        before, after = run(body)
        assert before["can_book_on_behalf"] is True
        assert before["on_behalf"] is None
        assert after["on_behalf"]["slot_booked"]["by_name"] == "Priya"
        assert after["can_book_on_behalf"] is False

    @pytest.mark.parametrize(
        "path",
        [
            "components/creator/ActiveCampaigns.jsx",
            "components/application/ApplicationDetail.jsx",
            "components/admin/CollaborationDetailPage.jsx",
            "pages/ManagerCampaign.jsx",
        ],
    )
    def test_each_surface_reads_the_block(self, path):
        src = (FRONTEND / path).read_text()
        assert "on_behalf" in src, f"{path} does not render the override"

    def test_the_one_renderer_speaks_both_voices_and_never_a_bare_booked(self):
        src = (FRONTEND / "components" / "collab" / "OnBehalfNote.jsx").read_text()
        assert "on your behalf" in src
        assert "on the creator's behalf" in src
        for path in ("components/creator/ActiveCampaigns.jsx",
                     "components/application/ApplicationDetail.jsx",
                     "components/admin/CollaborationDetailPage.jsx"):
            page = (FRONTEND / path).read_text()
            assert "OnBehalfNote" in page, path
        roster = (FRONTEND / "pages" / "ManagerCampaign.jsx").read_text()
        assert "Booked by WeAre on their behalf" in roster

    def test_the_admin_page_calls_both_routes(self):
        src = (FRONTEND / "components" / "admin" / "CollaborationDetailPage.jsx").read_text()
        assert "/on-behalf/book-slot" in src
        assert "/on-behalf/confirm-address" in src
        # The buttons are gated on the server's flags, not on a role check.
        assert "can_book_on_behalf" in src
        assert "can_confirm_address_on_behalf" in src
        assert not re.search(r"role\s*===\s*['\"]admin['\"]", src)

    def test_both_notification_templates_are_documented(self):
        env = (Path(server.__file__).resolve().parent / ".env.example").read_text()
        assert "AISENSY_TEMPLATE_SLOT_BOOKED_FOR_YOU" in env
        assert "AISENSY_TEMPLATE_ADDRESS_CONFIRMED_FOR_YOU" in env
        assert "slot_booked_for_you" in server.NOTIFY_EVENTS
        assert "address_confirmed_for_you" in server.NOTIFY_EVENTS
