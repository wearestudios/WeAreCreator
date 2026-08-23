"""Which scheduling fields each campaign type actually has.

Every campaign used to carry every scheduling field and the form asked for all
of them whatever you picked. So a launch — one evening, everybody arrives at
once — was asked which weekdays don't work and which hours of the day are
possible, questions with no answer for a thing that happens once. Brands
answered anyway, because a form that asks looks like a form that needs an
answer, and the result was a restriction nobody meant sitting on a brief that
could never be booked against it.

`_SCHEDULING_BY_TYPE` is the one table, read by the create payload, the edit
path and the admin path. These tests drive all three, because the rule is only
worth anything if the door that skips it does not exist — and the edit path
*was* that door: `_refuse_dates_foreign_to_type` checked the two date fields
and let restricted days through on any type.
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
        db = AsyncMongoMockClient()["scheduling"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return LOOP.run_until_complete(go())


DAY = (datetime.now(timezone.utc) + timedelta(days=14)).replace(
    hour=13, minute=0, second=0, microsecond=0
)


def _body(**over):
    """The fields every campaign needs, whatever its type."""
    body = {
        "title": "Two reels for the spring range",
        "brief": "Shoot in store, natural light, no flash.",
        "deliverable_items": [{"type": "reel", "quantity": 2}],
        "budget_per_creator": 9000,
        "category": "fashion",
        "area": "Indiranagar",
        "creators_needed": 2,
    }
    body.update(over)
    return body


def _launch(**over):
    return _body(campaign_type="launch", event_date=DAY, **over)


def _group(**over):
    over.setdefault(
        "sittings", [{"starts_at": DAY.replace(hour=12), "capacity": 4}]
    )
    return _body(campaign_type="group_event", event_date=DAY, **over)


def _table(**over):
    return _body(
        campaign_type="personal_table",
        start_date=DAY,
        end_date=DAY + timedelta(days=7),
        **over,
    )


# ---------------------------------------------------------------------------
# The table itself
# ---------------------------------------------------------------------------


class TestTheTableIsTheOnlyDefinition:
    def test_every_type_declares_a_shape(self):
        """A fourth type added later has to say what it carries rather than
        silently inheriting everything, which is how this went wrong the first
        time."""
        assert set(server._SCHEDULING_BY_TYPE) == set(server.CampaignType.__args__)

    def test_every_governed_field_has_a_label(self):
        """The refusal names the thing somebody ticked, not the field name.
        "shoot_windows is not allowed" is a stack trace; "the hours that work"
        is the control on the screen."""
        for field in server._SCHEDULING_FIELDS:
            assert field in server._SCHEDULING_LABELS, field

    def test_required_is_a_subset_of_allowed(self):
        """A shape that requires what it does not allow can never be
        satisfied — a campaign type nobody can post."""
        for ctype, shape in server._SCHEDULING_BY_TYPE.items():
            assert set(shape["required"]) <= set(shape["allowed"]), ctype

    def test_only_the_personal_table_gets_days_and_hours(self):
        """The rule this whole file exists for. Those two questions are only
        answerable when the *creator* picks the time."""
        for ctype, shape in server._SCHEDULING_BY_TYPE.items():
            has = {"restricted_days", "shoot_windows"} & set(shape["allowed"])
            assert has == (
                {"restricted_days", "shoot_windows"}
                if ctype == "personal_table"
                else set()
            ), ctype

    def test_an_unknown_type_is_not_checked_rather_than_refused(self):
        """Campaigns predate types. A shape check that refused them would turn
        every historical brief into an un-editable record on deploy — the same
        absent-reads-safe rule `_compensation_type` and `_execution_owner`
        hold."""
        assert server._scheduling_refusal(None, {"restricted_days"}) is None
        assert server._scheduling_refusal("", {"shoot_windows"}) is None


# ---------------------------------------------------------------------------
# Creating
# ---------------------------------------------------------------------------


class TestALaunchIsOneMoment:
    def test_it_takes_a_day_and_optionally_how_long_it_runs(self):
        payload = server.PostCampaignPayload(**_launch(duration_minutes=120))
        assert payload.event_date is not None
        assert payload.duration_minutes == 120

    def test_the_duration_is_optional(self):
        assert server.PostCampaignPayload(**_launch()).duration_minutes is None

    @pytest.mark.parametrize(
        "field,value",
        [
            ("restricted_days", [0, 1]),
            ("shoot_windows", [{"key": "lunch"}]),
            ("sittings", [{"starts_at": DAY, "capacity": 2}]),
        ],
    )
    def test_it_refuses_the_fields_it_has_no_use_for(self, field, value):
        """The bug, in one test. A launch asked which weekdays don't work, and
        a brand that answered got a restriction on a brief that has exactly one
        day in it."""
        with pytest.raises(Exception) as err:
            server.PostCampaignPayload(**_launch(**{field: value}))
        assert server._SCHEDULING_LABELS[field] in str(err.value)

    def test_an_empty_list_is_not_a_field_that_was_supplied(self):
        """A form that renders no control still sends `[]` on some paths.
        Refusing that would be refusing a launch for a field nobody filled
        in."""
        payload = server.PostCampaignPayload(
            **_launch(restricted_days=[], shoot_windows=[])
        )
        assert payload.campaign_type == "launch"


class TestAGroupEventIsATimetable:
    def test_it_needs_at_least_one_sitting(self):
        with pytest.raises(Exception) as err:
            server.PostCampaignPayload(**_body(
                campaign_type="group_event", event_date=DAY
            ))
        assert "sittings" in str(err.value).lower() or "sitting" in str(err.value)

    def test_several_sittings_are_kept_in_order_given(self):
        payload = server.PostCampaignPayload(
            **_group(
                sittings=[
                    {"starts_at": DAY.replace(hour=12), "capacity": 4},
                    {"starts_at": DAY.replace(hour=15), "capacity": 6},
                ]
            )
        )
        assert [s.capacity for s in payload.sittings] == [4, 6]

    def test_a_sitting_on_another_day_is_refused(self):
        """A creator reads one date on the brief and turns up to it. A sitting
        on a different day is a person at a locked door."""
        with pytest.raises(Exception) as err:
            server.PostCampaignPayload(
                **_group(
                    sittings=[{"starts_at": DAY + timedelta(days=3), "capacity": 4}]
                )
            )
        assert "own date" in str(err.value)

    def test_a_sitting_that_ends_before_it_starts_is_refused(self):
        with pytest.raises(Exception):
            server.PostCampaignPayload(
                **_group(
                    sittings=[
                        {
                            "starts_at": DAY.replace(hour=15),
                            "ends_at": DAY.replace(hour=14),
                            "capacity": 4,
                        }
                    ]
                )
            )

    @pytest.mark.parametrize(
        "field,value",
        [
            ("restricted_days", [0]),
            ("shoot_windows", [{"key": "lunch"}]),
            ("duration_minutes", 90),
        ],
    )
    def test_it_refuses_the_fields_it_has_no_use_for(self, field, value):
        with pytest.raises(Exception) as err:
            server.PostCampaignPayload(**_group(**{field: value}))
        assert server._SCHEDULING_LABELS[field] in str(err.value)


class TestAPersonalTableIsTheOnlyOneWithPreferences:
    def test_it_takes_days_and_windows(self):
        payload = server.PostCampaignPayload(
            **_table(restricted_days=[0, 1], shoot_windows=[{"key": "lunch"}])
        )
        assert payload.restricted_days == [0, 1]
        assert len(payload.shoot_windows) == 1

    def test_both_stay_optional(self):
        """Most briefs have no restriction and a form that insists gets a
        made-up answer."""
        payload = server.PostCampaignPayload(**_table())
        assert payload.restricted_days is None
        assert payload.shoot_windows is None

    @pytest.mark.parametrize(
        "field,value",
        [("duration_minutes", 60), ("sittings", [{"starts_at": DAY, "capacity": 2}])],
    )
    def test_it_refuses_the_event_only_fields(self, field, value):
        with pytest.raises(Exception) as err:
            server.PostCampaignPayload(**_table(**{field: value}))
        assert server._SCHEDULING_LABELS[field] in str(err.value)

    def test_the_window_still_has_to_run_forwards(self):
        with pytest.raises(Exception):
            server.PostCampaignPayload(
                **_body(
                    campaign_type="personal_table",
                    start_date=DAY,
                    end_date=DAY - timedelta(days=2),
                )
            )


# ---------------------------------------------------------------------------
# Editing — the door that skipped the rule
# ---------------------------------------------------------------------------


class TestTheEditPathHoldsTheSameRule:
    """`_refuse_dates_foreign_to_type` checked `event_date` against
    `start_date`/`end_date` and let everything else through. So a launch could
    be *given* restricted weekdays by a PATCH even once the create route
    refused them — which is the shape of every "validated on create only" bug.
    """

    @pytest.mark.parametrize("ctype", ["launch", "group_event"])
    @pytest.mark.parametrize(
        "field,value", [("restricted_days", [0, 1]), ("shoot_windows", [{"key": "lunch"}])]
    )
    def test_an_event_campaign_cannot_be_given_days_or_hours_by_an_edit(
        self, ctype, field, value
    ):
        with pytest.raises(HTTPException) as err:
            server._refuse_dates_foreign_to_type(
                {"campaign_type": ctype}, {field: value}
            )
        assert err.value.status_code == 422
        assert server._SCHEDULING_LABELS[field] in str(err.value.detail)

    def test_a_personal_table_still_takes_them(self):
        server._refuse_dates_foreign_to_type(
            {"campaign_type": "personal_table"},
            {"restricted_days": [0], "shoot_windows": [{"key": "lunch"}]},
        )

    def test_clearing_a_restriction_is_allowed_on_every_type(self):
        """An empty list is "no restriction", which is a legitimate thing to
        save on any type — including one that never had one."""
        for ctype in server._SCHEDULING_BY_TYPE:
            server._refuse_dates_foreign_to_type(
                {"campaign_type": ctype}, {"restricted_days": [], "shoot_windows": []}
            )

    def test_a_campaign_predating_types_is_left_alone(self):
        server._refuse_dates_foreign_to_type({}, {"restricted_days": [0, 1]})

    def test_the_existing_date_rules_still_hold(self):
        """Extending the guard must not lose what it already did."""
        with pytest.raises(HTTPException):
            server._refuse_dates_foreign_to_type(
                {"campaign_type": "launch"}, {"start_date": DAY}
            )
        with pytest.raises(HTTPException):
            server._refuse_dates_foreign_to_type(
                {"campaign_type": "personal_table"}, {"event_date": DAY}
            )


# ---------------------------------------------------------------------------
# The sittings become real slots
# ---------------------------------------------------------------------------


async def _brand(db):
    brand_oid = ObjectId()
    await db.users.insert_one(
        {"_id": brand_oid, "role": "brand_manager", "name": "Ninth Street",
         "brand_id": brand_oid, "phone": "+919900000001"}
    )
    await db.brand_profiles.insert_one(
        {"user_id": brand_oid, "business_name": "Ninth Street", "verified": True,
         "verified_at": datetime.now(timezone.utc)}
    )
    return {"_id": str(brand_oid), "role": "brand_manager", "name": "Ninth Street",
            "brand_id": str(brand_oid)}


class TestSittingsBecomeBookableSlots:
    def test_posting_a_group_event_writes_its_timetable(self):
        """Into `campaign_slots`, not a second collection: a sitting has a
        time, a capacity and people booking into it, which is a slot."""

        async def body(db):
            user = await _brand(db)
            result = await server.create_brand_campaign(
                server.PostCampaignPayload(
                    **_group(
                        sittings=[
                            {"starts_at": DAY.replace(hour=12), "capacity": 4},
                            {"starts_at": DAY.replace(hour=15), "capacity": 6},
                        ]
                    )
                ),
                user,
            )
            slots = await db.campaign_slots.find(
                {"campaign_id": ObjectId(result["id"])}
            ).sort("starts_at", 1).to_list(length=10)
            return slots

        slots = run(body)
        assert [s["capacity"] for s in slots] == [4, 6]
        assert all(s["booked_count"] == 0 for s in slots)

    def test_a_launch_writes_none(self):
        async def body(db):
            user = await _brand(db)
            result = await server.create_brand_campaign(
                server.PostCampaignPayload(**_launch(duration_minutes=90)), user
            )
            return await db.campaign_slots.count_documents(
                {"campaign_id": ObjectId(result["id"])}
            )

        assert run(body) == 0

    def test_rewriting_the_timetable_keeps_a_sitting_somebody_has_booked(self):
        """**The rule worth having.** A brand editing a timetable is editing a
        plan; a booked sitting is an arrangement with a person, and a form save
        is not the place to break one. A kept row is a conversation with the
        manager; a silently cancelled booking is a creator turning up to
        nothing."""

        async def body(db):
            campaign_oid = ObjectId()
            noon, three = DAY.replace(hour=12), DAY.replace(hour=15)
            await db.campaign_slots.insert_many(
                [
                    {"campaign_id": campaign_oid, "starts_at": noon, "ends_at": None,
                     "capacity": 4, "booked_count": 2},
                    {"campaign_id": campaign_oid, "starts_at": three, "ends_at": None,
                     "capacity": 6, "booked_count": 0},
                ]
            )
            # The brand rewrites the day to a single 5pm sitting.
            await server._sync_event_sittings(
                campaign_oid,
                [server.EventSitting(starts_at=DAY.replace(hour=17), capacity=5)],
            )
            return await db.campaign_slots.find(
                {"campaign_id": campaign_oid}
            ).sort("starts_at", 1).to_list(length=10)

        slots = run(body)
        hours = sorted(server._as_utc(s["starts_at"]).hour for s in slots)
        # Noon survives because two creators hold seats in it; 3pm goes.
        assert hours == [12, 17]

    def test_a_sitting_at_a_time_somebody_already_holds_is_not_duplicated(self):
        """Re-saving an unchanged timetable must not double the places."""

        async def body(db):
            campaign_oid = ObjectId()
            noon = DAY.replace(hour=12)
            await db.campaign_slots.insert_one(
                {"campaign_id": campaign_oid, "starts_at": noon, "ends_at": None,
                 "capacity": 4, "booked_count": 1}
            )
            await server._sync_event_sittings(
                campaign_oid, [server.EventSitting(starts_at=noon, capacity=4)]
            )
            return await db.campaign_slots.count_documents(
                {"campaign_id": campaign_oid}
            )

        assert run(body) == 1
