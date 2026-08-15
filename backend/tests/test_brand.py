"""Backend tests for the /api/brand/* router: profile, dashboard, campaigns list & post, cross-visibility."""
import os
import uuid
import pytest
import requests

import pipeline  # tests/ is on sys.path (no __init__.py, pytest prepend mode)

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "creators@wearemonk.in")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "WeAreMonk@2026")


def _rand_email(role):
    return f"TEST_{role}-{uuid.uuid4().hex[:10]}@example.com"


def _register(session, role):
    email = _rand_email(role)
    r = session.post(f"{BASE_URL}/auth/register", json={
        "email": email, "password": "Password123!", "name": f"Test {role.title()}", "role": role,
    })
    assert r.status_code == 200, r.text
    return email, r.json()


def _admin_session():
    s = requests.Session()
    _login(s, ADMIN_EMAIL, ADMIN_PASSWORD)
    return s


def _login(session, email, password):
    r = session.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def brand_session():
    s = requests.Session()
    email, user = _register(s, "brand")
    return s, email, user


@pytest.fixture
def brand_session_2():
    s = requests.Session()
    email, user = _register(s, "brand")
    return s, email, user


@pytest.fixture
def creator_session():
    s = requests.Session()
    email, user = _register(s, "creator")
    return s, email, user


@pytest.fixture
def admin_session():
    s = requests.Session()
    _login(s, ADMIN_EMAIL, ADMIN_PASSWORD)
    return s


# ---------- profile ----------

class TestBrandProfile:
    def test_get_profile_stub_after_signup(self, brand_session):
        s, email, _ = brand_session
        r = s.get(f"{BASE_URL}/brand/profile")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "business_name" in data
        assert data.get("category") in (None, "fnb", "hospitality", "retail", "lifestyle")

    def test_get_profile_forbidden_for_creator(self, creator_session):
        s, _, _ = creator_session
        r = s.get(f"{BASE_URL}/brand/profile")
        assert r.status_code == 403

    def test_get_profile_forbidden_for_admin(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/brand/profile")
        assert r.status_code == 403

    def test_put_profile_updates_and_mirrors_name(self, brand_session):
        s, email, _ = brand_session
        r = s.put(f"{BASE_URL}/brand/profile", json={
            "business_name": "Cafe Aroma",
            "category": "fnb",
            "areas": ["Indiranagar", "Koramangala"],
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["business_name"] == "Cafe Aroma"
        assert d["category"] == "fnb"
        assert d["areas"] == ["Indiranagar", "Koramangala"]

        # Mirrors business_name → users.name
        me = s.get(f"{BASE_URL}/auth/me")
        assert me.status_code == 200
        assert me.json()["name"] == "Cafe Aroma"

        # GET reflects persistence
        g = s.get(f"{BASE_URL}/brand/profile")
        assert g.status_code == 200
        assert g.json()["business_name"] == "Cafe Aroma"
        assert g.json()["areas"] == ["Indiranagar", "Koramangala"]

    def test_put_profile_wrong_category_422(self, brand_session):
        s, _, _ = brand_session
        r = s.put(f"{BASE_URL}/brand/profile", json={
            "business_name": "X", "category": "tech", "areas": ["Indiranagar"],
        })
        assert r.status_code == 422

    def test_put_profile_empty_areas_allowed(self, brand_session):
        s, _, _ = brand_session
        r = s.put(f"{BASE_URL}/brand/profile", json={
            "business_name": "X", "category": "retail", "areas": [],
        })
        assert r.status_code == 200
        assert r.json()["areas"] == []


# ---------- campaigns list & post ----------

class TestBrandCampaigns:
    def _seed_profile(self, s, *, verify=True):
        r = s.put(f"{BASE_URL}/brand/profile", json={
            "business_name": "Brand X", "category": "fnb", "areas": ["Indiranagar"],
        })
        assert r.status_code == 200, r.text
        if verify:
            pipeline.verify_brand(_admin_session(), pipeline.user_id_of(s))

    def _go_live(self, s, body):
        """Draft, submit, approve — the only way a campaign reaches creators."""
        r = s.post(f"{BASE_URL}/brand/campaigns", json={**body, "status": "draft"})
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        pipeline.submit_campaign(s, cid)
        status = pipeline.approve_campaign(_admin_session(), cid)
        return cid, status

    def test_post_campaign_cannot_go_live_straight_from_the_payload(self, brand_session):
        # This used to work, and it was the hole: a brand could publish itself.
        s, _, _ = brand_session
        self._seed_profile(s)
        r = s.post(f"{BASE_URL}/brand/campaigns", json={
            "title": "Straight to live", "brief": "b", "deliverables": "d",
            "budget_per_creator": 5000, "category": "fnb", "area": "Indiranagar",
            "creators_needed": 3, "status": "open",
            "campaign_type": "personal_table", "start_date": "2025-06-01T00:00:00Z", "end_date": "2027-06-01T00:00:00Z",
        })
        assert r.status_code == 422, r.text
        assert "review" in r.text.lower()

    def test_post_campaign_submitted_for_review_returns_row(self, brand_session):
        s, _, _ = brand_session
        self._seed_profile(s)
        body = {
            "title": "Weekend Reel", "brief": "Shoot a warm reel at our cafe.",
            "deliverables": "1 reel, 3 stories", "budget_per_creator": 5000,
            "category": "fnb", "area": "Indiranagar", "creators_needed": 3,
            "campaign_type": "personal_table",
            "start_date": "2025-02-15T00:00:00Z",
            "end_date": "2027-02-15T00:00:00Z",
            "status": "pending_review",
        }
        r = s.post(f"{BASE_URL}/brand/campaigns", json=body)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "pending_review"
        assert d["awaiting_review"] is True
        assert d["applicant_count"] == 0
        assert d["title"] == "Weekend Reel"
        assert d["creators_needed"] == 3
        assert "id" in d

    def test_a_draft_reaches_creators_only_after_approval(self, brand_session):
        s, _, _ = brand_session
        self._seed_profile(s)
        cid, status = self._go_live(s, {
            "title": "Reviewed Reel", "brief": "b", "deliverables": "d",
            "budget_per_creator": 5000, "category": "fnb", "area": "Indiranagar",
            "creators_needed": 3, "campaign_type": "personal_table",
            "start_date": "2025-02-15T00:00:00Z", "end_date": "2027-02-15T00:00:00Z",
        })
        assert status == "open"
        row = next(c for c in s.get(f"{BASE_URL}/brand/campaigns").json() if c["id"] == cid)
        assert row["status"] == "open"

    def test_post_campaign_draft_allowed(self, brand_session):
        s, _, _ = brand_session
        self._seed_profile(s)
        r = s.post(f"{BASE_URL}/brand/campaigns", json={
            "title": "Draft", "brief": "b", "deliverables": "d",
            "budget_per_creator": 100, "category": "fnb", "area": "Indiranagar",
            "creators_needed": 1, "status": "draft",
            "campaign_type": "personal_table", "start_date": "2025-06-01T00:00:00Z", "end_date": "2027-06-01T00:00:00Z",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "draft"

    def test_post_campaign_invalid_category_422(self, brand_session):
        s, _, _ = brand_session
        self._seed_profile(s)
        r = s.post(f"{BASE_URL}/brand/campaigns", json={
            "title": "X", "brief": "b", "deliverables": "d",
            "budget_per_creator": 100, "category": "tech", "area": "Indiranagar",
            "creators_needed": 1, "status": "draft",
            "campaign_type": "personal_table", "start_date": "2025-06-01T00:00:00Z", "end_date": "2027-06-01T00:00:00Z",
        })
        assert r.status_code == 422

    def test_post_campaign_end_before_start_422(self, brand_session):
        s, _, _ = brand_session
        self._seed_profile(s)
        r = s.post(f"{BASE_URL}/brand/campaigns", json={
            "title": "X", "brief": "b", "deliverables": "d",
            "budget_per_creator": 100, "category": "fnb", "area": "Indiranagar",
            "creators_needed": 1, "campaign_type": "personal_table",
            "start_date": "2026-02-15T00:00:00Z", "end_date": "2026-02-01T00:00:00Z",
            "status": "draft",
        })
        assert r.status_code == 422
        assert "End date cannot be before start date" in r.text

    def test_post_campaign_needed_lt_1_422(self, brand_session):
        s, _, _ = brand_session
        self._seed_profile(s)
        r = s.post(f"{BASE_URL}/brand/campaigns", json={
            "title": "X", "brief": "b", "deliverables": "d",
            "budget_per_creator": 100, "category": "fnb", "area": "Indiranagar",
            "creators_needed": 0, "status": "draft",
            "campaign_type": "personal_table", "start_date": "2025-06-01T00:00:00Z", "end_date": "2027-06-01T00:00:00Z",
        })
        assert r.status_code == 422

    def test_list_only_own_and_newest_first(self, brand_session, brand_session_2):
        s1, _, _ = brand_session
        s2, _, _ = brand_session_2
        self._seed_profile(s1)
        self._seed_profile(s2)

        # brand1 posts two, brand2 posts one
        base = {"brief": "b", "deliverables": "d", "budget_per_creator": 100,
                "category": "fnb", "area": "Indiranagar", "creators_needed": 1,
                "campaign_type": "personal_table",
                "start_date": "2025-06-01T00:00:00Z", "end_date": "2027-06-01T00:00:00Z"}
        r1 = s1.post(f"{BASE_URL}/brand/campaigns", json={**base, "title": "B1-first", "status": "draft"})
        assert r1.status_code == 200, r1.text
        self._go_live(s1, {**base, "title": "B1-second"})
        self._go_live(s2, {**base, "title": "B2-only"})

        lst = s1.get(f"{BASE_URL}/brand/campaigns")
        assert lst.status_code == 200
        rows = lst.json()
        titles = [r["title"] for r in rows]
        assert "B2-only" not in titles
        assert "B1-first" in titles and "B1-second" in titles
        # newest-first: B1-second created after B1-first
        assert titles.index("B1-second") < titles.index("B1-first")
        # includes draft
        statuses = {r["title"]: r["status"] for r in rows}
        assert statuses["B1-first"] == "draft"
        for row in rows:
            assert "applicant_count" in row

    def test_list_forbidden_for_creator(self, creator_session):
        s, _, _ = creator_session
        r = s.get(f"{BASE_URL}/brand/campaigns")
        assert r.status_code == 403

    def test_post_forbidden_for_creator(self, creator_session):
        s, _, _ = creator_session
        r = s.post(f"{BASE_URL}/brand/campaigns", json={
            "title": "X", "brief": "b", "deliverables": "d",
            "budget_per_creator": 100, "category": "fnb", "area": "Indiranagar",
            "creators_needed": 1, "status": "draft",
            "campaign_type": "personal_table", "start_date": "2025-06-01T00:00:00Z", "end_date": "2027-06-01T00:00:00Z",
        })
        assert r.status_code == 403


# ---------- dashboard ----------

class TestBrandDashboard:
    def test_dashboard_shape_and_totals(self, brand_session, creator_session):
        s, _, _ = brand_session
        s.put(f"{BASE_URL}/brand/profile", json={
            "business_name": "Brand D", "category": "hospitality",
            "areas": ["Whitefield"],
        })
        base = {"brief": "b", "deliverables": "d", "budget_per_creator": 100,
                "category": "hospitality", "area": "Whitefield", "creators_needed": 1,
                "campaign_type": "personal_table",
                "start_date": "2025-06-01T00:00:00Z", "end_date": "2027-06-01T00:00:00Z"}
        pipeline.verify_brand(_admin_session(), pipeline.user_id_of(s))
        r_open = s.post(f"{BASE_URL}/brand/campaigns", json={**base, "title": "Open1", "status": "draft"})
        r_draft = s.post(f"{BASE_URL}/brand/campaigns", json={**base, "title": "Draft1", "status": "draft"})
        open_id = r_open.json()["id"]
        pipeline.submit_campaign(s, open_id)
        assert pipeline.approve_campaign(_admin_session(), open_id) == "open"

        # A creator applies to the open campaign → applicant_count should become 1
        cs, _, cuser = creator_session
        # The creator must be onboarded *and verified* to apply.
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(_admin_session(), cuser["id"])
        ar = cs.post(f"{BASE_URL}/campaigns/{open_id}/apply",
                     json={"pitch": "hi there really keen", "quoted_rate": 5000})
        assert ar.status_code in (200, 201), ar.text

        r = s.get(f"{BASE_URL}/brand/dashboard")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["profile"]["business_name"] == "Brand D"
        assert d["totals"]["total_campaigns"] == 2
        assert d["totals"]["live_campaigns"] == 1
        assert d["totals"]["draft_campaigns"] == 1
        assert d["totals"]["total_applications"] == 1
        by_title = {c["title"]: c for c in d["campaigns"]}
        assert by_title["Open1"]["applicant_count"] == 1
        assert by_title["Draft1"]["applicant_count"] == 0

    def test_dashboard_forbidden_for_creator(self, creator_session):
        s, _, _ = creator_session
        r = s.get(f"{BASE_URL}/brand/dashboard")
        assert r.status_code == 403

    def test_dashboard_forbidden_for_admin(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/brand/dashboard")
        assert r.status_code == 403


# ---------- cross-visibility ----------

class TestCrossVisibility:
    def test_open_campaign_appears_on_creator_feed(self, brand_session, creator_session):
        s, _, _ = brand_session
        s.put(f"{BASE_URL}/brand/profile", json={
            "business_name": "Feed Brand", "category": "retail", "areas": ["HSR Layout"],
        })
        pipeline.verify_brand(_admin_session(), pipeline.user_id_of(s))
        title = f"OpenFeed-{uuid.uuid4().hex[:6]}"
        r = s.post(f"{BASE_URL}/brand/campaigns", json={
            "title": title, "brief": "b", "deliverables": "d",
            "budget_per_creator": 200, "category": "retail", "area": "HSR Layout",
            "creators_needed": 2, "status": "draft",
            "campaign_type": "personal_table", "start_date": "2025-06-01T00:00:00Z", "end_date": "2027-06-01T00:00:00Z",
        })
        assert r.status_code == 200
        cid = r.json()["id"]

        # Not on the feed until it has been read.
        assert title not in [c["title"] for c in creator_session[0].get(f"{BASE_URL}/campaigns").json()]
        pipeline.submit_campaign(s, cid)
        assert pipeline.approve_campaign(_admin_session(), cid) == "open"

        cs, _, _ = creator_session
        feed = cs.get(f"{BASE_URL}/campaigns")
        assert feed.status_code == 200
        titles = [c["title"] for c in feed.json()]
        assert title in titles

        # filter by area
        f2 = cs.get(f"{BASE_URL}/campaigns", params={"area": "HSR Layout"})
        assert f2.status_code == 200
        assert title in [c["title"] for c in f2.json()]

        # filter by category
        f3 = cs.get(f"{BASE_URL}/campaigns", params={"category": "retail"})
        assert f3.status_code == 200
        assert title in [c["title"] for c in f3.json()]

        # detail visible to brand (creator too since it's open)
        det_brand = s.get(f"{BASE_URL}/campaigns/{cid}")
        assert det_brand.status_code == 200
        det_creator = cs.get(f"{BASE_URL}/campaigns/{cid}")
        assert det_creator.status_code == 200

    def test_draft_hidden_from_creator_visible_to_admin(
        self, brand_session, creator_session, admin_session
    ):
        s, _, _ = brand_session
        s.put(f"{BASE_URL}/brand/profile", json={
            "business_name": "Draft Brand", "category": "lifestyle", "areas": ["Jayanagar"],
        })
        title = f"DraftHidden-{uuid.uuid4().hex[:6]}"
        r = s.post(f"{BASE_URL}/brand/campaigns", json={
            "title": title, "brief": "b", "deliverables": "d",
            "budget_per_creator": 100, "category": "lifestyle", "area": "Jayanagar",
            "creators_needed": 1, "status": "draft",
        })
        assert r.status_code == 200
        cid = r.json()["id"]

        cs, _, _ = creator_session
        feed = cs.get(f"{BASE_URL}/campaigns")
        assert feed.status_code == 200
        assert title not in [c["title"] for c in feed.json()]

        det_creator = cs.get(f"{BASE_URL}/campaigns/{cid}")
        assert det_creator.status_code == 404

        det_admin = admin_session.get(f"{BASE_URL}/campaigns/{cid}")
        assert det_admin.status_code == 200


# ---------- campaign lifecycle ----------

class TestCampaignLifecycle:
    """A draft used to be a trap door: no edit, no publish, no delete."""

    def _seed_profile(self, s, *, verify=True):
        s.put(f"{BASE_URL}/brand/profile", json={
            "business_name": "Lifecycle Co", "category": "fnb", "areas": ["Indiranagar"],
        })
        if verify:
            pipeline.verify_brand(_admin_session(), pipeline.user_id_of(s))

    def _live(self, s, **overrides):
        """A draft taken all the way live, through review."""
        draft = self._draft(s, **overrides)
        pipeline.submit_campaign(s, draft["id"])
        pipeline.approve_campaign(_admin_session(), draft["id"])
        return draft

    def _draft(self, s, **overrides):
        body = {
            "title": f"Draft-{uuid.uuid4().hex[:6]}", "brief": "b", "deliverables": "d",
            "budget_per_creator": 3000, "category": "fnb", "area": "Indiranagar",
            "creators_needed": 2, "status": "draft",
            "campaign_type": "personal_table", "start_date": "2025-06-01T00:00:00Z", "end_date": "2027-06-01T00:00:00Z",
        }
        body.update(overrides)
        r = s.post(f"{BASE_URL}/brand/campaigns", json=body)
        assert r.status_code == 200, r.text
        return r.json()

    def test_draft_can_be_edited_then_published(self, brand_session):
        s, _, _ = brand_session
        self._seed_profile(s)
        draft = self._draft(s)
        assert draft["can_publish"] and draft["can_edit"] and draft["can_delete"]

        r = s.put(f"{BASE_URL}/brand/campaigns/{draft['id']}", json={
            "title": "Polished title", "budget_per_creator": 4500,
        })
        assert r.status_code == 200, r.text
        assert r.json()["title"] == "Polished title"
        assert r.json()["budget_per_creator"] == 4500

        # "Publish" now hands the brief to us rather than to creators.
        r = s.post(f"{BASE_URL}/brand/campaigns/{draft['id']}/publish")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pending_review"

        # Submitting twice is refused.
        assert s.post(f"{BASE_URL}/brand/campaigns/{draft['id']}/publish").status_code == 409

        # And it is an admin approval that puts it in front of creators.
        assert pipeline.approve_campaign(_admin_session(), draft["id"]) in ("open", "upcoming")

    def test_live_campaign_can_be_corrected(self, brand_session):
        s, _, _ = brand_session
        self._seed_profile(s)
        live = self._live(s)
        r = s.put(f"{BASE_URL}/brand/campaigns/{live['id']}", json={"deliverables": "2 reels"})
        assert r.status_code == 200, r.text
        assert r.json()["deliverables"] == "2 reels"

    def test_end_before_start_is_refused_on_edit(self, brand_session):
        s, _, _ = brand_session
        self._seed_profile(s)
        c = self._draft(s, start_date="2026-09-01T00:00:00Z", end_date="2026-10-01T00:00:00Z")
        r = s.put(f"{BASE_URL}/brand/campaigns/{c['id']}",
                  json={"end_date": "2026-08-01T00:00:00Z"})
        assert r.status_code == 422

    def test_empty_draft_can_be_deleted_but_a_live_one_cannot(self, brand_session):
        s, _, _ = brand_session
        self._seed_profile(s)
        draft = self._draft(s)
        assert s.delete(f"{BASE_URL}/brand/campaigns/{draft['id']}").status_code == 200
        assert s.get(f"{BASE_URL}/campaigns/{draft['id']}").status_code == 404

        live = self._live(s)
        r = s.delete(f"{BASE_URL}/brand/campaigns/{live['id']}")
        assert r.status_code == 409
        assert "close" in r.json()["detail"].lower()

    def test_closing_answers_everyone_still_waiting(self, brand_session, creator_session):
        s, _, _ = brand_session
        cs, _, cuser = creator_session
        self._seed_profile(s)
        live = self._live(s)

        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(_admin_session(), cuser["id"])
        cs.post(f"{BASE_URL}/campaigns/{live['id']}/apply",
                json={"pitch": "keen on this one please", "quoted_rate": 3000})

        r = s.post(f"{BASE_URL}/brand/campaigns/{live['id']}/close",
                   json={"reason": "Changed the plan"})
        assert r.status_code == 200, r.text
        assert r.json()["applications_closed"] == 1

        # The creator is told, rather than left waiting forever.
        dash = cs.get(f"{BASE_URL}/creator/dashboard").json()
        row = next(a for a in dash["applications"] if a["campaign_id"] == live["id"])
        assert row["state"] == "declined"
        assert row["exit_reason"]

    def test_cannot_touch_another_brands_campaign(self, brand_session, brand_session_2):
        s1, _, _ = brand_session
        s2, _, _ = brand_session_2
        self._seed_profile(s1)
        self._seed_profile(s2)
        mine = self._draft(s1)
        assert s2.put(f"{BASE_URL}/brand/campaigns/{mine['id']}",
                      json={"title": "hijacked"}).status_code == 404
        assert s2.post(f"{BASE_URL}/brand/campaigns/{mine['id']}/publish").status_code == 404
        assert s2.delete(f"{BASE_URL}/brand/campaigns/{mine['id']}").status_code == 404


# ---------- applicant board ----------

class TestApplicantBoard:
    """Before this the brand side could only ever show a count."""

    def _live_campaign_with_applicant(self, bs, cs, cuser, creators_needed=2):
        bs.put(f"{BASE_URL}/brand/profile", json={
            "business_name": "Board Co", "category": "fnb", "areas": ["Indiranagar"],
        })
        cid = pipeline.seed_open_campaign(
            bs, _admin_session(), creators_needed=creators_needed
        )
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(_admin_session(), cuser["id"])
        collab_id = pipeline.apply_to_campaign(cs, cid)
        return cid, collab_id

    def test_brand_sees_the_pitch_and_the_rate(self, brand_session, creator_session):
        bs, _, _ = brand_session
        cs, _, cuser = creator_session
        cid, collab_id = self._live_campaign_with_applicant(bs, cs, cuser)

        r = bs.get(f"{BASE_URL}/brand/campaigns/{cid}/applicants")
        assert r.status_code == 200, r.text
        d = r.json()
        row = next(a for a in d["applicants"] if a["id"] == collab_id)
        assert row["pitch"]
        assert row["quoted_rate"] == 5500
        assert row["creator"]["instagram_handle"]
        assert d["totals"]["with_weare"] == 1

    def test_contact_details_are_withheld_until_acceptance(
        self, brand_session, creator_session
    ):
        bs, _, _ = brand_session
        cs, _, cuser = creator_session
        cid, collab_id = self._live_campaign_with_applicant(bs, cs, cuser)
        admin = _admin_session()

        row = bs.get(f"{BASE_URL}/brand/campaigns/{cid}/applicants").json()["applicants"][0]
        assert row["creator"]["email"] is None
        assert row["creator"]["phone"] is None

        pipeline.step(admin, bs, collab_id, "verified")
        pipeline.step(admin, bs, collab_id, "accepted")

        row2 = next(
            a for a in bs.get(f"{BASE_URL}/brand/campaigns/{cid}/applicants").json()["applicants"]
            if a["id"] == collab_id
        )
        assert row2["creator"]["email"], "contact should unlock once working together"

    def test_a_full_campaign_stops_accepting(self, brand_session, creator_session):
        """creators_needed used to be decoration."""
        bs, _, _ = brand_session
        cs, _, cuser = creator_session
        cid, collab_id = self._live_campaign_with_applicant(bs, cs, cuser, creators_needed=1)
        admin = _admin_session()

        pipeline.step(admin, bs, collab_id, "verified")
        pipeline.step(admin, bs, collab_id, "accepted")

        # The brief is full, so it leaves the feed and refuses new pitches.
        other = requests.Session()
        _, ouser = _register(other, "creator")
        pipeline.complete_creator_profile(other)
        pipeline.verify_creator(admin, ouser["id"])
        r = other.post(f"{BASE_URL}/campaigns/{cid}/apply",
                       json={"pitch": "any room left for me?", "quoted_rate": 4000})
        assert r.status_code in (404, 409), r.text

    def test_applicants_are_brand_scoped(self, brand_session, brand_session_2, creator_session):
        bs, _, _ = brand_session
        s2, _, _ = brand_session_2
        cs, _, cuser = creator_session
        cid, _ = self._live_campaign_with_applicant(bs, cs, cuser)
        assert s2.get(f"{BASE_URL}/brand/campaigns/{cid}/applicants").status_code == 404
