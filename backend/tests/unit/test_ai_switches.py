"""The public site's AI switches, held to what the backend can actually do.

`AI_FEATURES` in `frontend/src/content/marketing.js` decides whether the public
site may say a word about an AI feature. **A switch set to `true` is a claim**,
so CI fails when one is on and the backend capability behind it — its route
and its module — does not exist. The table below names that capability per
switch; a new switch with no entry here fails too, so nobody can add one
without saying what would make it true.
"""
from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"
MARKETING = FRONTEND / "content" / "marketing.js"

# What must exist before a switch may be true: the module the feature lives in,
# and the routes that serve it (method, path as FastAPI registers it).
CAPABILITIES = {
    "campaignSummary": {
        "module": "campaign_summary",
        "routes": [
            ("GET", "/api/brand/campaigns/{campaign_id}/summary"),
            ("POST", "/api/brand/campaigns/{campaign_id}/summary/regenerate"),
        ],
    },
    "nicheMatching": {
        "module": "niche_matching",
        "routes": [("GET", "/api/brand/campaigns/{campaign_id}/niche-matches")],
    },
    "briefWriter": {
        "module": "brief_writer",
        "routes": [("POST", "/api/brand/campaigns/brief-writer")],
    },
}


def switches() -> dict:
    """`AI_FEATURES`, read from the source. Only `true`/`false` literals are
    accepted — a computed switch is a switch nobody can read in a diff."""
    text = MARKETING.read_text()
    block = re.search(r"export const AI_FEATURES = \{(.*?)\};", text, re.S)
    assert block, "AI_FEATURES is gone from marketing.js"
    body = "\n".join(
        line for line in block.group(1).splitlines() if not line.strip().startswith("//")
    )
    pairs = re.findall(r"(\w+)\s*:\s*([^,\s]+)\s*,?", body)
    out = {}
    for key, value in pairs:
        assert value in ("true", "false"), f"{key} must be a literal true or false, not {value}"
        out[key] = value == "true"
    return out


def missing_for(key: str) -> list:
    """Everything the backend lacks for this switch to be true. Empty is ready."""
    need = CAPABILITIES[key]
    missing = []
    if importlib.util.find_spec(need["module"]) is None:
        missing.append(f"module {need['module']}")
    served = {
        (method, getattr(r, "path", ""))
        for r in server.app.routes
        for method in (getattr(r, "methods", None) or ())
    }
    for method, path in need["routes"]:
        if (method, path) not in served:
            missing.append(f"route {method} {path}")
    return missing


def test_the_switches_are_the_three_named():
    assert set(switches()) == {"campaignSummary", "nicheMatching", "briefWriter"}


def test_every_switch_names_its_capability():
    assert set(switches()) == set(CAPABILITIES), (
        "a switch with no capability entry here cannot be checked — add one"
    )


@pytest.mark.parametrize("key", sorted(CAPABILITIES))
def test_a_switch_that_is_on_has_its_backend(key):
    if not switches().get(key):
        pytest.skip(f"{key} is off")
    assert not missing_for(key), (
        f"AI_FEATURES.{key} is true but the backend lacks: {missing_for(key)}. "
        "Flip it on only in the PR that ships the feature."
    )


def test_the_check_would_fail_a_switch_with_no_backend():
    """The negative half, so the test above is known to be able to fail: the
    two features not built yet are missing their module and route."""
    assert missing_for("nicheMatching")
    assert missing_for("briefWriter")


def test_the_summary_backend_exists():
    """Built in this PR, so its switch *could* be flipped — but it stays off
    until the screen ships, which is the PR that shows it to a brand."""
    assert missing_for("campaignSummary") == []


def test_no_page_reads_the_switches_except_through_ai_live():
    offenders = []
    for path in FRONTEND.rglob("*.js*"):
        if path == MARKETING or "node_modules" in path.parts:
            continue
        if "AI_FEATURES" in path.read_text():
            offenders.append(str(path.relative_to(FRONTEND)))
    assert not offenders, f"read AI_FEATURES through aiLive(key) instead: {offenders}"


def test_the_comment_carries_the_three_rules():
    text = MARKETING.read_text()
    head = text.split("export const AI_FEATURES")[0][-2500:]
    head = re.sub(r"\s*\n\s*\*\s*", " ", head)
    assert "only in the PR that ships that feature" in head
    assert "renders only while its switch" in head
    assert "AI_ENABLED" in head and "flip these off too" in head


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_ai_live_reads_only_a_literal_true():
    script = (
        re.sub(r"^import .*?;\s*$", "", MARKETING.read_text(), flags=re.M)
        + "\nconsole.log(JSON.stringify(["
        "aiLive('campaignSummary'), aiLive('nicheMatching'), aiLive('briefWriter'),"
        "aiLive('nonsense'), aiLive(undefined)]));"
    )
    out = subprocess.run(
        ["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=60
    )
    assert out.returncode == 0, out.stderr
    got = out.stdout.strip()
    state = switches()
    expected = [state["campaignSummary"], state["nicheMatching"], state["briefWriter"], False, False]
    assert got == str(expected).replace("True", "true").replace("False", "false").replace(" ", "")
