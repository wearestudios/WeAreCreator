"""Backend tests for the brand-facing creator directory (iteration 14)."""
import os
import re
import time
import random
import subprocess
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "creators@wearemonk.in"
ADMIN_PASSWORD = "WeAreMonk@2026"
LOG_PATH = "/var/log/supervisor/backend.err.log"

# Seeded PII fields that must NOT appear in the public directory response
FORBIDDEN_FIELDS = {"email", "phone", "address", "password", "password_hash"}

SEEDED_CREATOR_NAMES = {
    "Priya Rao", "Arjun Mehta", "Ananya Gupta", "Rohan Kapoor",
    "Meera Iyer", "Kabir Singh", "Sana Khan", "Vivek Rao",
}


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


def _rand_phone() -> str:
    return f"+9198{random.randint(10000000, 99999999)}"


def _grep_otp(phone: str, timeout: float = 5.0) -> str:
    deadline = time.time() + timeout
    pat = re.compile(rf"OTP for {re.escape(phone)} is (\d{{6}})")
    while time.time() < deadline:
        try:
            out = subprocess.check_output(
                ["grep", f"OTP for {phone}", LOG_PATH], text=True, stderr=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError:
            out = ""
        m = None
        for line in reversed(out.splitlines()):
            m = pat.search(line)
            if m:
                return m.group(1)
        time.sleep(0.4)
    raise AssertionError(f"OTP for {phone} not found in log within {timeout}s")


def _otp_signup(role: str) -> requests.Session:
    s = requests.Session()
    phone = _rand_phone()
    name = f"TEST_{role}_{random.randint(1000,9999)}"
    r = s.post(f"{API}/auth/otp/request", json={"phone": phone, "purpose": "signup", "name": name, "role": role})
    assert r.status_code == 200, r.text
    code = _grep_otp(phone)
    r = s.post(f"{API}/auth/otp/verify", json={"phone": phone, "code": code, "purpose": "signup", "name": name, "role": role})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def creator_session():
    return _otp_signup("creator")


# ---------- auth guardrails ----------
class TestAuthGuardrails:
    def test_unauthenticated_directory_401(self):
        r = requests.get(f"{API}/brand/creators")
        assert r.status_code == 401

    def test_unauthenticated_filters_401(self):
        r = requests.get(f"{API}/brand/creators/filters")
        assert r.status_code == 401

    def test_creator_forbidden_directory(self, creator_session):
        r = creator_session.get(f"{API}/brand/creators")
        assert r.status_code == 403

    def test_creator_forbidden_filters(self, creator_session):
        r = creator_session.get(f"{API}/brand/creators/filters")
        assert r.status_code == 403


# ---------- directory basic ----------
class TestDirectoryPublicProjection:
    def test_admin_can_list(self, admin_session):
        r = admin_session.get(f"{API}/brand/creators")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 8, f"Expected >=8 seeded creators, got {len(data)}"

    def test_no_pii_in_projection(self, admin_session):
        r = admin_session.get(f"{API}/brand/creators")
        data = r.json()
        for item in data:
            leaked = FORBIDDEN_FIELDS.intersection(item.keys())
            assert not leaked, f"PII leaked in directory item: {leaked} | item={item}"

    def test_expected_public_fields(self, admin_session):
        r = admin_session.get(f"{API}/brand/creators")
        data = r.json()
        expected = {"id", "user_id", "name", "instagram_handle", "instagram_profile_url",
                    "city", "niches", "follower_count", "base_rate"}
        for item in data:
            missing = expected - set(item.keys())
            assert not missing, f"Missing fields {missing} in {item}"

    def test_seeded_creator_names_present(self, admin_session):
        r = admin_session.get(f"{API}/brand/creators")
        names = {c.get("name") for c in r.json()}
        overlap = SEEDED_CREATOR_NAMES.intersection(names)
        assert len(overlap) == 8, f"Expected all 8 seeded creators. Found: {overlap}"


# ---------- filters ----------
class TestDirectoryFilters:
    def test_city_filter_mumbai(self, admin_session):
        r = admin_session.get(f"{API}/brand/creators", params={"city": "Mumbai"})
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        for c in data:
            assert c["city"] == "Mumbai"

    def test_min_followers_filter(self, admin_session):
        r = admin_session.get(f"{API}/brand/creators", params={"min_followers": 100000})
        assert r.status_code == 200
        data = r.json()
        for c in data:
            assert (c["follower_count"] or 0) >= 100000, c

    def test_sort_followers_desc(self, admin_session):
        r = admin_session.get(f"{API}/brand/creators", params={"sort": "followers_desc"})
        assert r.status_code == 200
        data = r.json()
        # non-null followers should be sorted high->low
        counts = [c["follower_count"] for c in data if c["follower_count"] is not None]
        assert counts == sorted(counts, reverse=True), counts

    def test_search_q_case_insensitive(self, admin_session):
        r = admin_session.get(f"{API}/brand/creators", params={"q": "COCKTAILS"})
        assert r.status_code == 200
        data = r.json()
        # each match should contain 'cocktails' in some searchable field
        for c in data:
            hay = " ".join([str(c.get("name") or ""), str(c.get("instagram_handle") or ""),
                            " ".join(c.get("niches") or [])]).lower()
            assert "cocktail" in hay, c

    def test_search_travel_narrows(self, admin_session):
        r = admin_session.get(f"{API}/brand/creators", params={"q": "travel"})
        assert r.status_code == 200
        names = {c["name"] for c in r.json()}
        assert "Rohan Kapoor" in names

    def test_niche_filter(self, admin_session):
        r = admin_session.get(f"{API}/brand/creators", params={"niche": "fashion"})
        assert r.status_code == 200
        for c in r.json():
            assert any(n.lower() == "fashion" for n in c["niches"]), c


# ---------- filters endpoint ----------
class TestDirectoryFiltersEndpoint:
    def test_filters_shape(self, admin_session):
        r = admin_session.get(f"{API}/brand/creators/filters")
        assert r.status_code == 200
        data = r.json()
        assert set(data.keys()) >= {"cities", "niches", "total"}
        assert isinstance(data["cities"], list)
        assert isinstance(data["niches"], list)
        assert isinstance(data["total"], int)

    def test_filters_includes_seeded_cities(self, admin_session):
        data = admin_session.get(f"{API}/brand/creators/filters").json()
        cities = set(data["cities"])
        for expected in ("Bengaluru", "Mumbai", "Delhi NCR"):
            assert expected in cities, f"{expected} missing from {cities}"

    def test_filters_niches_case_deduplicated(self, admin_session):
        data = admin_session.get(f"{API}/brand/creators/filters").json()
        niches = data["niches"]
        lowered = [n.lower() for n in niches]
        assert len(lowered) == len(set(lowered)), f"Case-insensitive duplicates in {niches}"

    def test_filters_total_matches_directory_length(self, admin_session):
        filt = admin_session.get(f"{API}/brand/creators/filters").json()
        listing = admin_session.get(f"{API}/brand/creators").json()
        assert filt["total"] == len(listing)


# ---------- idempotency ----------
class TestSeedIdempotency:
    def test_count_stable_after_two_requests(self, admin_session):
        c1 = admin_session.get(f"{API}/brand/creators/filters").json()["total"]
        c2 = admin_session.get(f"{API}/brand/creators/filters").json()["total"]
        assert c1 == c2
        # 8 seeded (may be higher if real creators are also approved, but should not
        # keep growing between calls).
        assert c1 >= 8
