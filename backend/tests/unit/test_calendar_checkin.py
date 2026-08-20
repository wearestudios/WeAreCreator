"""The shoot calendar, and checking yourself in.

**The calendar** is one endpoint with three scopes and one payload. A brand
manager sees its own campaigns, a WeAre manager the ones assigned to them, an
admin everything — and all three get the same shape, carrying **no contact
detail for anybody**. The manager who needs a phone number has the roster and
the daysheet, which are behind the staff role for exactly that reason; a
planning view does not need one.

**Self check-in** puts a short-lived signed code on the manager's day-of screen
as a QR. The creator scans it. Four things are checked, all server-side,
because the code is the only part a phone can produce:

1. the code is one we signed, is a *check-in* code, and hasn't expired;
2. the slot it names still exists on the campaign it names;
3. **this creator has a booking on that slot** — the code names the slot and
   never the creator, so one screen serves the whole queue and identity comes
   from the session, never from the code;
4. now is close enough to the booking, so a screen photographed today cannot
   be used next week.

The manual button stays and is not a lesser path — it is what works when the
camera doesn't — and **both paths write the same audit line**, differing only
in `method`, because "who was actually here" has to be one question with one
answer.
"""
import asyncio
import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"


def read(*parts):
    return FRONTEND.joinpath(*parts).read_text()


def source(fn):
    return inspect.getsource(fn)


def _status(coro):
    try:
        asyncio.run(coro)
        return 200
    except HTTPException as e:
        return e.status_code


def _world(*, when=None):
    """Two brands, a WeAre manager, and a creator booked on a slot today."""
    server.db = AsyncMongoMockClient()["t"]
    now = datetime.now(timezone.utc)
    at = when or (now + timedelta(minutes=30))
    w = {"now": now, "at": at}

    async def build():
        for key, role in (
            ("brand_uid", "brand_manager"),
            ("rival_uid", "brand_manager"),
            ("manager_uid", "campaign_manager"),
            ("creator_uid", "creator"),
            ("other_creator_uid", "creator"),
        ):
            w[key] = ObjectId()
            await server.db.users.insert_one({"_id": w[key], "role": role, "name": key})
        await server.db.brand_profiles.insert_many([
            {"user_id": w["brand_uid"], "business_name": "Blue Tokai", "verified": True},
            {"user_id": w["rival_uid"], "business_name": "Rival Co", "verified": True},
        ])
        await server.db.creator_profiles.insert_many([
            {"user_id": w["creator_uid"], "name": "Asha Menon",
             # Planted for the leak test.
             "phone": "+919812345678", "email": "asha@example.com",
             "full_address": "14 Hidden Lane"},
            {"user_id": w["other_creator_uid"], "name": "Meera Rao"},
        ])
        base = {
            "status": "open", "campaign_type": "group_event", "area": "Indiranagar",
            "created_at": now, "event_date": at, "venue_address": "80 Ft Road",
        }
        w["campaign"] = (await server.db.campaigns.insert_one({
            **base, "title": "Brunch launch", "brand_id": w["brand_uid"],
            "manager_id": w["manager_uid"],
        })).inserted_id
        w["rival_campaign"] = (await server.db.campaigns.insert_one({
            **base, "title": "Someone else's night", "brand_id": w["rival_uid"],
            "manager_id": w["rival_uid"],
        })).inserted_id

        w["slot"] = (await server.db.campaign_slots.insert_one({
            "campaign_id": w["campaign"], "starts_at": at,
            "ends_at": at + timedelta(hours=2), "capacity": 4, "booked_count": 1,
            "created_at": now, "updated_at": now,
        })).inserted_id

        w["collab"] = (await server.db.collaborations.insert_one({
            "campaign_id": w["campaign"], "creator_id": w["creator_uid"],
            "slot_id": w["slot"], "state": "slot_booked", "scheduled_at": at,
            "created_at": now, "updated_at": now,
        })).inserted_id
        w["rival_collab"] = (await server.db.collaborations.insert_one({
            "campaign_id": w["rival_campaign"], "creator_id": w["other_creator_uid"],
            "state": "slot_booked", "scheduled_at": at,
            "created_at": now, "updated_at": now,
        })).inserted_id

    asyncio.run(build())
    w["brand"] = {"_id": str(w["brand_uid"]), "role": "brand_manager", "brand_id": None}
    w["rival"] = {"_id": str(w["rival_uid"]), "role": "brand_manager", "brand_id": None}
    w["manager"] = {"_id": str(w["manager_uid"]), "role": "campaign_manager"}
    w["creator"] = {"_id": str(w["creator_uid"]), "role": "creator", "name": "Asha"}
    w["other"] = {"_id": str(w["other_creator_uid"]), "role": "creator"}
    w["admin"] = {"_id": str(ObjectId()), "role": "admin", "name": "Admin"}
    return w


def _calendar(w, who, **kw):
    return asyncio.run(server.shoot_calendar(user=who, **kw))


# --- Three scopes, one payload ------------------------------------------------


def test_a_brand_sees_its_own_shoots_and_no_one_else_s():
    w = _world()
    out = _calendar(w, w["brand"])
    titles = {e["campaign_title"] for e in out["entries"]}

    assert titles == {"Brunch launch"}


def test_a_rival_brand_sees_only_its_own():
    w = _world()
    out = _calendar(w, w["rival"])

    assert {e["campaign_title"] for e in out["entries"]} == {"Someone else's night"}


def test_a_weare_manager_sees_the_campaigns_assigned_to_them():
    w = _world()
    out = _calendar(w, w["manager"])

    assert {e["campaign_title"] for e in out["entries"]} == {"Brunch launch"}


def test_an_admin_sees_everything():
    w = _world()
    out = _calendar(w, w["admin"])

    assert len(out["entries"]) == 2


def test_a_creator_has_no_calendar():
    """Their own bookings are on their dashboard. This view is a roster of
    other people, which is not theirs to read."""
    w = _world()
    assert _status(server.shoot_calendar(user={"_id": str(ObjectId()), "role": "creator"})) == 403


def test_the_campaign_filter_lists_only_campaigns_in_scope():
    """A dropdown listing every campaign in the database would be a directory
    of other brands' work."""
    w = _world()
    out = _calendar(w, w["brand"])

    assert [c["title"] for c in out["campaigns"]] == ["Brunch launch"]


def test_filtering_by_a_campaign_outside_the_scope_returns_nothing():
    """An empty calendar, not a 403 — whether that campaign exists is not this
    caller's business, the same reasoning as the 404s elsewhere."""
    w = _world()
    out = _calendar(w, w["brand"], campaign=str(w["rival_campaign"]))

    assert out["entries"] == []


# --- What a calendar entry may carry ------------------------------------------


def test_no_entry_carries_a_contact_detail():
    """Planted values, searched for in the real output — the same way the
    export leak tests work. A calendar is a planning view; the roster and the
    daysheet are where a phone number lives, behind the staff role."""
    w = _world()
    blob = str(_calendar(w, w["admin"]))

    for planted in ("+919812345678", "asha@example.com", "14 Hidden Lane"):
        assert planted not in blob
    for key in server.BRAND_FORBIDDEN_CREATOR_FIELDS:
        assert f"'{key}'" not in blob


def test_an_entry_says_who_what_when_and_where_it_goes():
    w = _world()
    entry = _calendar(w, w["admin"])["entries"][0]

    assert entry["creator_name"]
    assert entry["campaign_title"] and entry["starts_at"] and entry["state"]
    assert entry["href"].startswith("/applications/")


def test_an_exit_is_not_a_shoot():
    """Declined and cancelled rows keep the time they were booked for.
    Drawing them would put people on a calendar who are not coming."""
    w = _world()
    asyncio.run(server.db.collaborations.update_one(
        {"_id": w["collab"]}, {"$set": {"state": "cancelled"}}
    ))
    assert _calendar(w, w["brand"])["entries"] == []


def test_the_range_is_capped():
    """A month view asks for a month. Without a cap, one request asks for the
    whole history."""
    w = _world()
    out = _calendar(
        w, w["admin"],
        start=w["now"] - timedelta(days=1),
        end=w["now"] + timedelta(days=900),
    )
    span = datetime.fromisoformat(out["end"]) - datetime.fromisoformat(out["start"])
    assert span <= timedelta(days=server.MAX_CALENDAR_DAYS)


def test_a_backwards_range_is_refused():
    w = _world()
    assert _status(server.shoot_calendar(
        user=w["admin"], start=w["now"], end=w["now"] - timedelta(days=5)
    )) == 422


# --- The code -----------------------------------------------------------------


def _code_for(w):
    slot = asyncio.run(server.db.campaign_slots.find_one({"_id": w["slot"]}))
    campaign = asyncio.run(server.db.campaigns.find_one({"_id": w["campaign"]}))
    return server._mint_checkin_code(slot, campaign)["code"]


def test_the_code_names_the_slot_and_never_the_creator():
    """One screen serves the whole queue. A per-creator code would be one QR
    per person, which is the problem this exists to solve — and it is why
    identity comes from the session instead."""
    w = _world()
    claims = jwt.decode(_code_for(w), server._jwt_secret(), algorithms=[server.JWT_ALGORITHM])

    assert claims["slot"] == str(w["slot"])
    assert claims["typ"] == "checkin"
    assert "creator" not in claims and "sub" not in claims


def test_the_code_is_short_lived():
    """The property it actually has is "you were looking at the manager's
    screen a moment ago"."""
    assert server.CHECKIN_CODE_TTL_SECONDS <= 120
    w = _world()
    claims = jwt.decode(_code_for(w), server._jwt_secret(), algorithms=[server.JWT_ALGORITHM])
    life = claims["exp"] - datetime.now(timezone.utc).timestamp()
    assert 0 < life <= server.CHECKIN_CODE_TTL_SECONDS + 2


def test_an_expired_code_says_so_rather_than_failing_vaguely():
    """"This has expired" tells somebody at a venue to look at the screen
    again, which is the fix."""
    stale = jwt.encode(
        {"typ": "checkin", "slot": str(ObjectId()), "campaign": str(ObjectId()),
         "exp": datetime.now(timezone.utc) - timedelta(seconds=5)},
        server._jwt_secret(), algorithm=server.JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc:
        server._read_checkin_code(stale)
    assert exc.value.status_code == 422
    assert "expired" in str(exc.value.detail)


def test_a_session_token_is_not_a_check_in_code():
    """Every token this app signs verifies with the same key. Without the
    `typ` check, an access token or an impersonation token would work as a
    check-in code."""
    other = jwt.encode(
        {"sub": str(ObjectId()), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        server._jwt_secret(), algorithm=server.JWT_ALGORITHM,
    )
    assert _status_sync(lambda: server._read_checkin_code(other)) == 422


def test_a_forged_code_is_refused():
    forged = jwt.encode(
        {"typ": "checkin", "slot": str(ObjectId()),
         "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "not-the-secret", algorithm=server.JWT_ALGORITHM,
    )
    assert _status_sync(lambda: server._read_checkin_code(forged)) == 422


def _status_sync(fn):
    try:
        fn()
        return 200
    except HTTPException as e:
        return e.status_code


def test_only_the_manager_of_that_campaign_can_mint_one():
    """A code for somebody else's shoot would check their creators in. **404,
    not 403** — the same rule as everywhere else here: whether a slot exists
    is not a question an unassigned manager gets an answer to."""
    w = _world()
    stranger = {"_id": str(ObjectId()), "role": "campaign_manager"}

    assert _status(server.manager_checkin_code(str(w["slot"]), stranger)) == 404
    assert asyncio.run(server.manager_checkin_code(str(w["slot"]), w["manager"]))["code"]


# --- Scanning it --------------------------------------------------------------


def _scan(w, who=None, code=None):
    return server.creator_self_check_in(
        server.CheckInCodePayload(code=code or _code_for(w)), who or w["creator"]
    )


def test_the_creator_on_the_slot_is_checked_in():
    w = _world()
    out = asyncio.run(_scan(w))

    assert out["state"] == "attended"
    assert out["method"] == "self_qr"


def test_a_creator_with_no_booking_on_that_slot_is_refused():
    """The code says nothing about who is holding it. This is the check that
    makes that safe."""
    w = _world()
    assert _status(_scan(w, w["other"])) == 404


def test_the_refusal_does_not_say_whose_shoot_it_was():
    """A creator who scanned the wrong screen learns nothing about it."""
    w = _world()
    try:
        asyncio.run(_scan(w, w["other"]))
        pytest.fail("should have refused")
    except HTTPException as e:
        assert "Brunch launch" not in str(e.detail)
        assert str(w["slot"]) not in str(e.detail)


def test_a_screen_photographed_today_cannot_be_used_next_week():
    """Even with a live code — the window is what stops it."""
    w = _world(when=datetime.now(timezone.utc) + timedelta(days=7))
    assert _status(_scan(w)) == 409


def test_nor_can_one_from_a_shoot_that_finished_long_ago():
    w = _world(when=datetime.now(timezone.utc) - timedelta(days=2))
    assert _status(_scan(w)) == 409


def test_arriving_early_is_fine():
    """The creator who turns up an hour before and waits is the ordinary
    case, not an attack."""
    w = _world(when=datetime.now(timezone.utc) + timedelta(minutes=60))
    assert asyncio.run(_scan(w))["state"] == "attended"


def test_scanning_twice_is_refused_the_same_way_the_manual_path_is():
    """409 "already checked in" — the offline queue drops a 409 rather than
    retrying, and it must mean the same thing on both paths."""
    w = _world()
    asyncio.run(_scan(w))
    assert _status(_scan(w)) == 409


def test_a_creator_who_never_booked_cannot_be_checked_in():
    w = _world()
    asyncio.run(server.db.collaborations.update_one(
        {"_id": w["collab"]}, {"$set": {"state": "commercial_agreed"}}
    ))
    assert _status(_scan(w)) == 409


# --- Both paths, one record ---------------------------------------------------


def test_both_paths_go_through_one_implementation():
    """Who is holding the clipboard depends on whether the campaign was
    reassigned and on whether the camera worked. The attendance record must
    not depend on either."""
    assert "_check_in_collaboration(" in source(server.creator_self_check_in)
    assert "_check_in_collaboration(" in source(server.check_in_creator)


def test_both_paths_write_the_same_audit_line():
    src = source(server._check_in_collaboration)
    assert '"collaboration.check_in"' in src
    assert '"state": "slot_booked"' in src and '"state": "attended"' in src
    assert "_campaign_audit_context(campaign)" in src
    # Distinguishable without being different.
    assert '"method": method' in src


def test_the_manual_path_is_still_the_manual_path():
    """It is what works when the camera doesn't, and it is not a lesser one —
    so it keeps its default and nothing about it changed."""
    params = inspect.signature(server._check_in_collaboration).parameters
    assert params["method"].default == "manual"


# --- The frontend -------------------------------------------------------------


def test_the_agenda_is_the_mobile_view_and_the_grid_is_the_extra():
    """A month of centimetre-square cells on a 390px screen can hold a number
    and nothing else. The small screen gets the more useful thing."""
    src = read("pages", "ShootCalendar.jsx")
    grid = src[src.index("IDS.grid") : src.index("IDS.agenda")]
    assert "hidden md:block" in grid
    assert "hidden" not in src[src.index("data-testid={IDS.agenda}") : src.index("agendaDays.length")]


def test_the_calendar_buckets_by_the_ist_day():
    """`toISOString` would bucket an evening shoot into the next day for
    everybody in IST, which is the bug this product keeps having to answer.

    The bucketing moved into `lib/time.js` when the whole portal was put on
    IST — it used to be the browser's local day, which is right in Bengaluru
    and wrong everywhere else somebody might open it."""
    shared = read("lib", "time.js")
    bucket = shared[shared.index("export function dayKey") : shared.index("export const todayKey")]
    assert "toISOString" not in bucket
    assert "timeZone: IST" in bucket

    src = read("pages", "ShootCalendar.jsx")
    assert "toISOString().slice" not in src
    # Entries are bucketed on the instant's IST day; grid cells are keyed from
    # the parts they were built from. Two functions, so they cannot disagree.
    assert "dayKey(e.starts_at)" in src
    assert "cellKey(d)" in src


def test_the_qr_refreshes_before_the_code_expires():
    """Otherwise a creator who starts scanning as it turns over lands on a
    dead one."""
    src = read("components", "manager", "CheckInQr.jsx")
    assert "REFRESH_MS = 60_000" in src
    assert 60 < server.CHECKIN_CODE_TTL_SECONDS


def test_the_qr_is_dark_on_white():
    """A QR inverted on a dark card is one many phone cameras will not read,
    and this is held up in a badly lit venue."""
    src = read("components", "manager", "CheckInQr.jsx")
    assert "bg-white" in src


def test_the_manual_button_survives_beside_it():
    src = read("components", "manager", "DayOfMode.jsx")
    assert "CheckInQr" in src
    assert "/check-in`" in src, "the manual POST is still there"


def test_the_failure_page_names_the_fallback():
    """The person with the clipboard is standing ten feet away and can do this
    in one tap. Leaving somebody tapping Retry is worse than telling them."""
    src = read("pages", "SelfCheckIn.jsx")
    failure = src[src.index("IDS.failure") :]
    assert "campaign manager" in failure


def test_the_signed_out_page_does_not_promise_a_round_trip():
    """The code lives ninety seconds and an OTP round trip takes longer, so
    carrying it through would land somebody on an expired one."""
    src = read("pages", "SelfCheckIn.jsx")
    assert "next=" not in src
    assert "scan the screen again" in src


def test_the_calendar_is_in_the_navigation_for_all_three_roles():
    src = read("components", "Navbar.jsx")
    assert src.count('to: "/calendar"') == 3
