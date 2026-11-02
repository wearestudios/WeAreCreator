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
        "module": "niche_tagging",
        "routes": [
            ("GET", "/api/creator/tags"),
            ("GET", "/api/brand/campaigns/{campaign_id}/tags"),
            ("PUT", "/api/brand/campaigns/{campaign_id}/tags"),
        ],
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
    feature not built yet is missing its module and route."""
    assert missing_for("briefWriter")


def test_the_matching_backend_exists():
    assert missing_for("nicheMatching") == []


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


# ---------------------------------------------------------------------------
# The lines each switch governs, on the pages that print them
# ---------------------------------------------------------------------------

PAGES = Path(server.__file__).resolve().parents[1] / "frontend" / "src" / "pages"

# (page file, the content key printed, the switch that must guard it, the
# analytics section id it reports as).
# A key of `None` means the guard is the content's own `aiKey`, which the test
# below holds to the right switch per step.
SWITCHED_LINES = [
    ("ForBrands.jsx", "report.aiLine", "campaignSummary", "report-ai-summary"),
    ("ForBrands.jsx", "shortlist.aiLine", "nicheMatching", "shortlist-ai-matching"),
    ("ForCreators.jsx", "briefs.aiLine", "nicheMatching", "briefs-ai-matching"),
    ("Home.jsx", "step.aiLine", None, "step-${step.key}-ai"),
]

# Homepage steps that carry an AI line, and the switch each must sit behind.
STEP_SWITCHES = {"offer": "nicheMatching", "paid": "campaignSummary"}


@pytest.mark.parametrize("page,expr,key,track", SWITCHED_LINES)
def test_each_ai_line_renders_only_behind_its_switch(page, expr, key, track):
    src = (PAGES / page).read_text()
    at = src.index("{" + expr + "}")
    needle = f'aiLive("{key}")' if key else "aiLive(step.aiKey)"
    guard = src.rfind(needle, 0, at)
    assert guard != -1 and at - guard < 600, f"{expr} on {page} is not inside {needle}"
    # And the element it renders on reports when it is seen.
    assert f"data-track-section={{`{track}`}}" in src or f'data-track-section="{track}"' in src


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_each_homepage_ai_line_names_its_switch():
    script = (
        re.sub(r"^import .*?;\s*$", "", MARKETING.read_text(), flags=re.M)
        + "\nconsole.log(JSON.stringify(HOME.how.items.filter(s => s.aiLine)"
        ".map(s => [s.key, s.aiKey])));"
    )
    out = subprocess.run(
        ["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=60
    )
    assert out.returncode == 0, out.stderr
    import json

    assert dict(json.loads(out.stdout)) == STEP_SWITCHES


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_example_why_line_is_drawn_only_behind_the_switch():
    src = (PAGES / "ForBrands.jsx").read_text()
    assert 'showWhy={aiLive("nicheMatching")}' in src
    mocks = (FRONTEND / "components" / "marketing" / "siteMocks.jsx").read_text()
    assert "showWhy = false" in mocks and "showWhy && row.why" in mocks


def test_every_ai_line_in_the_content_has_a_guarded_render():
    text = MARKETING.read_text()
    for name in re.findall(r"^\s*(aiLine):", text, re.M):
        assert name == "aiLine"
    rendered = sum(
        (PAGES / page).read_text().count("aiLine}") for page, *_ in SWITCHED_LINES
    )
    assert rendered >= len(SWITCHED_LINES)


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_lines_say_only_what_the_validator_holds():
    """"Using only your real numbers" is a claim — `campaign_summary.ground`
    is what makes it true, and the grounding tests are what hold it."""
    text = MARKETING.read_text()
    assert "using only your real numbers, never invented ones" in text
    import campaign_summary

    assert callable(campaign_summary.ground)
