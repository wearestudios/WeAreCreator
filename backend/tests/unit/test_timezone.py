"""The portal is IST, and the database is UTC.

**The bug.** BSON has no time zone. A datetime written as
`datetime.now(timezone.utc)` comes back from Mongo *naive*, and
`datetime.isoformat()` on a naive value emits no offset at all — so the same
instant serialised two different ways depending on whether it had been round
tripped through the database, and `new Date()` read the naive half as the
reader's **local** time. For everybody here that is 5½ hours, which is the
notification panel saying "6h ago" about something twenty minutes old.

**The bargain.** Storage stays UTC and the API emits UTC *with its offset*
(`_iso`); the conversion to IST happens on the way to a screen, in one place
(`frontend/src/lib/time.js`), and in one place on the way to a phone
(`_when_text`, for the WhatsApp messages that tell a creator when to turn up).

Three rules, all pinned below:

1. no timestamp leaves this server without an offset;
2. every human-facing time the server writes goes through `_when_text`;
3. no screen formats a date without naming the zone, and `lib/time.js` is the
   only place that names it.
"""
import ast
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import server

BACKEND = Path(server.__file__).resolve().parent
FRONTEND = BACKEND.parent / "frontend"
SRC = FRONTEND / "src"
TIME_LIB = SRC / "lib" / "time.js"

# The moment that made this obvious: 19:00 in Bengaluru is 13:30 UTC, and it is
# the *next day* in UTC once you go past 18:30.
EVENING_IST = datetime(2026, 8, 20, 13, 30, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 1. Nothing leaves without an offset
# ---------------------------------------------------------------------------


def test_a_naive_timestamp_is_stamped_as_utc():
    """Naive means UTC by construction — every write goes through
    `datetime.now(timezone.utc)` — so stamping it states a fact rather than
    guessing."""
    naive = EVENING_IST.replace(tzinfo=None)
    assert server._iso(naive) == server._iso(EVENING_IST)
    assert server._iso(naive).endswith("+00:00")


def test_an_aware_timestamp_keeps_its_own_offset():
    ist = EVENING_IST.astimezone(server.SHOOT_TZ)
    assert server._iso(ist) == ist.isoformat()
    # Same instant either way, which is the whole point.
    assert datetime.fromisoformat(server._iso(ist)) == EVENING_IST


def test_iso_passes_through_anything_that_is_not_a_datetime():
    """It is called on `.get()`s of fields that are often absent."""
    assert server._iso(None) is None
    assert server._iso("already a string") == "already a string"


def test_no_serializer_calls_isoformat_directly():
    """A bare `.isoformat()` on a value read from Mongo is the bug, spelled
    out. `_iso` is the only way a *datetime* becomes a string here."""
    source = (BACKEND / "server.py").read_text()
    tree = ast.parse(source)
    # `_iso` itself ends in `return value.isoformat()`, which is the point.
    iso_lines = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_iso":
            iso_lines = set(range(node.lineno, (node.end_lineno or node.lineno) + 1))

    offenders = []
    for n, line in enumerate(source.splitlines(), start=1):
        if ".isoformat()" not in line or n in iso_lines:
            continue
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # Built aware in the same expression, so there is nothing to stamp.
        if "datetime.now(timezone.utc).isoformat()" in stripped:
            continue
        # A `date` has no time and therefore no zone — `.date().isoformat()`
        # is "2026-08-20", which is what it says it is.
        if ".date().isoformat()" in stripped:
            continue
        offenders.append(stripped)
    assert offenders == [], f"timestamps serialised without _iso: {offenders}"


def test_jsonable_routes_datetimes_through_iso():
    """The audit log's before/after blobs carry raw documents, so the generic
    converter has to hold the same rule as the hand-written serializers."""
    out = server._jsonable({"when": EVENING_IST.replace(tzinfo=None)})
    assert out["when"].endswith("+00:00")


# ---------------------------------------------------------------------------
# 2. What a phone is told
# ---------------------------------------------------------------------------


def test_the_message_time_is_the_time_at_the_venue():
    """A 19:00 Bengaluru sitting, told to a creator. Formatting the stored UTC
    directly said 2:00 pm, which is the same 5½ hours arriving on a phone
    instead of on a screen."""
    assert server._when_text(EVENING_IST) == "20 Aug, 7:00 pm"
    # And it does not care whether the value came back from the database naive.
    assert server._when_text(EVENING_IST.replace(tzinfo=None)) == "20 Aug, 7:00 pm"


def test_a_late_utc_stamp_is_already_tomorrow_here():
    """The direction the offset actually bites. 20:00 UTC on the 20th is 01:30
    on the 21st in Bengaluru, so anything reading the UTC date puts a shoot on
    the wrong day for everybody using this."""
    late_utc = datetime(2026, 8, 20, 20, 0, tzinfo=timezone.utc)
    assert late_utc.day == 20
    assert server._ist(late_utc).day == 21
    assert server._when_text(late_utc) == "21 Aug, 1:30 am"


def test_the_server_side_zone_is_the_one_the_operation_runs_in():
    """A fixed +05:30 rather than a named zone, and correct because IST has no
    daylight saving — there is no rule to look up. `lib/time.js` names
    "Asia/Kolkata" because `Intl` wants a name, and the two are the same
    offset every day of the year."""
    assert server.SHOOT_TZ.utcoffset(None) == timedelta(hours=5, minutes=30)


def test_ist_reads_a_naive_value_as_utc():
    assert server._ist(EVENING_IST.replace(tzinfo=None)).hour == 19
    assert server._ist(None) is None


# ---------------------------------------------------------------------------
# 3. What a screen does with it
# ---------------------------------------------------------------------------

_JS = sorted(
    p
    for p in list(SRC.rglob("*.js")) + list(SRC.rglob("*.jsx"))
    if "node_modules" not in p.parts
)

# The option keys that make a `toLocale*` call a *date* rather than a number.
_DATE_KEYS = ("day", "month", "year", "hour", "minute", "second", "weekday")


def _locale_calls(src: str):
    """Every `toLocaleDateString/TimeString/String` call with its arguments."""
    for match in re.finditer(r"\.toLocale(?:Date|Time)?String\(", src):
        i = match.end()
        depth = 1
        while i < len(src) and depth:
            if src[i] == "(":
                depth += 1
            elif src[i] == ")":
                depth -= 1
            i += 1
        yield src[match.end() : i - 1]


@pytest.mark.parametrize("path", _JS, ids=lambda p: str(p.relative_to(SRC)))
def test_no_screen_formats_a_date_without_naming_the_zone(path):
    """A formatter with no `timeZone` renders in whatever zone the reader's
    laptop is in — which is the browser half of the same bug. The portal shows
    IST, so every date formatter says so."""
    for args in _locale_calls(path.read_text()):
        if not any(f"{key}:" in args for key in _DATE_KEYS):
            continue  # a number, not a date
        assert "timeZone" in args, (
            f"{path.relative_to(SRC)} formats a date without a timeZone: {args.strip()[:80]}"
        )


def test_the_zone_is_named_in_exactly_one_place():
    """One definition, imported everywhere. A second literal is how half the
    app ends up in a different zone from the other half."""
    owners = [
        p.relative_to(SRC)
        for p in _JS
        if re.search(r'["\']Asia/Kolkata["\']', p.read_text())
    ]
    assert [str(o) for o in owners] == ["lib/time.js"], (
        f"the zone is spelled out in {owners}"
    )


def test_every_file_that_formats_a_date_imports_the_zone():
    """Passing `timeZone` and defining it locally would pass the rule above and
    still be a second source of truth."""
    for path in _JS:
        src = path.read_text()
        if path == TIME_LIB:
            continue
        formats = any(
            any(f"{key}:" in args for key in _DATE_KEYS)
            for args in _locale_calls(src)
        )
        if not formats:
            continue
        assert re.search(r'from "@/lib/time"', src), (
            f"{path.relative_to(SRC)} formats dates without importing the zone"
        )


def test_the_day_a_timestamp_falls_on_is_bucketed_in_ist():
    """`toISOString().slice(0, 10)` is the *UTC* day, which moves every evening
    shoot in India to the next date. `dayKey` is the fix and the only one."""
    lib = TIME_LIB.read_text()
    assert 'toLocaleDateString("en-CA", { timeZone: IST })' in lib
    for path in _JS:
        src = _no_comments(path)
        assert "toISOString().slice(0, 10)" not in src, (
            f"{path.relative_to(SRC)} buckets a day in UTC"
        )


def _no_comments(path: Path) -> str:
    """Source with its comments gone — a rule about what the code does must not
    be broken *or* satisfied by the comment explaining it."""
    src = re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


def test_nothing_takes_local_midnight_with_setHours():
    """`setHours(0, 0, 0, 0)` is midnight wherever the laptop is — and it
    mutates the Date it is called on, which in `ManagerHome`'s loop meant every
    campaign after the first was measured against midnight rather than now."""
    for path in _JS:
        src = _no_comments(path)
        assert "setHours(0, 0, 0, 0)" not in src, (
            f"{path.relative_to(SRC)} takes the browser's midnight"
        )


def test_relative_time_has_one_implementation():
    """"6h ago" is what the reported bug looked like. The arithmetic was always
    right; its input was wrong — so there is one `timeAgo`, and it lives beside
    the parsing that fixes the input.

    `admin/console/format.jsx` keeps its own `relative`, deliberately and with
    the reason written down: a console row says "3h ago" where the app says
    "3h". `admin/shared.jsx` had a *third* copy that nothing imported, which is
    what this now stops coming back.
    """
    lib = TIME_LIB.read_text()
    assert "export function timeAgo(" in lib
    others = [
        str(p.relative_to(SRC))
        for p in _JS
        if p != TIME_LIB
        and re.search(r"^(export )?(function |const )timeAgo\b", p.read_text(), re.M)
    ]
    assert others == [], f"a second timeAgo lives in {others}"
