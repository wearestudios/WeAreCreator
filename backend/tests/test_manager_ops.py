"""Backend tests for the campaign manager's day.

Everything here is scoped through the campaign: a manager touches a creator
because they are running the day that creator is booked onto. Most of these
tests are therefore about what a manager *cannot* reach.
"""
import csv
import io
import os
import uuid

import pytest
import requests

import pipeline  # tests/ is on sys.path (no __init__.py, pytest prepend mode)

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "creators@wearemonk.in")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "WeAreMonk@2026")

EVENT_DAY = "2027-09-01T00:00:00Z"
SLOT_TIME = "2027-09-01T11:00:00Z"
LATER_SLOT = "2027-09-01T15:00:00Z"


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
def anon():
    return requests.Session()


@pytest.fixture
def brand():
    s = requests.Session()
    _register(s, "brand")
    return s


def _make_manager(admin, name="Manager"):
    email = f"mgr-{uuid.uuid4().hex[:8]}@example.com"
    password = "ManagerPass123!"
    created = admin.post(f"{BASE_URL}/admin/managers", json={
        "name": f"{name} {uuid.uuid4().hex[:4]}",
        "email": email, "password": password, "phone": "+919876500000",
    }).json()
    s = requests.Session()
    assert s.post(f"{BASE_URL}/auth/login",
                  json={"email": email, "password": password}).status_code == 200
    return s, created


@pytest.fixture
def manager(admin):
    return _make_manager(admin)


def _event_campaign(brand_s, admin_s, **overrides):
    """A live group_event campaign, ready to have slots hung off it."""
    pipeline.setup_brand(brand_s, admin_s)
    body = {
        "title": f"Day-{uuid.uuid4().hex[:6]}", "brief": "b", "deliverables": "d",
        "budget_per_creator": 5000, "category": "fnb", "area": "Indiranagar",
        "creators_needed": 10, "campaign_type": "group_event",
        "event_date": EVENT_DAY, "status": "draft",
        "venue_address": "12 Church Street", "on_site_contact": "Riya",
    }
    body.update(overrides)
    r = brand_s.post(f"{BASE_URL}/brand/campaigns", json=body)
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    pipeline.submit_campaign(brand_s, cid)
    pipeline.approve_campaign(admin_s, cid)
    return cid


@pytest.fixture
def run(admin, brand, manager):
    """A campaign assigned to the manager, with a helper to add booked creators."""
    ms, created = manager
    cid = _event_campaign(brand, admin)
    admin.post(f"{BASE_URL}/admin/campaigns/{cid}/assign-manager",
               json={"manager_user_id": created["id"]})

    def add_slot(starts_at=SLOT_TIME, capacity=4):
        r = ms.post(f"{BASE_URL}/manager/slots", json={
            "campaign_id": cid, "starts_at": starts_at, "capacity": capacity,
        })
        assert r.status_code == 200, r.text
        return r.json()

    def add_creator(slot=None, booked=True):
        """A creator on the campaign, booked onto `slot` unless told otherwise."""
        cs = requests.Session()
        _, user = _register(cs, "creator")
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, user["id"])
        collab_id = pipeline.apply_to_campaign(cs, cid)
        pipeline.step(admin, brand, collab_id, "verified")
        pipeline.step(admin, brand, collab_id, "accepted")
        if not booked:
            return cs, collab_id
        pipeline.step(admin, brand, collab_id, "commercial_agreed", agreed_amount=5000)
        assert cs.post(f"{BASE_URL}/campaigns/slots/{slot['id']}/book").status_code == 200
        return cs, collab_id

    return {"campaign_id": cid, "manager": ms, "manager_row": created,
            "add_slot": add_slot, "add_creator": add_creator}


# ---------- 1. Scope ----------

class TestScope:
    def test_the_router_is_staff_only(self, anon, brand, run):
        cid = run["campaign_id"]
        cs = requests.Session()
        _register(cs, "creator")
        for path in (f"/manager/campaigns/{cid}/roster",
                     f"/manager/campaigns/{cid}/daysheet"):
            assert anon.get(f"{BASE_URL}{path}").status_code == 401
            assert brand.get(f"{BASE_URL}{path}").status_code == 403
            assert cs.get(f"{BASE_URL}{path}").status_code == 403

    def test_another_managers_campaign_is_invisible(self, admin, brand, run):
        other_ms, _ = _make_manager(admin, "Other")
        cid = run["campaign_id"]
        slot = run["add_slot"]()
        _, collab_id = run["add_creator"](slot)

        assert other_ms.get(f"{BASE_URL}/manager/campaigns/{cid}/roster").status_code == 404
        assert other_ms.get(f"{BASE_URL}/manager/campaigns/{cid}/daysheet").status_code == 404
        assert other_ms.post(f"{BASE_URL}/manager/campaigns/{cid}/broadcast",
                             json={"message": "hello there"}).status_code == 404
        assert other_ms.post(
            f"{BASE_URL}/manager/collaborations/{collab_id}/check-in"
        ).status_code == 404
        assert other_ms.patch(f"{BASE_URL}/manager/slots/{slot['id']}",
                              json={"capacity": 9}).status_code == 404

    def test_a_manager_cannot_create_slots_on_a_campaign_they_do_not_run(self, admin, brand, run):
        other_ms, _ = _make_manager(admin, "Other")
        r = other_ms.post(f"{BASE_URL}/manager/slots", json={
            "campaign_id": run["campaign_id"], "starts_at": SLOT_TIME, "capacity": 2,
        })
        assert r.status_code == 404, r.text

    def test_an_admin_reaches_everything(self, admin, run):
        cid = run["campaign_id"]
        assert admin.get(f"{BASE_URL}/manager/campaigns/{cid}/roster").status_code == 200


# ---------- 2. Campaigns and slots ----------

class TestCampaignsAndSlots:
    def test_my_campaigns_carry_slot_fill_counts(self, run):
        ms, cid = run["manager"], run["campaign_id"]
        slot = run["add_slot"](capacity=4)
        run["add_creator"](slot)

        row = next(c for c in ms.get(f"{BASE_URL}/manager/campaigns").json()
                   if c["id"] == cid)
        assert row["slot_count"] == 1
        assert row["slot_capacity"] == 4
        assert row["slot_booked"] == 1

    def test_a_slot_can_be_created_by_body(self, run):
        slot = run["add_slot"](capacity=3)
        assert slot["capacity"] == 3
        assert slot["spots_left"] == 3

    def test_capacity_can_be_raised(self, run):
        ms = run["manager"]
        slot = run["add_slot"](capacity=2)
        r = ms.patch(f"{BASE_URL}/manager/slots/{slot['id']}", json={"capacity": 6})
        assert r.status_code == 200, r.text
        assert r.json()["capacity"] == 6
        assert r.json()["spots_left"] == 6

    def test_capacity_cannot_shrink_below_what_is_booked(self, run):
        ms = run["manager"]
        slot = run["add_slot"](capacity=2)
        run["add_creator"](slot)
        r = ms.patch(f"{BASE_URL}/manager/slots/{slot['id']}", json={"capacity": 0})
        assert r.status_code in (409, 422), r.text
        r = ms.patch(f"{BASE_URL}/manager/slots/{slot['id']}", json={"capacity": 1})
        assert r.status_code == 200, "one booked, capacity one is fine"

    def test_moving_a_slot_moves_the_people_on_it(self, run, admin):
        ms = run["manager"]
        slot = run["add_slot"]()
        _, collab_id = run["add_creator"](slot)

        r = ms.patch(f"{BASE_URL}/manager/slots/{slot['id']}",
                     json={"starts_at": LATER_SLOT})
        assert r.status_code == 200, r.text
        assert r.json()["collaborations_moved"] == 1

        row = next(x for x in ms.get(
            f"{BASE_URL}/manager/campaigns/{run['campaign_id']}/roster"
        ).json()["roster"] if x["collaboration_id"] == collab_id)
        assert row["slot_time"].startswith("2027-09-01T15:00")

    def test_a_slot_cannot_be_moved_off_the_event_day(self, run):
        ms = run["manager"]
        slot = run["add_slot"]()
        r = ms.patch(f"{BASE_URL}/manager/slots/{slot['id']}",
                     json={"starts_at": "2027-10-01T11:00:00Z"})
        assert r.status_code == 422, r.text

    def test_an_empty_edit_is_refused(self, run):
        ms = run["manager"]
        slot = run["add_slot"]()
        assert ms.patch(f"{BASE_URL}/manager/slots/{slot['id']}", json={}).status_code == 422

    def test_an_unbooked_slot_can_be_deleted(self, run):
        ms = run["manager"]
        slot = run["add_slot"]()
        assert ms.delete(f"{BASE_URL}/manager/slots/{slot['id']}").status_code == 200

    def test_a_booked_slot_cannot(self, run):
        ms = run["manager"]
        slot = run["add_slot"]()
        run["add_creator"](slot)
        assert ms.delete(f"{BASE_URL}/manager/slots/{slot['id']}").status_code == 409


# ---------- 3. Roster and daysheet ----------

class TestRoster:
    def test_it_shows_who_is_coming_and_how_to_reach_them(self, run):
        ms, cid = run["manager"], run["campaign_id"]
        slot = run["add_slot"]()
        _, collab_id = run["add_creator"](slot)

        r = ms.get(f"{BASE_URL}/manager/campaigns/{cid}/roster")
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["venue_address"] == "12 Church Street"
        assert out["on_site_contact"] == "Riya"

        row = next(x for x in out["roster"] if x["collaboration_id"] == collab_id)
        assert row["name"]
        assert row["instagram_handle"]
        assert row["slot_time"]
        assert row["attendance"] == "expected"

    def test_an_applicant_is_not_on_the_roster(self, run, admin, brand):
        ms, cid = run["manager"], run["campaign_id"]
        cs = requests.Session()
        _, user = _register(cs, "creator")
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, user["id"])
        collab_id = pipeline.apply_to_campaign(cs, cid)

        roster = ms.get(f"{BASE_URL}/manager/campaigns/{cid}/roster").json()["roster"]
        assert not any(x["collaboration_id"] == collab_id for x in roster), (
            "nobody is expecting an applicant at a venue"
        )

    def test_the_counts_add_up(self, run):
        ms, cid = run["manager"], run["campaign_id"]
        slot = run["add_slot"](capacity=4)
        _, first = run["add_creator"](slot)
        run["add_creator"](slot)
        ms.post(f"{BASE_URL}/manager/collaborations/{first}/check-in")

        out = ms.get(f"{BASE_URL}/manager/campaigns/{cid}/roster").json()
        assert out["attended"] == 1
        assert out["expected"] == 1

    def test_the_daysheet_is_csv_with_a_filename(self, run):
        ms, cid = run["manager"], run["campaign_id"]
        slot = run["add_slot"]()
        run["add_creator"](slot)

        r = ms.get(f"{BASE_URL}/manager/campaigns/{cid}/daysheet")
        assert r.status_code == 200, r.text
        assert "text/csv" in r.headers["content-type"]
        assert "attachment" in r.headers["content-disposition"]

        rows = list(csv.reader(io.StringIO(r.text)))
        assert rows[0] == ["Slot time", "Name", "Instagram", "Phone",
                           "Attendance", "State"]
        assert len(rows) == 2, "header plus the one creator"
        assert rows[1][4] == "expected"

    def test_a_comma_in_a_name_does_not_become_two_columns(self, run, admin, brand):
        ms, cid = run["manager"], run["campaign_id"]
        slot = run["add_slot"]()
        cs = requests.Session()
        _, user = _register(cs, "creator")
        pipeline.complete_creator_profile(cs)
        # A real name that would break a hand-rolled join.
        cs.put(f"{BASE_URL}/creator/profile", json={
            "name": "Rao, Priya", "instagram_handle": f"@c_{uuid.uuid4().hex[:6]}",
            "city": "Bengaluru", "niches": ["cafe"], "follower_count": 1000,
            "base_rate": 5000, **pipeline.PAYOUT_DETAILS,
        })
        pipeline.verify_creator(admin, user["id"])
        collab_id = pipeline.apply_to_campaign(cs, cid)
        pipeline.step(admin, brand, collab_id, "verified")
        pipeline.step(admin, brand, collab_id, "accepted")
        pipeline.step(admin, brand, collab_id, "commercial_agreed", agreed_amount=5000)
        cs.post(f"{BASE_URL}/campaigns/slots/{slot['id']}/book")

        r = ms.get(f"{BASE_URL}/manager/campaigns/{cid}/daysheet")
        rows = list(csv.reader(io.StringIO(r.text)))
        assert any(row[1] == "Rao, Priya" for row in rows[1:]), rows


# ---------- 4. On the day ----------

class TestCheckIn:
    def test_it_marks_the_creator_attended(self, run, admin):
        ms = run["manager"]
        slot = run["add_slot"]()
        _, collab_id = run["add_creator"](slot)

        r = ms.post(f"{BASE_URL}/manager/collaborations/{collab_id}/check-in")
        assert r.status_code == 200, r.text
        assert r.json()["state"] == "attended"
        assert pipeline.current_state(admin, collab_id) == "attended"

    def test_checking_in_twice_is_refused(self, run):
        ms = run["manager"]
        slot = run["add_slot"]()
        _, collab_id = run["add_creator"](slot)
        assert ms.post(f"{BASE_URL}/manager/collaborations/{collab_id}/check-in").status_code == 200
        assert ms.post(f"{BASE_URL}/manager/collaborations/{collab_id}/check-in").status_code == 409

    def test_somebody_without_a_slot_cannot_be_checked_in(self, run):
        ms = run["manager"]
        _, collab_id = run["add_creator"](booked=False)
        r = ms.post(f"{BASE_URL}/manager/collaborations/{collab_id}/check-in")
        assert r.status_code == 409, r.text

    def test_it_is_audited(self, run, admin):
        ms = run["manager"]
        slot = run["add_slot"]()
        _, collab_id = run["add_creator"](slot)
        ms.post(f"{BASE_URL}/manager/collaborations/{collab_id}/check-in")

        entries = admin.get(f"{BASE_URL}/admin/audit",
                            params={"subject_id": collab_id, "limit": 100}).json()
        row = next(e for e in entries if e["action"] == "collaboration.check_in")
        assert row["actor_role"] == "campaign_manager"


class TestNoShow:
    def test_it_flags_without_cancelling(self, run, admin):
        ms = run["manager"]
        slot = run["add_slot"]()
        _, collab_id = run["add_creator"](slot)

        r = ms.post(f"{BASE_URL}/manager/collaborations/{collab_id}/no-show",
                    json={"note": "Waited an hour, no answer on the phone"})
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["no_show_reported"] is True
        # The collaboration is left where it is — ending it is the admin's call.
        assert out["state"] == "slot_booked"
        assert pipeline.current_state(admin, collab_id) == "slot_booked"

    def test_a_note_is_required(self, run):
        ms = run["manager"]
        slot = run["add_slot"]()
        _, collab_id = run["add_creator"](slot)
        assert ms.post(f"{BASE_URL}/manager/collaborations/{collab_id}/no-show",
                       json={}).status_code == 422
        assert ms.post(f"{BASE_URL}/manager/collaborations/{collab_id}/no-show",
                       json={"note": ""}).status_code == 422

    def test_the_flag_feeds_the_admin_cancel_path(self, run, admin):
        ms = run["manager"]
        slot = run["add_slot"]()
        _, collab_id = run["add_creator"](slot)
        ms.post(f"{BASE_URL}/manager/collaborations/{collab_id}/no-show",
                json={"note": "Never arrived"})

        # The admin picks it up and closes it as a no-show, which is the one
        # cancellation type that doesn't raise a settlement question.
        r = admin.post(f"{BASE_URL}/admin/collaborations/{collab_id}/cancel", json={
            "reason": "Reported as a no-show by the manager",
            "cancellation_type": "creator_no_show",
        })
        assert r.status_code == 200, r.text
        assert r.json()["settlement_review_needed"] is False

    def test_the_note_reaches_the_audit_log(self, run, admin):
        ms = run["manager"]
        slot = run["add_slot"]()
        _, collab_id = run["add_creator"](slot)
        ms.post(f"{BASE_URL}/manager/collaborations/{collab_id}/no-show",
                json={"note": "Waited an hour at the door"})

        entries = admin.get(f"{BASE_URL}/admin/audit",
                            params={"subject_id": collab_id, "limit": 100}).json()
        row = next(e for e in entries if e["action"] == "collaboration.no_show")
        assert "Waited an hour" in row["note"]

    def test_somebody_who_never_booked_cannot_be_a_no_show(self, run):
        ms = run["manager"]
        _, collab_id = run["add_creator"](booked=False)
        r = ms.post(f"{BASE_URL}/manager/collaborations/{collab_id}/no-show",
                    json={"note": "Not booked in the first place"})
        assert r.status_code == 409, r.text


class TestReschedule:
    def test_it_moves_the_creator_and_the_seats(self, run):
        ms, cid = run["manager"], run["campaign_id"]
        first = run["add_slot"](SLOT_TIME, capacity=1)
        second = run["add_slot"](LATER_SLOT, capacity=1)
        _, collab_id = run["add_creator"](first)

        r = ms.post(f"{BASE_URL}/manager/collaborations/{collab_id}/reschedule",
                    json={"slot_id": second["id"], "reason": "Creator asked for later"})
        assert r.status_code == 200, r.text
        assert r.json()["slot"]["id"] == second["id"]

        slots = {s["id"]: s for s in
                 ms.get(f"{BASE_URL}/manager/campaigns/{cid}/slots").json()["slots"]}
        assert slots[first["id"]]["booked_count"] == 0, "the old seat goes back on sale"
        assert slots[second["id"]]["booked_count"] == 1

    def test_a_full_target_is_refused_and_the_original_is_kept(self, run):
        ms, cid = run["manager"], run["campaign_id"]
        first = run["add_slot"](SLOT_TIME, capacity=1)
        second = run["add_slot"](LATER_SLOT, capacity=1)
        _, mine = run["add_creator"](first)
        run["add_creator"](second)  # fills the target

        r = ms.post(f"{BASE_URL}/manager/collaborations/{mine}/reschedule",
                    json={"slot_id": second["id"]})
        assert r.status_code == 409, r.text

        slots = {s["id"]: s for s in
                 ms.get(f"{BASE_URL}/manager/campaigns/{cid}/slots").json()["slots"]}
        assert slots[first["id"]]["booked_count"] == 1, (
            "a refused move must not leave the creator with no seat at all"
        )

    def test_moving_onto_the_same_slot_is_refused(self, run):
        ms = run["manager"]
        slot = run["add_slot"](capacity=2)
        _, collab_id = run["add_creator"](slot)
        r = ms.post(f"{BASE_URL}/manager/collaborations/{collab_id}/reschedule",
                    json={"slot_id": slot["id"]})
        assert r.status_code == 409, r.text

    def test_another_campaigns_slot_is_not_a_target(self, run, admin, brand):
        ms = run["manager"]
        slot = run["add_slot"]()
        _, collab_id = run["add_creator"](slot)

        # A slot on a different campaign, run by the same manager.
        other_cid = _event_campaign(brand, admin)
        admin.post(f"{BASE_URL}/admin/campaigns/{other_cid}/assign-manager",
                   json={"manager_user_id": run["manager_row"]["id"]})
        foreign = ms.post(f"{BASE_URL}/manager/slots", json={
            "campaign_id": other_cid, "starts_at": SLOT_TIME, "capacity": 4,
        }).json()

        r = ms.post(f"{BASE_URL}/manager/collaborations/{collab_id}/reschedule",
                    json={"slot_id": foreign["id"]})
        assert r.status_code == 404, r.text

    def test_somebody_unbooked_has_nothing_to_move(self, run):
        ms = run["manager"]
        slot = run["add_slot"]()
        _, collab_id = run["add_creator"](booked=False)
        r = ms.post(f"{BASE_URL}/manager/collaborations/{collab_id}/reschedule",
                    json={"slot_id": slot["id"]})
        assert r.status_code == 409, r.text

    def test_it_is_audited(self, run, admin):
        ms = run["manager"]
        first = run["add_slot"](SLOT_TIME, capacity=1)
        second = run["add_slot"](LATER_SLOT, capacity=1)
        _, collab_id = run["add_creator"](first)
        ms.post(f"{BASE_URL}/manager/collaborations/{collab_id}/reschedule",
                json={"slot_id": second["id"], "reason": "Traffic"})

        entries = admin.get(f"{BASE_URL}/admin/audit",
                            params={"subject_id": collab_id, "limit": 100}).json()
        assert any(e["action"] == "collaboration.reschedule" for e in entries)


# ---------- 5. Broadcast ----------

class TestBroadcast:
    def test_it_reaches_everyone_confirmed(self, run):
        ms, cid = run["manager"], run["campaign_id"]
        slot = run["add_slot"](capacity=4)
        run["add_creator"](slot)
        run["add_creator"](slot)

        r = ms.post(f"{BASE_URL}/manager/campaigns/{cid}/broadcast",
                    json={"message": "Parking is round the back today."})
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["recipients"] == 2
        assert out["delivered"] + out["failed"] == out["recipients"]
        assert len(out["results"]) == 2

    def test_every_recipient_gets_the_in_app_copy(self, run):
        ms, cid = run["manager"], run["campaign_id"]
        slot = run["add_slot"]()
        cs, _ = run["add_creator"](slot)

        ms.post(f"{BASE_URL}/manager/campaigns/{cid}/broadcast",
                json={"message": "Doors open at 11 sharp."})
        notes = cs.get(f"{BASE_URL}/notifications").json()["notifications"]
        assert any(n["event"] == "campaign_broadcast" and "11 sharp" in n["body"]
                   for n in notes)

    def test_an_applicant_is_not_messaged(self, run, admin):
        ms, cid = run["manager"], run["campaign_id"]
        slot = run["add_slot"]()
        run["add_creator"](slot)

        outsider = requests.Session()
        _, user = _register(outsider, "creator")
        pipeline.complete_creator_profile(outsider)
        pipeline.verify_creator(admin, user["id"])
        pipeline.apply_to_campaign(outsider, cid)

        out = ms.post(f"{BASE_URL}/manager/campaigns/{cid}/broadcast",
                      json={"message": "Only for the confirmed list"}).json()
        assert out["recipients"] == 1

    def test_an_empty_audience_is_refused(self, run):
        ms, cid = run["manager"], run["campaign_id"]
        r = ms.post(f"{BASE_URL}/manager/campaigns/{cid}/broadcast",
                    json={"message": "Anybody out there?"})
        assert r.status_code == 409, r.text

    def test_a_message_is_required(self, run):
        ms, cid = run["manager"], run["campaign_id"]
        assert ms.post(f"{BASE_URL}/manager/campaigns/{cid}/broadcast",
                       json={}).status_code == 422

    def test_it_is_audited_once_with_the_message(self, run, admin):
        ms, cid = run["manager"], run["campaign_id"]
        slot = run["add_slot"]()
        run["add_creator"](slot)
        ms.post(f"{BASE_URL}/manager/campaigns/{cid}/broadcast",
                json={"message": "Bring your own ring light"})

        entries = admin.get(f"{BASE_URL}/admin/audit",
                            params={"subject_id": cid, "limit": 100}).json()
        rows = [e for e in entries if e["action"] == "campaign.broadcast"]
        assert len(rows) == 1
        assert "ring light" in rows[0]["note"]


# ---------- 6. The manager's own alerts ----------

class TestManagerNotifications:
    def _notes(self, ms):
        return ms.get(f"{BASE_URL}/notifications").json()["notifications"]

    def test_booking_tells_the_manager(self, run):
        ms = run["manager"]
        slot = run["add_slot"]()
        run["add_creator"](slot)
        assert any(n["event"] == "manager_slot_booked" for n in self._notes(ms))

    def test_cancelling_tells_the_manager_the_seat_is_free(self, run, admin):
        ms = run["manager"]
        slot = run["add_slot"]()
        _, collab_id = run["add_creator"](slot)
        admin.post(f"{BASE_URL}/admin/collaborations/{collab_id}/cancel", json={
            "reason": "Creator pulled out the night before",
            "cancellation_type": "creator_no_show",
        })
        assert any(n["event"] == "manager_slot_released" for n in self._notes(ms))

    def test_reverting_tells_the_manager_too(self, run, admin):
        ms = run["manager"]
        slot = run["add_slot"]()
        _, collab_id = run["add_creator"](slot)
        admin.post(f"{BASE_URL}/admin/collaborations/{collab_id}/revert",
                   json={"reason": "Booked the wrong day"})
        assert any(n["event"] == "manager_slot_released" for n in self._notes(ms))
