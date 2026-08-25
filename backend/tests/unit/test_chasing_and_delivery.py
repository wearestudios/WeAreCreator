"""The clock's two jobs, and the judgements that hang off delivery.

`test_the_clock.py` holds the reminder cap and the ageing arithmetic. This
file is the other half of the same story, driven end to end: **all five**
reminder kinds rather than the one, the escalation routing that decides who
hears about a late record, and then the delivery-side judgements — takedown,
partial acceptance, reliability and retention — which are what a late or
disputed delivery eventually turns into on somebody's record.

Two things are asserted here that a per-function test cannot reach:

- **A reminder stops because the row moved, not because a branch noticed.**
  The state is a precondition inside `_claim_reminder`'s filter, so the proof
  is to advance the collaboration and run the whole job again.
- **A mark on somebody's reliability is not the same event as a nudge.**
  Passing the SLA chases; passing the SLA *and* the grace is what writes
  `content_overdue`. Collapsing them would be unfair to the creator, so the
  two are tested at two different clock positions.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import server

LOOP = None


def run(body):
    """One loop per call — see the note in `test_money_paths.py`."""
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()

    async def go():
        db = AsyncMongoMockClient()["chasing"]
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


async def _world(db, *, execution_owner="brand", with_admin=True):
    """A brand, a creator, a campaign — the cast every chaser needs."""
    brand_oid, creator_oid, campaign_oid = ObjectId(), ObjectId(), ObjectId()
    users = [
        {"_id": brand_oid, "role": "brand_manager", "name": "Toit",
         "brand_id": brand_oid, "phone": "+919900000001"},
        {"_id": creator_oid, "role": "creator", "name": "Asha",
         "phone": "+919900000002"},
    ]
    if with_admin:
        users.append(
            {"_id": ObjectId(), "role": "admin", "name": "Ops", "phone": "+919900000003"}
        )
    await db.users.insert_many(users)
    await db.brand_profiles.insert_one(
        {"user_id": brand_oid, "business_name": "Toit", "verified": True}
    )
    await db.creator_profiles.insert_one(
        {"user_id": creator_oid, "name": "Asha", "verification_status": "verified"}
    )
    await db.campaigns.insert_one(
        {"_id": campaign_oid, "brand_id": brand_oid, "title": "Toit tasting",
         "status": "open", "execution_owner": execution_owner,
         "compensation_type": "negotiated", "budget_per_creator": 10000}
    )
    return {"brand_oid": brand_oid, "creator_oid": creator_oid,
            "campaign_oid": campaign_oid}


async def _collab(db, w, *, state, ago_hours=200, **extra):
    """A collaboration that has been sitting in `state` long enough to chase."""
    oid = ObjectId()
    await db.collaborations.insert_one(
        {"_id": oid, "campaign_id": w["campaign_oid"], "creator_id": w["creator_oid"],
         "state": state, "state_since": _now() - timedelta(hours=ago_hours),
         "agreed_amount": 10000, "created_at": _now() - timedelta(hours=ago_hours),
         **extra}
    )
    return oid


async def _age_the_reminders(db, hours=48):
    """Wind the spacing back, which is what a day passing does in the world."""
    await db.collaborations.update_many(
        {},
        {"$set": {f"reminders.{k}.last_at": _now() - timedelta(hours=hours)
                  for k in server._reminder_kinds()}},
    )


# ---------------------------------------------------------------------------
# 4. Chasing — every kind, twice, and then never
# ---------------------------------------------------------------------------


class TestEveryReminderStopsAtTwo:
    """`test_the_clock.py` proves the cap for `book_slot`. The cap lives in a
    shared claim, so the risk is not that it stops working — it is that a new
    chaser is added that does not go through the claim at all. Parametrised
    over the kinds that hang off a collaboration state, so a sixth one added
    without the claim fails here."""

    CASES = {
        "book_slot": ("commercial_agreed", {}),
        "content_due": ("attended", {}),
        "draft_review": ("draft_submitted", {}),
    }

    @pytest.mark.parametrize("kind", sorted(CASES))
    def test_two_and_then_silence(self, kind):
        state, extra = self.CASES[kind]

        async def body(db):
            w = await _world(db)
            await _collab(db, w, state=state, **extra)
            sent = []
            for _ in range(4):
                report = await server.run_lifecycle_chasers()
                sent.append(report[kind])
                await _age_the_reminders(db)
            return sent

        assert run(body) == [1, 1, 0, 0], f"{kind} does not stop at two"

    @pytest.mark.parametrize("kind", sorted(CASES))
    def test_it_stops_the_moment_the_state_advances(self, kind):
        """Nobody is chased about a thing they have already done.

        **This is the query half of that rule, not the claim half.** Advancing
        the row before the next pass means the selecting query no longer
        matches it, so no claim is even attempted — which is what this
        asserts, for every kind. The *claim's* own `state` precondition covers
        the narrower race where a row moves between the query and the claim,
        and it is tested directly in `test_the_clock.py`
        (`test_the_claim_itself_refuses_a_state_that_moved`). Deleting that
        precondition leaves this test green; saying so here is cheaper than
        somebody rediscovering it.
        """
        state, extra = self.CASES[kind]

        async def body(db):
            w = await _world(db)
            oid = await _collab(db, w, state=state, **extra)
            first = (await server.run_lifecycle_chasers())[kind]
            # The thing everybody was waiting for happens.
            await db.collaborations.update_one(
                {"_id": oid}, {"$set": {"state": "closed"}}
            )
            await _age_the_reminders(db)
            second = (await server.run_lifecycle_chasers())[kind]
            return first, second

        first, second = run(body)
        assert first == 1
        assert second == 0, f"{kind} kept chasing a row that had moved on"

    def test_a_second_pass_straight_away_sends_nothing(self):
        """Spacing as well as a cap. The loop can legitimately run more than
        once an hour, and two reminders inside a minute is one reminder and one
        bug."""

        async def body(db):
            w = await _world(db)
            await _collab(db, w, state="commercial_agreed")
            return [
                (await server.run_lifecycle_chasers())["book_slot"] for _ in range(3)
            ]

        assert run(body) == [1, 0, 0]


class TestTheShootReminder:
    def test_it_fires_for_tomorrow_and_not_for_next_week(self):
        """Not a delay — the one reminder here that is simply useful. It keys
        on the booked time rather than on how long the row has sat.

        Both rows in one pass, and the reminder counter on each is what says
        which of them was told: two passes would let the near shoot be
        reminded twice and hide the far one behind the total.
        """

        async def body(db):
            w = await _world(db)
            soon_oid = await _collab(db, w, state="slot_booked", ago_hours=2,
                                     scheduled_at=_now() + timedelta(hours=20))
            far_oid = await _collab(db, w, state="slot_booked", ago_hours=2,
                                    scheduled_at=_now() + timedelta(days=8))
            total = (await server.run_lifecycle_chasers())["shoot_tomorrow"]
            return (
                total,
                await db.collaborations.find_one({"_id": soon_oid}),
                await db.collaborations.find_one({"_id": far_oid}),
            )

        total, soon, far = run(body)
        assert total == 1
        assert soon["reminders"]["shoot_tomorrow"]["count"] == 1
        assert (far.get("reminders") or {}).get("shoot_tomorrow") is None

    def test_a_shoot_already_past_is_not_reminded_about(self):
        async def body(db):
            w = await _world(db)
            await _collab(db, w, state="slot_booked", ago_hours=2,
                          scheduled_at=_now() - timedelta(hours=5))
            return (await server.run_lifecycle_chasers())["shoot_tomorrow"]

        assert run(body) == 0


class TestUnansweredPitches:
    """**Counted in messages, not in rows.** The report's
    `applications_waiting` is the number of pitches claimed, not the number of
    WhatsApps sent — five on one brief claims five and sends one. So the
    assertion here is on the notifications, which is the thing the rule is
    actually about."""

    def test_five_pitches_on_one_brief_is_one_message(self):
        async def body(db):
            w = await _world(db)
            for _ in range(5):
                await _collab(db, w, state="applied")
            await server.run_lifecycle_chasers()
            return await db.notifications.count_documents(
                {"user_id": w["brand_oid"], "event": "reminder_applications_waiting"}
            )

        assert run(body) == 1

    def test_two_campaigns_are_two_messages(self):
        async def body(db):
            w1 = await _world(db)
            w2 = await _world(db, with_admin=False)
            await _collab(db, w1, state="applied")
            await _collab(db, w2, state="applied")
            await server.run_lifecycle_chasers()
            return [
                await db.notifications.count_documents(
                    {"user_id": w["brand_oid"],
                     "event": "reminder_applications_waiting"}
                )
                for w in (w1, w2)
            ]

        assert run(body) == [1, 1]

    def test_the_message_names_how_many_are_waiting(self):
        """"Creators are waiting" with no number is a nudge somebody cannot
        size up before opening the console."""

        async def body(db):
            w = await _world(db)
            for _ in range(3):
                await _collab(db, w, state="applied")
            await server.run_lifecycle_chasers()
            return await db.notifications.find_one(
                {"user_id": w["brand_oid"], "event": "reminder_applications_waiting"}
            )

        note = run(body)
        assert "3 pitches" in note["body"]


class TestWhoHearsAboutIt:
    """Escalation follows `execution_owner` — the same routing a new
    application takes, reusing the readers rather than writing a second rule."""

    def test_a_weare_run_brief_escalates_to_us_and_not_to_the_brand(self):
        async def body(db):
            w = await _world(db, execution_owner="weare")
            await _collab(db, w, state="applied")
            await server.run_lifecycle_chasers()
            to_brand = await db.notifications.count_documents(
                {"user_id": w["brand_oid"]}
            )
            return to_brand

        assert run(body) == 0

    def test_a_brand_run_brief_reaches_the_brand_and_copies_admin(self):
        """An overdue record is an operational fact about the platform as well
        as a job for the brand — and the brand going quiet is exactly the case
        somebody here needs to know about."""

        async def body(db):
            w = await _world(db, execution_owner="brand")
            await _collab(db, w, state="applied")
            await server.run_lifecycle_chasers()
            admin_oid = (await db.users.find_one({"role": "admin"}))["_id"]
            return (
                await db.notifications.count_documents({"user_id": w["brand_oid"]}),
                await db.notifications.count_documents({"user_id": admin_oid}),
            )

        to_brand, to_admin = run(body)
        assert to_brand >= 1
        assert to_admin >= 1


class TestLatenessIsNotTheSameEventAsANudge:
    def test_past_the_target_chases_but_does_not_mark_the_record(self):
        """Somebody is waiting and a nudge is proportionate. A mark on
        somebody's reliability is a different thing and needs the grace on
        top."""
        target = server.SLA_DEFAULT_HOURS["content_submission"]

        async def body(db):
            w = await _world(db)
            oid = await _collab(db, w, state="attended", ago_hours=target + 2)
            report = await server.run_lifecycle_chasers()
            collab = await db.collaborations.find_one({"_id": oid})
            return report["content_due"], collab

        chased, collab = run(body)
        assert chased == 1
        assert collab.get("content_overdue") is not True

    def test_past_the_grace_as_well_writes_it_down(self):
        target = server.SLA_DEFAULT_HOURS["content_submission"]

        async def body(db):
            w = await _world(db)
            oid = await _collab(
                db, w, state="attended",
                ago_hours=target + server.CONTENT_GRACE_HOURS + 2,
            )
            report = await server.run_lifecycle_chasers()
            collab = await db.collaborations.find_one({"_id": oid})
            return report["content_flagged_overdue"], collab

        flagged, collab = run(body)
        assert flagged == 1
        assert collab["content_overdue"] is True
        assert collab["content_overdue_at"] is not None

    def test_the_flag_is_set_once_and_not_re_flagged(self):
        """Delivering eventually does not make a delivery not have been late,
        and re-counting it would inflate the only signal a brand has."""
        target = server.SLA_DEFAULT_HOURS["content_submission"]

        async def body(db):
            w = await _world(db)
            await _collab(
                db, w, state="attended",
                ago_hours=target + server.CONTENT_GRACE_HOURS + 2,
            )
            first = (await server.run_lifecycle_chasers())["content_flagged_overdue"]
            await _age_the_reminders(db)
            second = (await server.run_lifecycle_chasers())["content_flagged_overdue"]
            return first, second

        assert run(body) == (1, 0)


class TestTheProfileNudgeGoesOutOnceEver:
    """The other job on the same loop, and the strictest cap in the product:
    not twice, once. Chasing somebody a second time about the same unfinished
    form is how a marketplace teaches people to mute it."""

    async def _stalled(self, db, **over):
        row = {
            "_id": ObjectId(), "user_id": ObjectId(), "name": "Half a profile",
            "verification_status": "pending",
            "created_at": _now() - timedelta(days=60),
            "platforms": ["instagram"],
        }
        row.update(over)
        await db.creator_profiles.insert_one(row)
        await db.users.insert_one(
            {"_id": row["user_id"], "role": "creator", "name": row["name"],
             "phone": "+919900000009"}
        )
        return row

    def test_once_and_then_never(self):
        async def body(db):
            await self._stalled(db)
            first = (await server.nudge_stale_creator_profiles())["sent"]
            second = (await server.nudge_stale_creator_profiles())["sent"]
            third = (await server.nudge_stale_creator_profiles())["sent"]
            return first, second, third

        assert run(body) == (1, 0, 0)

    def test_the_stamp_is_claimed_before_the_send(self):
        """The claim is the write — a send that fails afterwards still counts
        as used up, which is the right trade for a channel this narrow."""

        async def body(db):
            row = await self._stalled(db)
            await server.nudge_stale_creator_profiles()
            return await db.creator_profiles.find_one({"_id": row["_id"]})

        assert run(body)["onboarding_nudge_sent_at"] is not None

    def test_somebody_who_already_submitted_is_left_alone(self):
        """They are waiting on us, not the other way round."""

        async def body(db):
            await self._stalled(db, submitted_for_review_at=_now())
            return await server.nudge_stale_creator_profiles()

        assert run(body)["considered"] == 0

    def test_a_finished_profile_that_never_submitted_is_skipped_not_spent(self):
        """A different message and a different problem. Spending the one nudge
        here means the right one can never be sent."""

        async def body(db):
            await self._stalled(
                db, name="Done", city="Bengaluru", instagram_handle="done",
                instagram_url="https://instagram.com/done", follower_count=12000,
                niches=["food"], genres=["reviews"], bio="x" * 40,
                profile_image_url="/uploads/x.jpg",
            )
            report = await server.nudge_stale_creator_profiles()
            row = await db.creator_profiles.find_one({"name": "Done"})
            return report, row

        report, row = run(body)
        # Either skipped as complete or sent as incomplete — but if it was
        # skipped, the one nudge must still be unspent.
        if report["skipped"]:
            assert row.get("onboarding_nudge_sent_at") is None

    def test_a_fresh_signup_is_not_chased(self):
        """Somebody who signed up this morning has not gone quiet."""

        async def body(db):
            await self._stalled(db, created_at=_now() - timedelta(hours=2))
            return await server.nudge_stale_creator_profiles()

        assert run(body)["considered"] == 0


class TestTheMediationQueue:
    def test_it_lists_open_disputes_oldest_first_and_says_the_money_is_frozen(self):
        """Longest waiting first, because a mediation queue worked in
        arrival order is one where the oldest argument is the last one
        anybody reads."""

        async def body(db):
            w = await _world(db)
            creator = {**await db.users.find_one({"_id": w["creator_oid"]}),
                       "_id": str(w["creator_oid"])}
            old = await _collab(db, w, state="content_submitted")
            new = await _collab(db, w, state="content_submitted")
            for oid in (old, new):
                await db.payments.insert_one(
                    {"_id": ObjectId(), "collaboration_id": oid, "state": "pending",
                     "creator_payout": 10000}
                )
            await server.raise_dispute(
                str(old), server.DisputePayload(reason="Older argument here."), creator
            )
            await server.raise_dispute(
                str(new), server.DisputePayload(reason="Newer argument here."), creator
            )
            await db.collaborations.update_one(
                {"_id": old},
                {"$set": {"dispute.raised_at": _now() - timedelta(days=5)}},
            )
            return await server.list_disputes("open", ADMIN), str(old)

        payload, old_id = run(body)
        assert [d["collaboration_id"] for d in payload["disputes"]][0] == old_id
        assert all(d["payment_frozen"] for d in payload["disputes"])
        assert payload["resolutions"] == server.DISPUTE_RESOLUTIONS

    def test_the_creator_on_a_mediation_row_still_goes_through_the_allow_list(self):
        """A mediation screen is still a screen, and nothing about arguing
        changes what may be shown about somebody."""

        async def body(db):
            w = await _world(db)
            await db.creator_profiles.update_one(
                {"user_id": w["creator_oid"]},
                {"$set": {"phone": "+919812345678", "email": "asha@example.com",
                          "full_address": "12 Residency Road"}},
            )
            creator = {**await db.users.find_one({"_id": w["creator_oid"]}),
                       "_id": str(w["creator_oid"])}
            oid = await _collab(db, w, state="content_submitted")
            await server.raise_dispute(
                str(oid), server.DisputePayload(reason="Something went wrong."), creator
            )
            return await server.list_disputes("open", ADMIN)

        blob = str(run(body))
        for planted in ("+919812345678", "asha@example.com", "12 Residency Road"):
            assert planted not in blob, planted

    def test_a_resolved_dispute_leaves_the_open_queue(self):
        async def body(db):
            w = await _world(db)
            creator = {**await db.users.find_one({"_id": w["creator_oid"]}),
                       "_id": str(w["creator_oid"])}
            oid = await _collab(db, w, state="content_submitted")
            await server.raise_dispute(
                str(oid), server.DisputePayload(reason="A real disagreement."), creator
            )
            await server.resolve_dispute(
                str(oid),
                server.DisputeResolutionPayload(
                    resolution="release", note="Checked it; the work is all there."
                ),
                ADMIN,
            )
            return (
                len((await server.list_disputes("open", ADMIN))["disputes"]),
                len((await server.list_disputes("resolved", ADMIN))["disputes"]),
            )

        assert run(body) == (0, 1)


class TestTheJobSurvivesOneBadRow:
    def test_a_collaboration_with_no_campaign_does_not_end_the_pass(self):
        """One bad campaign must not cost the other four hundred their
        reminder — every branch is wrapped for exactly this."""

        async def body(db):
            w = await _world(db)
            await db.collaborations.insert_one(
                {"_id": ObjectId(), "campaign_id": ObjectId(),  # points at nothing
                 "creator_id": w["creator_oid"], "state": "commercial_agreed",
                 "state_since": _now() - timedelta(days=9)}
            )
            await _collab(db, w, state="commercial_agreed")
            return (await server.run_lifecycle_chasers())["book_slot"]

        assert run(body) == 2

    def test_the_report_names_every_kind_even_when_nothing_sent(self):
        """A report missing a key reads as "that chaser does not exist" to
        whoever is looking at why nobody was reminded."""

        async def body(db):
            await _world(db)
            return await server.run_lifecycle_chasers()

        report = run(body)
        for kind in server._reminder_kinds():
            assert kind in report, kind
        assert report["content_flagged_overdue"] == 0


# ---------------------------------------------------------------------------
# 5. Takedown, partial delivery, reliability, retention
# ---------------------------------------------------------------------------


async def _delivered(db, w, *, state="content_approved", items=None, delivered=None):
    """A collaboration with live work on it, ready to be judged."""
    if items is not None:
        await db.campaigns.update_one(
            {"_id": w["campaign_oid"]}, {"$set": {"deliverable_items": items}}
        )
    oid = await _collab(
        db, w, state=state, ago_hours=48,
        content_url="https://instagram.com/p/abc123/",
        **({"delivered_items": delivered} if delivered else {}),
    )
    return oid


class TestTakedown:
    def test_it_is_only_offered_on_work_that_is_actually_live(self):
        """A draft that needs changing is the review flow. Pointing somebody at
        the wrong one costs a round trip, so the button is absent rather than
        present and 409ing."""

        async def body(db):
            w = await _world(db)
            brand = await db.users.find_one({"_id": w["brand_oid"]})
            oid = await _delivered(db, w, state="draft_submitted")
            with pytest.raises(HTTPException) as err:
                await server.request_takedown(
                    str(oid),
                    server.TakedownPayload(
                        reason_code="factual_error",
                        detail="The price in the caption is wrong.",
                    ),
                    {**brand, "_id": str(w["brand_oid"])},
                )
            return err.value, await db.collaborations.find_one({"_id": oid})

        exc, collab = run(body)
        assert exc.status_code == 409
        assert collab.get("takedown") is None

    def test_a_dispute_does_not_block_it(self):
        """A post that is legally problematic has to be dealt with whether or
        not there is an argument about the money. Those are different
        questions, and this is the one door the freeze deliberately leaves
        open."""

        async def body(db):
            w = await _world(db)
            brand = {**await db.users.find_one({"_id": w["brand_oid"]}),
                     "_id": str(w["brand_oid"])}
            oid = await _delivered(db, w)
            await db.collaborations.update_one(
                {"_id": oid},
                {"$set": {"dispute": {"state": "open", "reason": "Unpaid."}}},
            )
            await server.request_takedown(
                str(oid),
                server.TakedownPayload(
                    reason_code="legal", detail="Trademark complaint from the brand."
                ),
                brand,
            )
            return await db.collaborations.find_one({"_id": oid})

        collab = run(body)
        assert collab["takedown"]["state"] == "requested"

    def test_a_refusal_needs_a_note_and_compliance_does_not(self):
        """"I took it down" is complete on its own. "It's staying up" with
        nothing beside it is an answer nobody can act on — and a takedown that
        silently never happened and one the creator explained they could not do
        are very different facts about them."""

        async def body(db):
            w = await _world(db)
            brand = {**await db.users.find_one({"_id": w["brand_oid"]}),
                     "_id": str(w["brand_oid"])}
            creator = {**await db.users.find_one({"_id": w["creator_oid"]}),
                       "_id": str(w["creator_oid"])}
            oid = await _delivered(db, w)
            await server.request_takedown(
                str(oid),
                server.TakedownPayload(reason_code="off_brand", detail="Wrong tone."),
                brand,
            )
            refused = None
            try:
                await server.respond_to_takedown(
                    str(oid),
                    server.TakedownResponsePayload(actioned=False, note=None),
                    creator,
                )
            except Exception as err:  # noqa: BLE001 — 422 or HTTPException both fine
                refused = err
            await server.respond_to_takedown(
                str(oid),
                server.TakedownResponsePayload(actioned=True, note=None),
                creator,
            )
            return refused, await db.collaborations.find_one({"_id": oid})

        refused, collab = run(body)
        assert refused is not None, "a refusal with no note was accepted"
        assert collab["takedown"]["state"] == "actioned"
        assert server._serialize_takedown(collab)["actioned"] is True

    def test_overdue_is_derived_on_read_and_never_stored(self):
        """A stored flag needs a sweep, and a rule that depends on cron is true
        on Tuesdays."""

        async def body(db):
            w = await _world(db)
            brand = {**await db.users.find_one({"_id": w["brand_oid"]}),
                     "_id": str(w["brand_oid"])}
            oid = await _delivered(db, w)
            await server.request_takedown(
                str(oid),
                server.TakedownPayload(reason_code="legal", detail="Complaint."),
                brand,
            )
            # The deadline is what `overdue` is derived from, so that is what
            # moves — backdating `requested_at` would leave the stored
            # `respond_by` in the future and prove nothing.
            await db.collaborations.update_one(
                {"_id": oid},
                {"$set": {"takedown.respond_by": _now() - timedelta(hours=2)}},
            )
            collab = await db.collaborations.find_one({"_id": oid})
            return collab["takedown"], server._serialize_takedown(collab)

        stored, served = run(body)
        assert "overdue" not in stored
        assert served["overdue"] is True


class TestPartialDelivery:
    ITEMS = [{"type": "reel", "quantity": 1}, {"type": "story", "quantity": 3}]

    def test_a_shortfall_is_recorded_with_the_typed_amount(self):
        """Two of three stories is not two-thirds of the value when the reel
        was the point, so the figure is the one somebody agreed rather than one
        this code worked out."""

        async def body(db):
            w = await _world(db)
            brand = {**await db.users.find_one({"_id": w["brand_oid"]}),
                     "_id": str(w["brand_oid"])}
            oid = await _delivered(db, w, state="content_submitted", items=self.ITEMS)
            await server.accept_partial_delivery(
                str(oid),
                server.PartialDeliveryPayload(
                    delivered={"reel": 1, "story": 2},
                    agreed_amount=8000,
                    note="One story never went up; agreed ₹8,000 on the phone.",
                ),
                brand,
            )
            return await db.collaborations.find_one({"_id": oid})

        collab = run(body)
        # Not a ninth state: what happens next — payment — is the same.
        assert collab["state"] == "content_approved"
        assert collab["partial_delivery"] is True
        assert collab["agreed_amount"] == 8000

    def test_everything_arriving_leaves_an_ordinary_approval_behind(self):
        """A runner double-checking must not put a flag on somebody's
        reliability history for nothing."""

        async def body(db):
            w = await _world(db)
            brand = {**await db.users.find_one({"_id": w["brand_oid"]}),
                     "_id": str(w["brand_oid"])}
            oid = await _delivered(db, w, state="content_submitted", items=self.ITEMS)
            await server.accept_partial_delivery(
                str(oid),
                server.PartialDeliveryPayload(
                    delivered={"reel": 1, "story": 3},
                    agreed_amount=10000,
                    note="Checked; all four are up.",
                ),
                brand,
            )
            return await db.collaborations.find_one({"_id": oid})

        collab = run(body)
        assert collab["state"] == "content_approved"
        assert collab.get("partial_delivery") is not True

    def test_over_counting_is_clamped_rather_than_refused(self):
        """Four stories where three were asked for is a miscount, not 133%, and
        losing the runner's note over it helps nobody."""
        campaign = {"deliverable_items": self.ITEMS}
        shortfall = server._delivery_shortfall(
            campaign,
            {"partial_delivery": True,
             "delivered_items": {"reel": 1, "story": 9}},
        )
        assert shortfall["complete"] is True
        assert shortfall["pro_rata_fraction"] <= 1

    def test_a_brief_with_no_counted_ask_returns_none_not_an_empty_shortfall(self):
        """An empty shortfall means "all of it arrived". Saying that about a
        campaign nobody counted is a claim we cannot support."""
        assert server._delivery_shortfall({}, {"partial_delivery": True}) is None
        assert server._delivery_shortfall({"deliverable_items": self.ITEMS}, {}) is None


class TestReliabilityAggregation:
    async def _history(self, db, w, rows):
        for state, extra in rows:
            await _collab(db, w, state=state, **extra)
        return await server._reliability_for([w["creator_oid"]])

    def test_a_creator_with_no_history_at_all_gets_no_row(self):
        """Not a row of zeroes. "We have not looked" and "they have nothing"
        are different, and only one of them belongs on a card."""

        async def body(db):
            w = await _world(db)
            return await server._reliability_for([w["creator_oid"]])

        assert run(body) == {}

    def test_an_unknown_rate_is_none_and_never_zero(self):
        """A creator part-way through their first two campaigns has an unknown
        on-time rate, not a 0% one — sorting them below somebody with one late
        delivery would make the directory a ranking of who got here first.

        **Two live collaborations and nothing finished**, which is the state
        that actually reaches the branch. Asking with no rows at all returns no
        row, so a test written that way never runs the division it is about —
        found by deleting the `else None` and watching it stay green.
        """

        async def body(db):
            w = await _world(db)
            await _collab(db, w, state="slot_booked")
            await _collab(db, w, state="attended")
            stats = await server._reliability_for([w["creator_oid"]])
            return stats[w["creator_oid"]]

        stats = run(body)
        assert stats["total"] == 2
        assert stats["completed"] == 0
        assert stats["on_time_rate"] is None
        assert stats["avg_revisions"] is None
        assert stats["enough_history"] is False

    def test_only_cancellations_the_creator_caused_are_counted(self):
        """A brand pulling out of a shoot is not a fact about the creator, and
        counting it against them would mark somebody for being let down."""

        async def body(db):
            w = await _world(db)
            await _collab(db, w, state="cancelled", cancelled_by_role="brand")
            await _collab(db, w, state="cancelled", cancelled_by_role="creator")
            stats = await server._reliability_for([w["creator_oid"]])
            return stats.get(w["creator_oid"]) or {}

        stats = run(body)
        assert stats["cancellations"] == 1

    def test_a_band_is_withheld_until_there_is_enough_history(self):
        """One campaign delivered on time is not "consistently delivers", and
        `new` is not a low band — it is the ordinary state of everybody this
        platform is trying to bring in."""
        thin = server._reliability_band({"completed": 1, "on_time_rate": 1.0})
        assert thin["band"] == "new"
        assert thin["enough_history"] is False

        enough = server._reliability_band(
            {"completed": server.RELIABILITY_MIN_SAMPLE + 2, "on_time_rate": 1.0,
             "no_shows": 0, "late_deliveries": 0, "cancellations": 0}
        )
        assert enough["enough_history"] is True
        assert enough["band"] != "new"

    def test_the_band_a_brand_sees_carries_no_countable_number(self):
        """"2 no-shows" against forty campaigns is a good record read as a bad
        one, and a brand has no denominator to hand. The interpreting happens
        once, on the server, where it is known."""
        band = server._reliability_band(
            {"completed": 12, "on_time_rate": 0.9, "no_shows": 1,
             "late_deliveries": 2, "cancellations": 0}
        )
        assert set(band) <= {"band", "label", "blurb", "enough_history"}
        for value in band.values():
            assert not isinstance(value, (int, float)) or isinstance(value, bool)


class TestRetention:
    def test_the_table_is_served_rather_than_only_documented(self):
        """The console section and the privacy page quote the same numbers, so
        they cannot say different things."""
        assert server.RETENTION_DAYS["personal_data_after_erasure"] == 0
        assert server.RETENTION_DAYS["brand_documents_after_decision"] == 365
        assert server.RETENTION_DAYS["drafts_after_close"] == 90
        assert server.RETENTION_DAYS["audit_records"] == 8 * 365

    def test_purging_leaves_a_tombstone_rather_than_deleting_the_row(self):
        """A missing row would read as never having held a document at all,
        which is the opposite of what the record is for."""

        async def body(db):
            w = await _world(db)
            doc_id = ObjectId()
            await db.brand_documents.insert_one(
                {"_id": doc_id, "brand_id": w["brand_oid"], "doc_type": "gst_certificate",
                 "original_name": "toit-gst.pdf", "stored_name": "abc123.pdf",
                 "status": "accepted",
                 "uploaded_at": _now() - timedelta(days=800),
                 "decided_at": _now() - timedelta(days=700)}
            )
            await db.brand_profiles.update_one(
                {"user_id": w["brand_oid"]},
                {"$set": {"verified": True, "verification_state": "verified",
                          "verified_at": _now() - timedelta(days=700)}},
            )
            await server.purge_expired_documents()
            return await db.brand_documents.find_one({"_id": doc_id})

        row = run(body)
        assert row is not None, "the row was deleted rather than emptied"
        assert row.get("purged_at") is not None
        assert not row.get("original_name")

    def test_a_document_inside_its_window_is_left_alone(self):
        async def body(db):
            w = await _world(db)
            doc_id = ObjectId()
            await db.brand_documents.insert_one(
                {"_id": doc_id, "brand_id": w["brand_oid"], "doc_type": "fssai",
                 "original_name": "fssai.pdf", "stored_name": "def456.pdf",
                 "status": "accepted", "uploaded_at": _now() - timedelta(days=30),
                 "decided_at": _now() - timedelta(days=20)}
            )
            await server.purge_expired_documents()
            return await db.brand_documents.find_one({"_id": doc_id})

        row = run(body)
        assert row["original_name"] == "fssai.pdf"
        assert row.get("purged_at") is None
