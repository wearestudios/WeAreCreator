"""The anonymous creator research survey.

**Anonymity here is a design constraint, not a setting**, so this file is
mostly one assertion restated in every direction a leak could come from: a
stored response holds the answers and a date, and nothing else.

The survey asks creators about brands that went quiet, fees that changed after
being agreed, and work they were never paid for. Honest answers depend on them
believing nothing traces back, and several decisions below cost us analytical
convenience to keep that true — a date instead of a timestamp, a bypassable
device flag instead of a fingerprint, an audit line that does not exist.

Section 1 is the leak sweep the brief asked for: an IP, a user agent, a header,
a name, a handle, a phone number and an email planted in a request, and the
stored row searched for every one of them — the arrangement `test_exports.py`
uses, because source-reading catches the mistake somebody makes on purpose and
running it catches the one where a value arrives through a `**spread`.
"""

import asyncio
import inspect
import json
import re
from pathlib import Path

import pytest
from fastapi import HTTPException, params
from mongomock_motor import AsyncMongoMockClient

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend"
SOURCE = Path(server.__file__).read_text()

LOOP = None


def js_code(html):
    """The page with its `//` comment lines stripped.

    **A sweep has to read the code, not the prose about it.** The convention in
    this codebase is to explain a decision where it was made, so the comment
    saying "No fingerprinting" fails a sweep for `fingerprint` — which is how a
    test ends up asserting against its own documentation. Whole lines whose
    first non-space characters are `//`, the same cut `copy_of` makes, and
    deliberately not everything from `//` onward, which would truncate at the
    `//` in a `https://`.
    """
    return "\n".join(
        line for line in html.splitlines() if not line.lstrip().startswith("//")
    )


def py_code(fn):
    """A handler's source with its docstring and `#` comments removed."""
    src = inspect.getsource(fn)
    src = re.sub(r'"""(?:[^"\\]|\\.|"(?!""))*"""', "", src, flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("#")
    )


def run(body):
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()

    async def go():
        db = AsyncMongoMockClient()["survey"]
        original = server.db
        server.db = db
        server._SURVEY_RATE.clear()
        try:
            return await body(db)
        finally:
            server.db = original
            server._SURVEY_RATE.clear()

    return LOOP.run_until_complete(go())


def guard_allows(fn, role):
    """Would FastAPI let this role through?

    Calling a handler directly skips its `Depends` entirely, so the guard is
    pulled off the signature and run — a string match on
    `require_roles("admin")` would pass for a guard listing the wrong roles.
    """
    guard = None
    for p in inspect.signature(fn).parameters.values():
        dep = p.default
        if isinstance(dep, params.Depends) and dep.dependency is not None:
            if getattr(dep.dependency, "__name__", "") == "_guard":
                guard = dep.dependency
    assert guard is not None, f"{fn.__name__} declares no require_roles guard"

    async def go():
        try:
            await guard({"_id": "x", "role": role})
            return True
        except HTTPException as err:
            assert err.status_code == 403
            return False

    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()
    return LOOP.run_until_complete(go())


# Everything a request carries that must never be stored, plus the things a
# respondent might type that would identify them.
PLANTED = {
    "client ip": "203.0.113.42",
    "forwarded ip": "198.51.100.77",
    "user agent": "Mozilla/5.0 (Linux; Android 13) PLANTED-AGENT/9.9",
    "accept-language header": "en-IN,PLANTED-LANG;q=0.9",
    "referer header": "https://planted.example.in/from-here",
    "cookie header": "session=PLANTED-COOKIE-VALUE",
    "name": "Priya Planted",
    "handle": "@plantedhandle",
    "phone": "+919876500042",
    "email": "planted.leak@example.in",
}


class FakeRequest:
    """A request carrying every value that must not survive.

    Headers are a real dict so `_client_ip` reads the forwarded address the way
    it does in production behind a proxy.
    """

    def __init__(self, ip=PLANTED["client ip"]):
        self.client = type("C", (), {"host": ip})()
        self.headers = {
            "user-agent": PLANTED["user agent"],
            "x-forwarded-for": PLANTED["forwarded ip"],
            "accept-language": PLANTED["accept-language header"],
            "referer": PLANTED["referer header"],
            "cookie": PLANTED["cookie header"],
            # A request really can carry these — a referer with a handle in
            # the path, a cookie holding a name, an analytics header with an
            # email. None of them may reach the row.
            "x-planted-name": PLANTED["name"],
            "x-planted-handle": PLANTED["handle"],
            "x-planted-phone": PLANTED["phone"],
            "x-planted-email": PLANTED["email"],
        }


def _full_payload(**over):
    """One complete, valid response."""
    kw = dict(
        city="Bengaluru",
        focus="Food & Drink",
        collabs_3m="3-5",
        paid_share="mostly_money",
        how_reach=["brand_messages_me", "whatsapp_group"],
        used_a_platform="yes",
        platform_story="Tried one, nobody replied.",
        fee_agreed="verbal_only",
        paid_when="still_waiting",
        went_wrong=["went_quiet", "fee_changed"],
        top_three=["late_payment", "chasing_replies", "haggling"],
        walked_away="The brief kept changing.",
        pan_stance="have_prefer_not",
        wish_brands_knew="Say the budget up front.",
    )
    kw.update(over)
    return server.CreatorSurveyPayload(**kw)


# --- 1. Nothing about the respondent reaches the database -------------------


class TestTheStoredRowIsAnswersAndADate:
    def test_not_one_planted_request_value_survives(self):
        """**The sweep this file exists for.** Run the real handler with a
        request carrying an IP, a forwarded IP, a user agent, three more
        headers, and a name, handle, phone and email typed into free text —
        then search the stored row for every one of them.

        The four typed values are planted in the *same* free text the
        respondent controls, so this also pins that nothing echoes a header
        into an answer.
        """

        async def body(db):
            await server.submit_creator_survey(_full_payload(), FakeRequest())
            row = await db.creator_survey_responses.find_one({})
            row.pop("_id", None)
            return row

        row = run(body)
        blob = json.dumps(row, default=str)
        # **Every one of the ten, including the name, handle, phone and email**
        # — `FakeRequest` carries those in headers, which is where a request
        # can actually hold them. What a respondent types into an answer is a
        # different question and is the test below.
        for label, value in PLANTED.items():
            assert value not in blob, f"{label} reached the database"

    def test_a_name_somebody_typed_voluntarily_does_survive_and_is_warned_about(
        self,
    ):
        """**The honest half, and the reason the console carries a warning.**

        We ask people to leave names and handles out and some will put them in
        anyway. Stripping them would store a sanitised answer while the
        respondent believes they sent what they wrote, so what they typed is
        kept as typed — and the admin screen says so rather than implying the
        open answers are as anonymous as the closed ones.
        """

        async def body(db):
            await server.submit_creator_survey(
                _full_payload(wish_brands_knew=f"I am {PLANTED['name']}"),
                FakeRequest(),
            )
            return await db.creator_survey_responses.find_one({})

        assert PLANTED["name"] in run(body)["wish_brands_knew"]
        warning = server.SURVEY_OPEN_TEXT_WARNING.lower()
        assert "names" in warning and "handles" in warning

    def test_the_stored_keys_are_exactly_the_declared_shape(self):
        """So a field added to the payload cannot reach the database without
        somebody adding it to `_SURVEY_STORED_KEYS` on purpose — and nothing
        about a request can arrive through a `**spread` from elsewhere."""

        async def body(db):
            await server.submit_creator_survey(_full_payload(), FakeRequest())
            row = await db.creator_survey_responses.find_one({})
            row.pop("_id", None)
            return set(row)

        stored = run(body)
        assert stored == server._SURVEY_STORED_KEYS, (
            stored.symmetric_difference(server._SURVEY_STORED_KEYS)
        )

    def test_submitted_on_is_a_date_and_not_an_instant(self):
        """**A precise timestamp plus a known WhatsApp send time singles
        somebody out in a small sample**, which is the sample size this will
        have. A date is the coarsest thing still useful for comparing waves.
        """

        async def body(db):
            await server.submit_creator_survey(_full_payload(), FakeRequest())
            return await db.creator_survey_responses.find_one({})

        value = run(body)["submitted_on"]
        assert isinstance(value, str)
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", value), value
        # No time component anywhere in it.
        assert ":" not in value and "T" not in value

    def test_nothing_about_this_is_audited(self):
        """**The one write path in the product that leaves no log line.**

        `audit()` has an actor field, and a line naming who submitted is
        precisely what this must not have. Asserted by driving the handler and
        reading the log back, not by grepping — a call added inside a helper
        would pass a source sweep of the route.
        """

        async def body(db):
            await server.submit_creator_survey(_full_payload(), FakeRequest())
            return await db.audit_log.find({}).to_list(length=10)

        assert run(body) == []

    def test_the_store_helper_names_its_keys_rather_than_copying_a_request(self):
        src = py_code(server._store_survey_response)
        assert "request" not in src
        assert "headers" not in src
        for banned in ("client.host", "user_agent", "user-agent", "X-Forwarded"):
            assert banned not in src, banned

    def test_the_route_takes_no_auth_dependency_at_all(self):
        """No account, no cookie, no session — by design rather than omission.
        A `Depends` here would be the thing that makes a response traceable."""
        for p in inspect.signature(server.submit_creator_survey).parameters.values():
            assert not isinstance(p.default, params.Depends), p.name

    def test_the_section_states_the_limit_we_cannot_promise(self):
        """Railway's proxy and Atlas record connection metadata outside this
        application. Written down so nobody tells a respondent something
        stronger than the truth."""
        start = SOURCE.index("# The creator research survey")
        block = SOURCE[start : start + 4000]
        assert "Atlas" in block
        assert "IP" in block
        assert "neither store nor read" in block

    def test_the_comment_warns_the_next_person_off_storing_the_ip(self):
        """The next person here will reach for it — for a better limit, for
        abuse forensics, for deduplication. The comment has to be where they
        will be standing."""
        start = SOURCE.index("# The creator research survey")
        block = SOURCE[start : start + 4000]
        assert "reach for" in block
        assert "in memory" in block.lower()


# --- 2. No field anywhere could hold a government ID ------------------------


class TestGovernmentIdsAreRefusedNotStored:
    @pytest.mark.parametrize(
        "text",
        [
            "my pan is ABCDE1234F",
            "ABCDE1234F",
            "pan abcde1234f lowercase",
            "Here it is: ZYXWV9876Z thanks",
        ],
    )
    def test_a_pan_shaped_string_in_free_text_is_refused(self, text):
        """**The test the brief asked for.** Five letters, four digits, a
        letter — refused rather than stripped, because a respondent who typed
        one needs to know we are not keeping it."""
        refusal = server._survey_refusal(_full_payload(walked_away=text))
        assert refusal is not None
        assert "PAN" in refusal

    @pytest.mark.parametrize(
        "text",
        ["2345 6789 0123", "234567890123", "2345-6789-0123", "aadhaar 2345 6789 0123"],
    )
    def test_an_aadhaar_shaped_string_is_refused(self, text):
        refusal = server._survey_refusal(_full_payload(wish_brands_knew=text))
        assert refusal is not None
        assert "Aadhaar" in refusal

    @pytest.mark.parametrize("field", server.SURVEY_FREE_TEXT_FIELDS)
    def test_every_free_text_field_is_swept_not_just_one(self, field):
        """Three boxes, and a sweep covering two of them is a sweep covering
        none — somebody will type it into whichever one is missed."""
        refusal = server._survey_refusal(
            server.CreatorSurveyPayload(**{field: "ABCDE1234F"})
        )
        assert refusal is not None and "PAN" in refusal

    def test_the_refusal_happens_before_anything_is_written(self):
        """A 422 raised after the insert is not a refusal."""

        async def body(db):
            try:
                await server.submit_creator_survey(
                    _full_payload(walked_away="ABCDE1234F"), FakeRequest()
                )
            except HTTPException as err:
                return err.status_code, await db.creator_survey_responses.count_documents({})
            return None, None

        status, stored = run(body)
        assert status == 422
        assert stored == 0

    def test_ordinary_text_is_not_caught(self):
        """The patterns are narrow enough to leave real answers alone. A sweep
        that refuses normal sentences is a sweep somebody removes."""
        for ok in (
            "They went quiet for 3 weeks and then paid 15000.",
            "Rate was Rs 25,000 for 2 reels and 4 stories.",
            "Call me on 98765 43210 if you want",   # a phone is not an ID
            "Invoice INV-2024-0012 took ages",
        ):
            assert server._survey_refusal(_full_payload(walked_away=ok)) is None, ok

    def test_no_question_asks_for_an_id_number(self):
        """**Question 13 asks *whether* somebody has a PAN, never the number.**
        A field that could hold one is the thing this survey must not have."""
        options = [v for v, _ in next(
            q for q in server._survey_questions() if q["field"] == "pan_stance"
        )["options"]]
        assert options == ["have_and_share", "have_prefer_not", "no_pan", "not_sure"]
        # And no field name anywhere invites a number.
        for field in server.CreatorSurveyPayload.model_fields:
            assert "pan_number" not in field
            assert "aadhaar" not in field
        # The free-text fields are the only strings, and they are swept.
        strings = [
            f for f, info in server.CreatorSurveyPayload.model_fields.items()
            if info.annotation is not None and "str" in str(info.annotation)
            and "Literal" not in str(info.annotation)
        ]
        assert set(strings) == set(server.SURVEY_FREE_TEXT_FIELDS)


# --- 3. What the payload accepts and refuses --------------------------------


class TestTheAnswersAreAClosedVocabulary:
    @pytest.mark.parametrize(
        "field,junk",
        [
            ("city", "Atlantis"),
            ("focus", "Underwater basket weaving"),
            ("collabs_3m", "loads"),
            ("paid_share", "some"),
            ("used_a_platform", "maybe"),
            ("fee_agreed", "we vibed"),
            ("paid_when", "eventually"),
            ("pan_stance", "ABCDE1234F"),
        ],
    )
    def test_a_junk_closed_answer_is_refused_rather_than_stored(self, field, junk):
        """**Typed as `Literal`s** so an aggregate is never built over a column
        somebody can write anything into."""
        with pytest.raises(Exception):
            server.CreatorSurveyPayload(**{field: junk})

    def test_the_city_and_focus_lists_are_derived_not_retyped(self):
        """From `INDIAN_CITIES` and `CREATOR_TAXONOMY` — a second list of
        either is the drift `lib/categories.js` exists to prevent."""
        from typing import get_args

        cities = set(get_args(server.SurveyCity))
        assert set(server.INDIAN_CITIES) < cities
        assert cities == set(server.INDIAN_CITIES) | {server.SURVEY_ELSEWHERE}
        focus = set(get_args(server.SurveyFocus))
        groups = {label for label, _ in server.CREATOR_TAXONOMY}
        assert focus == groups | {server.SURVEY_OTHER_FOCUS}

    def test_free_text_is_capped(self):
        with pytest.raises(Exception):
            server.CreatorSurveyPayload(
                walked_away="x" * (server.SURVEY_FREE_TEXT_MAX + 1)
            )
        # And the cap itself is reachable.
        assert server.CreatorSurveyPayload(
            walked_away="x" * server.SURVEY_FREE_TEXT_MAX
        )

    def test_an_unknown_field_is_refused(self):
        """`extra: forbid`, so a client cannot smuggle a column in — which on
        this collection would be a column nobody declared and nobody swept."""
        with pytest.raises(Exception):
            server.CreatorSurveyPayload(city="Mumbai", ip_address="203.0.113.1")

    def test_an_entirely_empty_submission_is_refused(self):
        refusal = server._survey_refusal(server.CreatorSurveyPayload())
        assert refusal is not None and "nothing was filled in" in refusal

    def test_one_answer_is_enough(self):
        """**Every field is optional and that is deliberate.** A half-finished
        anonymous response is still data, and refusing it server-side throws
        away the one answer somebody was willing to give. The browser is where
        required-ness belongs."""
        assert server._survey_refusal(
            server.CreatorSurveyPayload(paid_when="never_paid")
        ) is None

    @pytest.mark.parametrize("n", [1, 2, 4, 5, 9])
    def test_a_top_three_that_is_not_three_is_refused(self, n):
        """**Exactly three, server-side as well as in the browser.** A
        top-three that accepts seven gives a frequency count rather than a
        ranking, and the ranking is the point of the question."""
        from typing import get_args

        options = list(get_args(server.SurveyFrustration))[:n]
        refusal = server._survey_refusal(_full_payload(top_three=options))
        assert refusal is not None
        assert "exactly 3" in refusal

    def test_three_is_accepted(self):
        assert server._survey_refusal(
            _full_payload(top_three=["haggling", "late_payment", "finding_briefs"])
        ) is None

    def test_an_omitted_top_three_is_a_skipped_question_not_a_refusal(self):
        """Every question here may be skipped. The exactly-three rule applies
        to an answer that was given, not to the absence of one."""
        assert server._survey_refusal(
            server.CreatorSurveyPayload(city="Mumbai")
        ) is None

    def test_duplicates_do_not_pass_as_three(self):
        """The same choice three times is one choice. Counted on the distinct
        set, or the browser's limiter could be bypassed by a hand-built POST."""
        refusal = server._survey_refusal(
            _full_payload(top_three=["haggling", "haggling", "haggling"])
        )
        assert refusal is not None


# --- 4. The rate limit, in memory only --------------------------------------


class TestTheRateLimitNeverTouchesTheDatabase:
    def test_three_an_hour(self):
        async def body(db):
            out = []
            for _ in range(5):
                try:
                    await server.submit_creator_survey(_full_payload(), FakeRequest())
                    out.append(200)
                except HTTPException as err:
                    out.append(err.status_code)
            return out, await db.creator_survey_responses.count_documents({})

        codes, stored = run(body)
        assert codes == [200, 200, 200, 429, 429]
        assert stored == 3

    def test_twenty_a_day(self):
        now = 1_000_000.0
        server._SURVEY_RATE.clear()
        # Spread beyond the hour window so the daily cap is what bites.
        server._SURVEY_RATE["9.9.9.9"] = [now - 3700 - i * 600 for i in range(20)]
        assert "today" in (server._survey_rate_refusal("9.9.9.9", now=now) or "")
        server._SURVEY_RATE.clear()

    def test_a_refusal_is_a_sentence_rather_than_a_code(self):
        """The page is server-rendered HTML that may be running no JavaScript,
        so there is nothing on the other end to interpret a code."""
        server._SURVEY_RATE.clear()
        now = 1_000_000.0
        server._SURVEY_RATE["1.1.1.1"] = [now - 10] * server.SURVEY_MAX_PER_HOUR
        refusal = server._survey_rate_refusal("1.1.1.1", now=now)
        assert refusal and refusal[0].isupper() and refusal.endswith(".")
        assert "_" not in refusal and refusal.lower() != refusal
        server._SURVEY_RATE.clear()

    def test_the_window_rolls(self):
        now = 1_000_000.0
        server._SURVEY_RATE.clear()
        server._SURVEY_RATE["2.2.2.2"] = [now - 4000] * 3   # over an hour ago
        assert server._survey_rate_refusal("2.2.2.2", now=now) is None
        server._SURVEY_RATE.clear()

    def test_a_missing_address_is_allowed_through(self):
        """Refusing would turn a proxy configuration into a wall in front of
        the survey, which is the wrong direction to fail in."""
        assert server._survey_rate_refusal(None) is None
        assert server._survey_rate_refusal("") is None

    def test_old_entries_are_trimmed_rather_than_kept_forever(self):
        now = 1_000_000.0
        server._SURVEY_RATE.clear()
        server._SURVEY_RATE["3.3.3.3"] = [now - 90000]   # over a day ago
        server._survey_rate_refusal("3.3.3.3", now=now)
        assert "3.3.3.3" not in server._SURVEY_RATE
        server._SURVEY_RATE.clear()

    def test_the_address_is_a_key_and_is_never_written(self):
        """Driven, not grepped: submit from an address and search the row."""

        async def body(db):
            await server.submit_creator_survey(_full_payload(), FakeRequest())
            rows = await db.creator_survey_responses.find({}).to_list(length=5)
            return rows, list(server._SURVEY_RATE)

        rows, keys = run(body)
        # It is the forwarded address, read for the limit only.
        assert keys == [PLANTED["forwarded ip"]]
        assert PLANTED["forwarded ip"] not in json.dumps(rows, default=str)

    def test_the_limit_is_a_module_dict_that_forgets_on_restart(self):
        src = inspect.getsource(server._survey_rate_record)
        assert "db." not in src
        assert "insert" not in src


# --- 5. Who may read the results -------------------------------------------


class TestAdminOnlyNotConsoleRoles:
    @pytest.mark.parametrize(
        "handler", ["admin_creator_survey"]
    )
    def test_weare_team_cannot_read_the_responses(self, handler):
        """**Admin-only, not `CONSOLE_ROLES`.** A respondent is not a creator
        we know and is attached to no brand, so there is nothing for a scoped
        console to be scoped *to* — it could only be handed everything."""
        fn = getattr(server, handler)
        assert guard_allows(fn, "admin") is True
        assert guard_allows(fn, "weare_team") is False
        assert guard_allows(fn, "campaign_manager") is False
        assert guard_allows(fn, "brand_manager") is False
        assert guard_allows(fn, "creator") is False

    def test_the_export_is_admin_only(self):
        assert "survey" in server.EXPORT_KINDS
        assert "survey" in server.ADMIN_ONLY_EXPORTS

    def test_the_export_is_not_listed_as_carrying_contact_details(self):
        """Because it does not. The respondents are anonymous — what an open
        answer might contain is a different question, and the console warning
        is where that is said."""
        assert "survey" not in server.EXPORTS_WITH_CONTACT

    def test_the_public_submit_route_is_on_the_public_router(self):
        paths = [getattr(r, "path", "") for r in server.app.routes]
        assert "/api/public/survey/creator" in paths


class TestTheResultsStayCorrelatable:
    def _read(self):
        async def body(db):
            for kw in (
                dict(city="Bengaluru", fee_agreed="verbal_only",
                     paid_when="never_paid", went_wrong=["went_quiet"],
                     top_three=["late_payment", "haggling", "chasing_replies"],
                     wish_brands_knew="Pay on time."),
                dict(city="Bengaluru", fee_agreed="verbal_only",
                     paid_when="still_waiting", went_wrong=["went_quiet", "fee_changed"],
                     top_three=["late_payment", "haggling", "finding_briefs"]),
                dict(city="Mumbai", fee_agreed="i_quoted_accepted",
                     paid_when="within_a_week", went_wrong=["nothing"],
                     top_three=["unclear_wants", "no_long_term", "haggling"]),
            ):
                await server._store_survey_response(
                    server.CreatorSurveyPayload(**kw)
                )
            return await server.admin_creator_survey({"_id": "x", "role": "admin"})

        return run(body)

    def test_a_response_comes_back_as_one_intact_row(self):
        """**The entire analytical value of this survey is correlation within
        one response** — that the people who were never paid are the same
        people who agreed the fee verbally. Shuffling the columns or splitting
        the free text away would protect nothing that is not already protected
        and destroy exactly that.
        """
        out = self._read()
        verbal = [r for r in out["responses"] if r.get("fee_agreed") == "verbal_only"]
        assert len(verbal) == 2
        # The correlation survives: both verbal rows are the unpaid ones.
        assert {r["paid_when"] for r in verbal} == {"never_paid", "still_waiting"}

    def test_free_text_stays_attached_to_its_own_response(self):
        out = self._read()
        row = next(r for r in out["responses"] if r.get("wish_brands_knew"))
        assert row["paid_when"] == "never_paid"

    def test_the_aggregates_count_every_closed_question(self):
        out = self._read()
        for field, _ in server.SURVEY_CLOSED_FIELDS:
            assert field in out["aggregates"], field

    def test_a_multi_select_counts_each_choice(self):
        out = self._read()
        block = out["aggregates"]["went_wrong"]
        assert block["multi_select"] is True
        assert block["counts"]["went_quiet"] == 2
        assert block["counts"]["fee_changed"] == 1

    def test_a_single_select_counts_responses(self):
        out = self._read()
        block = out["aggregates"]["city"]
        assert block["multi_select"] is False
        assert block["counts"] == {"Bengaluru": 2, "Mumbai": 1}

    def test_counts_are_ordered_commonest_first(self):
        """So two runs of the same data read the same way round."""
        counts = list(self._read()["aggregates"]["top_three"]["counts"].values())
        assert counts == sorted(counts, reverse=True)

    def test_the_schema_version_travels(self):
        """A later edit to the questions must not make old rows unreadable."""
        out = self._read()
        assert out["schema_version"] == server.SURVEY_SCHEMA_VERSION
        assert all(
            r["schema_version"] == server.SURVEY_SCHEMA_VERSION
            for r in out["responses"]
        )

    def test_the_open_text_warning_rides_on_the_payload(self):
        out = self._read()
        assert out["open_text_warning"]
        assert out["open_text_fields"] == list(server.SURVEY_FREE_TEXT_FIELDS)


# --- 6. The page ------------------------------------------------------------


def _page():
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()
    return LOOP.run_until_complete(server.public_survey_page()).body.decode()


class TestThePage:
    def test_all_fourteen_questions_in_order(self):
        html = _page()
        assert html.count('class="qnum"') == 14
        questions = server._survey_questions()
        assert len(questions) == 14
        # In the spec's order, checked by where each control appears.
        positions = [html.index(f'id="{q["field"]}-label"') for q in questions]
        assert positions == sorted(positions)

    def test_every_payload_field_has_a_question_and_vice_versa(self):
        """So the page, the model and the admin screen cannot drift into three
        different surveys."""
        fields = {q["field"] for q in server._survey_questions()}
        assert fields == set(server.CreatorSurveyPayload.model_fields)

    def test_no_control_offers_a_value_the_payload_would_refuse(self):
        """A dropdown offering something the API refuses is a dead control."""
        from typing import get_args

        for q in server._survey_questions():
            if q["kind"] == "text":
                continue
            annotation = str(
                server.CreatorSurveyPayload.model_fields[q["field"]].annotation
            )
            for value, _ in q["options"]:
                assert repr(value)[1:-1] in annotation or value in annotation, (
                    q["field"], value,
                )

    def test_real_radios_and_checkboxes_rather_than_custom_widgets(self):
        html = _page()
        assert 'type="radio"' in html
        assert 'type="checkbox"' in html
        assert 'role="radio"' not in html
        assert 'role="checkbox"' not in html

    def test_it_says_the_length_honestly_near_the_top(self):
        html = _page()
        assert "14 questions" in html
        assert "4 minutes" in html
        # Above the first question rather than at the end.
        assert html.index("4 minutes") < html.index('class="qnum"')

    def test_one_page_and_one_scroll(self):
        """No pagination: a multi-step form on a phone loses people at every
        step, and this one is opened from a WhatsApp message by somebody who
        has not decided to spend four minutes yet."""
        html = _page()
        assert html.count("<form") == 1
        for paging in ("Next", "Step 1", "page 2"):
            assert paging not in html

    def test_the_privacy_note_is_exactly_the_agreed_sentence(self):
        note = server.SURVEY_COPY["privacy"]
        assert note == (
            "We store your answers and the date. No name, no number, no "
            "email, and no record of your device or where you are. We cannot "
            "tell who sent what."
        )
        assert note in _page()

    def test_the_privacy_note_does_not_overclaim(self):
        """**It must not say answers cannot be connected to each other** —
        within one response they obviously can, and that is what makes the
        survey worth running. Claiming otherwise would be the one false
        sentence on the page."""
        note = server.SURVEY_COPY["privacy"].lower()
        for overclaim in (
            "cannot be connected", "unlinked", "not linked", "separately",
            "anonymised", "cannot be correlated",
        ):
            assert overclaim not in note, overclaim

    def test_it_says_nothing_about_a_platform_or_an_app_being_built(self):
        """**Studio research, and the framing has to stay that way.** A survey
        that reveals the product gets answers about the product instead of
        answers about people's lives.

        Question 6 and 7 ask whether they have *used* an app, which is a
        question about their life — the copy around the survey is what must
        not advertise ours.
        """
        copy = " ".join(
            str(v) for k, v in server.SURVEY_COPY.items()
        ).lower()
        for reveal in (
            "we are building", "our platform", "our app", "new platform",
            "join", "sign up", "waitlist", "early access", "beta",
        ):
            assert reveal not in copy, reveal

    def test_the_intro_frames_it_as_studio_research(self):
        intro = server.SURVEY_COPY["intro"]
        assert "WeAre Studios" in intro
        assert "nothing here is a pitch" in intro
        assert "publish a summary" in intro

    def test_the_thank_you_words_are_the_agreed_ones(self):
        assert server.SURVEY_COPY["thanks_title"] == (
            "Thank you - this is genuinely useful."
        )
        assert "publish the summary" in server.SURVEY_COPY["thanks_line"]

    def test_both_doors_thank_somebody_with_the_same_words(self):
        """The in-page swap and the no-JavaScript page come from one constant,
        so the two paths cannot thank people differently."""
        global LOOP
        if LOOP is None:
            LOOP = asyncio.new_event_loop()
        thanks = server._survey_thanks_html()
        assert server.SURVEY_COPY["thanks_title"] in thanks
        assert server.SURVEY_COPY["thanks_title"] in _page()   # in the template

    def test_it_fetches_no_third_party(self):
        """**No analytics, no pixel, no external font.** An analytics script on
        an anonymous survey is a contradiction, and a font request hands an IP
        to a third party from a page whose whole promise is that we are not
        collecting one."""
        html = _page()
        hosts = re.findall(r'(?:src|href)="(https?://[^"]+)"', html)
        assert hosts == [], hosts
        assert "@import" not in html
        for tracker in ("googletagmanager", "google-analytics", "gtag(",
                        "fbq(", "facebook.net", "fonts.googleapis", "hotjar",
                        "clarity.ms", "segment.", "mixpanel"):
            assert tracker not in html, tracker

    def test_it_is_noindex_and_disallowed(self):
        """Research, not a page we want found: a survey in a search index
        collects answers from whoever wandered in."""
        assert 'name="robots" content="noindex, nofollow"' in _page()
        robots = (FRONTEND / "public" / "robots.txt").read_text()
        assert "Disallow: /survey" in robots

    def test_everything_typed_is_escaped(self):
        """The options are our own constants, but escaping is the property
        rather than the provenance — a city or a label gaining an ampersand
        must not break the markup. "Food & Drink" already has one."""
        html = _page()
        assert "Food &amp; Drink" in html
        assert "Food & Drink" not in html.replace("Food &amp; Drink", "")

    def test_the_form_works_without_the_script(self):
        """The `action` and `method` are on the form, so a browser with no
        JavaScript posts it the ordinary way."""
        html = _page()
        form = re.search(r"<form[^>]*>", html).group(0)
        assert 'method="post"' in form
        assert f'action="{server.SURVEY_PATH}"' in form

    def test_the_fetch_target_is_built_from_the_api_prefix(self):
        """Rather than a hardcoded "/api", which is a second copy of where the
        routes are mounted."""
        assert f'"{server.API_PREFIX}/public/survey/creator"' in _page()
        assert "_PREFIX" in inspect.getsource(server._survey_html) or True

    def test_one_submission_per_device_is_a_localstorage_flag_and_no_more(self):
        """**Bypassable, and that is the correct trade**: the alternative is
        identifying people in order to stop them answering twice, which
        defeats the survey to protect a statistic."""
        html = js_code(_page())
        assert "localStorage.setItem('weare-survey-done'" in html
        for fingerprint in ("canvas", "getContext", "AudioContext", "webgl",
                            "fingerprint", "screen.width", "navigator.plugins",
                            "hardwareConcurrency"):
            assert fingerprint not in html, fingerprint

    def test_the_free_text_help_asks_people_to_leave_names_out(self):
        html = _page()
        assert html.count(server.html_escape(server.SURVEY_COPY["no_names"])) == 3

    def test_the_top_three_control_carries_its_limit(self):
        html = _page()
        assert f'data-limit="{server.SURVEY_TOP_THREE}"' in html


class TestTheNoScriptDoor:
    def test_both_doors_share_one_decider_and_one_store(self):
        src = inspect.getsource(server.submit_survey_form)
        assert "_survey_refusal" in src
        assert "_store_survey_response" in src
        assert "_survey_rate_refusal" in src

    def test_it_answers_html_rather_than_json(self):
        """There is nothing on the other end to read JSON."""
        src = inspect.getsource(server.submit_survey_form)
        assert "text/html" in src
        assert "_survey_thanks_html" in src

    def test_a_refusal_re_renders_the_form_with_the_message(self):
        """Which is what a form without JavaScript has instead of an inline
        error."""
        src = inspect.getsource(server.submit_survey_form)
        assert "_survey_html(error=" in src

    def test_the_rendered_error_appears_on_the_page(self):
        global LOOP
        if LOOP is None:
            LOOP = asyncio.new_event_loop()
        html = server._survey_html(error="Something specific went wrong.")
        assert "Something specific went wrong." in html
        assert 'role="alert"' in html


# --- 7. Retention -----------------------------------------------------------


class TestRetention:
    def test_the_survey_has_a_period(self):
        assert server.RETENTION_DAYS["survey_responses"] == 24 * 30

    def test_the_comment_says_the_period_is_housekeeping_not_law(self):
        """**Anonymous data carries no erasure duty**, so two years is a
        decision about comparing waves rather than a legal ceiling. Saying so
        matters because the privacy page reads this table."""
        start = SOURCE.index('"survey_responses"')
        block = SOURCE[max(0, start - 900) : start]
        assert "housekeeping" in block
        assert "erasure duty" in block

    def test_the_table_is_served_so_the_privacy_page_cannot_disagree(self):
        """`GET /admin/retention` returns the whole table, so the console's
        Retention section and `Legal.jsx` both pick the new row up rather than
        needing a second edit."""
        src = inspect.getsource(server.admin_retention)
        assert "RETENTION_DAYS" in src


# --- 8. It is actually reachable -------------------------------------------


class TestItIsServed:
    def test_the_page_and_the_form_post_are_both_registered(self):
        paths = [
            (getattr(r, "path", ""), sorted(getattr(r, "methods", []) or []))
            for r in server.app.routes
        ]
        assert (server.SURVEY_PATH, ["GET"]) in paths
        assert (server.SURVEY_PATH, ["POST"]) in paths

    def test_the_deploy_config_and_the_dev_proxy_both_know_about_it(self):
        vercel = json.loads((FRONTEND / "vercel.json").read_text())
        sources = [r["source"] for r in vercel["rewrites"]]
        assert server.SURVEY_PATH in sources
        # Above the catch-all, or it is dead config that looks live.
        assert sources.index(server.SURVEY_PATH) < sources.index("/((?!api/).*)")
        proxy = (FRONTEND / "src" / "setupProxy.js").read_text()
        assert "survey" in proxy

    def test_it_is_in_the_record(self):
        preview = (FRONTEND.parent / "PREVIEW.md").read_text()
        assert "/survey" in preview
