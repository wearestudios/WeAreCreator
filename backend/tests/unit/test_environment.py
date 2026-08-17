"""The process refuses to start without what it cannot do without.

Three variables have no default: MONGO_URL, DB_NAME and JWT_SECRET. The first
two were already read at import, so a missing one crashed the boot — loudly,
but with a bare `KeyError: 'MONGO_URL'` and nothing about the other two. The
third was worse: `_jwt_secret()` read it per call, so a deploy without it
started cleanly, served the marketing page, and 500'd the first person who
tried to sign in.

`validate_environment()` names all three at once, before the first read, so an
operator fixes the whole set in one restart rather than one variable per boot.

The second half of this file holds `.env.example` to its promise. A variable
the app reads and the file doesn't mention is a variable somebody discovers in
production, and the notification templates drift the fastest — they are looked
up dynamically as `AISENSY_TEMPLATE_{event.upper()}`, so nothing but a test
notices when a new event ships with no line documenting its template.
"""
import ast
import re
from pathlib import Path

import pytest

import server

BACKEND_ROOT = Path(server.__file__).resolve().parent
ENV_EXAMPLE = BACKEND_ROOT / ".env.example"


# --- The boot check ---------------------------------------------------------

REQUIRED = {"MONGO_URL", "DB_NAME", "JWT_SECRET"}


def test_required_set_is_exactly_the_three_with_no_default():
    """Pinned, because the cost of adding one is a deploy that won't start.

    Anything with a working default belongs in the warning list instead.
    """
    assert {key for key, _ in server._ENV_REQUIRED} == REQUIRED


def test_every_required_variable_carries_an_explanation():
    for key, why in server._ENV_REQUIRED:
        assert why.strip(), f"{key} has no explanation to print"


@pytest.mark.parametrize("missing", sorted(REQUIRED))
def test_a_missing_variable_is_named(monkeypatch, capsys, missing):
    monkeypatch.delenv(missing, raising=False)

    reported = server.validate_environment(exit_on_missing=False)

    assert [key for key, _ in reported] == [missing]
    assert missing in capsys.readouterr().err


def test_all_three_are_reported_together(monkeypatch, capsys):
    """One boot, one list. Reporting the first would cost three restarts."""
    for key in REQUIRED:
        monkeypatch.delenv(key, raising=False)

    reported = server.validate_environment(exit_on_missing=False)

    assert {key for key, _ in reported} == REQUIRED
    err = capsys.readouterr().err
    for key in REQUIRED:
        assert key in err
    assert ".env.example" in err, "the message should say where to look"


def test_a_blank_value_counts_as_missing(monkeypatch):
    """`JWT_SECRET=` in a .env file is an empty string, not an absent key."""
    monkeypatch.setenv("JWT_SECRET", "   ")

    assert "JWT_SECRET" in {key for key, _ in server.validate_environment(exit_on_missing=False)}


def test_a_complete_environment_reports_nothing(monkeypatch):
    for key in REQUIRED:
        monkeypatch.setenv(key, "set")

    assert server.validate_environment(exit_on_missing=False) == []


def test_the_default_is_to_exit(monkeypatch):
    """The signature defaults to stopping the process — the tests above opt out."""
    monkeypatch.delenv("MONGO_URL", raising=False)

    with pytest.raises(SystemExit) as exit_info:
        server.validate_environment()

    assert exit_info.value.code == 1


def test_production_is_the_default_reading_of_an_unset_environment(monkeypatch):
    """Unset means production. Guessing the other way makes a real deployment
    silently permit OTP simulation and swallow the missing-admin warning."""
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENV", raising=False)

    assert server._is_production() is True


@pytest.mark.parametrize("value", ["dev", "development", "local", "test", "  Development  "])
def test_the_development_names_are_not_production(monkeypatch, value):
    monkeypatch.setenv("APP_ENV", value)

    assert server._is_production() is False


def test_env_is_read_only_when_app_env_is_absent(monkeypatch):
    """Some hosts set ENV instead. APP_ENV wins where both are present, so
    setting it explicitly is never overridden by the platform's own value."""
    monkeypatch.setenv("ENV", "development")
    monkeypatch.delenv("APP_ENV", raising=False)
    assert server._is_production() is False

    monkeypatch.setenv("APP_ENV", "production")
    assert server._is_production() is True


def test_production_warns_about_what_still_works_without(monkeypatch, caplog):
    """These have defaults, so they warn rather than exit — but each breaks
    something an operator would otherwise discover from a user."""
    monkeypatch.setenv("APP_ENV", "production")
    for key, _ in server._ENV_PRODUCTION:
        monkeypatch.delenv(key, raising=False)

    with caplog.at_level("WARNING", logger="wearecreators"):
        server.validate_environment(exit_on_missing=False)

    logged = caplog.text
    for key, _ in server._ENV_PRODUCTION:
        assert key in logged


def test_development_stays_quiet(monkeypatch, caplog):
    """A laptop and the unit suite legitimately run with no admin account."""
    monkeypatch.setenv("APP_ENV", "development")
    for key, _ in server._ENV_PRODUCTION:
        monkeypatch.delenv(key, raising=False)

    with caplog.at_level("WARNING", logger="wearecreators"):
        server.validate_environment(exit_on_missing=False)

    for key, _ in server._ENV_PRODUCTION:
        assert key not in caplog.text


def test_jwt_secret_names_itself_rather_than_raising_a_bare_keyerror(monkeypatch):
    """Unreachable in a process that started normally. It exists so that if the
    variable is ever cleared at runtime the traceback says which one."""
    monkeypatch.delenv("JWT_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        server._jwt_secret()


def test_validate_environment_runs_at_import():
    """Not just defined — called, and called before the first bracket read, or
    the KeyError wins the race and the clear message is never printed."""
    source = (BACKEND_ROOT / "server.py").read_text()
    called = source.index("\nvalidate_environment()")
    first_read = source.index('os.environ["MONGO_URL"]')

    assert called < first_read


# --- .env.example -----------------------------------------------------------


def _documented_variables():
    """Every NAME= in the file, commented out or not.

    A commented line still documents the variable — most of these are optional
    and are meant to be left off.
    """
    return set(re.findall(r"^\s*#?\s*([A-Z_][A-Z0-9_]*)=", ENV_EXAMPLE.read_text(), re.M))


def _variables_read_by_the_backend():
    """Every literal os.environ read across the backend's own modules.

    AST rather than a grep: `os.environ.get("X", "y")` and `os.environ["X"]`
    and `os.getenv("X")` are all reads, and a regex catches some of them.
    """
    found = set()
    for path in BACKEND_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "environ"
                and isinstance(node.slice, ast.Constant)
            ):
                found.add(node.slice.value)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                base = node.func.value
                is_env = (isinstance(base, ast.Attribute) and base.attr == "environ") or (
                    isinstance(base, ast.Name) and base.id == "os"
                )
                if (
                    is_env
                    and node.func.attr in ("get", "getenv")
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                ):
                    found.add(node.args[0].value)
    return found


def test_env_example_exists():
    assert ENV_EXAMPLE.is_file()


def test_every_variable_the_backend_reads_is_documented():
    undocumented = _variables_read_by_the_backend() - _documented_variables()

    assert not undocumented, (
        "read by the backend but absent from .env.example: "
        + ", ".join(sorted(undocumented))
    )


def test_every_notification_event_has_a_documented_template():
    """The templates are resolved as AISENSY_TEMPLATE_{event.upper()}, so no
    static analysis of the source can find them and nothing else notices when
    a new event ships undocumented."""
    documented = _documented_variables()
    missing = [
        event for event in server.NOTIFY_EVENTS if f"AISENSY_TEMPLATE_{event.upper()}" not in documented
    ]

    assert not missing, "events with no template line in .env.example: " + ", ".join(sorted(missing))


def test_no_template_is_documented_for_an_event_that_does_not_exist():
    """The other direction: a renamed event leaves a line nothing will read."""
    known = {event.upper() for event in server.NOTIFY_EVENTS}
    stale = [
        name[len("AISENSY_TEMPLATE_"):]
        for name in _documented_variables()
        if name.startswith("AISENSY_TEMPLATE_") and name[len("AISENSY_TEMPLATE_"):] not in known
    ]

    assert not stale, "documented templates for unknown events: " + ", ".join(sorted(stale))


def test_the_required_three_are_documented_with_a_usable_default():
    """Uncommented, and with a value — this file is copied to .env and edited,
    so a commented-out MONGO_URL would produce a .env that refuses to boot."""
    text = ENV_EXAMPLE.read_text()
    for key in REQUIRED:
        match = re.search(rf"^{key}=(.*)$", text, re.M)
        assert match, f"{key} is required but not documented as a live line"
        assert match.group(1).strip(), f"{key} is documented with no example value"
