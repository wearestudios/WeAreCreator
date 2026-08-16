"""The brand manager: one named person per brand, and what they can reach.

Three things are under test here, and they pull against each other on purpose:
the brand manager can do more than a brand could before (pause, invite, settle
a fee, mark attendance), sees less than a brand could before (no creator
contact details, at any stage), and can reach nothing outside their own brand.
"""
import os
import random
import re
import subprocess
import time
import uuid

import pytest
import requests

import pipeline

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "creators@wearemonk.in")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "WeAreMonk@2026")

# Anything a brand must never be handed about a creator. Mirrors the tuple in
# server.py; asserted here against real HTTP responses rather than serialisers.
FORBIDDEN = (
    "phone", "whatsapp", "whatsapp_number", "email", "contact_phone",
    "contact_email", "full_address", "address", "payout_upi",
    "payout_account_name", "pan", "gstin",
)

# Simulation mode writes the login code to the backend log rather than sending
# it. Same approach as tests/test_otp_auth.py — the OTP flow is the only way to
# exercise a real brand signup, and there is no endpoint that hands the code back.
LOG_PATH = "/var/log/supervisor/backend.err.log"


def _read_otp_from_log(phone: str, timeout: float = 5.0) -> str:
    deadline = time.time() + timeout
    pattern = re.compile(rf"OTP for {re.escape(phone)} is (\d{{6}})")
    while time.time() < deadline:
        try:
            out = subprocess.check_output(
                ["grep", f"OTP for {phone}", LOG_PATH],
                text=True,
                stderr=subprocess.DEVNULL,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            out = ""
        matches = pattern.findall(out)
        if matches:
            return matches[-1]
        time.sleep(0.4)
    return ""


def _register(session, role):
    email = f"TEST_{role}-{uuid.uuid4().hex[:10]}@example.com"
    r = session.post(
        f"{BASE_URL}/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "name": f"Test {role.title()}",
            "role": role,
        },
    )
    assert r.status_code == 200, r.text
    return email, r.json()


@pytest.fixture
def admin():
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert r.status_code == 200, r.text
    return s


@pytest.fixture
def brand(admin):
    s = requests.Session()
    _register(s, "brand")
    uid = pipeline.setup_brand(s, admin)
    return s, uid


@pytest.fixture
def creator():
    s = requests.Session()
    _register(s, "creator")
    return s, pipeline.user_id_of(s)


@pytest.fixture
def applied(admin, brand, creator):
    """A verified creator sitting on a live campaign, awaiting a decision."""
    bs, brand_uid = brand
    cs, creator_uid = creator
    pipeline.complete_creator_profile(cs)
    pipeline.verify_creator(admin, creator_uid)
    campaign_id = pipeline.seed_open_campaign(bs, admin, brand_ready=True)
    collab_id = pipeline.apply_to_campaign(cs, campaign_id)
    return {
        "brand": bs,
        "brand_uid": brand_uid,
        "creator": cs,
        "creator_uid": creator_uid,
        "campaign_id": campaign_id,
        "collab_id": collab_id,
    }


def _leaks(payload, path="$"):
    """Every place a forbidden key appears in a response, with its path."""
    found = []
    if isinstance(payload, dict):
        for k, v in payload.items():
            if k in FORBIDDEN:
                found.append(f"{path}.{k}")
            found.extend(_leaks(v, f"{path}.{k}"))
    elif isinstance(payload, list):
        for i, v in enumerate(payload):
            found.extend(_leaks(v, f"{path}[{i}]"))
    return found


class TestOneNamedPersonPerBrand:
    def test_a_brand_signup_captures_the_person_behind_it(self):
        # The OTP flow is the real signup. It takes the business name, the
        # WhatsApp number, and who is asking on the business's behalf.
        s = requests.Session()
        phone = f"+9198{random.randint(10000000, 99999999)}"
        r = s.post(
            f"{BASE_URL}/auth/otp/request",
            json={
                "phone": phone,
                "purpose": "signup",
                "name": "Third Wave Coffee",
                "role": "brand",
                "accept_terms": True,
                "manager_name": "Priya Rao",
                "manager_designation": "Marketing Lead",
                "manager_email": "priya@thirdwave.in",
            },
        )
        assert r.status_code == 200, r.text
        code = _read_otp_from_log(phone)
        if not code:
            pytest.skip("OTP simulation is off, or the backend log isn't readable")

        r = s.post(
            f"{BASE_URL}/auth/otp/verify",
            json={"phone": phone, "code": code, "purpose": "signup"},
        )
        assert r.status_code == 200, r.text
        # The login is the manager, not a nameless brand account.
        assert r.json()["role"] == "brand_manager"

        # And the same three facts are already on the profile, because
        # verification is about to ask for exactly them.
        profile = s.get(f"{BASE_URL}/brand/profile").json()
        assert profile["contact_person_name"] == "Priya Rao"
        assert profile["contact_person_designation"] == "Marketing Lead"
        assert profile["contact_email"] == "priya@thirdwave.in"
        assert profile["contact_phone"] == phone

    def test_the_brand_manager_is_the_campaigns_manager_by_default(self, admin, brand):
        bs, _ = brand
        r = bs.post(
            f"{BASE_URL}/brand/campaigns",
            json={
                "title": f"C-{uuid.uuid4().hex[:6]}",
                "brief": "b",
                "deliverables": "d",
                "budget_per_creator": 5000,
                "category": "fnb",
                "area": "Indiranagar",
                "creators_needed": 1,
                "campaign_type": "personal_table",
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2027-01-01T00:00:00Z",
                "status": "draft",
            },
        )
        assert r.status_code == 200, r.text
        # A campaign with nobody on it spends its first days with no contact,
        # which is exactly when a creator is most likely to have a question.
        assert r.json().get("manager_name")

    def test_an_admin_can_still_hand_it_to_a_weare_manager(self, admin, brand):
        bs, _ = brand
        campaign_id = pipeline.seed_open_campaign(bs, admin, brand_ready=True)
        email = f"TEST_mgr-{uuid.uuid4().hex[:8]}@example.com"
        r = admin.post(
            f"{BASE_URL}/admin/managers",
            json={"email": email, "password": "Password123!", "name": "WeAre Manager"},
        )
        assert r.status_code == 200, r.text
        manager_id = r.json()["id"]
        r = admin.post(
            f"{BASE_URL}/admin/campaigns/{campaign_id}/assign-manager",
            json={"manager_id": manager_id},
        )
        assert r.status_code == 200, r.text
        assert r.json()["manager_name"] == "WeAre Manager"


class TestScopedToTheirOwnBrand:
    def test_another_brands_campaign_is_a_404(self, admin, brand):
        bs, _ = brand
        other = requests.Session()
        _register(other, "brand")
        other_campaign = pipeline.seed_open_campaign(other, admin)

        for path in (
            f"/brand/campaigns/{other_campaign}/applicants",
            f"/brand/campaigns/{other_campaign}/roster",
            f"/brand/campaigns/{other_campaign}/suggested-creators",
        ):
            assert bs.get(f"{BASE_URL}{path}").status_code == 404, path
        for path in (
            f"/brand/campaigns/{other_campaign}/pause",
            f"/brand/campaigns/{other_campaign}/resume",
        ):
            r = bs.post(f"{BASE_URL}{path}", json={"reason": "no reason at all"})
            assert r.status_code == 404, path

    def test_a_brand_cannot_reach_the_weare_manager_router(self, admin, brand):
        # Campaigns default their manager to the brand's own person, so
        # ownership alone would let them in. The role guard is what keeps them
        # out — and out of the daysheet, which carries phone numbers.
        bs, _ = brand
        campaign_id = pipeline.seed_open_campaign(bs, admin, brand_ready=True)
        for path in (
            "/manager/campaigns",
            f"/manager/campaigns/{campaign_id}/roster",
            f"/manager/campaigns/{campaign_id}/daysheet",
        ):
            assert bs.get(f"{BASE_URL}{path}").status_code == 403, path

    def test_a_creator_cannot_reach_the_brand_router(self, creator):
        cs, _ = creator
        assert cs.get(f"{BASE_URL}/brand/dashboard").status_code == 403
        assert cs.get(f"{BASE_URL}/brand/creators").status_code == 403


class TestWhatTheBrandManagerCanDo:
    def test_they_can_pause_and_resume_their_own_campaign(self, admin, brand):
        bs, _ = brand
        campaign_id = pipeline.seed_open_campaign(bs, admin, brand_ready=True)

        r = bs.post(
            f"{BASE_URL}/brand/campaigns/{campaign_id}/pause",
            json={"reason": "Kitchen is closed for two weeks"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "paused"
        assert r.json()["paused_from_status"] == "open"

        r = bs.post(f"{BASE_URL}/brand/campaigns/{campaign_id}/resume", json={})
        assert r.status_code == 200, r.text
        # Back where it was, not to a guess.
        assert r.json()["status"] == "open"

    def test_they_still_cannot_put_a_campaign_live(self, admin, brand):
        bs, _ = brand
        r = bs.post(
            f"{BASE_URL}/brand/campaigns",
            json={
                "title": f"C-{uuid.uuid4().hex[:6]}",
                "brief": "b",
                "deliverables": "d",
                "budget_per_creator": 5000,
                "category": "fnb",
                "area": "Indiranagar",
                "creators_needed": 1,
                "campaign_type": "personal_table",
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2027-01-01T00:00:00Z",
                "status": "open",
            },
        )
        assert r.status_code == 422, r.text
        assert "review" in r.text.lower()

    def test_they_can_record_a_fee_agreed_offline(self, applied):
        bs, collab_id = applied["brand"], applied["collab_id"]
        admin_session = requests.Session()
        admin_session.post(
            f"{BASE_URL}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        pipeline.step(admin_session, bs, collab_id, "verified")
        pipeline.step(admin_session, bs, collab_id, "accepted")

        r = bs.post(
            f"{BASE_URL}/brand/collaborations/{collab_id}/agreed-amount",
            json={"agreed_amount": 9500, "note": "Agreed on the call, includes a reel"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["state"] == "commercial_agreed"
        assert r.json()["agreed_amount"] == 9500

    def test_a_fee_cannot_be_agreed_before_the_creator_is_on_the_campaign(self, applied):
        bs, collab_id = applied["brand"], applied["collab_id"]
        r = bs.post(
            f"{BASE_URL}/brand/collaborations/{collab_id}/agreed-amount",
            json={"agreed_amount": 9500},
        )
        assert r.status_code == 409, r.text
        assert "Accept the creator first" in r.text

    def test_they_can_invite_a_named_creator(self, admin, brand, creator):
        bs, _ = brand
        cs, creator_uid = creator
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, creator_uid)
        campaign_id = pipeline.seed_open_campaign(bs, admin, brand_ready=True)

        r = bs.post(
            f"{BASE_URL}/brand/campaigns/{campaign_id}/invite",
            json={"creator_ids": [creator_uid], "note": "We'd love to have you"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["invited"] == 1
        # The invite went out through us. Nothing came back that could be used
        # to contact the creator directly.
        assert not _leaks(body), _leaks(body)

    def test_an_unverified_brand_cannot_invite_anyone(self, admin, creator):
        unverified = requests.Session()
        _register(unverified, "brand")
        r = unverified.put(
            f"{BASE_URL}/brand/profile",
            json={"business_name": "Unchecked Co", "category": "fnb", "areas": ["HSR"]},
        )
        assert r.status_code == 200, r.text
        r = unverified.post(
            f"{BASE_URL}/brand/campaigns",
            json={
                "title": "Draft only",
                "brief": "b",
                "deliverables": "d",
                "budget_per_creator": 5000,
                "category": "fnb",
                "area": "HSR Layout",
                "creators_needed": 1,
                "campaign_type": "personal_table",
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2027-01-01T00:00:00Z",
                "status": "draft",
            },
        )
        assert r.status_code == 200, r.text
        campaign_id = r.json()["id"]
        _, creator_uid = creator

        r = unverified.post(
            f"{BASE_URL}/brand/campaigns/{campaign_id}/invite",
            json={"creator_ids": [creator_uid]},
        )
        # Their own campaign, so ownership passes; verification is what stops
        # them. Creators are not reachable by a brand we have not checked.
        assert r.status_code == 403, r.text


class TestBrandsNeverGetContactDetails:
    def test_the_applicant_board_carries_no_way_to_reach_anyone(self, applied):
        bs = applied["brand"]
        r = bs.get(f"{BASE_URL}/brand/campaigns/{applied['campaign_id']}/applicants")
        assert r.status_code == 200, r.text
        assert not _leaks(r.json()), _leaks(r.json())

    def test_not_even_once_they_are_working_together(self, applied):
        # This is the case that used to leak: accepting an application handed
        # over an email and a phone number the creator never offered.
        bs, collab_id = applied["brand"], applied["collab_id"]
        admin_session = requests.Session()
        admin_session.post(
            f"{BASE_URL}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        pipeline.step(admin_session, bs, collab_id, "verified")
        pipeline.step(admin_session, bs, collab_id, "accepted")

        r = bs.get(f"{BASE_URL}/brand/campaigns/{applied['campaign_id']}/applicants")
        assert r.status_code == 200, r.text
        leaks = _leaks(r.json())
        assert not leaks, f"contact details leaked once accepted: {leaks}"

    @pytest.mark.parametrize(
        "path", ["/brand/dashboard", "/brand/creators", "/brand/creators/filters"]
    )
    def test_no_brand_surface_leaks(self, applied, path):
        r = applied["brand"].get(f"{BASE_URL}{path}")
        assert r.status_code == 200, r.text
        body = r.json()
        # The dashboard carries the brand's *own* profile, whose contact fields
        # share names with the forbidden ones. Their own details are theirs to
        # see; drop that subtree rather than weakening the key list.
        if isinstance(body, dict):
            body = {k: v for k, v in body.items() if k != "profile"}
        assert not _leaks(body), _leaks(body)

    def test_the_brand_roster_withholds_what_the_weare_roster_shows(self, applied):
        bs, collab_id = applied["brand"], applied["collab_id"]
        admin_session = requests.Session()
        admin_session.post(
            f"{BASE_URL}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        pipeline.step(admin_session, bs, collab_id, "verified")
        pipeline.step(admin_session, bs, collab_id, "accepted")

        r = bs.get(f"{BASE_URL}/brand/campaigns/{applied['campaign_id']}/roster")
        assert r.status_code == 200, r.text
        assert not _leaks(r.json()), _leaks(r.json())
        assert r.json()["roster"], "the roster should not be empty"

        # The WeAre-side roster does carry the number — that is the job, and it
        # is behind the staff role.
        weare = admin_session.get(
            f"{BASE_URL}/manager/campaigns/{applied['campaign_id']}/roster"
        )
        assert weare.status_code == 200, weare.text
        assert "phone" in weare.json()["roster"][0]

    def test_the_brand_still_sees_what_it_needs(self, applied):
        r = applied["brand"].get(
            f"{BASE_URL}/brand/campaigns/{applied['campaign_id']}/applicants"
        )
        row = r.json()["applicants"][0]["creator"]
        assert row["name"]
        assert row["instagram_handle"]
        assert row["city"]
        assert row["niches"]
        assert r.json()["applicants"][0]["quoted_rate"]


class TestWorkNotes:
    def test_the_brand_can_write_and_read_the_thread(self, applied):
        bs, collab_id = applied["brand"], applied["collab_id"]
        r = bs.post(
            f"{BASE_URL}/collaborations/{collab_id}/notes",
            json={"body": "Asked for 12k on the call, offered 8k"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["author_role"] in ("brand", "brand_manager")

        r = bs.get(f"{BASE_URL}/collaborations/{collab_id}/notes")
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["notes"]) == 1
        assert body["notes"][0]["body"].startswith("Asked for 12k")
        assert body["notes"][0]["author_name"]
        # The number sits above the conversation that produced it.
        assert "agreed_amount" in body

    def test_the_creator_can_never_see_them(self, applied):
        bs, cs, collab_id = applied["brand"], applied["creator"], applied["collab_id"]
        bs.post(
            f"{BASE_URL}/collaborations/{collab_id}/notes",
            json={"body": "Worth 8k, not 12k"},
        )
        # Their own collaboration — but whether a private thread exists on it
        # is itself not something we answer.
        assert cs.get(f"{BASE_URL}/collaborations/{collab_id}/notes").status_code == 403
        r = cs.post(
            f"{BASE_URL}/collaborations/{collab_id}/notes", json={"body": "hello?"}
        )
        assert r.status_code == 403

    def test_another_brand_gets_a_404_not_a_403(self, admin, applied):
        other = requests.Session()
        _register(other, "brand")
        pipeline.setup_brand(other, admin)
        r = other.get(f"{BASE_URL}/collaborations/{applied['collab_id']}/notes")
        assert r.status_code == 404

    def test_an_admin_sees_the_thread(self, admin, applied):
        applied["brand"].post(
            f"{BASE_URL}/collaborations/{applied['collab_id']}/notes",
            json={"body": "Holding at 8k"},
        )
        r = admin.get(f"{BASE_URL}/collaborations/{applied['collab_id']}/notes")
        assert r.status_code == 200, r.text
        assert len(r.json()["notes"]) == 1

    def test_the_thread_reads_oldest_first(self, applied):
        bs, collab_id = applied["brand"], applied["collab_id"]
        for body in ("first", "second", "third"):
            bs.post(f"{BASE_URL}/collaborations/{collab_id}/notes", json={"body": body})
        notes = bs.get(f"{BASE_URL}/collaborations/{collab_id}/notes").json()["notes"]
        assert [n["body"] for n in notes] == ["first", "second", "third"]

    def test_an_empty_note_is_refused(self, applied):
        r = applied["brand"].post(
            f"{BASE_URL}/collaborations/{applied['collab_id']}/notes",
            json={"body": "   "},
        )
        assert r.status_code == 422

    def test_agreeing_a_fee_with_a_note_leaves_one_behind(self, applied):
        bs, collab_id = applied["brand"], applied["collab_id"]
        admin_session = requests.Session()
        admin_session.post(
            f"{BASE_URL}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        pipeline.step(admin_session, bs, collab_id, "verified")
        pipeline.step(admin_session, bs, collab_id, "accepted")
        bs.post(
            f"{BASE_URL}/brand/collaborations/{collab_id}/agreed-amount",
            json={"agreed_amount": 9500, "note": "Includes a reel and two stories"},
        )
        body = bs.get(f"{BASE_URL}/collaborations/{collab_id}/notes").json()
        assert body["agreed_amount"] == 9500
        assert any("Includes a reel" in n["body"] for n in body["notes"])


class TestSuggestedCreators:
    def test_a_matching_creator_is_suggested_with_a_reason(self, admin, brand):
        bs, _ = brand
        cs = requests.Session()
        _register(cs, "creator")
        creator_uid = pipeline.user_id_of(cs)
        pipeline.complete_creator_profile(cs)
        # Match the campaign that seed_open_campaign builds: fnb, Indiranagar.
        r = cs.put(
            f"{BASE_URL}/creator/profile",
            json={
                "niches": ["brunch", "cafe"],
                "genres": ["food"],
                "city": "Indiranagar",
                "follower_count": 24000,
            },
        )
        assert r.status_code == 200, r.text
        pipeline.verify_creator(admin, creator_uid)

        campaign_id = pipeline.seed_open_campaign(bs, admin, brand_ready=True)
        r = bs.get(f"{BASE_URL}/brand/campaigns/{campaign_id}/suggested-creators")
        assert r.status_code == 200, r.text
        body = r.json()
        row = next((x for x in body["suggestions"] if x["user_id"] == creator_uid), None)
        assert row, "a matching verified creator should be suggested"
        assert row["match_score"] > 0
        assert row["match_reason"]
        # The score is arguable, not an oracle: the breakdown ships with it.
        assert round(sum(row["match_components"].values()), 1) == row["match_score"]
        assert body["weights"]
        assert body["budget_tier"]["label"]

    def test_suggestions_carry_no_contact_details(self, admin, brand):
        bs, _ = brand
        cs = requests.Session()
        _register(cs, "creator")
        creator_uid = pipeline.user_id_of(cs)
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, creator_uid)
        campaign_id = pipeline.seed_open_campaign(bs, admin, brand_ready=True)

        r = bs.get(f"{BASE_URL}/brand/campaigns/{campaign_id}/suggested-creators")
        assert r.status_code == 200, r.text
        assert not _leaks(r.json()), _leaks(r.json())

    def test_an_applicant_is_not_also_a_suggestion(self, applied):
        bs = applied["brand"]
        r = bs.get(
            f"{BASE_URL}/brand/campaigns/{applied['campaign_id']}/suggested-creators"
        )
        assert r.status_code == 200, r.text
        ids = [x["user_id"] for x in r.json()["suggestions"]]
        assert applied["creator_uid"] not in ids

    def test_an_invited_creator_is_not_suggested_again(self, admin, brand, creator):
        bs, _ = brand
        cs, creator_uid = creator
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, creator_uid)
        campaign_id = pipeline.seed_open_campaign(bs, admin, brand_ready=True)

        before = bs.get(
            f"{BASE_URL}/brand/campaigns/{campaign_id}/suggested-creators"
        ).json()
        assert creator_uid in [x["user_id"] for x in before["suggestions"]]

        bs.post(
            f"{BASE_URL}/brand/campaigns/{campaign_id}/invite",
            json={"creator_ids": [creator_uid]},
        )
        after = bs.get(
            f"{BASE_URL}/brand/campaigns/{campaign_id}/suggested-creators"
        ).json()
        assert creator_uid not in [x["user_id"] for x in after["suggestions"]]

    def test_unverified_creators_are_never_suggested(self, admin, brand, creator):
        bs, _ = brand
        cs, creator_uid = creator
        pipeline.complete_creator_profile(cs)  # submitted, not yet approved
        campaign_id = pipeline.seed_open_campaign(bs, admin, brand_ready=True)
        r = bs.get(f"{BASE_URL}/brand/campaigns/{campaign_id}/suggested-creators")
        assert creator_uid not in [x["user_id"] for x in r.json()["suggestions"]]

    def test_the_filters_and_pagination_work(self, admin, brand):
        bs, _ = brand
        campaign_id = pipeline.seed_open_campaign(bs, admin, brand_ready=True)
        r = bs.get(
            f"{BASE_URL}/brand/campaigns/{campaign_id}/suggested-creators",
            params={"city": "Nowhere-" + uuid.uuid4().hex[:6]},
        )
        assert r.status_code == 200, r.text
        assert r.json()["suggestions"] == []

        r = bs.get(
            f"{BASE_URL}/brand/campaigns/{campaign_id}/suggested-creators",
            params={"limit": 1, "offset": 0},
        )
        assert r.status_code == 200, r.text
        assert len(r.json()["suggestions"]) <= 1
        assert r.json()["limit"] == 1

    def test_an_admin_can_see_them_on_any_campaign(self, admin, brand):
        bs, _ = brand
        campaign_id = pipeline.seed_open_campaign(bs, admin, brand_ready=True)
        r = admin.get(f"{BASE_URL}/brand/campaigns/{campaign_id}/suggested-creators")
        assert r.status_code == 200, r.text


class TestAuditCarriesTheContext:
    def test_a_brand_action_is_findable_by_brand_and_by_campaign(self, admin, applied):
        bs, collab_id = applied["brand"], applied["collab_id"]
        bs.post(
            f"{BASE_URL}/collaborations/{collab_id}/notes",
            json={"body": "Recorded for the audit trail"},
        )
        r = admin.get(
            f"{BASE_URL}/admin/audit", params={"campaign_id": applied["campaign_id"]}
        )
        assert r.status_code == 200, r.text
        rows = r.json()
        assert any(x["action"] == "collaboration.note" for x in rows)
        assert all(x["campaign_id"] == applied["campaign_id"] for x in rows)

        r = admin.get(f"{BASE_URL}/admin/audit", params={"brand_id": applied["brand_uid"]})
        assert r.status_code == 200, r.text
        assert r.json(), "the brand's own actions should be findable by brand"

    def test_a_bad_id_is_refused_rather_than_ignored(self, admin):
        r = admin.get(f"{BASE_URL}/admin/audit", params={"brand_id": "not-an-id"})
        assert r.status_code == 422
