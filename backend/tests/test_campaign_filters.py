"""Backend tests for the new /api/campaigns filter/sort/search + filters.budget_bounds contract."""
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


def _rand_phone() -> str:
    return f"+9198{random.randint(10000000, 99999999)}"


def _read_otp_from_log(phone: str, timeout: float = 5.0) -> str:
    deadline = time.time() + timeout
    pattern = re.compile(rf"OTP for {re.escape(phone)} is (\d{{6}})")
    while time.time() < deadline:
        try:
            out = subprocess.check_output(
                ["grep", f"OTP for {phone}", LOG_PATH], text=True, stderr=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError:
            out = ""
        m = pattern.findall(out)
        if m:
            return m[-1]
        time.sleep(0.4)
    return ""


@pytest.fixture(scope="module")
def creator_session():
    """Create a fresh creator via OTP and return an authenticated session."""
    phone = _rand_phone()
    r = requests.post(
        f"{API}/auth/otp/request",
        json={"phone": phone, "purpose": "signup", "name": "Filter QA", "role": "creator"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    code = _read_otp_from_log(phone)
    assert code, f"OTP not logged for {phone}"
    s = requests.Session()
    v = s.post(
        f"{API}/auth/otp/verify",
        json={"phone": phone, "code": code, "purpose": "signup", "name": "Filter QA", "role": "creator"},
        timeout=10,
    )
    assert v.status_code == 200, v.text
    return s


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
    assert r.status_code == 200, r.text
    return s


# --- /api/campaigns/filters --------------------------------------------------

def test_filters_returns_budget_bounds(creator_session):
    r = creator_session.get(f"{API}/campaigns/filters", timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "areas" in data and isinstance(data["areas"], list)
    assert "categories" in data and isinstance(data["categories"], list)
    assert "budget_bounds" in data
    bb = data["budget_bounds"]
    assert set(bb.keys()) == {"min", "max"}
    assert isinstance(bb["min"], (int, float))
    assert isinstance(bb["max"], (int, float))
    assert bb["min"] <= bb["max"]


# --- /api/campaigns list: sort ----------------------------------------------

def test_list_default_newest_first(creator_session):
    r = creator_session.get(f"{API}/campaigns", timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list) and len(data) >= 2
    times = [c.get("created_at") for c in data if c.get("created_at")]
    assert times == sorted(times, reverse=True), "default sort should be newest first"


def test_sort_budget_desc(creator_session):
    r = creator_session.get(f"{API}/campaigns", params={"sort": "budget_desc"}, timeout=10)
    assert r.status_code == 200
    budgets = [c["budget_per_creator"] for c in r.json()]
    assert budgets == sorted(budgets, reverse=True), f"budget_desc not descending: {budgets}"


def test_sort_budget_asc(creator_session):
    r = creator_session.get(f"{API}/campaigns", params={"sort": "budget_asc"}, timeout=10)
    assert r.status_code == 200
    budgets = [c["budget_per_creator"] for c in r.json()]
    assert budgets == sorted(budgets), f"budget_asc not ascending: {budgets}"


def test_sort_newest_explicit(creator_session):
    r = creator_session.get(f"{API}/campaigns", params={"sort": "newest"}, timeout=10)
    assert r.status_code == 200
    times = [c.get("created_at") for c in r.json() if c.get("created_at")]
    assert times == sorted(times, reverse=True)


# --- /api/campaigns list: budget bucket -------------------------------------

def test_budget_min_filter_gt_15k(creator_session):
    r = creator_session.get(f"{API}/campaigns", params={"budget_min": 15001}, timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert all(c["budget_per_creator"] >= 15001 for c in data), [c["budget_per_creator"] for c in data]


def test_budget_range_15k_to_50k(creator_session):
    r = creator_session.get(
        f"{API}/campaigns", params={"budget_min": 15000, "budget_max": 50000}, timeout=10
    )
    assert r.status_code == 200
    data = r.json()
    assert all(15000 <= c["budget_per_creator"] <= 50000 for c in data)


def test_budget_max_only_under_5k(creator_session):
    r = creator_session.get(f"{API}/campaigns", params={"budget_max": 5000}, timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert all(c["budget_per_creator"] <= 5000 for c in data)


# --- /api/campaigns list: q keyword search ----------------------------------

def test_q_keyword_narrows_list(creator_session):
    full = creator_session.get(f"{API}/campaigns", timeout=10).json()
    # find a keyword that exists in at least one title/brief/deliverables
    keyword = None
    for c in full:
        for f in ("title", "brief", "deliverables"):
            v = c.get(f) or ""
            words = [w for w in re.split(r"\W+", v) if len(w) >= 4]
            if words:
                keyword = words[0]
                break
        if keyword:
            break
    assert keyword, "no keyword found in seed campaigns"
    r = creator_session.get(f"{API}/campaigns", params={"q": keyword}, timeout=10)
    assert r.status_code == 200
    filtered = r.json()
    assert 1 <= len(filtered) <= len(full)
    kl = keyword.lower()
    for c in filtered:
        blob = " ".join(str(c.get(f) or "") for f in ("title", "brief", "deliverables")).lower()
        assert kl in blob, f"campaign {c.get('id')} does not contain '{kl}': {blob[:120]}"


def test_q_nonmatching_returns_empty(creator_session):
    r = creator_session.get(f"{API}/campaigns", params={"q": "zzzq_definitely_not_present_xxxx"}, timeout=10)
    assert r.status_code == 200
    assert r.json() == []


def test_q_is_case_insensitive(creator_session):
    lower = creator_session.get(f"{API}/campaigns", params={"q": "coffee"}, timeout=10).json()
    upper = creator_session.get(f"{API}/campaigns", params={"q": "COFFEE"}, timeout=10).json()
    assert {c["id"] for c in lower} == {c["id"] for c in upper}


# --- Combining filters ------------------------------------------------------

def test_combined_area_category_budget(creator_session):
    # Pull filters to grab a real area/category pair
    filt = creator_session.get(f"{API}/campaigns/filters", timeout=10).json()
    if not filt["areas"] or not filt["categories"]:
        pytest.skip("no areas/categories seeded")
    area = filt["areas"][0]
    category = filt["categories"][0]
    r = creator_session.get(
        f"{API}/campaigns",
        params={"area": area, "category": category, "budget_min": 0, "budget_max": 10_000_000},
        timeout=10,
    )
    assert r.status_code == 200
    for c in r.json():
        assert c["area"] == area
        assert c["category"] == category
        assert 0 <= c["budget_per_creator"] <= 10_000_000


def test_combined_q_and_sort(creator_session):
    full = creator_session.get(f"{API}/campaigns", timeout=10).json()
    if not full:
        pytest.skip("no campaigns")
    # pick a broadly-matching keyword from title of first campaign
    title = full[0].get("title") or ""
    kw = next((w for w in re.split(r"\W+", title) if len(w) >= 4), None)
    if not kw:
        pytest.skip("no long word in first title")
    r = creator_session.get(f"{API}/campaigns", params={"q": kw, "sort": "budget_desc"}, timeout=10)
    assert r.status_code == 200
    data = r.json()
    budgets = [c["budget_per_creator"] for c in data]
    assert budgets == sorted(budgets, reverse=True)


# --- Auth regression: shapes preserved --------------------------------------

def test_admin_login_shape_unchanged(admin_session):
    r = admin_session.get(f"{API}/auth/me", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body.get("role") == "admin"
    assert body.get("email") == ADMIN_EMAIL
    assert "id" in body


def test_creator_me_shape(creator_session):
    r = creator_session.get(f"{API}/auth/me", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "creator"
    assert body["phone"].startswith("+91")
    assert "id" in body


def test_list_requires_auth():
    r = requests.get(f"{API}/campaigns", timeout=10)
    assert r.status_code == 401


def test_admin_can_list_campaigns_with_new_params(admin_session):
    r = admin_session.get(f"{API}/campaigns", params={"sort": "budget_desc", "budget_min": 0}, timeout=10)
    assert r.status_code == 200
    data = r.json()
    budgets = [c["budget_per_creator"] for c in data]
    assert budgets == sorted(budgets, reverse=True)
