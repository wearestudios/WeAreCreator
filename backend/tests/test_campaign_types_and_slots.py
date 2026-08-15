"""Backend tests for campaign types, the assigned manager, and slot booking.

Campaigns used to be shapeless: two optional dates and no idea whether the work
was a one-day launch or a month of tables. These cover the type rules, the
manager's scoped access, and the booking race — two creators after the last
place has to resolve to exactly one of them.
"""
import os
import threading
import uuid

import pytest
import requests

import pipeline  # tests/ is on sys.path (no __init__.py, pytest prepend mode)

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "creators@wearemonk.in")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "WeAreMonk@2026")

# Far enough out that the expiry sweep leaves these alone.
EVENT_DAY = "2027-09-01T00:00:00Z"
SLOT_TIME = "2027-09-01T11:00:00Z"
WINDOW_START = "2025-01-01T00:00:00Z"
WINDOW_END = "2027-12-01T00:00:00Z"


def _register(session, role):
    email = f"test_{role}-{uuid.uuid4().hex[:10]}@example.com"
    r = session.post(f"{BASE_URL}/auth/register", json={
        "email": email, "password": "Password123!", "name": f"Test {role.title()}", "role": role,
    })
    assert r.status_code == 200, r.text
    return email, r.json()


def _login(session, email, password):
    r = session.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    return r


@pytest.fixture
def admin():
    s = requests.Session()
    assert _login(s, ADMIN_EMAIL, ADMIN_PASSWORD).status_code == 200
    return s


@pytest.fixture
def anon():
    return requests.Session()


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
        "password": password,
        "phone": "+919876500000",
    })
    assert r.status_code == 200, r.text
    created = r.json()

    s = requests.Session()
    assert _login(s, email, password).status_code == 200, "a manager signs in like an admin"
    return s, created


def _body(campaign_type="personal_table", **overrides):
    body = {
        "title": f"T-{uuid.uuid4().hex[:6]}",
        "brief": "b",
        "deliverables": "d",
        "budget_per_creator": 5000,
        "category": "fnb",
        "area": "Indiranagar",
        "creators_needed": 2,
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


def _live_campaign(brand_s, admin_s, campaign_type="personal_table", **overrides):
    """A campaign of the given type, taken all the way live."""
    pipeline.setup_brand(brand_s, admin_s)
    r = brand_s.post(f"{BASE_URL}/brand/campaigns", json=_body(campaign_type, **overrides))
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    pipeline.submit_campaign(brand_s, cid)
    pipeline.approve_campaign(admin_s, cid)
    return cid


# ---------- 1. Campaign types ----------

class TestCampaignTypes:
    @pytest.mark.parametrize("ctype", ["launch", "group_event"])
    def test_an_event_campaign_takes_a_day(self, brand, admin, ctype):
        pipeline.setup_brand(brand, admin)
        r = brand.post(f"{BASE_URL}/brand/campaigns", json=_body(ctype))
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["campaign_type"] == ctype
        assert d["event_date"] is not None
        assert d["start_date"] is None and d["end_date"] is None

    @pytest.mark.parametrize("ctype", ["launch", "group_event"])
    def test_an_event_campaign_without_a_day_is_refused(self, brand, admin, ctype):
        pipeline.setup_brand(brand, admin)
        body = _body(ctype)
        body.pop("event_date")
        assert brand.post(f"{BASE_URL}/brand/campaigns", json=body).status_code == 422

    @pytest.mark.parametrize("stray", ["start_date", "end_date"])
    def test_an_event_campaign_cannot_also_carry_a_window(self, brand, admin, stray):
        pipeline.setup_brand(brand, admin)
        body = _body("launch", **{stray: WINDOW_END})
        r = brand.post(f"{BASE_URL}/brand/campaigns", json=body)
        assert r.status_code == 422, r.text

    def test_a_personal_table_takes_a_window(self, brand, admin):
        pipeline.setup_brand(brand, admin)
        r = brand.post(f"{BASE_URL}/brand/campaigns", json=_body("personal_table"))
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["campaign_type"] == "personal_table"
        assert d["start_date"] and d["end_date"]
        assert d["event_date"] is None

    def test_a_personal_table_needs_both_ends(self, brand, admin):
        pipeline.setup_brand(brand, admin)
        body = _body("personal_table")
        body.pop("end_date")
        assert brand.post(f"{BASE_URL}/brand/campaigns", json=body).status_code == 422

    def test_a_personal_table_cannot_carry_an_event_day(self, brand, admin):
        pipeline.setup_brand(brand, admin)
        body = _body("personal_table", event_date=EVENT_DAY)
        assert brand.post(f"{BASE_URL}/brand/campaigns", json=body).status_code == 422

    def test_a_type_is_required(self, brand, admin):
        pipeline.setup_brand(brand, admin)
        body = _body()
        body.pop("campaign_type")
        assert brand.post(f"{BASE_URL}/brand/campaigns", json=body).status_code == 422

    def test_an_invented_type_is_refused(self, brand, admin):
        pipeline.setup_brand(brand, admin)
        assert brand.post(
            f"{BASE_URL}/brand/campaigns", json=_body("popup")
        ).status_code == 422

    def test_an_edit_cannot_give_a_launch_a_booking_window(self, brand, admin):
        cid = _live_campaign(brand, admin, "launch")
        r = brand.put(f"{BASE_URL}/brand/campaigns/{cid}", json={"end_date": WINDOW_END})
        assert r.status_code == 422, r.text

    def test_an_edit_cannot_give_a_table_an_event_day(self, admin, brand):
        cid = _live_campaign(brand, admin, "personal_table")
        r = admin.patch(f"{BASE_URL}/admin/campaigns/{cid}", json={"event_date": EVENT_DAY})
        assert r.status_code == 422, r.text

    def test_the_type_shows_on_the_creator_feed(self, brand, admin, creator):
        cid = _live_campaign(brand, admin, "launch")
        cs, cuid = creator
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, cuid)
        row = next(c for c in cs.get(f"{BASE_URL}/campaigns").json() if c["id"] == cid)
        assert row["campaign_type"] == "launch"
        assert row["event_date"]

    def test_venue_details_are_stored_on_the_campaign(self, brand, admin):
        pipeline.setup_brand(brand, admin)
        r = brand.post(f"{BASE_URL}/brand/campaigns", json=_body(
            "launch",
            venue_address="12 Church Street, Bengaluru",
            venue_instructions="Ask for the events desk",
            on_site_contact="Riya · +919876543210",
        ))
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["venue_address"] == "12 Church Street, Bengaluru"
        assert d["venue_instructions"] == "Ask for the events desk"
        assert d["on_site_contact"] == "Riya · +919876543210"


# ---------- 2. Campaign managers ----------

class TestManagerAccounts:
    def test_only_an_admin_creates_one(self, anon, brand, creator, manager):
        cs, _ = creator
        ms, _ = manager
        body = {"name": "X", "email": f"x-{uuid.uuid4().hex[:6]}@e.com", "password": "Password123!"}
        assert anon.post(f"{BASE_URL}/admin/managers", json=body).status_code == 401
        assert brand.post(f"{BASE_URL}/admin/managers", json=body).status_code == 403
        assert cs.post(f"{BASE_URL}/admin/managers", json=body).status_code == 403
        # Not even another manager — this role can read creators' phone numbers.
        assert ms.post(f"{BASE_URL}/admin/managers", json=body).status_code == 403

    def test_nobody_can_sign_themselves_up_as_a_manager(self, anon):
        r = anon.post(f"{BASE_URL}/auth/register", json={
            "email": f"sneak-{uuid.uuid4().hex[:6]}@e.com",
            "password": "Password123!", "name": "Sneak", "role": "campaign_manager",
        })
        assert r.status_code == 422, r.text

    def test_a_manager_signs_in_with_a_password(self, manager):
        ms, created = manager
        me = ms.get(f"{BASE_URL}/auth/me").json()
        assert me["role"] == "campaign_manager"
        assert me["id"] == created["id"]

    def test_a_duplicate_email_is_refused(self, admin, manager):
        _, created = manager
        r = admin.post(f"{BASE_URL}/admin/managers", json={
            "name": "Twin", "email": created["email"], "password": "Password123!",
        })
        assert r.status_code == 409, r.text

    def test_the_roster_shows_how_much_each_is_carrying(self, admin, manager, brand):
        ms, created = manager
        cid = _live_campaign(brand, admin, "launch")
        admin.post(f"{BASE_URL}/admin/campaigns/{cid}/assign-manager",
                   json={"manager_user_id": created["id"]})

        row = next(m for m in admin.get(f"{BASE_URL}/admin/managers").json()
                   if m["id"] == created["id"])
        assert row["active_campaigns"] >= 1


class TestAssignment:
    def test_only_an_admin_assigns(self, anon, brand, creator, admin, manager):
        ms, created = manager
        cs, _ = creator
        cid = _live_campaign(brand, admin, "launch")
        path = f"{BASE_URL}/admin/campaigns/{cid}/assign-manager"
        body = {"manager_user_id": created["id"]}
        assert anon.post(path, json=body).status_code == 401
        assert cs.post(path, json=body).status_code == 403
        assert brand.post(path, json=body).status_code == 403
        assert ms.post(path, json=body).status_code == 403

    def test_assigning_snapshots_the_manager_onto_the_campaign(self, admin, brand, manager):
        _, created = manager
        cid = _live_campaign(brand, admin, "launch")
        r = admin.post(f"{BASE_URL}/admin/campaigns/{cid}/assign-manager",
                       json={"manager_user_id": created["id"]})
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["manager_name"] == created["name"]
        assert out["manager_phone"] == created["phone"]

    def test_the_brand_sees_who_runs_its_campaign(self, admin, brand, manager):
        _, created = manager
        cid = _live_campaign(brand, admin, "launch")
        admin.post(f"{BASE_URL}/admin/campaigns/{cid}/assign-manager",
                   json={"manager_user_id": created["id"]})
        row = next(c for c in brand.get(f"{BASE_URL}/brand/campaigns").json() if c["id"] == cid)
        assert row["manager_name"] == created["name"]
        assert row["manager_phone"] == created["phone"]

    def test_reassigning_replaces_and_reports_the_previous(self, admin, brand, manager):
        _, first = manager
        second = admin.post(f"{BASE_URL}/admin/managers", json={
            "name": "Second Manager", "email": f"m2-{uuid.uuid4().hex[:6]}@e.com",
            "password": "Password123!", "phone": "+919876511111",
        }).json()
        cid = _live_campaign(brand, admin, "launch")

        admin.post(f"{BASE_URL}/admin/campaigns/{cid}/assign-manager",
                   json={"manager_user_id": first["id"]})
        r = admin.post(f"{BASE_URL}/admin/campaigns/{cid}/assign-manager",
                       json={"manager_user_id": second["id"]})
        assert r.status_code == 200, r.text
        assert r.json()["manager_name"] == "Second Manager"
        assert r.json()["reassigned_from"] == first["name"]

    def test_different_campaigns_carry_different_managers(self, admin, brand, manager):
        _, first = manager
        second = admin.post(f"{BASE_URL}/admin/managers", json={
            "name": "Other Manager", "email": f"m3-{uuid.uuid4().hex[:6]}@e.com",
            "password": "Password123!",
        }).json()
        one = _live_campaign(brand, admin, "launch")
        two = _live_campaign(brand, admin, "group_event")

        admin.post(f"{BASE_URL}/admin/campaigns/{one}/assign-manager",
                   json={"manager_user_id": first["id"]})
        admin.post(f"{BASE_URL}/admin/campaigns/{two}/assign-manager",
                   json={"manager_user_id": second["id"]})

        rows = {c["id"]: c for c in brand.get(f"{BASE_URL}/brand/campaigns").json()}
        assert rows[one]["manager_name"] == first["name"]
        assert rows[two]["manager_name"] == "Other Manager"

    def test_assigning_somebody_who_is_not_a_manager_is_404(self, admin, brand, creator):
        cs, cuid = creator
        cid = _live_campaign(brand, admin, "launch")
        r = admin.post(f"{BASE_URL}/admin/campaigns/{cid}/assign-manager",
                       json={"manager_user_id": cuid})
        assert r.status_code == 404, r.text

    def test_assignment_is_audited(self, admin, brand, manager):
        _, created = manager
        cid = _live_campaign(brand, admin, "launch")
        admin.post(f"{BASE_URL}/admin/campaigns/{cid}/assign-manager",
                   json={"manager_user_id": created["id"]})
        entries = admin.get(f"{BASE_URL}/admin/audit",
                            params={"subject_type": "campaign", "limit": 200}).json()
        assert any(e["action"] == "campaign.assign_manager" and e["subject_id"] == cid
                   for e in entries)


class TestManagerScope:
    def _assigned(self, admin, brand, manager, ctype="launch"):
        _, created = manager
        cid = _live_campaign(brand, admin, ctype)
        admin.post(f"{BASE_URL}/admin/campaigns/{cid}/assign-manager",
                   json={"manager_user_id": created["id"]})
        return cid

    def test_a_manager_sees_only_what_they_are_assigned(self, admin, brand, manager):
        ms, _ = manager
        mine = self._assigned(admin, brand, manager)
        # A campaign assigned to somebody else.
        other = admin.post(f"{BASE_URL}/admin/managers", json={
            "name": "Not Me", "email": f"m4-{uuid.uuid4().hex[:6]}@e.com",
            "password": "Password123!",
        }).json()
        theirs = _live_campaign(brand, admin, "launch")
        admin.post(f"{BASE_URL}/admin/campaigns/{theirs}/assign-manager",
                   json={"manager_user_id": other["id"]})

        ids = {c["id"] for c in ms.get(f"{BASE_URL}/manager/campaigns").json()}
        assert mine in ids
        assert theirs not in ids

    def test_another_managers_campaign_is_404_not_403(self, admin, brand, manager):
        ms, _ = manager
        other = admin.post(f"{BASE_URL}/admin/managers", json={
            "name": "Not Me", "email": f"m5-{uuid.uuid4().hex[:6]}@e.com",
            "password": "Password123!",
        }).json()
        theirs = _live_campaign(brand, admin, "launch")
        admin.post(f"{BASE_URL}/admin/campaigns/{theirs}/assign-manager",
                   json={"manager_user_id": other["id"]})

        assert ms.get(f"{BASE_URL}/manager/campaigns/{theirs}/slots").status_code == 404
        r = ms.post(f"{BASE_URL}/manager/campaigns/{theirs}/slots",
                    json={"starts_at": SLOT_TIME, "capacity": 4})
        assert r.status_code == 404

    def test_an_unassigned_campaign_is_invisible_to_every_manager(self, admin, brand, manager):
        ms, _ = manager
        loose = _live_campaign(brand, admin, "launch")
        assert ms.get(f"{BASE_URL}/manager/campaigns/{loose}/slots").status_code == 404

    def test_a_manager_gets_the_venue_details(self, admin, brand, manager):
        ms, created = manager
        pipeline.setup_brand(brand, admin)
        r = brand.post(f"{BASE_URL}/brand/campaigns", json=_body(
            "launch", venue_address="12 Church Street", on_site_contact="Riya",
        ))
        cid = r.json()["id"]
        pipeline.submit_campaign(brand, cid)
        pipeline.approve_campaign(admin, cid)
        admin.post(f"{BASE_URL}/admin/campaigns/{cid}/assign-manager",
                   json={"manager_user_id": created["id"]})

        row = next(c for c in ms.get(f"{BASE_URL}/manager/campaigns").json() if c["id"] == cid)
        assert row["venue_address"] == "12 Church Street"
        assert row["on_site_contact"] == "Riya"

    def test_brands_and_creators_cannot_reach_the_manager_router(self, brand, creator, anon):
        cs, _ = creator
        assert anon.get(f"{BASE_URL}/manager/campaigns").status_code == 401
        assert brand.get(f"{BASE_URL}/manager/campaigns").status_code == 403
        assert cs.get(f"{BASE_URL}/manager/campaigns").status_code == 403


# ---------- 3. Slots ----------

class TestSlotCreation:
    def _assigned(self, admin, brand, manager, ctype):
        _, created = manager
        cid = _live_campaign(brand, admin, ctype)
        admin.post(f"{BASE_URL}/admin/campaigns/{cid}/assign-manager",
                   json={"manager_user_id": created["id"]})
        return cid

    def test_a_manager_pre_creates_slots_on_an_event_campaign(self, admin, brand, manager):
        ms, _ = manager
        cid = self._assigned(admin, brand, manager, "group_event")
        r = ms.post(f"{BASE_URL}/manager/campaigns/{cid}/slots",
                    json={"starts_at": SLOT_TIME, "capacity": 6})
        assert r.status_code == 200, r.text
        slot = r.json()
        assert slot["capacity"] == 6
        assert slot["booked_count"] == 0
        assert slot["spots_left"] == 6

    def test_an_event_slot_has_to_be_on_the_event_day(self, admin, brand, manager):
        ms, _ = manager
        cid = self._assigned(admin, brand, manager, "launch")
        r = ms.post(f"{BASE_URL}/manager/campaigns/{cid}/slots",
                    json={"starts_at": "2027-10-15T11:00:00Z", "capacity": 4})
        assert r.status_code == 422, r.text

    def test_a_personal_table_window_needs_an_end(self, admin, brand, manager):
        ms, _ = manager
        cid = self._assigned(admin, brand, manager, "personal_table")
        r = ms.post(f"{BASE_URL}/manager/campaigns/{cid}/slots",
                    json={"starts_at": "2026-03-01T11:00:00Z", "capacity": 2})
        assert r.status_code == 422, r.text

    def test_a_window_has_to_sit_inside_the_campaign_dates(self, admin, brand, manager):
        ms, _ = manager
        cid = self._assigned(admin, brand, manager, "personal_table")
        r = ms.post(f"{BASE_URL}/manager/campaigns/{cid}/slots", json={
            "starts_at": "2028-01-01T11:00:00Z",
            "ends_at": "2028-01-01T13:00:00Z",
            "capacity": 2,
        })
        assert r.status_code == 422, r.text

    def test_a_valid_window_is_accepted(self, admin, brand, manager):
        ms, _ = manager
        cid = self._assigned(admin, brand, manager, "personal_table")
        r = ms.post(f"{BASE_URL}/manager/campaigns/{cid}/slots", json={
            "starts_at": "2026-03-01T11:00:00Z",
            "ends_at": "2026-03-01T13:00:00Z",
            "capacity": 2,
        })
        assert r.status_code == 200, r.text
        assert r.json()["ends_at"]

    def test_a_slot_has_to_end_after_it_starts(self, admin, brand, manager):
        ms, _ = manager
        cid = self._assigned(admin, brand, manager, "personal_table")
        r = ms.post(f"{BASE_URL}/manager/campaigns/{cid}/slots", json={
            "starts_at": "2026-03-01T13:00:00Z",
            "ends_at": "2026-03-01T11:00:00Z",
            "capacity": 2,
        })
        assert r.status_code == 422

    def test_slots_come_back_in_time_order(self, admin, brand, manager):
        ms, _ = manager
        cid = self._assigned(admin, brand, manager, "group_event")
        for hour in ("15", "11", "13"):
            ms.post(f"{BASE_URL}/manager/campaigns/{cid}/slots",
                    json={"starts_at": f"2027-09-01T{hour}:00:00Z", "capacity": 2})
        starts = [s["starts_at"] for s in
                  ms.get(f"{BASE_URL}/manager/campaigns/{cid}/slots").json()["slots"]]
        assert starts == sorted(starts)

    def test_an_empty_slot_can_be_deleted(self, admin, brand, manager):
        ms, _ = manager
        cid = self._assigned(admin, brand, manager, "group_event")
        slot = ms.post(f"{BASE_URL}/manager/campaigns/{cid}/slots",
                       json={"starts_at": SLOT_TIME, "capacity": 2}).json()
        assert ms.delete(f"{BASE_URL}/manager/slots/{slot['id']}").status_code == 200


class TestBooking:
    def _ready_creator(self, admin, brand, campaign_id, quoted=5000):
        """A creator on the campaign, sitting at commercial_agreed."""
        cs = requests.Session()
        _, user = _register(cs, "creator")
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, user["id"])
        collab_id = pipeline.apply_to_campaign(cs, campaign_id, quoted_rate=quoted)
        pipeline.step(admin, brand, collab_id, "verified")
        pipeline.step(admin, brand, collab_id, "accepted")
        pipeline.step(admin, brand, collab_id, "commercial_agreed", agreed_amount=quoted)
        return cs, collab_id

    def _campaign_with_slot(self, admin, brand, manager, capacity=1, needed=5):
        _, created = manager
        ms, _ = manager
        cid = _live_campaign(brand, admin, "group_event", creators_needed=needed)
        admin.post(f"{BASE_URL}/admin/campaigns/{cid}/assign-manager",
                   json={"manager_user_id": created["id"]})
        slot = ms.post(f"{BASE_URL}/manager/campaigns/{cid}/slots",
                       json={"starts_at": SLOT_TIME, "capacity": capacity}).json()
        return cid, slot

    def test_booking_moves_the_collaboration_to_slot_booked(self, admin, brand, manager):
        cid, slot = self._campaign_with_slot(admin, brand, manager, capacity=2)
        cs, collab_id = self._ready_creator(admin, brand, cid)

        r = cs.post(f"{BASE_URL}/campaigns/slots/{slot['id']}/book")
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["state"] == "slot_booked"
        assert out["slot"]["booked_count"] == 1
        assert pipeline.current_state(admin, collab_id) == "slot_booked"

    def test_the_last_place_goes_to_exactly_one_of_two_creators(self, admin, brand, manager):
        # The race this whole model exists to survive.
        cid, slot = self._campaign_with_slot(admin, brand, manager, capacity=1)
        first, _ = self._ready_creator(admin, brand, cid)
        second, _ = self._ready_creator(admin, brand, cid)

        results = {}

        def book(name, session):
            results[name] = session.post(
                f"{BASE_URL}/campaigns/slots/{slot['id']}/book"
            ).status_code

        threads = [
            threading.Thread(target=book, args=("a", first)),
            threading.Thread(target=book, args=("b", second)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        codes = sorted(results.values())
        assert codes == [200, 409], f"expected one winner and one refusal, got {results}"

        rows = admin.get(f"{BASE_URL}/manager/campaigns/{cid}/slots").json()["slots"]
        booked = next(s for s in rows if s["id"] == slot["id"])
        assert booked["booked_count"] == 1, "capacity must never be exceeded"

    def test_a_full_slot_is_refused(self, admin, brand, manager):
        cid, slot = self._campaign_with_slot(admin, brand, manager, capacity=1)
        first, _ = self._ready_creator(admin, brand, cid)
        second, _ = self._ready_creator(admin, brand, cid)

        assert first.post(f"{BASE_URL}/campaigns/slots/{slot['id']}/book").status_code == 200
        r = second.post(f"{BASE_URL}/campaigns/slots/{slot['id']}/book")
        assert r.status_code == 409, r.text
        assert "filled" in r.text.lower()

    def test_booking_before_the_fee_is_agreed_is_refused(self, admin, brand, manager):
        cid, slot = self._campaign_with_slot(admin, brand, manager, capacity=2)
        cs = requests.Session()
        _, user = _register(cs, "creator")
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, user["id"])
        pipeline.apply_to_campaign(cs, cid)

        r = cs.post(f"{BASE_URL}/campaigns/slots/{slot['id']}/book")
        assert r.status_code == 409, r.text
        assert "fee is agreed" in r.text.lower()

    def test_a_creator_not_on_the_campaign_cannot_book(self, admin, brand, manager):
        cid, slot = self._campaign_with_slot(admin, brand, manager, capacity=2)
        outsider = requests.Session()
        _, user = _register(outsider, "creator")
        pipeline.complete_creator_profile(outsider)
        pipeline.verify_creator(admin, user["id"])
        assert outsider.post(
            f"{BASE_URL}/campaigns/slots/{slot['id']}/book"
        ).status_code == 404

    def test_booking_twice_is_refused(self, admin, brand, manager):
        cid, slot = self._campaign_with_slot(admin, brand, manager, capacity=5)
        cs, _ = self._ready_creator(admin, brand, cid)
        assert cs.post(f"{BASE_URL}/campaigns/slots/{slot['id']}/book").status_code == 200
        r = cs.post(f"{BASE_URL}/campaigns/slots/{slot['id']}/book")
        assert r.status_code == 409, r.text

    def test_reverting_gives_the_seat_back(self, admin, brand, manager):
        cid, slot = self._campaign_with_slot(admin, brand, manager, capacity=1)
        cs, collab_id = self._ready_creator(admin, brand, cid)
        assert cs.post(f"{BASE_URL}/campaigns/slots/{slot['id']}/book").status_code == 200

        r = admin.post(f"{BASE_URL}/admin/collaborations/{collab_id}/revert",
                       json={"reason": "Booked the wrong day"})
        assert r.status_code == 200, r.text

        rows = admin.get(f"{BASE_URL}/manager/campaigns/{cid}/slots").json()["slots"]
        assert next(s for s in rows if s["id"] == slot["id"])["booked_count"] == 0

        # And the freed seat is genuinely bookable again.
        other, _ = self._ready_creator(admin, brand, cid)
        assert other.post(f"{BASE_URL}/campaigns/slots/{slot['id']}/book").status_code == 200

    def test_cancelling_gives_the_seat_back(self, admin, brand, manager):
        cid, slot = self._campaign_with_slot(admin, brand, manager, capacity=1)
        cs, collab_id = self._ready_creator(admin, brand, cid)
        cs.post(f"{BASE_URL}/campaigns/slots/{slot['id']}/book")

        admin.post(f"{BASE_URL}/admin/collaborations/{collab_id}/cancel", json={
            "reason": "Creator pulled out", "cancellation_type": "creator_no_show",
        })
        rows = admin.get(f"{BASE_URL}/manager/campaigns/{cid}/slots").json()["slots"]
        assert next(s for s in rows if s["id"] == slot["id"])["booked_count"] == 0

    def test_a_booked_slot_cannot_be_deleted(self, admin, brand, manager):
        ms, _ = manager
        cid, slot = self._campaign_with_slot(admin, brand, manager, capacity=2)
        cs, _ = self._ready_creator(admin, brand, cid)
        cs.post(f"{BASE_URL}/campaigns/slots/{slot['id']}/book")

        r = ms.delete(f"{BASE_URL}/manager/slots/{slot['id']}")
        assert r.status_code == 409, r.text


# ---------- 4. What the creator sees ----------

class TestCreatorView:
    def _campaign(self, admin, brand, manager):
        _, created = manager
        pipeline.setup_brand(brand, admin)
        r = brand.post(f"{BASE_URL}/brand/campaigns", json=_body(
            "group_event",
            venue_address="12 Church Street, Bengaluru",
            venue_instructions="Ask for the events desk",
            on_site_contact="Riya · +919876543210",
        ))
        cid = r.json()["id"]
        pipeline.submit_campaign(brand, cid)
        pipeline.approve_campaign(admin, cid)
        admin.post(f"{BASE_URL}/admin/campaigns/{cid}/assign-manager",
                   json={"manager_user_id": created["id"]})
        return cid, created

    def test_an_applicant_does_not_get_the_venue_or_the_phone_number(
        self, admin, brand, manager, creator
    ):
        cid, _ = self._campaign(admin, brand, manager)
        cs, cuid = creator
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, cuid)
        pipeline.apply_to_campaign(cs, cid)

        detail = cs.get(f"{BASE_URL}/campaigns/{cid}").json()
        assert detail["has_applied"] is True
        assert detail["coordination"] is None, (
            "a staff phone number is not applicant information"
        )

    def test_an_accepted_creator_gets_the_manager_and_the_venue(
        self, admin, brand, manager, creator
    ):
        cid, created = self._campaign(admin, brand, manager)
        cs, cuid = creator
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, cuid)
        collab_id = pipeline.apply_to_campaign(cs, cid)
        pipeline.step(admin, brand, collab_id, "verified")
        pipeline.step(admin, brand, collab_id, "accepted")

        detail = cs.get(f"{BASE_URL}/campaigns/{cid}").json()
        block = detail["coordination"]
        assert block, "an accepted creator has to be able to find the place"
        assert block["manager_name"] == created["name"]
        assert block["manager_phone"] == created["phone"]
        assert block["venue_address"] == "12 Church Street, Bengaluru"
        assert block["venue_instructions"] == "Ask for the events desk"
        assert block["on_site_contact"] == "Riya · +919876543210"
        # The manager's email is internal.
        assert "manager_email" not in block

    def test_the_open_feed_never_carries_the_venue(self, admin, brand, manager, creator):
        cid, _ = self._campaign(admin, brand, manager)
        cs, cuid = creator
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, cuid)
        row = next(c for c in cs.get(f"{BASE_URL}/campaigns").json() if c["id"] == cid)
        for leaked in ("venue_address", "manager_phone", "on_site_contact", "manager_email"):
            assert leaked not in row

    def test_slots_are_only_visible_once_accepted(self, admin, brand, manager, creator):
        cid, _ = self._campaign(admin, brand, manager)
        ms, _ = manager
        ms.post(f"{BASE_URL}/manager/campaigns/{cid}/slots",
                json={"starts_at": SLOT_TIME, "capacity": 4})

        cs, cuid = creator
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, cuid)
        collab_id = pipeline.apply_to_campaign(cs, cid)
        assert cs.get(f"{BASE_URL}/campaigns/{cid}/slots").status_code == 404

        pipeline.step(admin, brand, collab_id, "verified")
        pipeline.step(admin, brand, collab_id, "accepted")
        r = cs.get(f"{BASE_URL}/campaigns/{cid}/slots")
        assert r.status_code == 200, r.text
        assert len(r.json()["slots"]) == 1
        # Not bookable until the fee is agreed.
        assert r.json()["can_book"] is False
