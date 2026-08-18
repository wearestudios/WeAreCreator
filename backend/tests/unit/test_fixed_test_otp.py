"""OTP_TEST_CODE — the fixed login code, and the four fences around it.

Reading a code out of the Railway log to test signup is slow enough that
signup stops being tested. A fixed code fixes that and is, unavoidably, a
login bypass for anybody who knows a phone number — so the interesting tests
here are not the ones where it works. They are the ones where it refuses.

Two structural points this file holds:

  * The fixed code changes the *value* and nothing else. It is hashed, stored,
    expired, counted and locked out exactly like a random one, and the verify
    path has no branch for it — so the TTL, the attempt lockout and both rate
    limits stay on, which is the whole point of still being able to test them.
  * The code never appears in a response body. The request handler returns a
    boolean saying a fixed code is in force, and nothing more.
"""
import ast
import inspect
import re
from pathlib import Path

import pytest

import server

FIXED = "123456"


@pytest.fixture
def testable(monkeypatch):
    """The environment in which the fixed code is meant to work: a laptop."""
    monkeypatch.setenv("OTP_TEST_CODE", FIXED)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("AISENSY_API_KEY", raising=False)
    monkeypatch.delenv("AISENSY_CAMPAIGN_NAME", raising=False)
    monkeypatch.delenv("ALLOW_OTP_SIMULATION", raising=False)


# --- When it is permitted ---------------------------------------------------


def test_the_fixed_code_is_used_when_everything_permits_it(testable):
    assert server._fixed_test_otp() == FIXED
    assert server._fixed_test_otp_refusal() is None


def test_it_is_off_unless_asked_for(monkeypatch):
    """Absent is the default. No refusal either — there is nothing to refuse."""
    monkeypatch.delenv("OTP_TEST_CODE", raising=False)
    monkeypatch.setenv("APP_ENV", "development")

    assert server._fixed_test_otp() is None
    assert server._fixed_test_otp_refusal() is None


def test_it_works_on_a_staging_box(monkeypatch):
    """Staging is the case that motivated this, so it must not be collateral.

    `_is_production()` treats anything that isn't dev/local/test as production,
    which is right for warning about a missing admin account and wrong here —
    it would refuse the fixed code on a box labelled APP_ENV=staging.
    """
    monkeypatch.setenv("OTP_TEST_CODE", FIXED)
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("ALLOW_OTP_SIMULATION", "true")
    monkeypatch.delenv("AISENSY_API_KEY", raising=False)
    monkeypatch.delenv("AISENSY_CAMPAIGN_NAME", raising=False)

    assert server._is_production() is True, "precondition: staging reads as production"
    assert server._fixed_test_otp() == FIXED


def test_every_use_is_logged(testable, caplog):
    """Loud on every code, not once at boot. A staging setting riding into
    production is the failure being guarded against, and it will not announce
    itself."""
    with caplog.at_level("WARNING", logger="wearecreators"):
        server._fixed_test_otp()

    assert "FIXED TEST OTP in use — never enable in production" in caplog.text


def test_the_code_is_never_in_the_log_line(testable, caplog):
    """The warning says that a fixed code is in use, not what it is. The
    simulation path already logs the issued code; this line is separate and
    should not duplicate it."""
    with caplog.at_level("WARNING", logger="wearecreators"):
        server._fixed_test_otp()

    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert warnings
    assert not any(FIXED in message for message in warnings)


# --- When it must not be ----------------------------------------------------


@pytest.mark.parametrize("env_name", ["production", "prod", "live", "PRODUCTION", " Production "])
def test_production_refuses_it(testable, monkeypatch, env_name):
    monkeypatch.setenv("APP_ENV", env_name)

    assert server._fixed_test_otp() is None
    assert "APP_ENV/ENV is" in server._fixed_test_otp_refusal()


def test_production_via_the_env_alias_refuses_it(testable, monkeypatch):
    """Some hosts set ENV rather than APP_ENV; the gate reads both."""
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("ALLOW_OTP_SIMULATION", "true")

    assert server._fixed_test_otp() is None


def test_production_refuses_it_even_with_simulation_forced_on(testable, monkeypatch):
    """The important one. `_simulation_allowed()` returns True for
    ALLOW_OTP_SIMULATION=true *regardless of APP_ENV*, so leaning on it alone
    would let `APP_ENV=production ALLOW_OTP_SIMULATION=true` hand out a fixed
    code. The production check is independent for exactly this reason."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ALLOW_OTP_SIMULATION", "true")

    assert server._simulation_allowed() is True, "precondition: simulation is on"
    assert server._fixed_test_otp() is None


@pytest.mark.parametrize("key", ["AISENSY_API_KEY", "AISENSY_CAMPAIGN_NAME"])
def test_configured_aisensy_refuses_it(testable, monkeypatch, key):
    """Either half is enough. If anything is wired up to really send messages,
    a fixed code would be delivered to a real phone."""
    monkeypatch.setenv(key, "something")

    assert server._fixed_test_otp() is None
    assert "AiSensy is configured" in server._fixed_test_otp_refusal()


def test_it_is_refused_when_simulation_is_not_permitted(testable, monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.delenv("ALLOW_OTP_SIMULATION", raising=False)

    assert server._simulation_allowed() is False, "precondition"
    assert server._fixed_test_otp() is None
    assert "simulation is not permitted" in server._fixed_test_otp_refusal()


@pytest.mark.parametrize("bad", ["12345", "1234567", "abcdef", "12 34 56", "12345a", "-12345"])
def test_a_code_that_is_not_six_digits_is_refused(testable, monkeypatch, bad):
    """The form and the WhatsApp template both assume six digits. Accepting
    anything else would fail later and more confusingly."""
    monkeypatch.setenv("OTP_TEST_CODE", bad)

    assert server._fixed_test_otp() is None
    assert "not six digits" in server._fixed_test_otp_refusal()


def test_a_refusal_is_logged_as_an_error(testable, monkeypatch, caplog):
    monkeypatch.setenv("APP_ENV", "production")

    with caplog.at_level("ERROR", logger="wearecreators"):
        server._fixed_test_otp()

    assert "IGNORED" in caplog.text
    errors = [r.getMessage() for r in caplog.records if r.levelname == "ERROR"]
    assert not any(FIXED in message for message in errors), "a refusal must not print the code"


# --- The startup announcement -----------------------------------------------


def test_startup_announces_it_when_enabled(testable, caplog):
    with caplog.at_level("WARNING", logger="wearecreators"):
        server.warn_about_fixed_test_otp()

    assert "FIXED TEST OTP is ENABLED" in caplog.text


def test_startup_announces_it_when_set_but_refused(testable, monkeypatch, caplog):
    """Set-and-ignored is its own state, and worth saying: somebody believes
    they enabled it and is about to wonder why the codes keep changing."""
    monkeypatch.setenv("APP_ENV", "production")

    with caplog.at_level("ERROR", logger="wearecreators"):
        server.warn_about_fixed_test_otp()

    assert "will be IGNORED" in caplog.text


def test_startup_is_silent_when_unset(monkeypatch, caplog):
    monkeypatch.delenv("OTP_TEST_CODE", raising=False)

    with caplog.at_level("WARNING", logger="wearecreators"):
        server.warn_about_fixed_test_otp()

    assert caplog.text == ""


def test_startup_actually_calls_it():
    """A warning nothing invokes is not a warning."""
    source = inspect.getsource(server._startup)

    assert "warn_about_fixed_test_otp()" in source


# --- It is accepted on verify, through the ordinary path --------------------


def test_the_fixed_code_round_trips_through_the_real_hash_functions():
    """This is what "accepted on verify" means here. `verify_otp` compares the
    submitted code against the stored bcrypt hash, so a fixed code verifies
    because it is the code that was issued — not because anything special-cases
    it."""
    phone = "+919900000001"
    stored = server._hash_otp_code(phone, FIXED)

    assert server._verify_otp_code(phone, FIXED, stored) is True
    assert server._verify_otp_code(phone, "654321", stored) is False


def test_the_hash_is_still_salted_per_phone():
    """A fixed code must not produce a hash that is reusable across numbers."""
    stored = server._hash_otp_code("+919900000001", FIXED)

    assert server._verify_otp_code("+919900000002", FIXED, stored) is False


# --- Structural guarantees --------------------------------------------------

SERVER_SOURCE = Path(server.__file__).resolve()


def _function_source(name: str) -> str:
    tree = ast.parse(SERVER_SOURCE.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(SERVER_SOURCE.read_text(), node) or ""
    raise AssertionError(f"{name} not found in server.py")


def test_verify_otp_has_no_knowledge_of_the_test_code():
    """The safeguards stay real only while verification has no shortcut. If the
    fixed code were special-cased in `verify_otp`, it could skip the attempt
    counter and the expiry — and those are paths worth testing."""
    source = _function_source("verify_otp")

    assert "OTP_TEST_CODE" not in source
    assert "_fixed_test_otp" not in source


def test_the_request_handler_still_generates_a_random_code_otherwise():
    """The fixed code replaces the random one; it does not remove it."""
    source = _function_source("request_otp")

    assert "_secrets.randbelow(1_000_000)" in source
    assert "_fixed_test_otp()" in source


def test_the_rate_limits_are_untouched_by_the_test_code():
    """Only the value is fixed, not the safeguards — the request handler must
    still consult every limit."""
    source = _function_source("request_otp")

    for guard in ("_otp_cooldown()", "_otp_hourly_limit()", "_otp_ttl()"):
        assert guard in source, f"{guard} is no longer applied on the request path"
    assert "_otp_max_attempts()" in _function_source("verify_otp")


def test_the_response_reports_test_mode_as_a_boolean_and_never_the_code():
    """`test_mode` must be derived from whether a fixed code is in force, not
    be the code itself — a response body is the one place it must never
    appear."""
    source = _function_source("request_otp")

    assert '"test_mode": bool(fixed_code)' in source
    # Nothing on the return path may carry the value.
    returned = source[source.index("return {"):]
    assert "OTP_TEST_CODE" not in returned
    assert re.search(r'"code"\s*:', returned) is None
