"""When a shoot may happen.

A venue's Monday is not its Saturday and its 11am is not its 8pm. Two fields
say so: `restricted_days` (weekdays out) and `shoot_windows` (hours in). Before
them the only way a brand could express "not during service" was in the brief,
where nothing reads it, and a manager found out by putting six creators in a
kitchen at lunch.

Three rules hold this up.

**Every comparison is in IST.** Slots are stored in UTC and a 19:00 Bengaluru
sitting is the next day in UTC, so reading `.weekday()` off the stored value
puts a Friday evening on Saturday — for everybody, always. `SHOOT_TZ` is the
one place that is answered.

**`_shoot_time_refusal` is the only decider**, so creating a slot, moving one,
and a creator naming their own time on a personal table cannot disagree about
what the brand asked for. It returns the sentence rather than raising, because
one caller needs to label rather than refuse.

**A slot that predates a restriction is labelled, not killed.** People may
already hold seats on it, and refusing bookings on a slot we advertised strands
a creator with a dead picker.
"""
import asyncio
import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"
IST = server.SHOOT_TZ


def read(*parts):
    return FRONTEND.joinpath(*parts).read_text()


def ist(y, m, d, hh=12, mm=0):
    """A moment in Bengaluru, stored the way the database stores it."""
    return datetime(y, m, d, hh, mm, tzinfo=IST).astimezone(timezone.utc)


# --- The timezone, which is the whole trap -----------------------------------


def test_the_comparison_happens_in_ist_not_utc():
    """21 Aug 2026 is a Friday. A 22:00 Bengaluru sitting is 16:30 UTC the same
    day — but a 02:00 one is Thursday 20:30 UTC, and reading the weekday off
    the stored value would call it Thursday."""
    late = ist(2026, 8, 21, 2, 0)  # Friday 2am IST
    assert late.astimezone(timezone.utc).weekday() == 3, "the trap is real"

    fridays_out = {"restricted_days": [4]}  # Friday
    assert server._shoot_time_refusal(fridays_out, late) is not None


def test_an_evening_slot_is_not_tomorrow():
    evening = ist(2026, 8, 21, 20, 0)  # Friday 8pm IST = 14:30 UTC Friday
    saturdays_out = {"restricted_days": [5]}

    assert server._shoot_time_refusal(saturdays_out, evening) is None


def test_the_offset_is_five_thirty():
    assert server.SHOOT_TZ.utcoffset(None) == timedelta(hours=5, minutes=30)


# --- Absent means unrestricted ------------------------------------------------


@pytest.mark.parametrize("campaign", [None, {}, {"restricted_days": [], "shoot_windows": []}])
def test_a_campaign_that_said_nothing_restricts_nothing(campaign):
    """Every campaign written before these fields existed. A rule that only
    works after a migration has run refuses every slot on a box that hasn't
    restarted."""
    assert server._shoot_time_refusal(campaign, ist(2026, 8, 17, 3, 0)) is None
    assert server._restricted_days(campaign) == set()
    assert server._shoot_windows(campaign) == []


# --- Restricted days ----------------------------------------------------------


def test_a_restricted_day_is_refused_and_the_open_ones_are_named():
    """A refusal that only says no makes somebody guess. 17 Aug 2026 is a
    Monday."""
    campaign = {"restricted_days": [0, 1]}  # Monday, Tuesday
    refusal = server._shoot_time_refusal(campaign, ist(2026, 8, 17, 13, 0))

    assert refusal and "Monday" in refusal
    assert "Wednesday" in refusal and "Sunday" in refusal


def test_an_open_day_passes():
    campaign = {"restricted_days": [0, 1]}
    assert server._shoot_time_refusal(campaign, ist(2026, 8, 19, 13, 0)) is None


def test_ruling_out_every_day_is_refused():
    """A campaign with no day it can happen on is not a restriction, it is a
    campaign nobody can ever book — found by a creator with a dead picker."""
    with pytest.raises(HTTPException) as exc:
        server._clean_restricted_days([0, 1, 2, 3, 4, 5, 6])
    assert exc.value.status_code == 422


def test_the_days_are_cleaned_rather_than_trusted():
    assert server._clean_restricted_days([3, 3, 1, "2", 9, -1, None]) == [1, 2, 3]
    assert server._clean_restricted_days(None) == []


# --- Shoot windows ------------------------------------------------------------


def test_a_preset_resolves_from_the_server_s_own_table():
    """Whatever the client sends for a preset's times is ignored. A "lunch"
    window running 2am–4am because somebody posted one is a window whose label
    lies."""
    out = server._clean_shoot_windows([{"key": "lunch", "start": "02:00", "end": "04:00"}])

    assert out == [{"key": "lunch", "start": "12:00", "end": "15:00"}]


def test_a_custom_window_keeps_the_times_it_was_given():
    out = server._clean_shoot_windows([{"key": "custom", "start": "06:30", "end": "09:00"}])

    assert out == [{"key": "custom", "start": "06:30", "end": "09:00"}]


@pytest.mark.parametrize(
    "row",
    [
        {"key": "custom", "start": "09:00", "end": "09:00"},   # zero length
        {"key": "custom", "start": "18:00", "end": "09:00"},   # backwards
        {"key": "custom", "start": "25:00", "end": "26:00"},   # not a time
        {"key": "custom", "start": "09:00"},                    # no end
        {"key": "brunch"},                                      # not a preset
        "lunch",                                                # not a dict
    ],
)
def test_an_unusable_window_is_dropped_not_stored_half_formed(row):
    """A window with no end is not a window, and enforcing against one would
    refuse every slot on the campaign."""
    assert server._clean_shoot_windows([row]) == []


def test_windows_are_deduped_and_capped_and_ordered():
    rows = [{"key": "evening"}, {"key": "lunch"}, {"key": "lunch"}]
    out = server._clean_shoot_windows(rows)

    assert [w["key"] for w in out] == ["lunch", "evening"], "sorted by start time"
    assert len(server._clean_shoot_windows([{"key": k} for k in server.SHOOT_WINDOW_PRESETS] * 3)) <= server.MAX_SHOOT_WINDOWS


def test_a_time_inside_a_window_passes_and_one_outside_is_refused():
    campaign = {"shoot_windows": server._clean_shoot_windows([{"key": "evening"}])}

    assert server._shoot_time_refusal(campaign, ist(2026, 8, 19, 19, 0)) is None
    refusal = server._shoot_time_refusal(campaign, ist(2026, 8, 19, 13, 0))
    assert refusal and "Evening" in refusal


def test_a_slot_may_not_straddle_two_windows():
    """A sitting running from lunch into the afternoon is one the venue never
    agreed to, however each half looks on its own."""
    campaign = {
        "shoot_windows": server._clean_shoot_windows([{"key": "lunch"}, {"key": "afternoon"}])
    }
    inside = server._shoot_time_refusal(
        campaign, ist(2026, 8, 19, 12, 30), ist(2026, 8, 19, 14, 30)
    )
    straddling = server._shoot_time_refusal(
        campaign, ist(2026, 8, 19, 14, 30), ist(2026, 8, 19, 16, 0)
    )

    assert inside is None
    assert straddling is not None


def test_a_window_running_past_midnight_matches_nothing():
    campaign = {"shoot_windows": server._clean_shoot_windows([{"key": "late"}])}
    over = server._shoot_time_refusal(
        campaign, ist(2026, 8, 19, 23, 0), ist(2026, 8, 20, 1, 0)
    )
    assert over is not None


def test_the_day_check_outranks_the_window_check():
    """Both wrong should say the more fundamental thing: "we're shut" beats
    "not at that hour", because the second implies another hour would do."""
    campaign = {
        "restricted_days": [0],
        "shoot_windows": server._clean_shoot_windows([{"key": "evening"}]),
    }
    refusal = server._shoot_time_refusal(campaign, ist(2026, 8, 17, 13, 0))

    assert "Monday" in refusal


# --- One decider, three callers ----------------------------------------------


def test_slot_creation_and_editing_share_the_check():
    """A slot dragged onto a Monday the venue is shut is exactly as wrong as
    one created there, so the rule lives in the function they both call."""
    assert "_shoot_time_refusal(" in inspect.getsource(server._validate_slot_times)
    for fn in (server.create_campaign_slot, server.update_slot):
        assert "_validate_slot_times(" in inspect.getsource(fn)


def test_the_creator_s_own_time_is_checked_again_on_book():
    """A personal table is the one place a creator names their own time, so it
    is the one booking path where this has to be re-checked. A fixed slot was
    checked when it was created."""
    assert "_shoot_time_refusal(" in inspect.getsource(server.creator_book_slot)


def test_a_slot_outside_the_preferences_is_labelled_not_refused():
    campaign = {"restricted_days": [0]}
    doc = {
        "_id": ObjectId(),
        "campaign_id": ObjectId(),
        "starts_at": ist(2026, 8, 17, 13, 0),  # a Monday
        "capacity": 4,
        "booked_count": 1,
    }
    assert _serialize(doc, campaign)["outside_preferences"] is True
    assert _serialize(doc, {})["outside_preferences"] is False
    # No campaign in hand — the creator's list, where the flag is not the
    # question — reads as false rather than guessing.
    assert _serialize(doc, None)["outside_preferences"] is False


def _serialize(doc, campaign):
    return server._serialize_slot(doc, campaign)


# --- Round trip through the real handlers ------------------------------------


def _world():
    server.db = AsyncMongoMockClient()["t"]
    now = datetime.now(timezone.utc)
    w = {}

    async def build():
        w["manager_uid"] = ObjectId()
        await server.db.users.insert_one(
            {"_id": w["manager_uid"], "role": "campaign_manager", "name": "Rohan"}
        )
        w["campaign"] = (await server.db.campaigns.insert_one({
            "brand_id": ObjectId(), "title": "Brunch launch", "status": "open",
            "campaign_type": "personal_table", "manager_id": w["manager_uid"],
            "start_date": now - timedelta(days=1), "end_date": now + timedelta(days=60),
            "restricted_days": [0, 1],  # Mondays and Tuesdays out
            "shoot_windows": server._clean_shoot_windows([{"key": "evening"}]),
            "created_at": now,
        })).inserted_id

    asyncio.run(build())
    w["manager"] = {"_id": str(w["manager_uid"]), "role": "campaign_manager"}
    return w


def _make_slot(w, starts, ends):
    return server.create_campaign_slot(
        str(w["campaign"]),
        server.SlotPayload(starts_at=starts, ends_at=ends, capacity=4),
        w["manager"],
    )


def _status(coro):
    try:
        asyncio.run(coro)
        return 200
    except HTTPException as e:
        return e.status_code


def test_a_manager_cannot_open_a_slot_on_a_restricted_day():
    w = _world()
    monday = _status(_make_slot(w, ist(2026, 8, 24, 19, 0), ist(2026, 8, 24, 21, 0)))
    wednesday = _status(_make_slot(w, ist(2026, 8, 26, 19, 0), ist(2026, 8, 26, 21, 0)))

    assert monday == 422
    assert wednesday == 200


def test_a_manager_cannot_open_a_slot_outside_the_hours():
    w = _world()
    lunch = _status(_make_slot(w, ist(2026, 8, 26, 12, 0), ist(2026, 8, 26, 14, 0)))
    assert lunch == 422


def test_the_refusal_names_what_is_allowed():
    w = _world()
    try:
        asyncio.run(_make_slot(w, ist(2026, 8, 24, 19, 0), ist(2026, 8, 24, 21, 0)))
        pytest.fail("should have refused")
    except HTTPException as e:
        assert "Wednesday" in str(e.detail)


def test_the_manager_s_slot_list_carries_the_rules():
    """So the manager reads them rather than discovering them in a 422."""
    w = _world()
    out = asyncio.run(server.list_campaign_slots(str(w["campaign"]), w["manager"]))

    assert out["restricted_days"] == [0, 1]
    assert out["shoot_windows"][0]["key"] == "evening"


# --- What the screens are given ----------------------------------------------


def test_the_rules_ship_on_every_campaign_shape():
    """The creator deciding whether to apply is the person most affected by
    "Saturdays only, evenings"."""
    for fn in (server._serialize_campaign, server._serialize_brand_campaign):
        src = inspect.getsource(fn)
        assert '"restricted_days"' in src and '"shoot_windows"' in src


def test_the_creator_s_slot_list_carries_them_too():
    src = inspect.getsource(server.list_creator_slots)
    assert '"restricted_days"' in src and '"shoot_windows"' in src


# --- The frontend mirror ------------------------------------------------------


def test_the_presets_match_the_server_s():
    """A picker that offers a window the server has never heard of produces a
    422 nobody can act on."""
    src = read("lib", "shootWindows.js")
    for key, (start, end) in server.SHOOT_WINDOW_PRESETS.items():
        assert f'key: "{key}"' in src, f"{key} missing from the frontend"
        assert f'start: "{start}", end: "{end}"' in src, f"{key} has different hours"


def test_the_weekday_convention_matches():
    """JavaScript's getDay() puts Sunday at 0 and Python's weekday() puts
    Monday at 0. One has to win, and it is the one the stored data uses."""
    src = read("lib", "shootWindows.js")
    for i, name in enumerate(server.WEEKDAY_NAMES):
        assert f'value: {i}, label: "{name}"' in src


def test_the_browser_compares_in_ist_too():
    """Or the picker greys out a different set of times than the API refuses."""
    src = read("lib", "shootWindows.js")
    assert "5 * 60 + 30" in src


def test_the_picker_cuts_the_disallowed_times_out():
    """Offering a time and then refusing it is the difference between a rule
    and a trap."""
    src = read("components", "creator", "SlotPicker.jsx")
    assert "shootTimeRefusal" in src
    assert "dayIndex" in src


def test_the_note_renders_nothing_when_nothing_was_set():
    """An empty box headed "When it shoots" reads as a fact about the venue
    rather than a question nobody answered."""
    src = read("components", "campaign", "ShootWindowNote.jsx")
    assert "hasSchedulingPreferences" in src
    assert "return null" in src


def test_the_note_says_the_positive():
    """"Not Mondays, not Tuesdays" is a list to invert in your head."""
    src = read("components", "campaign", "ShootWindowNote.jsx")
    assert "openDayLabels" in src


def test_the_form_sends_presets_by_key_alone():
    """The server owns what "lunch" means; sending times back would let a
    stale form redefine it."""
    src = read("pages", "PostCampaign.jsx")
    assert '{ key: w.key }' in src
    assert "setRestrictedDays(data.restricted_days || [])" in src, "not re-seeded on edit"


def test_the_control_refuses_to_close_every_day():
    src = read("components", "campaign", "ShootPreferences.jsx")
    assert "next.size < 6" in src
