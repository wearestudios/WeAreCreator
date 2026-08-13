"""Backend tests for creator onboarding profile endpoints (GET/PUT /api/creator/profile)."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"


def _rand_email(role):
    return f"TEST_{role}-{uuid.uuid4().hex[:10]}@example.com"


def _register(session, role):
    email = _rand_email(role)
    r = session.post(f"{BASE_URL}/auth/register", json={
        "email": email, "password": "Password123!", "name": f"Test {role.title()}", "role": role
    })
    assert r.status_code == 200, r.text
    return email, r.json()


@pytest.fixture
def creator_session():
    s = requests.Session()
    email, user = _register(s, "creator")
    return s, email, user


@pytest.fixture
def brand_session():
    s = requests.Session()
    email, user = _register(s, "brand")
    return s, email, user


@pytest.fixture
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "creators@wearemonk.in"),
        "password": os.environ.get("ADMIN_PASSWORD", "WeAreMonk@2026"),
    })
    assert r.status_code == 200, r.text
    return s


# ---------- role guard ----------

def test_get_profile_requires_creator_brand_403(brand_session):
    s, _, _ = brand_session
    r = s.get(f"{BASE_URL}/creator/profile")
    assert r.status_code == 403


def test_get_profile_requires_creator_admin_403(admin_session):
    r = admin_session.get(f"{BASE_URL}/creator/profile")
    assert r.status_code == 403


def test_get_profile_creator_200(creator_session):
    s, email, _ = creator_session
    r = s.get(f"{BASE_URL}/creator/profile")
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == email.lower()
    assert data["vetting_status"] == "pending"
    assert data["niches"] == []


# ---------- PUT normalization ----------

def test_put_profile_normalizes_and_persists(creator_session):
    s, email, user = creator_session
    payload = {
        "name": "Priya Rao",
        "instagram_handle": "@Priya.Rao",  # leading @ stripped, lowercased
        "instagram_profile_url": "https://instagram.com/priya.rao",
        "email": email,
        "address": "Indiranagar, Bengaluru",
        "niches": ["Cafe", "  BRUNCH  ", "Homely"],  # lowercased, stripped
        "base_rate": 5000,
        "follower_count": 12400,
    }
    r = s.put(f"{BASE_URL}/creator/profile", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["instagram_handle"] == "priya.rao"
    assert data["niches"] == ["cafe", "brunch", "homely"]
    assert data["vetting_status"] == "pending"
    assert data["base_rate"] == 5000
    assert data["follower_count"] == 12400
    assert data["name"] == "Priya Rao"

    # GET verifies persistence
    r2 = s.get(f"{BASE_URL}/creator/profile")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["instagram_handle"] == "priya.rao"
    assert d2["niches"] == ["cafe", "brunch", "homely"]
    assert d2["vetting_status"] == "pending"

    # user's name mirrored
    me = s.get(f"{BASE_URL}/auth/me").json()
    assert me["name"] == "Priya Rao"


def test_put_profile_brand_403(brand_session):
    s, email, _ = brand_session
    r = s.put(f"{BASE_URL}/creator/profile", json={
        "name": "X", "instagram_handle": "x", "instagram_profile_url": "https://ig/x",
        "email": email, "address": "y", "niches": ["cafe"],
    })
    assert r.status_code == 403


def test_put_profile_vetting_reset_to_pending(creator_session):
    s, email, _ = creator_session
    payload = {
        "name": "N", "instagram_handle": "n", "instagram_profile_url": "https://ig/n",
        "email": email, "address": "addr", "niches": ["cafe"],
    }
    r = s.put(f"{BASE_URL}/creator/profile", json=payload)
    assert r.status_code == 200
    assert r.json()["vetting_status"] == "pending"
    # second edit still pending
    r2 = s.put(f"{BASE_URL}/creator/profile", json=payload)
    assert r2.json()["vetting_status"] == "pending"


def test_put_profile_unauthenticated_401():
    r = requests.put(f"{BASE_URL}/creator/profile", json={
        "name": "N", "instagram_handle": "n", "instagram_profile_url": "https://ig/n",
        "email": "x@y.com", "address": "a", "niches": ["cafe"],
    })
    assert r.status_code == 401
