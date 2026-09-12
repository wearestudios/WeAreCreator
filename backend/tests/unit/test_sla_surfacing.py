"""SLA breaches, driven to the surfaces an operator actually reads.

There is a lot of clock coverage already — `test_the_clock.py` holds the stamp,
the ageing arithmetic, the targets and their overrides, and
`test_chasing_and_delivery.py` holds the reminders and the escalation routing.
What neither of them does is **drive the two screens the whole mechanism exists
to reach**.

The health panel's overdue check and the four review queues were asserted by
`inspect.getsource` — that `admin_health` calls `_overdue_check`, that
`_overdue_check` mentions the four ageing readers, that the queue handlers
mention `_brand_review_ageing`. Every one of those strings survives the reader
being handed the wrong document, or the target being looked up under a key the
table does not have, or `overdue` never coming back true because the row was
aged from a field nothing writes. That is the failure this file is for: **the
guard is present, and the record is still invisible.**

So these seed a record that is genuinely past its target, call the real
handler, and read the response back. Every test has a not-overdue control
beside it, because a test that cannot distinguish "the check works" from "the
check returns nothing ever" is a test that passes on a deleted function.
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
    """One loop per call, kept in a module global.

    `asyncio.get_event_loop` fails inside a pytest-xdist worker thread, and
    `asyncio.run` closes the loop mongomock's cursors were built on.
    """
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()

    async def go():
        db = AsyncMongoMockClient()["sla_surfacing"]
        original = server.db
        server.db = db
        # **`sla_targets()` caches for 30 seconds in a module global**, so a
        # test that stores an override and immediately calls a handler reads
        # whatever the *previous* test left behind — across a fresh mock
        # database, which makes it look like the override was dropped on the
        # way to the row. Cleared here rather than in the one test that stores
        # an override, because the next person to write one would meet the
        # same thing and have no reason to suspect a cache.
        server._SLA_CACHE["at"] = None
        server._SLA_CACHE["value"] = None
        try:
            return await body(db)
        finally:
            server.db = original
            server._SLA_CACHE["at"] = None
            server._SLA_CACHE["value"] = None

    return LOOP.run_until_complete(go())


def _now():
    return datetime.now(timezone.utc)


def _hours_ago(h):
    return _now() - timedelta(hours=h)


ADMIN = {"_id": str(ObjectId()), "role": "admin"}


# How far past each target counts as "well over" for these fixtures. Derived
# from the table rather than written down, so retuning a target moves the
# fixture with it instead of turning a test amber.
def _well_over(key):
    return server.SLA_DEFAULT_HOURS[key] * 2 + 1


def _just_started(key):
    """Inside the target by a wide margin — the control every case needs."""
    return 1


async def _campaign(db, *, status="open", title="Toit tasting", brand_oid=None):
    oid = ObjectId()
    await db.campaigns.insert_one(
        {
            "_id": oid,
            "brand_id": brand_oid or ObjectId(),
            "title": title,
            "status": status,
            "execution_owner": "brand",
        }
    )
    return oid


async def _collab(db, campaign_oid, *, state, hours):
    """A collaboration that has been sitting in `state` for `hours`.

    Written the way the app writes one: `state_since` is the clock,
    `updated_at` is not — a row whose age came off `updated_at` would read as
    touched five minutes ago the moment anybody added a note.
    """
    oid = ObjectId()
    await db.collaborations.insert_one(
        {
            "_id": oid,
            "campaign_id": campaign_oid,
            "creator_id": ObjectId(),
            "state": state,
            "state_since": _hours_ago(hours),
            "updated_at": _now(),
        }
    )
    return oid


# --- The health panel -------------------------------------------------------


class TestTheHealthPanelShowsWhatIsOverdue:
    def _health(self, body):
        async def go(db):
            await body(db)
            return await server.admin_health(user=ADMIN)

        out = run(go)
        return {c["key"]: c for c in out["checks"]}

    def test_an_overdue_collaboration_reaches_the_panel(self):
        """**The end-to-end claim**, and the one that was only ever asserted by
        reading `admin_health` for the string `_overdue_check`."""
        checks = self._health(
            lambda db: self._seed_collab(db, hours=_well_over("application_response"))
        )
        assert "overdue" in checks, sorted(checks)
        rows = checks["overdue"]["items"]
        assert len(rows) == 1, rows
        assert rows[0]["sla_key"] == "application_response"
        assert rows[0]["overdue_hours"] > 0
        # A count tells you there is a problem and then makes you go and find
        # it. Every row carries the way there.
        assert rows[0]["href"].startswith("/admin/collaborations/")

    def test_a_collaboration_inside_its_target_does_not(self):
        """The control. Without it, a check that returned nothing at all would
        pass the test above by never being reached."""
        checks = self._health(
            lambda db: self._seed_collab(db, hours=_just_started("application_response"))
        )
        assert not (checks.get("overdue") or {}).get("items")

    async def _seed_collab(self, db, *, hours):
        campaign_oid = await _campaign(db)
        await _collab(db, campaign_oid, state="applied", hours=hours)

    def test_a_brief_waiting_on_us_reaches_the_panel(self):
        async def body(db):
            await db.campaigns.insert_one(
                {
                    "_id": ObjectId(),
                    "brand_id": ObjectId(),
                    "title": "Spring range",
                    "status": server.CAMPAIGN_REVIEW_STATUS,
                    "submitted_for_review_at": _hours_ago(_well_over("campaign_review")),
                }
            )

        rows = self._health(body)["overdue"]["items"]
        assert [r["sla_key"] for r in rows] == ["campaign_review"]
        assert rows[0]["href"].startswith("/admin/campaigns/")

    def test_a_business_waiting_on_us_reaches_the_panel(self):
        async def body(db):
            oid = ObjectId()
            await db.users.insert_one(
                {"_id": oid, "role": "brand_manager", "brand_id": oid, "name": "Toit"}
            )
            await db.brand_profiles.insert_one(
                {
                    "user_id": oid,
                    "business_name": "Toit",
                    "verified": False,
                    "verification_state": "pending_verification",
                    "submitted_for_verification_at": _hours_ago(
                        _well_over("brand_verification")
                    ),
                }
            )

        rows = self._health(body)["overdue"]["items"]
        assert [r["sla_key"] for r in rows] == ["brand_verification"]

    def test_a_creator_waiting_on_us_reaches_the_panel(self):
        async def body(db):
            oid = ObjectId()
            await db.users.insert_one({"_id": oid, "role": "creator", "name": "Asha"})
            await db.creator_profiles.insert_one(
                {
                    "user_id": oid,
                    "name": "Asha",
                    "verification_status": "pending",
                    "submitted_for_review_at": _hours_ago(
                        _well_over("creator_verification")
                    ),
                }
            )

        rows = self._health(body)["overdue"]["items"]
        assert [r["sla_key"] for r in rows] == ["creator_verification"]

    def test_a_creator_who_never_submitted_is_not_in_a_queue_at_all(self):
        """A profile stub is created at signup, so ageing off the *state*
        would report a fortnight of somebody's own half-finished form as our
        delay — the kind of wrong that makes an operator stop believing the
        panel."""

        async def body(db):
            oid = ObjectId()
            await db.users.insert_one({"_id": oid, "role": "creator", "name": "Bo"})
            await db.creator_profiles.insert_one(
                {
                    "user_id": oid,
                    "name": "Bo",
                    "verification_status": "pending",
                    # Signed up a year ago and never finished.
                    "created_at": _hours_ago(24 * 365),
                    "updated_at": _hours_ago(24 * 365),
                }
            )

        assert not (self._health(body).get("overdue") or {}).get("items")

    def test_the_reader_refuses_them_too_and_not_only_the_query(self):
        """**The rule is enforced twice and the test above only reaches one of
        them.** `_AWAITING_REVIEW_QUERY` keeps an unsubmitted profile out of
        the panel's query, so `_creator_review_ageing` is never called for that
        row — which means breaking the reader leaves the panel test green while
        every *other* caller starts ageing somebody's own half-finished form as
        our delay. Found by break-testing, not by review.
        """
        never_submitted = {
            "user_id": ObjectId(),
            "name": "Bo",
            "verification_status": "pending",
            "created_at": _hours_ago(24 * 365),
            "updated_at": _hours_ago(24 * 365),
        }
        assert server._creator_review_ageing(never_submitted, server.SLA_DEFAULT_HOURS) is None

        # And the control: the same profile, once they actually submit.
        submitted = {
            **never_submitted,
            "submitted_for_review_at": _hours_ago(_well_over("creator_verification")),
        }
        block = server._creator_review_ageing(submitted, server.SLA_DEFAULT_HOURS)
        assert block and block["overdue"] is True

    def test_a_verified_creator_is_in_no_queue_at_all(self):
        """Drawing a clock on somebody who is not waiting invents a queue they
        are not in."""
        assert (
            server._creator_review_ageing(
                {"user_id": ObjectId(), "verification_status": "verified"},
                server.SLA_DEFAULT_HOURS,
            )
            is None
        )

    def test_every_kind_appears_together_worst_first(self):
        """**How far over, not how old.** A creator verification two days past
        a 48-hour target is a worse failure than a payment two days past a
        seven-day one, and sorting by age puts them the other way round.

        Driven, where the existing version of this reads `_overdue_check` for
        the string `"presorted": True` — which survives the health panel
        re-sorting the rows underneath it.

        **Both rows are deliberately `critical`**, which is what makes this
        able to fail. The health panel re-sorts every other check by severity
        and then oldest-first; with one row critical and one merely warning,
        that generic sort produces the *same* order as worst-first and the
        test passes whether the check is presorted or not. Two critical rows
        send the generic sort to its age tiebreak, which is the opposite
        order — so the assertion now distinguishes them. Found by breaking
        `presorted` and watching an earlier version stay green.
        """

        async def body(db):
            campaign_oid = await _campaign(db)
            # Twice its seven-day target — critical, and by far the oldest row
            # here, but only 2.0x over.
            await _collab(
                db,
                campaign_oid,
                state="in_payment",
                hours=server.SLA_DEFAULT_HOURS["payment"] * 2 + 6,
            )
            # A third of the age, and more than four times its one-day target.
            await db.campaigns.insert_one(
                {
                    "_id": ObjectId(),
                    "brand_id": ObjectId(),
                    "title": "Late brief",
                    "status": server.CAMPAIGN_REVIEW_STATUS,
                    "submitted_for_review_at": _hours_ago(
                        server.SLA_DEFAULT_HOURS["campaign_review"] * 5
                    ),
                }
            )

        rows = self._health(body)["overdue"]["items"]
        # Both critical, so severity cannot be what ordered them.
        assert {r["severity"] for r in rows} == {"critical"}
        assert [r["sla_key"] for r in rows] == ["campaign_review", "payment"]

        # And the fixture really does distinguish all three candidate keys,
        # or the assertion above would be passing on an accident:
        fractions = [r["hours"] / r["sla_hours"] for r in rows]
        assert fractions == sorted(fractions, reverse=True)
        # ...older second (so it is not oldest-first),
        assert rows[0]["hours"] < rows[1]["hours"]
        # ...and fewer absolute hours over (so it is not absolute-hours-over,
        # which is what this actually did until a fixture separated them).
        assert rows[0]["overdue_hours"] < rows[1]["overdue_hours"]

    def test_the_row_says_who_is_being_waited_on(self):
        """Half of these are our delay and half are somebody else's, and the
        action is different: one is "do it", the other is "ring them"."""
        checks = self._health(
            lambda db: self._seed_collab(db, hours=_well_over("application_response"))
        )
        assert checks["overdue"]["items"][0]["waiting_on"]

    def test_the_severity_rises_with_how_far_over_it_is(self):
        """Four tones rather than two: "fine" and "on fire" leaves nothing to
        say about the record that is *about* to become a problem, which is the
        only one somebody can still act on."""

        async def body(db):
            campaign_oid = await _campaign(db)
            await _collab(
                db,
                campaign_oid,
                state="applied",
                # Past the target but not past double it.
                hours=server.SLA_DEFAULT_HOURS["application_response"] + 2,
            )

        warning = self._health(body)["overdue"]["items"][0]["severity"]

        async def worse(db):
            campaign_oid = await _campaign(db)
            await _collab(
                db,
                campaign_oid,
                state="applied",
                hours=_well_over("application_response"),
            )

        critical = self._health(worse)["overdue"]["items"][0]["severity"]
        assert warning == "warning"
        assert critical == "critical"

    def test_a_state_that_waits_on_nobody_has_no_clock(self):
        """`slot_booked` waits on a date in the future rather than on a person,
        and the terminal states are finished. Absent means no clock, never
        zero — drawing one would invent a queue nobody is in."""

        async def body(db):
            campaign_oid = await _campaign(db)
            for state in ("slot_booked", "closed", "declined"):
                await _collab(db, campaign_oid, state=state, hours=24 * 400)

        assert not (self._health(body).get("overdue") or {}).get("items")


# --- The review queues ------------------------------------------------------


class TestTheQueuesCarryTheVerdict:
    """The four endpoints the action queue is built from.

    Each attaches an `ageing` block, and each was asserted by reading the
    handler for the reader's name — which survives the reader being passed the
    wrong document or the targets never arriving.
    """

    @staticmethod
    def _one_row(payload):
        """The console's collaboration list is grouped by state, not flat."""
        rows = [r for group in payload["by_state"].values() for r in group]
        assert len(rows) == 1, rows
        return rows[0]

    def test_an_overdue_application_arrives_with_its_verdict(self):
        async def body(db):
            campaign_oid = await _campaign(db)
            await _collab(
                db,
                campaign_oid,
                state="applied",
                hours=_well_over("application_response"),
            )
            return await server.list_all_collaborations(user=ADMIN)

        ageing = self._one_row(run(body))["ageing"]
        assert ageing["overdue"] is True
        assert ageing["sla_key"] == "application_response"
        assert ageing["sla_hours"] == server.SLA_DEFAULT_HOURS["application_response"]

    def test_a_fresh_application_arrives_calm(self):
        async def body(db):
            campaign_oid = await _campaign(db)
            await _collab(db, campaign_oid, state="applied", hours=1)
            return await server.list_all_collaborations(user=ADMIN)

        ageing = self._one_row(run(body))["ageing"]
        assert ageing["overdue"] is False
        assert ageing["tone"] == "calm"

    def test_an_overdue_brief_arrives_with_its_verdict(self):
        async def body(db):
            await db.campaigns.insert_one(
                {
                    "_id": ObjectId(),
                    "brand_id": ObjectId(),
                    "title": "Spring range",
                    "status": server.CAMPAIGN_REVIEW_STATUS,
                    "submitted_for_review_at": _hours_ago(_well_over("campaign_review")),
                }
            )
            return await server.list_campaigns_for_review(user=ADMIN)

        rows = run(body)
        assert rows[0]["ageing"]["overdue"] is True
        assert rows[0]["ageing"]["sla_key"] == "campaign_review"

    def test_an_overdue_business_arrives_with_its_verdict(self):
        async def body(db):
            oid = ObjectId()
            await db.users.insert_one(
                {"_id": oid, "role": "brand_manager", "brand_id": oid, "name": "Toit"}
            )
            await db.brand_profiles.insert_one(
                {
                    "user_id": oid,
                    "business_name": "Toit",
                    "verified": False,
                    "verification_state": "pending_verification",
                    "submitted_for_verification_at": _hours_ago(
                        _well_over("brand_verification")
                    ),
                }
            )
            return await server.list_pending_brands(user=ADMIN)

        rows = run(body)
        assert rows[0]["ageing"]["overdue"] is True
        assert rows[0]["ageing"]["sla_key"] == "brand_verification"

    def test_an_overdue_creator_arrives_with_its_verdict(self):
        async def body(db):
            oid = ObjectId()
            await db.users.insert_one({"_id": oid, "role": "creator", "name": "Asha"})
            await db.creator_profiles.insert_one(
                {
                    "user_id": oid,
                    "name": "Asha",
                    "verification_status": "pending",
                    "submitted_for_review_at": _hours_ago(
                        _well_over("creator_verification")
                    ),
                }
            )
            return await server.list_pending_creators(user=ADMIN)

        rows = run(body)
        assert rows[0]["ageing"]["overdue"] is True
        assert rows[0]["ageing"]["sla_key"] == "creator_verification"

    def test_a_stored_override_reaches_the_queue_and_not_just_the_table(self):
        """An operating target that needs a deploy to change is one that never
        changes — so the point of storing it is that the *screens* move. A test
        that only checks `sla_targets()` would pass with the override read once
        and then dropped on the way to the row."""

        async def body(db):
            await db.platform_settings.update_one(
                {"_id": "sla_targets"},
                {"$set": {"targets": {"application_response": 1}}},
                upsert=True,
            )
            campaign_oid = await _campaign(db)
            # Well inside the 72-hour default, well past a one-hour override.
            await _collab(db, campaign_oid, state="applied", hours=6)
            return await server.list_all_collaborations(user=ADMIN)

        ageing = self._one_row(run(body))["ageing"]
        assert ageing["sla_hours"] == 1
        assert ageing["overdue"] is True


# --- The creator is not held to our operating targets -----------------------


class TestTheCreatorSeesTheAgeAndNotTheVerdict:
    def test_the_same_overdue_collaboration_reads_differently_to_each_side(self):
        """An SLA is the standard this operation holds itself to internally; it
        is not a promise made to the creator, and publishing "the brand is 4
        days over target" on their row would turn one into the other. Where the
        wait is the brand's, the target is a standard they are being held to
        and being told is the entire point.

        **Asserted as the contrast on one row**, which is the only form of this
        that can fail usefully: the creator's block is not empty — it carries
        `overdue: False` and `tone: "calm"` as the neutral defaults of a block
        built with no targets — so checking it in isolation would pass just as
        well on a row that genuinely was not overdue. The brand's half is what
        proves the row *is* over, and the creator's half is what proves they
        are not being shown it.
        """

        async def body(db):
            campaign_oid = await _campaign(db)
            collab_oid = await _collab(
                db,
                campaign_oid,
                state="applied",
                hours=_well_over("application_response"),
            )
            collab = await db.collaborations.find_one({"_id": collab_oid})
            campaign = await db.campaigns.find_one({"_id": campaign_oid})
            creator_row = server._serialize_collab_row(collab, campaign, "Toit")
            brand_row = server._serialize_applicant(
                collab,
                {"_id": collab["creator_id"], "name": "Asha"},
                {},
                None,
                campaign=campaign,
                targets=await server.sla_targets(),
            )
            return creator_row["ageing"], brand_row["ageing"]

        creator, brand = run(body)

        # The brand is told it is over, because the wait is theirs.
        assert brand["overdue"] is True
        assert brand["sla_hours"] == server.SLA_DEFAULT_HOURS["application_response"]
        assert brand["tone"] in ("overdue", "critical")

        # The creator is told how long they have been waiting, and nothing
        # about our internal target — same row, same instant.
        assert creator["hours"] == brand["hours"]
        assert creator["sla_hours"] is None
        assert creator["overdue"] is False
        assert creator["tone"] == "calm"
