"""Backend tests for pivot iteration 13:
- creator profile `city` field
- expanded CATEGORY_LITERAL (real_estate, fashion, travel, wellness)
- admin creator list includes `city`
"""
import os
import re
import time
import random
import subprocess
import pytest

import pipeline  # tests/ is on sys.path
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


def _rand_phone() -> str:
    return f"+9198{random.randint(10000000, 99999999)}"


def _read_otp(phone: str, timeout: float = 5.0) -> str:
    deadline = time.time() + timeout
    pat = re.compile(rf"OTP for {re.escape(phone)} is (\d{{6}})")
    while time.time() < deadline:
        try:
            out = subprocess.check_output(
                ["grep", f"OTP for {phone}", LOG_PATH], text=True, stderr=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError:
            out = ""
        m = pat.findall(out)
        if m:
            return m[-1]
        time.sleep(0.3)
    return ""


def _signup(role: str):
    """Sign up a new creator/brand via OTP and return an authenticated session."""
    phone = _rand_phone()
    s = requests.Session()
    r = s.post(f"{API}/auth/otp/request", json={
        "phone": phone, "purpose": "signup", "name": f"QA {role}", "role": role
    }, timeout=10)
    assert r.status_code == 200, r.text
    code = _read_otp(phone)
    assert code, f"OTP not found in log for {phone}"
    v = s.post(f"{API}/auth/otp/verify", json={
        "phone": phone, "code": code, "purpose": "signup", "name": f"QA {role}", "role": role
    }, timeout=10)
    assert v.status_code == 200, v.text
    return s, phone, v.json()


@pytest.fixture
def creator():
    return _signup("creator")


@pytest.fixture
def brand():
    return _signup("brand")


@pytest.fixture
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
    assert r.status_code == 200, r.text
    return s


# -------- Creator profile: city field --------

def _creator_profile_payload(**overrides):
    body = {
        "name": "City Tester",
        "instagram_handle": "citytester",
        "instagram_profile_url": "https://instagram.com/citytester",
        "email": f"TEST_ct_{random.randint(1000,999999)}@example.com",
        "address": "Bandra West",
        "niches": ["fashion", "travel"],
        "base_rate": 6000,
        "follower_count": 21000,
    }
    body.update(overrides)
    return body


def test_creator_put_and_get_city_mumbai(creator):
    s, _, _ = creator
    payload = _creator_profile_payload(city="Mumbai")
    r = s.put(f"{API}/creator/profile", json=payload, timeout=10)
    assert r.status_code == 200, r.text
    assert r.json()["city"] == "Mumbai"

    g = s.get(f"{API}/creator/profile", timeout=10)
    assert g.status_code == 200
    assert g.json()["city"] == "Mumbai"


def test_creator_put_city_null_returns_null(creator):
    s, _, _ = creator
    # Explicit null
    payload = _creator_profile_payload(city=None)
    r = s.put(f"{API}/creator/profile", json=payload, timeout=10)
    assert r.status_code == 200, r.text
    assert r.json()["city"] is None
    g = s.get(f"{API}/creator/profile", timeout=10).json()
    assert g["city"] is None


def test_creator_put_city_omitted_returns_null(creator):
    s, _, _ = creator
    payload = _creator_profile_payload()  # no city key
    r = s.put(f"{API}/creator/profile", json=payload, timeout=10)
    assert r.status_code == 200, r.text
    assert r.json()["city"] is None


def test_creator_put_city_whitespace_normalized_to_null(creator):
    s, _, _ = creator
    payload = _creator_profile_payload(city="   ")
    r = s.put(f"{API}/creator/profile", json=payload, timeout=10)
    assert r.status_code == 200
    assert r.json()["city"] is None


# -------- New categories on brand campaigns --------

def _brand_setup(brand_session, category="fnb"):
    """Post brand profile and return the session."""
    s, _, _ = brand_session
    r = s.put(f"{API}/brand/profile", json={
        "business_name": f"QA Brand {random.randint(100,999)}",
        "category": category,
        "areas": ["Bengaluru", "Mumbai", "Delhi NCR"],
    }, timeout=10)
    assert r.status_code == 200, r.text
    return s


@pytest.mark.parametrize("cat", ["fnb", "hospitality", "retail", "real_estate", "fashion", "travel", "wellness", "lifestyle"])
def test_brand_profile_accepts_all_8_categories(brand, cat):
    s = _brand_setup(brand, category=cat)
    g = s.get(f"{API}/brand/profile", timeout=10)
    assert g.status_code == 200
    assert g.json()["category"] == cat


@pytest.mark.parametrize("cat", ["real_estate", "fashion", "travel", "wellness"])
def test_post_campaign_new_categories(brand, cat):
    s = _brand_setup(brand, category=cat)
    r = s.post(f"{API}/brand/campaigns", json={
        "title": f"Pivot Campaign {cat}",
        "brief": f"Testing {cat} category",
        "deliverables": "1 reel",
        "budget_per_creator": 5000,
        "category": cat,
        "area": "Mumbai",
        "creators_needed": 2,
        "status": "draft",
        "campaign_type": "personal_table", "start_date": "2025-06-01T00:00:00Z", "end_date": "2027-06-01T00:00:00Z",
    }, timeout=10)
    assert r.status_code == 200, r.text
    assert r.json()["category"] == cat


def test_post_campaign_invalid_category_422(brand):
    s = _brand_setup(brand, category="fnb")
    r = s.post(f"{API}/brand/campaigns", json={
        "title": "Bad Cat",
        "brief": "invalid",
        "deliverables": "1 reel",
        "budget_per_creator": 5000,
        "category": "foo",
        "area": "Mumbai",
        "creators_needed": 1,
        "campaign_type": "personal_table", "start_date": "2025-06-01T00:00:00Z", "end_date": "2027-06-01T00:00:00Z",
    }, timeout=10)
    assert r.status_code == 422, r.text


def test_new_category_campaign_appears_in_list(creator, brand, admin):
    s_b = _brand_setup(brand, category="fashion")
    # A campaign reaches the feed through review, not through the payload.
    pipeline.verify_brand(admin, pipeline.user_id_of(s_b))
    unique_title = f"TEST_pivot_fashion_{random.randint(1000,999999)}"
    r = s_b.post(f"{API}/brand/campaigns", json={
        "title": unique_title,
        "brief": "Fashion pivot",
        "deliverables": "reel",
        "budget_per_creator": 8000,
        "category": "fashion",
        "area": "Mumbai",
        "creators_needed": 1,
        "status": "draft",
        "campaign_type": "personal_table", "start_date": "2025-06-01T00:00:00Z", "end_date": "2027-06-01T00:00:00Z",
    }, timeout=10)
    assert r.status_code == 200
    pipeline.submit_campaign(s_b, r.json()["id"])
    assert pipeline.approve_campaign(admin, r.json()["id"]) == "open"
    # Creator lists campaigns
    s_c, _, _ = creator
    listing = s_c.get(f"{API}/campaigns", timeout=10).json()
    titles = [c["title"] for c in listing]
    assert unique_title in titles
    row = next(c for c in listing if c["title"] == unique_title)
    assert row["category"] == "fashion"


# -------- Filters endpoint shape unchanged --------

def test_filters_endpoint_shape(creator):
    s, _, _ = creator
    r = s.get(f"{API}/campaigns/filters", timeout=10)
    assert r.status_code == 200
    d = r.json()
    for k in ("areas", "categories", "budget_bounds"):
        assert k in d, f"missing key {k} in filters response"
    assert isinstance(d["areas"], list)
    assert isinstance(d["categories"], list)


def test_list_campaigns_filters_still_work(creator):
    s, _, _ = creator
    # budget_min / budget_max / q / sort
    r = s.get(f"{API}/campaigns", params={"budget_min": 0, "budget_max": 1000000, "sort": "newest"}, timeout=10)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    r2 = s.get(f"{API}/campaigns", params={"sort": "budget_desc"}, timeout=10)
    assert r2.status_code == 200
    r3 = s.get(f"{API}/campaigns", params={"q": "cafe"}, timeout=10)
    assert r3.status_code == 200


# -------- Admin list returns city --------

def test_admin_creators_pending_returns_city(creator, admin):
    s_c, _, _ = creator
    r = s_c.put(f"{API}/creator/profile", json=_creator_profile_payload(city="Hyderabad"), timeout=10)
    assert r.status_code == 200
    # Admin lists pending creators
    lr = admin.get(f"{API}/admin/creators/pending", timeout=10)
    assert lr.status_code == 200, lr.text
    rows = lr.json()
    # Find our creator by instagram_handle
    match = [row for row in rows if row.get("instagram_handle") == "citytester"]
    assert match, "created creator not found in admin/creators/pending list"
    assert match[0]["city"] == "Hyderabad"


# -------- Admin login unchanged --------

def test_admin_login_still_works(admin):
    me = admin.get(f"{API}/auth/me", timeout=10)
    assert me.status_code == 200
    assert me.json()["role"] == "admin"
