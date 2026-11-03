"""The pre-revamp site's look, restored over the new public-site content.

The founder compared both live sites: the old one (8263b6f) was better on
visuals, motion and ease of understanding, the new one right on content. This
file holds what the restoration brought back, and the lines it was not allowed
to cross:

- **illustrations placed by meaning**, decorative, lazy below the fold, and
  stacked above their text on a phone;
- **photo slots show a drawing** until a photograph arrives, with the headline
  on a navy band that keeps its contrast;
- **motion that explains** — the film beside the four steps, the fee drawn as
  it flows, the payout window drawn, the hero card cycling the four steps —
  every one of which lands on its end state under reduced motion, and none of
  which is allowed to put an animation library in the homepage's first paint;
- **bands** alternating the page ground, a warm tint and navy, never two alike
  side by side and never more than two navy;
- **both sides of every step**, and `/how-it-works` landing on them.

The claims the restored components make are checked against the product, the
way `test_site_claims.py` checks the copy: no escrow, no unsourced comparison
with other operators, no fee figure while the fee is undecided.
"""

from __future__ import annotations

import functools
import json
import re
import subprocess
from pathlib import Path

import pytest

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend"
SRC = FRONTEND / "src"
MKT = SRC / "components" / "marketing"
PAGES = {
    "home": SRC / "pages" / "Home.jsx",
    "brands": SRC / "pages" / "ForBrands.jsx",
    "creators": SRC / "pages" / "ForCreators.jsx",
}


def _code(path: Path) -> str:
    """Source with comments removed — the explanations here quote what they
    replaced, and a rule about the page must not fail on its own reasoning."""
    src = path.read_text()
    src = re.sub(r"\{/\*.*?\*/\}", "", src, flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("//"))


@functools.lru_cache(maxsize=1)
def _content():
    script = (SRC / "content" / "marketing.js").read_text() + (
        "\nconsole.log(JSON.stringify({HOME, BRANDS, CREATORS, FACTS}));"
    )
    out = subprocess.run(["node", "--input-type=module", "-e", script],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@functools.lru_cache(maxsize=1)
def _illustrations():
    script = (SRC / "content" / "illustrations.js").read_text() + (
        "\nconsole.log(JSON.stringify(ILLUSTRATIONS));"
    )
    out = subprocess.run(["node", "--input-type=module", "-e", script],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


# ---------------------------------------------------------------------------
# 1 · Illustrations, placed by meaning
# ---------------------------------------------------------------------------

# The placements the restoration asked for, section by section.
PLACED = {
    # The four step drawings left with the old "How it works": the process
    # spine draws each step as product UI instead.
    "home": {"why-production"},
    "brands": {"brands-city-dusk", "why-roster-tablet", "brands-door-checkin", "how-report-desk"},
    "creators": {"creators-profile-phone", "creators-cafe-shoot", "why-fees-closeup"},
}


def test_every_illustration_named_is_a_file_we_serve():
    art = _illustrations()
    assert set().union(*PLACED.values()) <= set(art)
    for name, spec in art.items():
        assert spec["src"] == f"/img/marketing/{name}.svg", name
        assert (FRONTEND / "public" / spec["src"].lstrip("/")).is_file(), name


@pytest.mark.parametrize("page", list(PAGES))
def test_each_page_places_its_illustrations(page):
    code = _code(PAGES[page])
    named = set(re.findall(r'<Illustration name="([\w-]+)"', code))
    named |= set(re.findall(r'art="([\w-]+)"', code))
    assert named == PLACED[page], (page, named ^ PLACED[page])


def test_the_hero_deck_keeps_its_four_steps():
    """The hero's card still cycles Offer → Agree → Deliver → Get paid; the
    list moved from the retired "How it works" copy into the deck's own."""
    keys = [i["key"] for i in _content()["HOME"]["deck"]["steps"]]
    assert keys == ["offer", "agree", "deliver", "paid"]
    assert set(keys) == set(_content()["HOME"]["deck"]["screen"])
    assert "STEP_ART" not in _code(PAGES["home"])


def test_an_illustration_is_decorative_reserved_and_lazy_below_the_fold():
    code = _code(MKT / "Illustration.jsx")
    assert 'alt=""' in code
    assert 'loading={eager ? "eager" : "lazy"}' in code and "eager = false" in code
    # The ratio is on the frame, never the <img>, so nothing moves on arrival.
    frame = code[code.index("const frame") : code.index("<img")]
    assert "aspectRatio:" in frame
    img = code[code.index("<img") : code.index("/>", code.index("<img"))]
    assert "aspect" not in img
    # Only the two heroes are eager — they are above the fold. Every other
    # drawing waits for the viewport.
    eager = []
    for page, path in PAGES.items():
        eager += [(page, n) for n in re.findall(r'<Illustration name="([\w-]+)" eager', _code(path))]
    assert sorted(eager) == [("brands", "brands-city-dusk"), ("creators", "creators-profile-phone")]
    assert "loading" not in _code(SRC / "content" / "illustrations.js")


@pytest.mark.parametrize("page", list(PAGES))
def test_on_a_phone_every_drawing_stacks_above_its_text(page):
    """At 390px the drawing comes first and fills the width. Placed second in
    the DOM for the desktop columns, so `order-first` carries it up — and the
    home steps put it first in the DOM outright."""
    code = _code(PAGES[page]) + _code(MKT / "SiteParts.jsx")
    for m in re.finditer(r'<Illustration name=(?:"[\w-]+"|\{art\})([^>]*)/>', code):
        attrs = m.group(1)
        if 'ratio="4 / 3"' in attrs:  # the home steps: first in their <li>
            continue
        assert "order-first" in attrs, (page, m.group(0))


# ---------------------------------------------------------------------------
# 2 · A photo slot shows a drawing until a photograph exists
# ---------------------------------------------------------------------------


def test_the_slot_fallback_is_the_drawing_with_the_headline_on_navy():
    manifest = (SRC / "content" / "photoSlots.js").read_text()
    pairs = dict(re.findall(r'"([\w-]+)": \{[^}]*?fallbackIllustration: "([^"]+)"', manifest, flags=re.S))
    assert pairs == {
        "home-on-location": "/img/marketing/home-on-location.svg",
        "brands-full-room": "/img/marketing/brands-full-house.svg",
        # `creators-cafe-shoot` is already beside "Briefs that fit".
        "creators-on-shoot": "/img/marketing/home-venue-wide.svg",
    }
    code = _code(MKT / "PhotoSlot.jsx")
    fallback = code.split('data-empty="fallback"', 1)[1]
    # The drawing first, then the band over it: navy at 92% in the inverse
    # set, so the headline is the inverse ink on navy whatever is beneath.
    assert fallback.index("slot.fallbackIllustration") < fallback.index("bg-background/[0.92]")
    assert 'data-surface="inverse"' in fallback
    # With a photograph, the photograph replaces it and nothing else changes.
    assert code.index("if (slot.src)") < code.index('data-empty="placeholder"') < code.index('data-empty="fallback"')


# ---------------------------------------------------------------------------
# 3 · Motion that explains
# ---------------------------------------------------------------------------


def _static_imports(path: Path, seen=None):
    """Every module `path` pulls in at load, following `@/` imports and
    skipping anything behind a dynamic `import()` — which is a separate chunk
    fetched later."""
    seen = set() if seen is None else seen
    if path in seen:
        return seen
    seen.add(path)
    code = _code(path)
    for spec in re.findall(r'^\s*import\s[^;]*?from\s+"([^"]+)"', code, flags=re.M | re.S):
        if spec.startswith("@/"):
            base = SRC / spec[2:]
            for cand in (base.with_suffix(".jsx"), base.with_suffix(".js"), base / "index.js"):
                if cand.is_file():
                    _static_imports(cand, seen)
                    break
        else:
            seen.add(spec)
    return seen


def test_the_homepage_first_paint_carries_no_animation_library():
    """The homepage's LCP is its h1. framer-motion is 36KB gzip; on the page
    whose first paint is a heading, putting it in front would be the one
    regression this restoration must not cause. The deck reads the media query
    itself, `Rise` is CSS, and the process spine that replaced the film is
    CSS transitions driven by two observers — it is in the page's chunk and
    brings no animation library with it."""
    loaded = _static_imports(PAGES["home"])
    assert "framer-motion" not in loaded
    assert MKT / "ProcessSpine.jsx" in loaded
    assert not (MKT / "CampaignFilm.jsx").exists()
    # The deck's four screens are their own chunk too, into a frame already
    # the right size: they are not needed to paint the h1. Measured: with
    # them in the page's chunk the median LCP sat 18ms behind main's.
    assert MKT / "heroScreens.jsx" not in loaded
    assert 'webpackChunkName: "hero-screens"' in (MKT / "HeroDeck.jsx").read_text()
    # The other two pages already load it for CountUp; the explaining pieces
    # there may use it.
    assert "framer-motion" in _static_imports(PAGES["brands"])


def test_the_spine_claims_only_what_the_product_does():
    """Replaces the film's claims test. Every promise on the spine is held by
    something the server does: the payout window, the revision cap, the
    contact allow-list, barter being opt-in, and the shortlisting being ours
    on a brief we run."""
    spine = _content()["HOME"]["processSpine"]
    text = json.dumps(spine).lower()
    assert "escrow" not in text and "held before" not in text and "receipt" not in text
    assert "in minutes" not in text, "a brief is reviewed before it goes live"
    assert "one tap" not in text, "an application carries a rate and a pitch"
    creators = {s["key"]: s for s in spine["steps"]["creators"]}
    brands = {s["key"]: s for s in spine["steps"]["brands"]}
    assert "within 7 days of approval" in creators["paid"]["line"]
    assert "all of it" in creators["paid"]["line"]
    assert server.CREATOR_PAYOUT_DAYS == 7 and server._CREATOR_PAYOUT_MAX == 7
    assert "within 7 days" in brands["results"]["card"]["paid"]
    # The revision cap.
    assert "revisions included" in brands["approve"]["line"]
    assert "1 of 2 used" in brands["approve"]["card"]["revisions"]
    assert callable(server._revision_allowance)
    # The contact allow-list.
    assert "never a phone or email" in brands["shortlist"]["line"]
    assert {"phone", "email"} <= set(server.BRAND_FORBIDDEN_CREATOR_FIELDS)
    # Barter is opt-in for creators.
    assert "only if you turn them on" in creators["find"]["line"]
    assert callable(server._shows_barter_briefs)
    # We shortlist, because every brand brief is ours to run.
    assert "we shortlist" in brands["shortlist"]["line"]
    assert server.NEW_CAMPAIGN_EXECUTION_OWNER == "weare"


def test_the_fee_flow_draws_our_flow_and_no_one_elses():
    """The old version compared us with a 35–60% share it said other
    operators pay — unsourced, and gone. What is drawn is ours: the brand, us,
    the creator, and 100% of the agreed fee arriving."""
    flow = _content()["BRANDS"]["pricing"]["flow"]
    assert [s["key"] for s in flow["steps"]] == ["brand", "weare", "creator"]
    assert flow["share"] == 100
    text = json.dumps(flow).lower()
    assert "escrow" not in text, "there is no escrow; the FAQ says so"
    code = _code(MKT / "FeeFlow.jsx")
    for gone in ("theirShare", "UNSOURCED", "data-unsourced", "35–", "–60"):
        assert gone not in code, gone


def test_the_fee_flow_prints_no_fee_while_the_fee_is_undecided():
    assert _content()["FACTS"]["platformFeePercent"] is None
    code = _code(MKT / "FeeFlow.jsx")
    assert "platformFeeText" in code
    assert re.search(r'step\.key === "weare" && fee \?', code), "the fee line renders only when there is one"
    # Driven: the helper the flow calls answers null for the null fact.
    script = (SRC / "content" / "marketing.js").read_text() + (
        "\nconsole.log(JSON.stringify([platformFeeText(), platformFeeText(8)]));"
    )
    out = json.loads(subprocess.run(["node", "--input-type=module", "-e", script],
                                    capture_output=True, text=True, timeout=60).stdout)
    assert out == [None, "8% of the creator's fee"]


def test_the_payout_clock_draws_the_window_the_server_promises():
    code = _code(MKT / "PayoutClock.jsx")
    assert "ourDays = CREATOR_PAYOUT_DAYS" in code
    for gone in ("theirDays", "UNSOURCED", "data-unsourced", "90"):
        assert gone not in code, gone
    payout = (SRC / "lib" / "payoutWindow.js").read_text()
    assert re.search(r"export const CREATOR_PAYOUT_DAYS = 7;", payout)


@pytest.mark.parametrize("name", ["FeeFlow.jsx", "PayoutClock.jsx"])
def test_the_drawings_land_on_their_end_state_under_reduced_motion(name):
    code = re.sub(r"\s+", " ", _code(MKT / name))
    assert "useReducedMotion" in code
    assert "reduced ? { duration: 0 }" in code
    assert "scaleX: reduced || inView ? 1 : 0" in code


# ---------------------------------------------------------------------------
# 4 · Bands
# ---------------------------------------------------------------------------


def _grounds(page):
    """The page's sections, top to bottom, as the ground each sits on."""
    code = _code(PAGES[page])
    body = code[code.index("export default function") :]
    helpers = code[: code.index("export default function")]
    out = []
    tokens = re.finditer(
        r"<(Hero|WhoBuiltIt|CreatorDoor|MoneyBand) |<Band ground=\"(\w+)\"|<PhotoBand |<ProcessSpine |<AiSection |"
        r"<PromiseBand|<ComparisonBand[^>]*ground=\"([\w-]+)\"|<Closing\b([^>]*)>",
        body,
    )
    for t in tokens:
        if t.group(1):
            fn = helpers[helpers.index(f"function {t.group(1)}(") :]
            out.append(re.search(r'<Band ground="(\w+)"', fn).group(1))
        elif t.group(2):
            out.append(t.group(2))
        elif t.group(0).startswith("<PhotoBand"):
            out.append("photo")
        elif t.group(0).startswith("<ProcessSpine"):
            out.append(re.search(r'<Band ground="(\w+)"', (MKT / "ProcessSpine.jsx").read_text()).group(1))
        elif t.group(0).startswith("<AiSection"):
            out.append(re.search(r'<Band ground="(\w+)"', helpers[helpers.index("function AiSection(") :]).group(1))
        elif t.group(0).startswith("<PromiseBand"):
            out.append("navy")
        elif t.group(3):
            out.append({"bg-muted": "tint", "bg-background": "page"}[t.group(3)])
        else:
            m = re.search(r'ground="(\w+)"', t.group(4) or "")
            out.append(m.group(1) if m else "page")
    return out


@pytest.mark.parametrize("page,expected", [
    # How it works is the navy process spine, which the brief that built it
    # asked for by colour; the AI section (tint) sits between it and the
    # promise band. Navy three times on home is that brief's decision.
    ("home", ["page", "tint", "photo", "navy", "tint", "navy", "tint", "navy", "page"]),
    ("brands", ["page", "tint", "page", "tint", "photo", "navy", "page", "tint", "navy"]),
    ("creators", ["page", "tint", "navy", "page", "photo", "tint", "page", "navy"]),
])
def test_the_grounds_alternate_and_navy_is_at_most_twice(page, expected):
    grounds = _grounds(page)
    assert grounds == expected, grounds
    for a, b in zip(grounds, grounds[1:]):
        assert a != b, (page, grounds)
    assert grounds.count("navy") <= (3 if page == "home" else 2)
    if page == "home":
        # The tint between the spine and the promise band is the AI section,
        # which renders while any switch is on. Every switch off would put
        # two navy bands side by side: hold the dependency where it lives.
        switches = re.search(r"export const AI_FEATURES = \{(.*?)\};", (SRC / "content" / "marketing.js").read_text(), re.S)
        assert ": true" in switches.group(1), "the spine and the promise band would touch"


def test_the_bands_are_the_existing_tokens():
    """Light base unchanged: the page ground, the warm `--muted` already in
    the light set, and navy through the dark token set — no new colour."""
    parts = _code(MKT / "SiteParts.jsx")
    ground = re.search(r"export const GROUND = \{(.*?)\};", parts, flags=re.S).group(1)
    assert dict(re.findall(r'(\w+): "([\w-]+)"', ground)) == {
        "page": "bg-background", "tint": "bg-muted", "navy": "bg-background",
    }
    assert 'data-surface={ground === "navy" ? "dark" : undefined}' in parts


# ---------------------------------------------------------------------------
# Every section is measured
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("page", list(PAGES))
def test_every_section_reports_a_view_by_name(page):
    """`section_view` reads `data-track-section` off each outermost section.
    The restored ones carry it too: every `Band` passes `track`, the photo
    band and the problem band set their own, and the process spine goes
    through `Band` like any other section."""
    code = _code(PAGES[page])
    for m in re.finditer(r"<Band\b([^>]*)>", code):
        assert "track=" in m.group(1), (page, m.group(0))
    assert "<section" not in code, "a page section goes through Band"
    parts = _code(MKT / "SiteParts.jsx")
    assert "data-track-section={track}" in parts
    assert "data-track-section={`photo-${id}`}" in parts
    assert 'track="promises"' in parts and 'track="close"' in parts
    assert 'data-track-section="problem"' in _code(MKT / "ComparisonBand.jsx")
    spine = _code(MKT / "ProcessSpine.jsx")
    assert "<section" not in spine and 'track="how"' in spine


# ---------------------------------------------------------------------------
# 5 · Easier to understand
# ---------------------------------------------------------------------------


def test_every_step_shows_both_sides_of_the_deal():
    """Both sides of the deal, now as a switch: the brand's five steps and
    the creator's five, each a title and a line, behind one control."""
    spine = _content()["HOME"]["processSpine"]
    assert set(spine["steps"]) == {"brands", "creators"}
    for side, steps in spine["steps"].items():
        assert len(steps) == 5, side
        for step in steps:
            assert step["title"] and step["line"], (side, step["key"])
    code = _code(MKT / "ProcessSpine.jsx")
    assert 'role="tablist"' in code and "copy.steps[shown]" in code


def test_how_it_works_lands_on_the_homepage_section():
    assert dict(server.RETIRED_MARKETING_PATHS)["/how-it-works"] == "/#how-it-works"
    assert dict(server.RETIRED_MARKETING_PATHS)["/why-weare"] == "/for-brands"
    code = _code(PAGES["home"])
    assert 'id="how-it-works"' in code


# ---------------------------------------------------------------------------
# Reduced motion, everywhere
# ---------------------------------------------------------------------------


def test_reduced_motion_resolves_every_restored_piece():
    """Every one of these shows its final state: no auto-advance, no rise,
    no drawing bar, and the process spine full with every step at strength."""
    css = (SRC / "index.css").read_text()
    reduced = "\n".join(re.findall(r"@media \(prefers-reduced-motion: reduce\) \{(.*?)\n\}", css, flags=re.S))
    assert ".mkt-rise" in reduced
    assert '[style*="heroWipe"]' in reduced and '[style*="heroProgress"]' in reduced
    deck = _code(MKT / "HeroDeck.jsx")
    assert "if (!autoAdvances({ reduced, paused })) return undefined;" in deck
    assert "(prefers-reduced-motion: reduce)" in deck
    spine = _code(MKT / "ProcessSpine.jsx")
    assert 'const state = reduced ? "full"' in spine
    assert 'fill.style.transform = "scaleY(1)"' in spine
