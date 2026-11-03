""""AI-powered" on the public site, held to what is switched on.

The site may say "AI" only where a switch backs it. Every string in the
content module that says "AI" must live under a switched key — an `ai*` field,
the home page's `ai` section, a step's `ai` list, or a FAQ item with an
`aiKey` — and each one is listed here with the switch that backs it, so a new
"AI" sentence without a switch fails CI. On top of that:

- the AI is never said to do pricing, approval or payment;
- no h1 says "AI";
- "AI-powered" appears only in the strings the two-switch rule governs: the
  page title and description, the deal's lead, the hero's badge and the AI
  slide's tab.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend"
SRC = FRONTEND / "src"
MARKETING = SRC / "content" / "marketing.js"
AI_WORD = re.compile(r"\bAI\b")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _content():
    script = re.sub(r"^import .*?;\s*$", "", MARKETING.read_text(), flags=re.M) + (
        "\nconsole.log(JSON.stringify({HOME, BRANDS, CREATORS, AI_FEATURES}));"
    )
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def _strings(node, path=()):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _strings(v, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _strings(v, path + (i,))
    elif isinstance(node, str):
        yield path, node


def _switch_for(content, page, path):
    """The switch an AI string sits behind, or None if it sits behind none."""
    node = content[page]
    owner = None
    for part in path:
        if isinstance(node, dict) and "aiKey" in node:
            owner = node["aiKey"]
        if isinstance(node, dict) and "key" in node and node.get("key") in content["AI_FEATURES"]:
            owner = node["key"]
        node = node[part]
    last = next((p for p in reversed(path) if isinstance(p, str)), "")
    if owner:
        return owner
    rules = {
        ("HOME", "aiLead"): "two", ("HOME", "aiTitle"): "two", ("HOME", "aiDescription"): "two",
        ("HOME", "aiBadge"): "two", ("HOME", "aiTab"): "two",
        ("BRANDS", "aiLead"): "briefWriter",
    }
    if (page, last) in rules:
        return rules[(page, last)]
    if (page, path[:1]) == ("HOME", ("ai",)):
        return "any"  # the AI slide itself renders while any switch is on
    if last == "aiLine":
        section = path[0]
        return {
            ("BRANDS", "report"): "campaignSummary",
            ("BRANDS", "shortlist"): "nicheMatching",
            ("CREATORS", "briefs"): "nicheMatching",
            ("CREATORS", "hero"): "nicheMatching",
        }.get((page, section))
    return None


def ai_strings():
    content = _content()
    found = []
    for page in ("HOME", "BRANDS", "CREATORS"):
        for path, text in _strings(content[page]):
            if AI_WORD.search(text):
                found.append((page, ".".join(map(str, path)), _switch_for(content, page, path), text))
    return found


def test_every_ai_sentence_sits_behind_a_switch():
    found = ai_strings()
    assert found, "the sweep found nothing — it cannot be working"
    unbacked = [(p, path, text) for p, path, switch, text in found if switch is None]
    assert not unbacked, f"'AI' with no switch behind it: {unbacked}"


def test_ai_powered_is_only_the_two_switch_strings():
    content = _content()
    hits = []
    for page in ("HOME", "BRANDS", "CREATORS"):
        for path, text in _strings(content[page]):
            if "AI-powered" in text:
                hits.append((page, path[-1]))
    assert sorted(hits) == [
        ("HOME", "aiBadge"), ("HOME", "aiDescription"), ("HOME", "aiLead"), ("HOME", "aiTab"), ("HOME", "aiTitle"),
    ]
    assert {_switch_for(content, "HOME", p) for p, t in _strings(content["HOME"]) if "AI-powered" in t} == {"two"}


FORBIDDEN = re.compile(
    r"\bAI(?:-powered)?\s+(?:pric\w*|approv\w*|pays?|payments?|payouts?|negotiat\w*|sets?\s+(?:the\s+)?fees?|"
    r"agrees?|decides?|invoic\w*)\b"
    r"|\b(?:pric\w*|approv\w*|payments?|payouts?|fees?)\s+(?:are|is)\s+(?:set|decided|handled|done)\s+by\s+(?:the\s+)?AI\b",
    re.I,
)


def test_the_ai_is_never_said_to_price_approve_or_pay():
    for page, path, _switch, text in ai_strings():
        assert not FORBIDDEN.search(text), (page, path, text)
    for bad in ("AI pricing", "AI approves the content", "AI pays creators", "fees are set by AI"):
        assert FORBIDDEN.search(bad), bad
    # And the section says the opposite in so many words.
    lead = _content()["HOME"]["ai"]["lead"]
    assert "People agree every fee, approve every post and pay every creator" in lead


def test_no_h1_says_ai():
    content = _content()
    for page in ("HOME", "BRANDS", "CREATORS"):
        assert not AI_WORD.search(content[page]["hero"]["title"]), page
    for path in (SRC / "pages").glob("*.jsx"):
        for h1 in re.findall(r"<h1[^>]*>(.*?)</h1>", path.read_text(), re.S):
            assert not AI_WORD.search(re.sub(r"\{[^}]*\}", "", h1)), path.name


def test_the_ai_slide_rows_are_the_three_switches_and_show_no_percentage():
    """Was `test_the_ai_cards_are_the_three_switches_with_drawings_we_serve`.
    The section's cards became the hero slider's AI slide: one row per
    feature, keyed by its switch, each with a drawn example under `card`
    rather than a drawing. **No percentage anywhere on the slide** — the
    scorer's number ranks a shortlist and is not a figure a brand is shown."""
    content = _content()
    ai = content["HOME"]["ai"]
    assert [c["key"] for c in ai["cards"]] == ["briefWriter", "nicheMatching", "campaignSummary"]
    assert set(c["key"] for c in ai["cards"]) == set(content["AI_FEATURES"])
    assert [c["title"] for c in ai["cards"]] == [
        "Drafts your brief",
        "Matches creators on what they actually post",
        "Reads your results, in plain English",
    ]
    assert ai["card"]["foot"] == "Fees, approvals and payments stay with people."
    assert ai["card"]["tag"] == "Example"
    for path, text in _strings(ai):
        assert "%" not in text and "percent" not in text.lower(), (path, text)
    assert "label" not in ai, "the section's label went with the section"


def test_the_ai_is_said_only_on_the_slide_and_nowhere_else_on_home():
    """No AI section and no AI card anywhere else on home: the feature row is
    the six product features, and the page mounts two sections."""
    home = (SRC / "pages" / "Home.jsx").read_text()
    assert "HOME.ai.cards.filter((card) => aiLive(card.key))" in home
    assert "<AiSection" not in home and "function AiSection" not in home and "IDS.aiCard" not in home
    content = _content()
    assert not [i for i in content["HOME"]["processSpine"]["features"]["items"] if "aiKey" in i]
    for path, text in _strings(content["HOME"]):
        if AI_WORD.search(text):
            assert path[0] in ("ai", "meta", "hero", "slides"), path
