"""The OTP refusal contract, which crosses into the login form.

Every way the OTP flow can refuse now carries a machine-readable `code`
alongside the prose. The form does not pattern-match the English: it looks the
code up in a table (`FAILURES` in `frontend/src/components/OtpForm.jsx`) that
decides whether to start a countdown, offer a resend, clear the code field, or
send somebody back to the number.

That makes the code strings an interface between two files in two languages,
and interfaces that nothing checks drift. Renaming `wrong_code` here would not
break a single Python test while quietly turning "2 tries left" into a dead end
with no resend offered.

So: the set of codes is pinned, the two that carry data are pinned to carrying
it, and the form's table is checked against both.
"""
import ast

import pytest

import server


BACKEND_SRC = (server.ROOT_DIR / "server.py").read_text()
OTP_FORM = server.ROOT_DIR.parent / "frontend" / "src" / "components" / "OtpForm.jsx"


def _otp_error_calls():
    """Every `_otp_error(...)` in server.py, as (code, {keyword names}).

    Parsed rather than grepped: the code is the second positional argument and
    the extras are keywords, and a regex over four-line call formatting gets
    that wrong the first time somebody reflows one.
    """
    calls = []
    for node in ast.walk(ast.parse(BACKEND_SRC)):
        if not isinstance(node, ast.Call):
            continue
        if getattr(node.func, "id", None) != "_otp_error":
            continue
        # _otp_error(status, code, message, **extra)
        assert len(node.args) >= 3, "an _otp_error call is missing an argument"
        code = node.args[1]
        assert isinstance(code, ast.Constant) and isinstance(code.value, str), (
            "the code must be a literal — a computed one cannot be checked here "
            "and cannot be found by anybody reading the form"
        )
        calls.append((code.value, {kw.arg for kw in node.keywords}))
    return calls


# The contract. Adding a refusal means adding it here, which means deciding
# what the form should do about it rather than letting it fall through to the
# do-nothing default.
DOCUMENTED_CODES = {
    # Asking for a code
    "no_account",           # login, number we don't know
    "admin_uses_password",  # admins are not an OTP audience
    "already_registered",   # signup, number we do know
    "missing_fields",       # signup without a name or a role
    "cooldown",             # 30s between codes — carries retry_after
    "hourly_limit",         # 5 an hour, and no countdown will clear it
    "send_failed",          # AiSensy, or no AiSensy at all
    # Entering one
    "no_active_code",       # nothing outstanding for this number
    "expired",              # 5 minute TTL
    "locked_out",           # 5 wrong attempts
    "wrong_code",           # carries remaining
}


class TestTheCodes:
    def test_every_refusal_is_documented(self):
        emitted = {code for code, _ in _otp_error_calls()}
        assert emitted == DOCUMENTED_CODES, (
            "the OTP refusal codes have changed. Update DOCUMENTED_CODES and "
            "the FAILURES table in frontend/src/components/OtpForm.jsx — a code "
            "the form has no rule for shows its message and does nothing else."
        )

    def test_the_helper_puts_the_code_beside_the_message(self):
        exc = server._otp_error(429, "cooldown", "Wait 12s.", retry_after=12)
        assert exc.status_code == 429
        assert exc.detail == {
            "message": "Wait 12s.",
            "code": "cooldown",
            "retry_after": 12,
        }

    def test_the_message_survives_being_structured(self):
        """`formatApiError` reads `detail.message`; nothing may be only a code.

        A refusal that arrives as a bare code renders as "Something went
        wrong", which is the state this work exists to remove.
        """
        for node in ast.walk(ast.parse(BACKEND_SRC)):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "_otp_error":
                message = node.args[2]
                if isinstance(message, ast.Constant):
                    assert message.value.strip(), "an OTP refusal has an empty message"


class TestTheDataTheyCarry:
    """Two refusals are useless without a number attached."""

    def test_cooldown_carries_retry_after(self):
        # Without it the form has to guess the wait, and a guess of 30 when the
        # server means 23 leaves the resend button dead for seven seconds after
        # it would have worked. Worse the other way round.
        cooldowns = [kw for code, kw in _otp_error_calls() if code == "cooldown"]
        assert cooldowns, "no cooldown refusal found"
        for kw in cooldowns:
            assert "retry_after" in kw

    def test_wrong_code_carries_remaining(self):
        # "That code isn't right" and "that code isn't right, one try left" are
        # different messages to be reading.
        wrongs = [kw for code, kw in _otp_error_calls() if code == "wrong_code"]
        assert wrongs, "no wrong_code refusal found"
        for kw in wrongs:
            assert "remaining" in kw

    def test_locked_out_is_raised_before_and_after_the_last_attempt(self):
        """Both doors, or the fifth wrong code reads as a sixth.

        One check runs before comparing (you already used them all), one after
        decrementing (that was the last one). Losing the second would answer
        the final wrong attempt with "0 tries left" and no way forward.
        """
        assert sum(1 for code, _ in _otp_error_calls() if code == "locked_out") == 2


class TestTheFormAgrees:
    """The other half of the interface, read where it lives."""

    @classmethod
    def setup_class(cls):
        cls.src = OTP_FORM.read_text()
        block = cls.src.split("const FAILURES = {", 1)
        assert len(block) == 2, "FAILURES table not found in OtpForm.jsx"
        body = block[1].split("};", 1)[0]
        cls.rules = {}
        for line in body.splitlines():
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            key, _, rest = line.partition(":")
            cls.rules[key.strip()] = rest

    def test_it_has_no_rules_for_codes_the_server_cannot_send(self):
        # A dead rule is a claim about behaviour that can never happen, and it
        # is how somebody concludes a code is handled when it is not.
        assert set(self.rules) <= DOCUMENTED_CODES, (
            f"stale rules: {set(self.rules) - DOCUMENTED_CODES}"
        )

    @pytest.mark.parametrize(
        "code,behaviour",
        [
            # Refusals whose whole point is what the form then does. The
            # message alone would leave the user stuck on each of these.
            ("cooldown", "coolsDown"),
            ("expired", "offerResend"),
            ("no_active_code", "offerResend"),
            ("locked_out", "offerResend"),
            ("send_failed", "offerResend"),
            ("wrong_code", "clearCode"),
            ("hourly_limit", "backToPhone"),
            ("no_account", "backToPhone"),
            ("already_registered", "backToPhone"),
            ("admin_uses_password", "backToPhone"),
        ],
    )
    def test_the_rule_that_makes_each_refusal_recoverable(self, code, behaviour):
        assert code in self.rules, f"the form has no rule for {code}"
        assert behaviour in self.rules[code], (
            f"{code} needs {behaviour}: without it the message is a dead end"
        )

    def test_wrong_code_does_not_offer_a_resend(self):
        """They got the code. Telling them to ask for another is bad advice.

        The hint used to be appended to every failure, which meant a mistyped
        digit was answered with "didn't get it? resend" — and resending
        invalidates the code they are holding, so following the advice makes it
        worse.
        """
        assert "offerResend" not in self.rules["wrong_code"]

    def test_an_unknown_code_still_shows_its_message(self):
        # The lookup has to default, or a code added on the server before the
        # form is redeployed throws instead of degrading to plain prose.
        assert "FAILURES[res.code] || {}" in self.src
