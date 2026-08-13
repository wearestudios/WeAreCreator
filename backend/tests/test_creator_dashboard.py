"""Tests for GET /api/creator/dashboard endpoint."""
import os
import uuid
import pytest
import requests
from bson import ObjectId
from pymongo import MongoClient

import pipeline  # tests/ is on sys.path (no __init__.py, pytest prepend mode)

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

_mongo = MongoClient(MONGO_URL)
_db = _mongo[DB_NAME]


ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "creators@wearemonk.in")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "WeAreMonk@2026")


def _admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


def _rand(prefix):
    return f"TEST_{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def creator_session():
    s = requests.Session()
    email = f"{_rand('creator')}@example.com"
    r = s.post(f"{API}/auth/register", json={
        "email": email, "password": "Password123!",
        "name": "Priya D", "role": "creator",
    })
    assert r.status_code == 200, r.text
    s.email = email
    s.user_id = r.json()["id"]
    return s


@pytest.fixture(scope="module")
def brand_session():
    s = requests.Session()
    email = f"{_rand('brand')}@example.com"
    r = s.post(f"{API}/auth/register", json={
        "email": email, "password": "Password123!",
        "name": "Brand X", "role": "brand",
    })
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "creators@wearemonk.in"),
        "password": os.environ.get("ADMIN_PASSWORD", "WeAreMonk@2026"),
    })
    assert r.status_code == 200, r.text
    return s


# --- Role gating ----------------------------------------------------------

def test_dashboard_requires_auth():
    r = requests.get(f"{API}/creator/dashboard")
    assert r.status_code == 401


def test_dashboard_forbidden_for_brand(brand_session):
    r = brand_session.get(f"{API}/creator/dashboard")
    assert r.status_code == 403


def test_dashboard_forbidden_for_admin(admin_session):
    r = admin_session.get(f"{API}/creator/dashboard")
    assert r.status_code == 403


# --- Fresh creator dashboard shape ----------------------------------------

def test_fresh_creator_dashboard_shape(creator_session):
    r = creator_session.get(f"{API}/creator/dashboard")
    assert r.status_code == 200
    d = r.json()
    # Keys present
    for k in ["profile", "applications", "upcoming", "payments",
              "in_payment_collaborations", "totals"]:
        assert k in d, f"missing {k}"
    # Profile keys
    for k in ["name", "instagram_handle", "instagram_profile_url",
              "verification_status", "niches", "follower_count", "base_rate"]:
        assert k in d["profile"], f"missing profile.{k}"
    assert d["profile"]["verification_status"] == "pending"
    assert d["applications"] == []
    assert d["upcoming"] == []
    assert d["payments"] == []
    assert d["totals"]["applications"] == 0


# --- End-to-end: onboard + apply + verify ---------------------------------

def test_creator_onboarding_and_dashboard_flow(creator_session):
    # PUT profile
    r = creator_session.put(f"{API}/creator/profile", json={
        "name": "Priya D",
        "instagram_handle": "@priyad",
        "instagram_profile_url": "https://instagram.com/priyad",
        "email": creator_session.email,
        "address": "Indiranagar, Bengaluru",
        "niches": ["cafe", "brunch"],
        "base_rate": 7000,
        "follower_count": 22400,
    })
    assert r.status_code == 200, r.text
    prof = r.json()
    assert prof["instagram_handle"] == "priyad"
    assert prof["follower_count"] == 22400
    assert prof["base_rate"] == 7000
    assert prof["niches"] == ["cafe", "brunch"]

    # Verification gates applying, so the profile has to be approved before pitching.
    me = creator_session.get(f"{API}/auth/me").json()
    pipeline.verify_creator(_admin_session(), me["id"])

    # Fetch 2 open campaigns
    r = creator_session.get(f"{API}/campaigns")
    assert r.status_code == 200
    open_camps = [c for c in r.json() if c["status"] == "open"][:2]
    assert len(open_camps) >= 2, "seed data must have >=2 open campaigns"

    for c in open_camps:
        r = creator_session.post(
            f"{API}/campaigns/{c['id']}/apply",
            json={"pitch": "Excited to pitch this one.", "quoted_rate": 7500},
        )
        assert r.status_code == 200, r.text

    # Dashboard should now show 2 applications
    r = creator_session.get(f"{API}/creator/dashboard")
    assert r.status_code == 200
    d = r.json()
    assert d["profile"]["follower_count"] == 22400
    assert d["profile"]["instagram_handle"] == "priyad"
    assert d["profile"]["niches"] == ["cafe", "brunch"]
    assert len(d["applications"]) == 2
    for a in d["applications"]:
        assert a["state"] == "applied"
        assert a["quoted_rate"] == 7500
        assert a["campaign_title"], "campaign_title missing"
        assert a["brand_name"], "brand_name missing"
        # area/category expected from seed data
        assert "area" in a
        assert "category" in a
    assert d["upcoming"] == []
    assert d["payments"] == []
    assert d["totals"]["applications"] == 2
    # Sorted newest first
    dates = [a["created_at"] for a in d["applications"]]
    assert dates == sorted(dates, reverse=True)


# --- Manual mongo mutations for upcoming / in_payment / paid --------------

def test_slot_booked_appears_in_upcoming(creator_session):
    creator_oid = ObjectId(creator_session.user_id)
    collab = _db.collaborations.find_one({"creator_id": creator_oid})
    assert collab is not None, "prev flow must have created a collab"
    _db.collaborations.update_one(
        {"_id": collab["_id"]}, {"$set": {"state": "slot_booked"}}
    )
    try:
        r = creator_session.get(f"{API}/creator/dashboard")
        assert r.status_code == 200
        d = r.json()
        up_ids = [u["id"] for u in d["upcoming"]]
        assert str(collab["_id"]) in up_ids
        assert d["totals"]["upcoming"] >= 1
    finally:
        # Restore for next test isolation
        _db.collaborations.update_one(
            {"_id": collab["_id"]}, {"$set": {"state": "applied"}}
        )


def test_in_payment_appears_in_in_payment_collaborations(creator_session):
    creator_oid = ObjectId(creator_session.user_id)
    collab = _db.collaborations.find_one({"creator_id": creator_oid})
    assert collab is not None
    _db.collaborations.update_one(
        {"_id": collab["_id"]}, {"$set": {"state": "in_payment"}}
    )
    try:
        r = creator_session.get(f"{API}/creator/dashboard")
        assert r.status_code == 200
        d = r.json()
        ids = [c["id"] for c in d["in_payment_collaborations"]]
        assert str(collab["_id"]) in ids
    finally:
        _db.collaborations.update_one(
            {"_id": collab["_id"]}, {"$set": {"state": "applied"}}
        )


def test_paid_payment_appears_in_payments(creator_session):
    creator_oid = ObjectId(creator_session.user_id)
    collab = _db.collaborations.find_one({"creator_id": creator_oid})
    assert collab is not None
    from datetime import datetime, timezone
    pay_doc = {
        "collaboration_id": collab["_id"],
        "agreed_amount": 7500.0,
        "platform_fee": 500.0,
        "creator_payout": 7000.0,
        "state": "paid",
        "paid_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    _db.payments.delete_many({"collaboration_id": collab["_id"]})
    pid = _db.payments.insert_one(pay_doc).inserted_id
    try:
        r = creator_session.get(f"{API}/creator/dashboard")
        assert r.status_code == 200
        d = r.json()
        assert len(d["payments"]) >= 1
        p = next((x for x in d["payments"] if x["id"] == str(pid)), None)
        assert p is not None, "inserted payment not present"
        assert p["state"] == "paid"
        assert p["creator_payout"] == 7000.0
        assert p["campaign_title"]
        assert p["brand_name"]
    finally:
        _db.payments.delete_one({"_id": pid})
