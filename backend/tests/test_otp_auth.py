"""Backend tests for WhatsApp OTP auth (simulation mode) + admin email login."""
import os
import re
import time
import random
import subprocess
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback read from frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "creators@wearemonk.in"
ADMIN_PASSWORD = "WeAreMonk@2026"

LOG_PATH = "/var/log/supervisor/backend.err.log"


def _rand_phone() -> str:
    # random unused Indian phone number
    return f"+9198{random.randint(10000000, 99999999)}"


def _read_otp_from_log(phone: str, timeout: float = 5.0) -> str:
    """Grep the backend log for the most recent OTP for the given phone."""
    deadline = time.time() + timeout
    pattern = re.compile(rf"OTP for {re.escape(phone)} is (\d{{6}})")
    while time.time() < deadline:
        try:
            out = subprocess.check_output(
                ["grep", f"OTP for {phone}", LOG_PATH], text=True, stderr=subprocess.DEVNULL
            )
        except subprocess.CalledProcessError:
            out = ""
        matches = pattern.findall(out)
        if matches:
            return matches[-1]
        time.sleep(0.4)
    return ""


@pytest.fixture
def phone():
    return _rand_phone()


# --- /otp/request signup happy path (simulation mode) -----------------------

def test_signup_request_returns_simulation_and_logs_code(phone):
    r = requests.post(
        f"{API}/auth/otp/request",
        json={"phone": phone, "purpose": "signup", "name": "Test Creator", "role": "creator"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("success") is True
    assert data.get("mode") == "simulation"
    code = _read_otp_from_log(phone)
    assert re.match(r"^\d{6}$", code or ""), f"OTP not found in log for {phone}"


# --- 30s per-phone cooldown -------------------------------------------------

def test_cooldown_30s(phone):
    r1 = requests.post(
        f"{API}/auth/otp/request",
        json={"phone": phone, "purpose": "signup", "name": "Alice", "role": "creator"},
        timeout=10,
    )
    assert r1.status_code == 200
    r2 = requests.post(
        f"{API}/auth/otp/request",
        json={"phone": phone, "purpose": "signup", "name": "Alice", "role": "creator"},
        timeout=10,
    )
    assert r2.status_code == 429
    assert "wait" in r2.json().get("detail", "").lower()


# --- Verify happy path (creates creator user, sets cookies) -----------------

def test_verify_signup_creates_creator_and_sets_cookies(phone):
    r = requests.post(
        f"{API}/auth/otp/request",
        json={"phone": phone, "purpose": "signup", "name": "QA Alice", "role": "creator"},
        timeout=10,
    )
    assert r.status_code == 200
    code = _read_otp_from_log(phone)
    assert code, "OTP not logged"

    s = requests.Session()
    v = s.post(
        f"{API}/auth/otp/verify",
        json={"phone": phone, "code": code, "purpose": "signup", "name": "QA Alice", "role": "creator"},
        timeout=10,
    )
    assert v.status_code == 200, v.text
    body = v.json()
    assert body["role"] == "creator"
    assert body["phone"] == phone
    assert body["name"] == "QA Alice"
    assert "id" in body
    # cookies set
    cookie_names = {c.name for c in s.cookies}
    assert "access_token" in cookie_names
    assert "refresh_token" in cookie_names

    me = s.get(f"{API}/auth/me", timeout=10)
    assert me.status_code == 200
    assert me.json()["phone"] == phone


# --- Wrong code lockout ------------------------------------------------------

def test_wrong_code_locks_after_5_attempts(phone):
    r = requests.post(
        f"{API}/auth/otp/request",
        json={"phone": phone, "purpose": "signup", "name": "Lock Test", "role": "creator"},
        timeout=10,
    )
    assert r.status_code == 200
    correct_code = _read_otp_from_log(phone)
    assert correct_code
    # 5 wrong attempts
    wrong = "000000" if correct_code != "000000" else "111111"
    statuses = []
    for _ in range(5):
        vr = requests.post(
            f"{API}/auth/otp/verify",
            json={"phone": phone, "code": wrong, "purpose": "signup", "name": "Lock Test", "role": "creator"},
            timeout=10,
        )
        statuses.append(vr.status_code)
    # 6th attempt with correct code should still be blocked
    final = requests.post(
        f"{API}/auth/otp/verify",
        json={"phone": phone, "code": correct_code, "purpose": "signup", "name": "Lock Test", "role": "creator"},
        timeout=10,
    )
    assert final.status_code == 429, f"Expected 429 after lockout, got {final.status_code} - {final.text}. Prior statuses: {statuses}"
    assert "too many" in final.json().get("detail", "").lower()


# --- Signup with existing phone => 409 --------------------------------------

def test_signup_existing_phone_returns_409():
    phone = _rand_phone()
    # Create the user first
    r = requests.post(
        f"{API}/auth/otp/request",
        json={"phone": phone, "purpose": "signup", "name": "Dup", "role": "creator"},
        timeout=10,
    )
    assert r.status_code == 200
    code = _read_otp_from_log(phone)
    assert code
    v = requests.post(
        f"{API}/auth/otp/verify",
        json={"phone": phone, "code": code, "purpose": "signup", "name": "Dup", "role": "creator"},
        timeout=10,
    )
    assert v.status_code == 200

    # Wait cooldown then try signup again
    time.sleep(31)
    r2 = requests.post(
        f"{API}/auth/otp/request",
        json={"phone": phone, "purpose": "signup", "name": "Dup", "role": "creator"},
        timeout=10,
    )
    assert r2.status_code == 409


# --- Login flow with newly registered phone ---------------------------------

def test_login_flow_after_signup():
    phone = _rand_phone()
    # signup
    r = requests.post(
        f"{API}/auth/otp/request",
        json={"phone": phone, "purpose": "signup", "name": "LoginUser", "role": "brand"},
        timeout=10,
    )
    assert r.status_code == 200
    code = _read_otp_from_log(phone)
    v = requests.post(
        f"{API}/auth/otp/verify",
        json={"phone": phone, "code": code, "purpose": "signup", "name": "LoginUser", "role": "brand"},
        timeout=10,
    )
    assert v.status_code == 200

    # wait cooldown and now login
    time.sleep(31)
    lr = requests.post(
        f"{API}/auth/otp/request",
        json={"phone": phone, "purpose": "login"},
        timeout=10,
    )
    assert lr.status_code == 200, lr.text
    lcode = _read_otp_from_log(phone)
    assert lcode
    s = requests.Session()
    lv = s.post(
        f"{API}/auth/otp/verify",
        json={"phone": phone, "code": lcode, "purpose": "login"},
        timeout=10,
    )
    assert lv.status_code == 200, lv.text
    assert lv.json()["phone"] == phone
    assert "access_token" in {c.name for c in s.cookies}


# --- Login on unknown phone => 404 -----------------------------------------

def test_login_unknown_phone_returns_404():
    phone = _rand_phone()
    r = requests.post(
        f"{API}/auth/otp/request",
        json={"phone": phone, "purpose": "login"},
        timeout=10,
    )
    assert r.status_code == 404


# --- Admin email login still works -----------------------------------------

def test_admin_email_login_success():
    s = requests.Session()
    r = s.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "admin"
    assert "access_token" in {c.name for c in s.cookies}


def test_admin_email_login_wrong_password():
    r = requests.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": "wrong-password"},
        timeout=10,
    )
    assert r.status_code in (401, 403)


# --- Invalid phone => 400 ---------------------------------------------------

@pytest.mark.parametrize("bad", ["9999911111", "+abcdefghij", "+12", ""])
def test_invalid_phone_returns_400(bad):
    r = requests.post(
        f"{API}/auth/otp/request",
        json={"phone": bad, "purpose": "signup", "name": "X", "role": "creator"},
        timeout=10,
    )
    # Pydantic min_length=8 may make some fail as 422; treat both as validation failure
    assert r.status_code in (400, 422), f"got {r.status_code} for {bad!r}: {r.text}"
