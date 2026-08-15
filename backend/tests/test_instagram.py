"""Backend tests for official Instagram stats.

The predecessor here was an Apify scraper: it breached Instagram's terms and
put the connected Meta Business account at risk, so it was removed and follower
counts fell back to self-reported. This is the sanctioned replacement —
"Instagram API with Instagram Login", two read scopes, tokens encrypted at
rest, and readings cached on a schedule rather than pulled on every page load.

The app is still in review, so these run against a server with no Meta
credentials. That is the state that matters most to get right: every route has
to degrade politely rather than error, and nothing about the rest of the
product may depend on Instagram being switched on.
"""
import os
import uuid

import pytest
import requests

import pipeline  # tests/ is on sys.path (no __init__.py, pytest prepend mode)

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "creators@wearemonk.in")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "WeAreMonk@2026")

# Set only when a real Meta app is wired up. Everything that needs live
# credentials skips without them rather than failing a suite that can't
# possibly pass.
CONFIGURED = bool(
    os.environ.get("INSTAGRAM_APP_ID")
    and os.environ.get("INSTAGRAM_APP_SECRET")
    and os.environ.get("INSTAGRAM_REDIRECT_URI")
    and os.environ.get("INSTAGRAM_TOKEN_KEY")
)
needs_credentials = pytest.mark.skipif(
    not CONFIGURED, reason="Meta app credentials are not configured"
)
needs_no_credentials = pytest.mark.skipif(
    CONFIGURED, reason="only meaningful while the Meta app is unconfigured"
)


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


# ---------- 1. Reading the connection ----------

class TestConnectionStatus:
    def test_a_creator_with_no_connection_gets_a_shape_not_a_404(self, creator):
        # The UI needs to render a disabled button, not handle an error.
        cs, _ = creator
        r = cs.get(f"{BASE_URL}/creator/instagram")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["connected"] is False
        assert data["status"] is None
        assert "configured" in data

    def test_the_status_never_carries_a_token(self, creator):
        cs, _ = creator
        body = cs.get(f"{BASE_URL}/creator/instagram").text
        assert "access_token" not in body

    def test_it_is_on_the_dashboard_too(self, creator):
        # So the hero can show the verified badge without a second request.
        cs, _ = creator
        profile = cs.get(f"{BASE_URL}/creator/dashboard").json()["profile"]
        assert "instagram" in profile
        assert profile["instagram"]["connected"] is False

    def test_brands_and_admins_cannot_reach_the_creator_routes(self, brand, admin):
        assert brand.get(f"{BASE_URL}/creator/instagram").status_code == 403
        assert admin.get(f"{BASE_URL}/creator/instagram").status_code == 403

    def test_it_needs_a_login(self):
        assert requests.get(f"{BASE_URL}/creator/instagram").status_code == 401


# ---------- 2. Life without credentials (the app-review state) ----------

class TestUnconfigured:
    @needs_no_credentials
    def test_the_status_says_it_is_not_switched_on(self, creator):
        cs, _ = creator
        assert cs.get(f"{BASE_URL}/creator/instagram").json()["configured"] is False

    @needs_no_credentials
    def test_starting_a_connection_is_a_503_that_explains_itself(self, creator):
        cs, _ = creator
        r = cs.post(f"{BASE_URL}/creator/instagram/connect")
        assert r.status_code == 503, r.text
        # Not a stack trace and not "coming soon" — a reason and a reassurance.
        assert "review" in r.text
        assert "self-reported" in r.text

    @needs_no_credentials
    def test_the_callback_is_refused_the_same_way(self, creator):
        cs, _ = creator
        r = cs.post(
            f"{BASE_URL}/creator/instagram/callback",
            json={"code": "whatever", "state": "whatever"},
        )
        assert r.status_code == 503, r.text

    @needs_no_credentials
    def test_the_jobs_no_op_rather_than_erroring(self, admin):
        r = admin.post(f"{BASE_URL}/admin/jobs/instagram")
        assert r.status_code == 200, r.text
        assert r.json()["tokens"]["skipped"] == "not configured"
        assert r.json()["stats"]["skipped"] == "not configured"

    @needs_no_credentials
    def test_everything_else_still_works(self, brand, admin, creator):
        # The point of the whole degradation: a creator can be verified and
        # apply to a campaign with Instagram switched off entirely.
        cs, user_id = creator
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, user_id)
        cid = pipeline.seed_open_campaign(brand, admin)
        r = cs.post(
            f"{BASE_URL}/campaigns/{cid}/apply",
            json={"pitch": "Would love this one", "quoted_rate": 5000},
        )
        assert r.status_code in (200, 201), r.text

    @needs_no_credentials
    def test_the_follower_count_stays_self_reported(self, creator):
        cs, _ = creator
        pipeline.complete_creator_profile(cs, submit=False)
        profile = cs.get(f"{BASE_URL}/creator/profile").json()
        assert profile["follower_count_source"] == "self_reported"
        assert profile["follower_count_verified"] is False
        assert profile["verified_stats_available"] is False


# ---------- 3. Starting the OAuth journey ----------

class TestConnectStart:
    @needs_credentials
    def test_it_hands_back_an_instagram_authorize_url(self, creator):
        cs, _ = creator
        r = cs.post(f"{BASE_URL}/creator/instagram/connect")
        assert r.status_code == 200, r.text
        url = r.json()["authorize_url"]
        # The Instagram-Login flow, not the Facebook one — the whole point of
        # this integration is not needing a Facebook Page.
        assert url.startswith("https://www.instagram.com/oauth/authorize")
        assert "facebook.com" not in url

    @needs_credentials
    def test_it_asks_for_exactly_the_two_read_scopes(self, creator):
        cs, _ = creator
        r = cs.post(f"{BASE_URL}/creator/instagram/connect")
        assert set(r.json()["scopes"]) == {
            "instagram_business_basic",
            "instagram_business_manage_insights",
        }
        url = r.json()["authorize_url"]
        assert "instagram_business_basic" in url
        assert "instagram_business_manage_insights" in url
        # Nothing that could post, reply or change anything.
        for forbidden in ("publish", "manage_messages", "manage_comments"):
            assert forbidden not in url

    @needs_credentials
    def test_each_start_gets_its_own_state(self, creator):
        cs, _ = creator
        first = cs.post(f"{BASE_URL}/creator/instagram/connect").json()["state"]
        second = cs.post(f"{BASE_URL}/creator/instagram/connect").json()["state"]
        assert first != second

    @needs_credentials
    def test_a_made_up_state_is_refused(self, creator):
        cs, _ = creator
        r = cs.post(
            f"{BASE_URL}/creator/instagram/callback",
            json={"code": "anything", "state": "never-issued"},
        )
        assert r.status_code == 400, r.text

    @needs_credentials
    def test_another_creators_state_is_refused(self, creator):
        # The state is bound to whoever started the journey.
        cs, _ = creator
        state = cs.post(f"{BASE_URL}/creator/instagram/connect").json()["state"]
        attacker = requests.Session()
        _register(attacker, "creator")
        r = attacker.post(
            f"{BASE_URL}/creator/instagram/callback",
            json={"code": "anything", "state": state},
        )
        assert r.status_code == 400, r.text


# ---------- 4. Disconnecting ----------

class TestDisconnect:
    def test_disconnecting_when_never_connected_is_not_an_error(self, creator):
        cs, _ = creator
        r = cs.delete(f"{BASE_URL}/creator/instagram")
        assert r.status_code == 200, r.text
        assert r.json()["connected"] is False

    def test_refreshing_without_a_connection_is_a_404(self, creator):
        cs, _ = creator
        assert cs.post(f"{BASE_URL}/creator/instagram/refresh").status_code == 404


# ---------- 5. The self-reported fallback ----------

class TestSelfReportedFallback:
    def test_a_typed_count_is_kept_as_the_fallback(self, creator):
        cs, _ = creator
        cs.put(f"{BASE_URL}/creator/profile", json={"follower_count": 12400})
        profile = cs.get(f"{BASE_URL}/creator/profile").json()
        assert profile["follower_count"] == 12400
        assert profile["follower_count_self_reported"] == 12400
        assert profile["follower_count_source"] == "self_reported"

    def test_provenance_travels_with_the_number_for_brands_too(self, admin, brand, creator):
        cs, user_id = creator
        pipeline.complete_creator_profile(cs)
        pipeline.verify_creator(admin, user_id)
        pipeline.setup_brand(brand, admin)
        # The directory returns a bare list of public fields.
        rows = brand.get(f"{BASE_URL}/brand/creators").json()
        row = next(c for c in rows if c.get("user_id") == user_id)
        assert row["follower_count_source"] == "self_reported"
        assert row["follower_count_verified"] is False

    def test_the_admin_row_carries_it(self, admin, creator):
        cs, user_id = creator
        pipeline.complete_creator_profile(cs)
        rows = admin.get(f"{BASE_URL}/admin/creators", params={"page_size": 100}).json()
        row = next(c for c in rows["creators"] if c["user_id"] == user_id)
        assert row["follower_count_source"] == "self_reported"


# ---------- 6. The jobs ----------

class TestJobs:
    def test_only_an_admin_may_run_them(self, brand, creator):
        cs, _ = creator
        assert cs.post(f"{BASE_URL}/admin/jobs/instagram").status_code == 403
        assert brand.post(f"{BASE_URL}/admin/jobs/instagram").status_code == 403

    def test_a_manual_run_reports_both_passes(self, admin):
        r = admin.post(f"{BASE_URL}/admin/jobs/instagram")
        assert r.status_code == 200, r.text
        assert set(r.json()) == {"tokens", "stats"}

    def test_it_lands_in_the_audit_log(self, admin):
        admin.post(f"{BASE_URL}/admin/jobs/instagram")
        rows = admin.get(
            f"{BASE_URL}/admin/audit", params={"action": "job.instagram_refresh"}
        ).json()
        assert rows

    def test_running_it_twice_is_harmless(self, admin):
        # Both passes are cache-window bounded, so a second run inside the
        # window has nothing to do and spends no calls.
        first = admin.post(f"{BASE_URL}/admin/jobs/instagram")
        second = admin.post(f"{BASE_URL}/admin/jobs/instagram")
        assert first.status_code == 200 and second.status_code == 200
