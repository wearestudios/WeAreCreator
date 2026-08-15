"""Backend tests for the creator's own side of the product.

Slots and the whole manager toolkit shipped before the creator could see
either: a creator sat at `commercial_agreed` with a booking screen that didn't
exist, and a dashboard that could tell them what they had applied for but not
what they had earned, where to go, or who to call. These cover the way out of
that — the profile fields brands actually match on, booking and cancelling a
slot, and the dashboard that has to be readable on the way to a venue.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

import pipeline  # tests/ is on sys.path (no __init__.py, pytest prepend mode)

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "creators@wearemonk.in")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "WeAreMonk@2026")

# Far enough out that the expiry sweep leaves these alone, and far enough out
# that the cancellation cutoff is never the reason a test fails.
EVENT_DAY = "2027-09-01T00:00:00Z"
SLOT_TIME = "2027-09-01T11:00:00Z"
WINDOW_START = "2025-01-01T00:00:00Z"
WINDOW_END = "2027-12-01T00:00:00Z"
# Inside the personal-table window above, so a creator can name it.
PREFERRED_TIME = "2027-06-01T15:30:00Z"


def _register(session, role):
    email = f"test_{role}-{uuid.uuid4().hex[:10]}@example.com"
    r = session.post(f"{BASE_URL}/auth/register", json={
        "email": email, "password": "Password123!", "name": f"Test {role.title()}", "role": role,
    })
    assert r.status_code == 200, r.text
    return email, r.json()


@pytest.fixture
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture
def brand():
    s = requests.Session()
    _register(s, "brand")
    return s


@pytest.fixture
def creator():
    s = requests.Session()
    _, user = _register(s, "creator")
    return s, user["id"]


@pytest.fixture
def manager(admin):
    """A campaign-manager account, plus a logged-in session for it."""
    email = f"mgr-{uuid.uuid4().hex[:8]}@example.com"
    password = "ManagerPass123!"
    r = admin.post(f"{BASE_URL}/admin/managers", json={
        "name": f"Manager {uuid.uuid4().hex[:4]}",
        "email": email,
        "phone": "+919876500000",
        "password": password,
    })
    assert r.status_code == 200, r.text
    created = r.json()
    ms = requests.Session()
    assert ms.post(
        f"{BASE_URL}/auth/login", json={"email": email, "password": password}
    ).status_code == 200
    return ms, created


def _campaign_body(campaign_type, **overrides):
    body = {
        "title": f"Camp-{uuid.uuid4().hex[:6]}",
        "brief": "b",
        "deliverables": "d",
        "budget_per_creator": 5000,
        "category": "cafe",
        "area": "Indiranagar",
        "creators_needed": 5,
        "campaign_type": campaign_type,
        "status": "draft",
    }
    if campaign_type == "personal_table":
        body["start_date"] = WINDOW_START
        body["end_date"] = WINDOW_END
    else:
        body["event_date"] = EVENT_DAY
    body.update(overrides)
    return body


def _live_campaign(brand_s, admin_s, campaign_type="group_event", *, brand_ready=False, **overrides):
    if not brand_ready:
        pipeline.setup_brand(brand_s, admin_s)
    r = brand_s.post(f"{BASE_URL}/brand/campaigns", json=_campaign_body(campaign_type, **overrides))
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    pipeline.submit_campaign(brand_s, cid)
    pipeline.approve_campaign(admin_s, cid)
    return cid


def _managed_campaign(admin_s, brand_s, manager_fixture, campaign_type="group_event", **overrides):
    """A live campaign with a manager on it, so slots can be created."""
    _, created = manager_fixture
    cid = _live_campaign(brand_s, admin_s, campaign_type, **overrides)
    r = admin_s.post(
        f"{BASE_URL}/admin/campaigns/{cid}/assign-manager",
        json={"manager_user_id": created["id"]},
    )
    assert r.status_code == 200, r.text
    return cid


def _make_slot(manager_fixture, campaign_id, *, starts_at=SLOT_TIME, ends_at=None, capacity=2):
    ms, _ = manager_fixture
    body = {"starts_at": starts_at, "capacity": capacity}
    if ends_at:
        body["ends_at"] = ends_at
    r = ms.post(f"{BASE_URL}/manager/campaigns/{campaign_id}/slots", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _creator_at_commercial_agreed(admin_s, brand_s, campaign_id, *, quoted=5000):
    """A verified creator on the campaign with a fee agreed — the state
    booking opens from."""
    cs = requests.Session()
    _, user = _register(cs, "creator")
    pipeline.complete_creator_profile(cs)
    pipeline.verify_creator(admin_s, user["id"])
    collab_id = pipeline.apply_to_campaign(cs, campaign_id, quoted_rate=quoted)
    pipeline.step(admin_s, brand_s, collab_id, "verified")
    pipeline.step(admin_s, brand_s, collab_id, "accepted")
    pipeline.step(admin_s, brand_s, collab_id, "commercial_agreed", agreed_amount=quoted)
    return cs, collab_id, user["id"]


# ---------- 1. Profile fields ----------

class TestCreatorProfileFields:
    def _full_body(self, session, **overrides):
        suf = uuid.uuid4().hex[:6]
        me = session.get(f"{BASE_URL}/auth/me").json()
        body = {
            "name": f"Creator {suf}",
            "instagram_handle": f"@c_{suf}",
            "instagram_profile_url": f"https://instagram.com/c_{suf}",
            "email": me.get("email"),
            "city": "Bengaluru",
            "address": "Indiranagar",
            "full_address": "42 12th Main, Indiranagar, Bengaluru 560038",
            "niches": ["cafe", "brunch"],
            "genres": ["Food", "Travel"],
            "platforms": ["instagram", "youtube"],
            "follower_count": 12000,
            "base_rate": 5000,
        }
        body.update(overrides)
        return body

    def test_the_new_fields_round_trip(self, creator):
        cs, _ = creator
        r = cs.put(f"{BASE_URL}/creator/profile", json=self._full_body(cs))
        assert r.status_code == 200, r.text
        profile = r.json()
        assert profile["genres"] == ["food", "travel"]
        assert profile["platforms"] == ["instagram", "youtube"]
        assert profile["full_address"].startswith("42 12th Main")

    def test_the_existing_fields_are_untouched(self, creator):
        cs, _ = creator
        profile = cs.put(f"{BASE_URL}/creator/profile", json=self._full_body(cs)).json()
        assert profile["niches"] == ["cafe", "brunch"]
        assert profile["city"] == "Bengaluru"
        assert profile["address"] == "Indiranagar"
        assert profile["base_rate"] == 5000

    def test_genres_are_stored_lowercase(self, creator):
        # Suggestions match on these; "Food" never matching "food" would
        # silently empty the list.
        cs, _ = creator
        profile = cs.put(
            f"{BASE_URL}/creator/profile", json=self._full_body(cs, genres=["FOOD"])
        ).json()
        assert profile["genres"] == ["food"]

    def test_duplicate_platforms_collapse(self, creator):
        cs, _ = creator
        profile = cs.put(
            f"{BASE_URL}/creator/profile",
            json=self._full_body(cs, platforms=["instagram", "instagram"]),
        ).json()
        assert profile["platforms"] == ["instagram"]

    def test_a_platform_we_do_not_run_on_is_refused(self, creator):
        cs, _ = creator
        r = cs.put(f"{BASE_URL}/creator/profile", json=self._full_body(cs, platforms=["tiktok"]))
        assert r.status_code == 422, r.text

    def test_the_neighbourhood_is_still_required(self, creator):
        # It is what a brand filters on; a full postal address does not replace it.
        cs, _ = creator
        body = self._full_body(cs)
        body.pop("address")
        assert cs.put(f"{BASE_URL}/creator/profile", json=body).status_code == 422

    def test_the_full_address_is_optional(self, creator):
        cs, _ = creator
        body = self._full_body(cs)
        body.pop("full_address")
        r = cs.put(f"{BASE_URL}/creator/profile", json=body)
        assert r.status_code == 200, r.text
        assert r.json()["full_address"] is None

    def test_the_dashboard_shows_the_creator_their_own_email(self, creator):
        cs, _ = creator
        body = self._full_body(cs)
        cs.put(f"{BASE_URL}/creator/profile", json=body)
        profile = cs.get(f"{BASE_URL}/creator/dashboard").json()["profile"]
        assert profile["email"] == body["email"]
        assert profile["genres"] == ["food", "travel"]
        assert profile["platforms"] == ["instagram", "youtube"]
        assert profile["full_address"] == body["full_address"]


# ---------- 2. Profile completeness ----------

class TestProfileCompleteness:
    def test_a_bare_profile_is_incomplete_and_says_what_is_missing(self, creator):
        cs, _ = creator
        data = cs.get(f"{BASE_URL}/creator/dashboard").json()["profile_completeness"]
        assert data["percent"] < 100
        assert data["complete"] is False
        assert data["missing"], "an empty profile has to name something"
        assert all(row["field"] and row["label"] for row in data["missing"])

    def test_filling_the_profile_moves_the_number_up(self, creator):
        cs, _ = creator
        before = cs.get(f"{BASE_URL}/creator/dashboard").json()["profile_completeness"]
        pipeline.complete_creator_profile(cs)
        after = cs.get(f"{BASE_URL}/creator/dashboard").json()["profile_completeness"]
        assert after["percent"] > before["percent"]

    def test_the_missing_list_names_the_fields_not_yet_filled(self, creator):
        cs, _ = creator
        # complete_creator_profile leaves genres, platforms and full_address unset.
        pipeline.complete_creator_profile(cs)
        data = cs.get(f"{BASE_URL}/creator/dashboard").json()["profile_completeness"]
        missing = {row["field"] for row in data["missing"]}
        assert {"genres", "platforms", "full_address"} <= missing

    def test_a_complete_profile_reads_a_hundred(self, creator):
        cs, _ = creator
        suf = uuid.uuid4().hex[:6]
        me = cs.get(f"{BASE_URL}/auth/me").json()
        cs.put(f"{BASE_URL}/creator/profile", json={
            "name": f"Creator {suf}",
            "instagram_handle": f"@c_{suf}",
            "instagram_profile_url": f"https://instagram.com/c_{suf}",
            "email": me.get("email"),
            "city": "Bengaluru",
            "address": "Indiranagar",
            "full_address": "42 12th Main, Indiranagar",
            "niches": ["cafe"],
            "genres": ["food"],
            "platforms": ["instagram"],
            "follower_count": 12000,
            "base_rate": 5000,
            **pipeline.PAYOUT_DETAILS,
        })
        # The profile photo is the one field a form can't supply.
        data = cs.get(f"{BASE_URL}/creator/dashboard").json()["profile_completeness"]
        missing = {row["field"] for row in data["missing"]}
        assert missing <= {"profile_image_url"}


# ---------- 3. Seeing slots ----------

class TestCreatorSeesSlots:
    def test_a_creator_on_the_campaign_sees_the_schedule(self, admin, brand, manager):
        cid = _managed_campaign(admin, brand, manager)
        slot = _make_slot(manager, cid, capacity=3)
        cs, collab_id, _ = _creator_at_commercial_agreed(admin, brand, cid)

        r = cs.get(f"{BASE_URL}/creator/campaigns/{cid}/slots")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["can_book"] is True
        assert data["collaboration_id"] == collab_id
        row = next(s for s in data["slots"] if s["id"] == slot["id"])
        assert row["spots_left"] == 3
        assert row["is_full"] is False
        assert row["is_mine"] is False
        assert row["starts_at"]

    def test_an_applicant_the_brand_has_not_taken_sees_nothing(self, admin, brand, manager):
        # A slot list names dates, capacity and a venue's rhythm. That is not
        # an applicant's to read.
        cid = _managed_campaign(admin, brand, manager)
        _make_slot(manager, cid)
        cs = requests.Session()
        _, user = _register(cs, "creator")
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, user["id"])
        pipeline.apply_to_campaign(cs, cid)

        assert cs.get(f"{BASE_URL}/creator/campaigns/{cid}/slots").status_code == 404

    def test_a_creator_with_no_collaboration_at_all_sees_nothing(self, admin, brand, manager, creator):
        cid = _managed_campaign(admin, brand, manager)
        _make_slot(manager, cid)
        cs, _ = creator
        assert cs.get(f"{BASE_URL}/creator/campaigns/{cid}/slots").status_code == 404

    def test_a_full_slot_is_shown_and_marked_rather_than_hidden(self, admin, brand, manager):
        cid = _managed_campaign(admin, brand, manager)
        slot = _make_slot(manager, cid, capacity=1)
        first, first_collab, _ = _creator_at_commercial_agreed(admin, brand, cid)
        second, _, _ = _creator_at_commercial_agreed(admin, brand, cid)
        assert first.post(
            f"{BASE_URL}/creator/collaborations/{first_collab}/book-slot",
            json={"slot_id": slot["id"]},
        ).status_code == 200

        data = second.get(f"{BASE_URL}/creator/campaigns/{cid}/slots").json()
        row = next(s for s in data["slots"] if s["id"] == slot["id"])
        assert row["is_full"] is True
        assert row["spots_left"] == 0

    def test_an_invitation_comes_back_with_the_schedule(self, admin, brand, manager):
        cid = _managed_campaign(admin, brand, manager)
        _make_slot(manager, cid)
        cs, _, user_id = _creator_at_commercial_agreed(admin, brand, cid)
        admin.post(
            f"{BASE_URL}/admin/campaigns/{cid}/invite",
            json={"creator_ids": [user_id], "note": "We'd love you on this"},
        )
        data = cs.get(f"{BASE_URL}/creator/campaigns/{cid}/slots").json()
        assert data["invited"] is True
        assert data["invitation_note"] == "We'd love you on this"

    def test_an_uninvited_creator_can_still_book(self, admin, brand, manager):
        # Applying off the open list puts you on the campaign just as much as
        # being hand-picked does.
        cid = _managed_campaign(admin, brand, manager)
        _make_slot(manager, cid)
        cs, _, _ = _creator_at_commercial_agreed(admin, brand, cid)
        data = cs.get(f"{BASE_URL}/creator/campaigns/{cid}/slots").json()
        assert data["invited"] is False
        assert data["can_book"] is True

    def test_a_personal_table_says_the_creator_picks_the_time(self, admin, brand, manager):
        cid = _managed_campaign(admin, brand, manager, "personal_table")
        _make_slot(manager, cid, starts_at=WINDOW_START, ends_at=WINDOW_END)
        cs, _, _ = _creator_at_commercial_agreed(admin, brand, cid)
        data = cs.get(f"{BASE_URL}/creator/campaigns/{cid}/slots").json()
        assert data["picks_own_time"] is True
        assert data["campaign_type"] == "personal_table"

    def test_an_event_campaign_says_the_time_is_fixed(self, admin, brand, manager):
        cid = _managed_campaign(admin, brand, manager, "launch")
        _make_slot(manager, cid)
        cs, _, _ = _creator_at_commercial_agreed(admin, brand, cid)
        data = cs.get(f"{BASE_URL}/creator/campaigns/{cid}/slots").json()
        assert data["picks_own_time"] is False


# ---------- 4. Booking ----------

class TestCreatorBooksSlot:
    def test_booking_moves_the_collaboration_and_takes_a_place(self, admin, brand, manager):
        cid = _managed_campaign(admin, brand, manager)
        slot = _make_slot(manager, cid, capacity=2)
        cs, collab_id, _ = _creator_at_commercial_agreed(admin, brand, cid)

        r = cs.post(
            f"{BASE_URL}/creator/collaborations/{collab_id}/book-slot",
            json={"slot_id": slot["id"]},
        )
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["state"] == "slot_booked"
        assert out["slot"]["booked_count"] == 1
        assert pipeline.current_state(admin, collab_id) == "slot_booked"

    def test_the_slot_list_then_shows_it_as_mine(self, admin, brand, manager):
        cid = _managed_campaign(admin, brand, manager)
        slot = _make_slot(manager, cid, capacity=2)
        cs, collab_id, _ = _creator_at_commercial_agreed(admin, brand, cid)
        cs.post(
            f"{BASE_URL}/creator/collaborations/{collab_id}/book-slot",
            json={"slot_id": slot["id"]},
        )
        data = cs.get(f"{BASE_URL}/creator/campaigns/{cid}/slots").json()
        assert data["booked_slot_id"] == slot["id"]
        assert data["can_book"] is False
        row = next(s for s in data["slots"] if s["id"] == slot["id"])
        assert row["is_mine"] is True

    def test_a_full_slot_is_refused(self, admin, brand, manager):
        cid = _managed_campaign(admin, brand, manager)
        slot = _make_slot(manager, cid, capacity=1)
        first, first_collab, _ = _creator_at_commercial_agreed(admin, brand, cid)
        second, second_collab, _ = _creator_at_commercial_agreed(admin, brand, cid)

        assert first.post(
            f"{BASE_URL}/creator/collaborations/{first_collab}/book-slot",
            json={"slot_id": slot["id"]},
        ).status_code == 200
        r = second.post(
            f"{BASE_URL}/creator/collaborations/{second_collab}/book-slot",
            json={"slot_id": slot["id"]},
        )
        assert r.status_code == 409, r.text
        assert "filled" in r.text.lower()

    def test_booking_before_the_fee_is_agreed_is_refused(self, admin, brand, manager):
        cid = _managed_campaign(admin, brand, manager)
        slot = _make_slot(manager, cid)
        cs = requests.Session()
        _, user = _register(cs, "creator")
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, user["id"])
        collab_id = pipeline.apply_to_campaign(cs, cid)

        r = cs.post(
            f"{BASE_URL}/creator/collaborations/{collab_id}/book-slot",
            json={"slot_id": slot["id"]},
        )
        assert r.status_code == 409, r.text

    def test_booking_twice_is_refused(self, admin, brand, manager):
        cid = _managed_campaign(admin, brand, manager)
        slot = _make_slot(manager, cid, capacity=5)
        cs, collab_id, _ = _creator_at_commercial_agreed(admin, brand, cid)
        cs.post(
            f"{BASE_URL}/creator/collaborations/{collab_id}/book-slot",
            json={"slot_id": slot["id"]},
        )
        r = cs.post(
            f"{BASE_URL}/creator/collaborations/{collab_id}/book-slot",
            json={"slot_id": slot["id"]},
        )
        assert r.status_code == 409, r.text
        assert "already" in r.text.lower()

    def test_somebody_elses_collaboration_is_a_404(self, admin, brand, manager):
        cid = _managed_campaign(admin, brand, manager)
        slot = _make_slot(manager, cid, capacity=5)
        _, victim_collab, _ = _creator_at_commercial_agreed(admin, brand, cid)
        attacker, _, _ = _creator_at_commercial_agreed(admin, brand, cid)

        r = attacker.post(
            f"{BASE_URL}/creator/collaborations/{victim_collab}/book-slot",
            json={"slot_id": slot["id"]},
        )
        assert r.status_code == 404, r.text

    def test_another_campaigns_slot_is_a_404(self, admin, brand, manager):
        mine = _managed_campaign(admin, brand, manager)
        elsewhere = _managed_campaign(admin, brand, manager, brand_ready=True)
        stray = _make_slot(manager, elsewhere)
        cs, collab_id, _ = _creator_at_commercial_agreed(admin, brand, mine)

        r = cs.post(
            f"{BASE_URL}/creator/collaborations/{collab_id}/book-slot",
            json={"slot_id": stray["id"]},
        )
        assert r.status_code == 404, r.text

    def test_a_personal_table_creator_names_their_time(self, admin, brand, manager):
        cid = _managed_campaign(admin, brand, manager, "personal_table")
        slot = _make_slot(manager, cid, starts_at=WINDOW_START, ends_at=WINDOW_END, capacity=3)
        cs, collab_id, _ = _creator_at_commercial_agreed(admin, brand, cid)

        r = cs.post(
            f"{BASE_URL}/creator/collaborations/{collab_id}/book-slot",
            json={"slot_id": slot["id"], "preferred_time": PREFERRED_TIME},
        )
        assert r.status_code == 200, r.text
        assert r.json()["scheduled_at"].startswith("2027-06-01T15:30")

    def test_a_personal_table_without_a_time_is_refused(self, admin, brand, manager):
        cid = _managed_campaign(admin, brand, manager, "personal_table")
        slot = _make_slot(manager, cid, starts_at=WINDOW_START, ends_at=WINDOW_END)
        cs, collab_id, _ = _creator_at_commercial_agreed(admin, brand, cid)

        r = cs.post(
            f"{BASE_URL}/creator/collaborations/{collab_id}/book-slot",
            json={"slot_id": slot["id"]},
        )
        assert r.status_code == 422, r.text

    def test_a_time_outside_the_window_is_refused(self, admin, brand, manager):
        cid = _managed_campaign(admin, brand, manager, "personal_table")
        slot = _make_slot(manager, cid, starts_at=WINDOW_START, ends_at=WINDOW_END)
        cs, collab_id, _ = _creator_at_commercial_agreed(admin, brand, cid)

        r = cs.post(
            f"{BASE_URL}/creator/collaborations/{collab_id}/book-slot",
            json={"slot_id": slot["id"], "preferred_time": "2028-01-01T10:00:00Z"},
        )
        assert r.status_code == 422, r.text
        assert "window" in r.text.lower()

    def test_an_event_creator_cannot_write_their_own_time(self, admin, brand, manager):
        # Everyone arrives together on a launch; one creator choosing their own
        # hour would put them at the venue alone.
        cid = _managed_campaign(admin, brand, manager, "launch")
        slot = _make_slot(manager, cid)
        cs, collab_id, _ = _creator_at_commercial_agreed(admin, brand, cid)

        r = cs.post(
            f"{BASE_URL}/creator/collaborations/{collab_id}/book-slot",
            json={"slot_id": slot["id"], "preferred_time": SLOT_TIME},
        )
        assert r.status_code == 422, r.text

    def test_the_manager_is_told(self, admin, brand, manager):
        ms, _ = manager
        cid = _managed_campaign(admin, brand, manager)
        slot = _make_slot(manager, cid, capacity=2)
        cs, collab_id, _ = _creator_at_commercial_agreed(admin, brand, cid)
        cs.post(
            f"{BASE_URL}/creator/collaborations/{collab_id}/book-slot",
            json={"slot_id": slot["id"]},
        )
        events = [n["event"] for n in ms.get(f"{BASE_URL}/notifications").json()["notifications"]]
        assert "manager_slot_booked" in events


# ---------- 5. Cancelling ----------

class TestCreatorCancelsSlot:
    def _booked(self, admin, brand, manager, **kwargs):
        cid = _managed_campaign(admin, brand, manager, **kwargs)
        slot = _make_slot(manager, cid, capacity=2)
        cs, collab_id, _ = _creator_at_commercial_agreed(admin, brand, cid)
        r = cs.post(
            f"{BASE_URL}/creator/collaborations/{collab_id}/book-slot",
            json={"slot_id": slot["id"]},
        )
        assert r.status_code == 200, r.text
        return cs, collab_id, cid, slot

    def test_cancelling_returns_them_to_commercial_agreed(self, admin, brand, manager):
        # Still on the campaign, still owed a place — just not that one.
        cs, collab_id, _, _ = self._booked(admin, brand, manager)
        r = cs.post(
            f"{BASE_URL}/creator/collaborations/{collab_id}/cancel-slot",
            json={"reason": "Clashes with a shoot"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["state"] == "commercial_agreed"
        assert pipeline.current_state(admin, collab_id) == "commercial_agreed"

    def test_the_place_goes_back_on_sale(self, admin, brand, manager):
        cs, collab_id, cid, slot = self._booked(admin, brand, manager)
        cs.post(f"{BASE_URL}/creator/collaborations/{collab_id}/cancel-slot", json={})
        rows = admin.get(f"{BASE_URL}/manager/campaigns/{cid}/slots").json()["slots"]
        row = next(s for s in rows if s["id"] == slot["id"])
        assert row["booked_count"] == 0
        assert row["spots_left"] == row["capacity"]

    def test_they_can_book_again_afterwards(self, admin, brand, manager):
        cs, collab_id, _, slot = self._booked(admin, brand, manager)
        cs.post(f"{BASE_URL}/creator/collaborations/{collab_id}/cancel-slot", json={})
        r = cs.post(
            f"{BASE_URL}/creator/collaborations/{collab_id}/book-slot",
            json={"slot_id": slot["id"]},
        )
        assert r.status_code == 200, r.text

    def test_a_reason_is_optional(self, admin, brand, manager):
        # We would rather know early without one than have the seat held
        # because a form asked a question they didn't want to answer.
        cs, collab_id, _, _ = self._booked(admin, brand, manager)
        assert cs.post(
            f"{BASE_URL}/creator/collaborations/{collab_id}/cancel-slot", json={}
        ).status_code == 200

    def test_cancelling_without_a_booking_is_refused(self, admin, brand, manager):
        cid = _managed_campaign(admin, brand, manager)
        _make_slot(manager, cid)
        cs, collab_id, _ = _creator_at_commercial_agreed(admin, brand, cid)
        r = cs.post(f"{BASE_URL}/creator/collaborations/{collab_id}/cancel-slot", json={})
        assert r.status_code == 409, r.text

    def test_somebody_elses_booking_is_a_404(self, admin, brand, manager):
        _, victim_collab, cid, _ = self._booked(admin, brand, manager)
        attacker, _, _ = _creator_at_commercial_agreed(admin, brand, cid)
        r = attacker.post(
            f"{BASE_URL}/creator/collaborations/{victim_collab}/cancel-slot", json={}
        )
        assert r.status_code == 404, r.text

    def test_inside_the_cutoff_they_have_to_talk_to_the_manager(self, admin, brand, manager):
        # A venue plans staffing off the day's bookings, so a walk-away an hour
        # before is not a self-service action.
        # Three hours out: on the event day the validator checks, still in the
        # future so the expiry sweep leaves the campaign alone, and well inside
        # the cutoff.
        soon = (datetime.now(timezone.utc) + timedelta(hours=3)).replace(microsecond=0)
        when = soon.isoformat().replace("+00:00", "Z")
        cid = _managed_campaign(admin, brand, manager, "group_event", event_date=when)
        slot = _make_slot(manager, cid, starts_at=when, capacity=2)
        cs, collab_id, _ = _creator_at_commercial_agreed(admin, brand, cid)
        assert cs.post(
            f"{BASE_URL}/creator/collaborations/{collab_id}/book-slot",
            json={"slot_id": slot["id"]},
        ).status_code == 200

        r = cs.post(f"{BASE_URL}/creator/collaborations/{collab_id}/cancel-slot", json={})
        assert r.status_code == 409, r.text
        assert "manager" in r.text.lower()

    def test_the_manager_is_told_the_seat_freed(self, admin, brand, manager):
        ms, _ = manager
        cs, collab_id, _, _ = self._booked(admin, brand, manager)
        cs.post(f"{BASE_URL}/creator/collaborations/{collab_id}/cancel-slot", json={})
        events = [n["event"] for n in ms.get(f"{BASE_URL}/notifications").json()["notifications"]]
        assert "manager_slot_released" in events

    def test_it_lands_in_the_audit_log(self, admin, brand, manager):
        cs, collab_id, _, _ = self._booked(admin, brand, manager)
        cs.post(
            f"{BASE_URL}/creator/collaborations/{collab_id}/cancel-slot",
            json={"reason": "Down with flu"},
        )
        rows = admin.get(
            f"{BASE_URL}/admin/audit", params={"action": "collaboration.cancel_slot"}
        ).json()
        assert any(row.get("note") == "Down with flu" for row in rows)


# ---------- 6. The dashboard ----------

class TestCreatorDashboardGrouping:
    def test_an_applicant_sits_in_applied(self, admin, brand, creator):
        cs, user_id = creator
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, user_id)
        cid = pipeline.seed_open_campaign(brand, admin)
        collab_id = pipeline.apply_to_campaign(cs, cid)

        groups = cs.get(f"{BASE_URL}/creator/dashboard").json()["collaborations"]
        assert [r["id"] for r in groups["applied"]] == [collab_id]
        assert groups["active"] == []

    def test_an_accepted_collaboration_is_active(self, admin, brand, manager):
        cid = _managed_campaign(admin, brand, manager)
        cs, collab_id, _ = _creator_at_commercial_agreed(admin, brand, cid)
        groups = cs.get(f"{BASE_URL}/creator/dashboard").json()["collaborations"]
        assert [r["id"] for r in groups["active"]] == [collab_id]

    def test_a_declined_application_is_grouped_apart(self, admin, brand, creator):
        cs, user_id = creator
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, user_id)
        cid = pipeline.seed_open_campaign(brand, admin)
        collab_id = pipeline.apply_to_campaign(cs, cid)
        r = admin.post(
            f"{BASE_URL}/admin/collaborations/{collab_id}/decline",
            json={"reason": "Not the right fit this time"},
        )
        assert r.status_code == 200, r.text

        groups = cs.get(f"{BASE_URL}/creator/dashboard").json()["collaborations"]
        assert [r["id"] for r in groups["declined"]] == [collab_id]
        assert groups["applied"] == []

    def test_a_closed_collaboration_is_completed(self, admin, brand, creator):
        cs, user_id = creator
        collab_id, _ = pipeline.make_collab_in_state(
            admin, brand, cs, user_id, "closed"
        )
        data = cs.get(f"{BASE_URL}/creator/dashboard").json()
        assert [r["id"] for r in data["collaborations"]["completed"]] == [collab_id]
        assert data["earnings"]["campaigns_completed"] == 1

    def test_nothing_falls_out_of_the_record(self, admin, brand, creator):
        cs, user_id = creator
        collab_id, _ = pipeline.make_collab_in_state(
            admin, brand, cs, user_id, "attended"
        )
        data = cs.get(f"{BASE_URL}/creator/dashboard").json()
        grouped = [
            r["id"] for group in data["collaborations"].values() for r in group
        ]
        assert grouped.count(collab_id) == 1


class TestActiveCollaborationDetail:
    def test_it_carries_the_manager_and_the_venue(self, admin, brand, manager):
        # This is the screen a creator opens on the way to a venue, so it must
        # not need a second request to be useful.
        ms, created = manager
        cid = _managed_campaign(
            admin, brand, manager,
            venue_address="12 Church Street, Bengaluru",
            venue_instructions="Ask for Riya at the counter",
        )
        cs, collab_id, _ = _creator_at_commercial_agreed(admin, brand, cid)

        row = cs.get(f"{BASE_URL}/creator/dashboard").json()["collaborations"]["active"][0]
        assert row["manager"]["name"] == created["name"]
        assert row["manager"]["phone"]
        assert row["venue"]["address"] == "12 Church Street, Bengaluru"
        assert row["venue"]["instructions"] == "Ask for Riya at the counter"
        assert row["campaign"]["title"]

    def test_it_carries_the_booked_time_once_booked(self, admin, brand, manager):
        cid = _managed_campaign(admin, brand, manager)
        slot = _make_slot(manager, cid, capacity=2)
        cs, collab_id, _ = _creator_at_commercial_agreed(admin, brand, cid)
        cs.post(
            f"{BASE_URL}/creator/collaborations/{collab_id}/book-slot",
            json={"slot_id": slot["id"]},
        )
        row = cs.get(f"{BASE_URL}/creator/dashboard").json()["collaborations"]["active"][0]
        assert row["slot_starts_at"]
        assert row["slot"]["id"] == slot["id"]
        assert row["can_cancel_slot"] is True

    def test_an_agreed_fee_asks_for_a_booking(self, admin, brand, manager):
        cid = _managed_campaign(admin, brand, manager)
        cs, _, _ = _creator_at_commercial_agreed(admin, brand, cid)
        row = cs.get(f"{BASE_URL}/creator/dashboard").json()["collaborations"]["active"][0]
        assert row["next_action"]["action"] == "book_slot"
        assert row["next_action"]["waiting_on"] == "you"

    def test_after_attending_it_asks_for_content(self, admin, brand, creator):
        cs, user_id = creator
        pipeline.make_collab_in_state(admin, brand, cs, user_id, "attended")
        row = cs.get(f"{BASE_URL}/creator/dashboard").json()["collaborations"]["active"][0]
        assert row["next_action"]["action"] == "submit_content"

    def test_waiting_on_the_brand_is_said_plainly(self, admin, brand, creator):
        cs, user_id = creator
        pipeline.make_collab_in_state(admin, brand, cs, user_id, "content_submitted")
        row = cs.get(f"{BASE_URL}/creator/dashboard").json()["collaborations"]["active"][0]
        assert row["next_action"]["waiting_on"] == "brand"

    def test_missing_payout_details_are_surfaced_as_the_next_action(self, admin, brand):
        # The one place a creator blocks their own money without being told.
        cs = requests.Session()
        _, user = _register(cs, "creator")
        pipeline.complete_creator_profile(cs, with_payout=False)
        pipeline.verify_creator(admin, user["id"])
        cid = pipeline.seed_open_campaign(brand, admin)
        collab_id = pipeline.apply_to_campaign(cs, cid)
        pipeline.advance_to(admin, brand, cs, collab_id, "content_approved")

        row = cs.get(f"{BASE_URL}/creator/dashboard").json()["collaborations"]["active"][0]
        assert row["next_action"]["action"] == "add_payout_details"
        assert row["next_action"]["waiting_on"] == "you"


class TestCreatorEarnings:
    def test_an_empty_creator_has_nothing(self, creator):
        cs, _ = creator
        earnings = cs.get(f"{BASE_URL}/creator/dashboard").json()["earnings"]
        assert earnings == {
            "lifetime_earned": 0,
            "pending_earnings": 0,
            "campaigns_completed": 0,
        }

    def test_an_agreed_fee_is_pending_not_earned(self, admin, brand, creator):
        cs, user_id = creator
        pipeline.make_collab_in_state(admin, brand, cs, user_id, "commercial_agreed")
        earnings = cs.get(f"{BASE_URL}/creator/dashboard").json()["earnings"]
        assert earnings["pending_earnings"] > 0
        assert earnings["lifetime_earned"] == 0

    def test_a_paid_collaboration_becomes_lifetime_earnings(self, admin, brand, creator):
        cs, user_id = creator
        pipeline.make_collab_in_state(admin, brand, cs, user_id, "closed")
        data = cs.get(f"{BASE_URL}/creator/dashboard").json()
        assert data["earnings"]["lifetime_earned"] > 0
        assert data["earnings"]["pending_earnings"] == 0
        assert data["earnings"]["campaigns_completed"] == 1

    def test_the_figure_matches_the_payout_actually_recorded(self, admin, brand, creator):
        # Net of our fee — a dashboard that quotes the gross and then pays less
        # is one nobody trusts twice.
        cs, user_id = creator
        pipeline.make_collab_in_state(admin, brand, cs, user_id, "closed")
        data = cs.get(f"{BASE_URL}/creator/dashboard").json()
        payout = sum(
            p["creator_payout"] for p in data["payments"] if p["state"] == "paid"
        )
        assert data["earnings"]["lifetime_earned"] == pytest.approx(payout)

    def test_a_declined_application_is_not_money_owed(self, admin, brand, creator):
        cs, user_id = creator
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, user_id)
        cid = pipeline.seed_open_campaign(brand, admin)
        collab_id = pipeline.apply_to_campaign(cs, cid)
        admin.post(
            f"{BASE_URL}/admin/collaborations/{collab_id}/decline",
            json={"reason": "Not this time"},
        )
        earnings = cs.get(f"{BASE_URL}/creator/dashboard").json()["earnings"]
        assert earnings["pending_earnings"] == 0


class TestSuggestedCampaigns:
    def _matching_campaign(self, brand_s, admin_s, **overrides):
        return _live_campaign(brand_s, admin_s, "personal_table", **overrides)

    def test_a_campaign_in_my_niche_is_suggested_with_a_reason(self, admin, brand, creator):
        cs, user_id = creator
        pipeline.complete_creator_profile(cs)  # niches: ["cafe"], address "Indiranagar"
        pipeline.verify_creator(admin, user_id)
        cid = self._matching_campaign(brand, admin)

        suggestions = cs.get(f"{BASE_URL}/creator/dashboard").json()["suggested_campaigns"]
        row = next((s for s in suggestions if s["id"] == cid), None)
        assert row is not None, "a cafe brief in their own neighbourhood should surface"
        assert row["match_reason"]

    def test_a_campaign_i_already_applied_to_is_not_suggested(self, admin, brand, creator):
        cs, user_id = creator
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, user_id)
        cid = self._matching_campaign(brand, admin)
        pipeline.apply_to_campaign(cs, cid)

        suggestions = cs.get(f"{BASE_URL}/creator/dashboard").json()["suggested_campaigns"]
        assert all(s["id"] != cid for s in suggestions)

    def test_a_campaign_matching_nothing_is_not_suggested(self, admin, brand, creator):
        cs, user_id = creator
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, user_id)
        cid = self._matching_campaign(brand, admin, category="fitness", area="Whitefield")

        suggestions = cs.get(f"{BASE_URL}/creator/dashboard").json()["suggested_campaigns"]
        assert all(s["id"] != cid for s in suggestions)

    def test_a_genre_match_counts_too(self, admin, brand, creator):
        cs, user_id = creator
        me = cs.get(f"{BASE_URL}/auth/me").json()
        suf = uuid.uuid4().hex[:6]
        cs.put(f"{BASE_URL}/creator/profile", json={
            "name": f"Creator {suf}",
            "instagram_handle": f"@c_{suf}",
            "instagram_profile_url": f"https://instagram.com/c_{suf}",
            "email": me.get("email"),
            "city": "Bengaluru",
            "address": "Koramangala",
            "niches": [],
            "genres": ["fitness"],
            "follower_count": 9000,
            "base_rate": 4000,
        })
        pipeline.verify_creator(admin, user_id)
        cid = self._matching_campaign(brand, admin, category="fitness", area="Whitefield")

        suggestions = cs.get(f"{BASE_URL}/creator/dashboard").json()["suggested_campaigns"]
        row = next((s for s in suggestions if s["id"] == cid), None)
        assert row is not None
        assert "fitness" in row["match_reason"].lower()

    def test_a_profile_with_nothing_to_match_on_gets_no_suggestions(self, creator):
        # Better an empty list than a random one presented as a recommendation.
        cs, _ = creator
        assert cs.get(f"{BASE_URL}/creator/dashboard").json()["suggested_campaigns"] == []


class TestDashboardStaysBackwardsCompatible:
    def test_the_old_keys_are_still_there(self, admin, brand, creator):
        # The creator app reads these today; the extension adds alongside them.
        cs, user_id = creator
        pipeline.make_collab_in_state(admin, brand, cs, user_id, "slot_booked")
        data = cs.get(f"{BASE_URL}/creator/dashboard").json()
        for key in ("profile", "applications", "upcoming", "payments", "totals"):
            assert key in data
        assert data["totals"]["applications"] >= 1
