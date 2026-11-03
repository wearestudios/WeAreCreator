"""The homepage hero slider, driven where it can be and read where it cannot.

The hero is one slider: the deal (the page's only `h1`), the problem, the
shoot and — while any AI switch is on — what the AI does. **It runs on the
old hero deck's engine, generalised rather than written twice**, so the rules
that would regress quietly are behavioural and are **run**: `lib/heroDeck.js`
is pure, and these load it into node and drive the reducer the slider uses.

- a tab advances the slide, and choosing one stops the clock for good;
- at most two slides are ever painted, whatever sequence of tab presses,
  timer ticks and crossfade endings arrives;
- reduced motion never auto-advances, and never paints a second layer;
- each slide dwells 7000ms, the old slider's hold, on one timer;
- the arrow keys wrap at both ends.

The rest — visuals that are pure presentation, names that are invented,
claims the product actually makes, a chunk that keeps them off the first
paint — is read off the source, because that is where it lives.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import server

ROOT = Path(server.__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "src"
HOME = (SRC / "pages" / "Home.jsx").read_text()
CONTENT = (SRC / "content" / "marketing.js").read_text()
DECK = (SRC / "components" / "marketing" / "HeroSlider.jsx").read_text()
SCREENS = (SRC / "components" / "marketing" / "heroSlides.jsx").read_text()
MOCKS = (SRC / "components" / "marketing" / "siteMocks.jsx").read_text()


def _code(src: str) -> str:
    src = re.sub(r"\{/\*.*?\*/\}", "", src, flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("//"))


# ---------------------------------------------------------------------------
# Driven: the deck's state machine, in node
# ---------------------------------------------------------------------------

_HARNESS = r"""
import * as deck from "./heroDeck.mjs";
const script = JSON.parse(process.argv[2]);
const out = {};
for (const [name, steps] of Object.entries(script)) {
  let s = deck.INITIAL;
  const trace = [];
  for (const a of steps) {
    s = deck.deckReducer(s, a);
    trace.push({ active: s.active, leaving: s.leaving, stopped: s.stopped, painted: deck.painted(s) });
  }
  out[name] = trace;
}
out.auto = {
  running: deck.autoAdvances({ reduced: false, paused: false }),
  reduced: deck.autoAdvances({ reduced: true, paused: false }),
  paused: deck.autoAdvances({ reduced: false, paused: true }),
  stopped: deck.autoAdvances({ reduced: false, paused: false, stopped: true }),
};
out.keys = ["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp", "Home", "End", "a"].map(
  (k) => [deck.stepFrom(0, k, 4), deck.stepFrom(3, k, 4)]
);
out.hold = deck.HOLD_MS;
out.swap = deck.SWAP_MS;
console.log(JSON.stringify(out));
"""


def _drive(script, tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    (tmp_path / "heroDeck.mjs").write_text((SRC / "lib" / "heroDeck.js").read_text())
    (tmp_path / "harness.mjs").write_text(_HARNESS)
    done = subprocess.run(
        [node, str(tmp_path / "harness.mjs"), json.dumps(script)],
        capture_output=True, text=True, timeout=30,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def _view(trace):
    return [{k: t[k] for k in ("active", "leaving", "painted")} for t in trace]


def test_a_tab_advances_the_slide_and_stops_the_clock(tmp_path):
    out = _drive({
        "tabs": [
            {"type": "go", "to": 2, "reduced": False, "chosen": True},
            {"type": "settle"},
            {"type": "go", "to": 2, "reduced": False, "chosen": True},  # the active tab
            {"type": "advance", "count": 4, "reduced": False},  # the timer, after a choice
            {"type": "go", "to": 0, "reduced": False, "chosen": True},
        ],
    }, tmp_path)
    t = out["tabs"]
    assert _view(t)[0] == {"active": 2, "leaving": 0, "painted": [0, 2]}
    assert _view(t)[1] == {"active": 2, "leaving": None, "painted": [2]}
    assert t[2] == t[1], "choosing the slide already showing is a no-op, not a crossfade"
    assert t[3] == t[2], "once somebody has chosen, the timer never moves the slide again"
    assert all(s["stopped"] for s in t)
    assert t[4]["active"] == 0 and t[4]["painted"] == [2, 0]
    assert out["auto"]["stopped"] is False


def test_the_timer_advances_and_wraps_and_never_stops_itself(tmp_path):
    out = _drive({
        "timer": [{"type": "advance", "count": 4, "reduced": False}, {"type": "settle"}] * 5,
        "three": [{"type": "advance", "count": 3, "reduced": False}, {"type": "settle"}] * 4,
    }, tmp_path)
    assert [s["active"] for s in out["timer"][::2]] == [1, 2, 3, 0, 1]
    assert not any(s["stopped"] for s in out["timer"])
    # With every AI switch off there are three slides, and the clock wraps
    # at three.
    assert [s["active"] for s in out["three"][::2]] == [1, 2, 0, 1]


def test_never_more_than_two_slides_are_painted(tmp_path):
    """The two-layer budget the old slider earned, held under any order of
    tab presses, ticks and crossfade endings — including a press landing
    mid-crossfade, which is the case that would stack a third layer if
    `leaving` were a list rather than one slot."""
    import random

    rng = random.Random(20261103)
    actions = []
    for _ in range(600):
        kind = rng.choice(["go", "go", "advance", "advance", "settle"])
        if kind == "go":
            actions.append({"type": "go", "to": rng.randrange(4), "reduced": False, "chosen": rng.random() < 0.1})
        elif kind == "advance":
            actions.append({"type": "advance", "count": 4, "reduced": False})
        else:
            actions.append({"type": "settle"})
    out = _drive({"random": actions}, tmp_path)
    for s in out["random"]:
        assert 1 <= len(s["painted"]) <= 2, s
        assert s["painted"][-1] == s["active"], "the incoming slide paints last"
    assert max(len(s["painted"]) for s in out["random"]) == 2


def test_reduced_motion_never_auto_advances_and_never_paints_two(tmp_path):
    out = _drive({
        "reduced": [
            {"type": "go", "to": 3, "reduced": True, "chosen": True},
            {"type": "go", "to": 1, "reduced": True, "chosen": True},
        ],
    }, tmp_path)
    assert out["auto"] == {"running": True, "reduced": False, "paused": False, "stopped": False}
    for s in out["reduced"]:
        assert s["leaving"] is None and len(s["painted"]) == 1
    assert [s["active"] for s in out["reduced"]] == [3, 1], "the tabs still switch"


def test_the_arrow_keys_wrap_at_both_ends(tmp_path):
    keys = _drive({}, tmp_path)["keys"]
    assert keys == [[1, 0], [3, 2], [1, 0], [3, 2], [0, 0], [3, 3], [None, None]]


def test_each_slide_dwells_seven_seconds_on_one_timer(tmp_path):
    """The old slider's 7000ms hold, and one `setTimeout` chain off it — no
    interval, and nothing else in the hero owning a clock. Hovering or
    focusing anywhere in the slider pauses it; the crossfade is 400ms."""
    out = _drive({}, tmp_path)
    assert out["hold"] == 7000 and out["swap"] == 400
    code = _code(DECK)
    assert code.count("setTimeout(") == 2, "the hold, and the crossfade's one-shot unmount"
    assert "setInterval" not in code and "requestAnimationFrame" not in code
    for event in ("pointerenter", "pointerleave", "focusin", "focusout"):
        assert f'addEventListener("{event}"' in code, event
    assert "autoAdvances({ reduced, paused, stopped: state.stopped })" in code
    home = _code(HOME)
    assert "setTimeout" not in home and "setInterval" not in home


def test_a_choice_is_a_tab_click_or_an_arrow_key():
    code = _code(DECK)
    assert 'dispatch({ type: "go", to, reduced, chosen: true })' in code
    assert "onClick={() => choose(i)}" in code
    assert "onKeyDown={onKeyDown}" in code and "stepFrom(state.active, e.key, count)" in code


def test_the_stage_paints_exactly_what_painted_returns():
    """The driven rule only holds if the component renders through it: a
    visual is mounted only for a slide in `painted(state)`, and the words of
    every other slide are laid out but `invisible` — they hold the stage at
    the tallest slide's height and never paint."""
    code = _code(DECK)
    assert "const mounted = painted(state);" in code
    assert "const shown = mounted.includes(i);" in code
    assert "{shown ? (" in code and '${\n                                        shown ? "" : "invisible"' in DECK
    assert "aria-hidden={active ? undefined : true}" in code
    assert "inert={active ? undefined : true}" in code


def test_the_carousel_is_announced_as_one():
    code = _code(DECK)
    assert 'aria-roledescription="carousel"' in code
    assert 'aria-roledescription="slide"' in code
    assert "aria-label={`${i + 1} of ${count}`}" in code
    assert 'role="tablist"' in code and 'role="tab"' in code and "aria-selected={on}" in code


def test_the_h1_is_slide_a_and_nowhere_else():
    """One heading per page at the top level, and it is the content module's
    title in slide A — the deal. The other slides are h2s at the same size."""
    title = re.search(r'title: "(Creator campaigns, minus the chasing\.)"', CONTENT).group(1)
    code = _code(DECK)
    assert code.count("<h1") == 1 and "<h1" not in SCREENS and "<h1" not in HOME
    deal = code[code.index('case "deal":') : code.index('case "problem":')]
    assert "<HeroTitle title={hero.title} accent={hero.accent} />" in deal
    assert code.count('<h2 className={H2}>') == 3
    assert 'const H2 = "mkt-display text-heading";' in code
    assert title in CONTENT


def test_the_ctas_and_the_note_never_change_per_slide():
    code = _code(DECK)
    stage_end = code.index("{/* The asks and the tabs.") if "{/* The asks" in code else code.index("<Cta ask={ASK.postBrief}")
    assert code.index("<Cta ask={ASK.postBrief}") > code.index("list.map((slide, i) => {")
    # The asks are rendered once, outside the per-slide map.
    assert code.count("<Cta ask={ASK.postBrief}") == 1 and code.count("<Cta ask={ASK.talkWhatsapp}") == 1
    assert code.count("{hero.note}") == 1
    assert stage_end


def test_slides_b_to_d_are_their_own_chunk_after_first_paint():
    code = _code(DECK)
    assert 'import(/* webpackChunkName: "hero-slides" */ "@/components/marketing/heroSlides")' in DECK
    assert code.count("heroSlides") == 1, "the chunk's one import, and no static one"
    # Slide A's card is in the page, because it is on screen at first paint.
    assert "<DealCard" in code and "export function DealCard" in MOCKS
    # Asked for when the page is idle — after the h1 has painted, never on a
    # timer. A bare effect started the request before the LCP was recorded
    # and cost the h1 157ms in Lighthouse's median.
    assert "window.requestIdleCallback(fetchSlides, { timeout: 4000 })" in code
    assert 'window.addEventListener("load", fetchSlides, { once: true })' in code
    assert "<Suspense fallback={<EmptyFrame />}>" in code


# ---------------------------------------------------------------------------
# Read: what the source has to be
# ---------------------------------------------------------------------------


def test_every_visual_is_pure_presentation():
    """No state, no effects, no data, no context — which is what keeps a DOM
    visual as cheap to mount as the image it replaced."""
    code = _code(SCREENS)
    for banned in ("useState", "useEffect", "useLayoutEffect", "useReducer", "useContext",
                   "useRef", "useMemo", "useCallback", "fetch(", "api.", "@/lib/api", "<img"):
        assert banned not in code, banned
    assert set(re.findall(r"^export function (\w+)", code, re.M)) >= {
        "ProblemVisual", "OnLocationVisual", "AiVisual",
    }
    keys = re.findall(r"^\s+(problem|onLocation|ai): \w+Visual,", code, re.M)
    assert keys == ["problem", "onLocation", "ai"]


def test_every_drawn_card_says_it_is_an_example():
    content = CONTENT
    for block in ("    card: {", "    swap: {", "    slides: {", "    ai: {"):
        part = content[content.index(block) :]
        assert 'tag: "Example"' in part[: part.index("\n    },\n")], block
    code = _code(SCREENS)
    assert code.count("<ExampleTag>") + code.count("tag={") >= 3


def test_every_visual_has_a_compact_variant_at_phone_width():
    """Not the desktop card scaled down: rows and padding drop below `sm`,
    and nothing on a phone is set under 12px."""
    code = _code(SCREENS) + _code(MOCKS[MOCKS.index("export function DealCard") : MOCKS.index("/** Scored applicants")])
    assert code.count("max-sm:hidden") >= 4
    assert "hidden sm:block" in code
    sizes = re.findall(r"text-\[(\d*\.?\d+)rem\]", code)
    assert sizes and min(float(x) for x in sizes) * 16 >= 12, sizes


def test_the_hero_uses_no_image_of_its_own_and_names_no_colour():
    """No `<img>` except the photo slot's, and tokens only — so this inherits
    whichever theme is live."""
    palette = re.compile(
        r"\b(?:bg|text|border|ring|from|to|via|divide|fill|stroke|shadow|outline)-"
        r"(?:white|black|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|green|"
        r"emerald|teal|cyan|sky|blue|indigo|violet|purple|pink|rose|navy)(?:-\d{2,3})?\b"
    )
    literal = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(\s*\d")
    for name, src in (("HeroSlider", DECK), ("heroSlides", SCREENS), ("Home", HOME)):
        code = _code(src)
        assert "<img" not in code and "PlaceholderImage" not in code, name
        assert not palette.search(code), (name, palette.search(code).group(0))
        assert not literal.search(code), (name, literal.search(code).group(0))
    assert "<PhotoSlot id={slide.slot} fill bare />" in _code(SCREENS)


def test_no_real_brand_is_named_in_public_product_ui():
    """A real business in product UI on a public page reads as an
    endorsement from somebody who is not a customer. The demo seed is where
    real-sounding names live in this repo, so none of them may appear here —
    plus a handful of the market's best-known names."""
    seed = (ROOT / "backend" / "seed_demo.py").read_text()
    seeded = set(re.findall(r'"business": "([^"]+)"', seed))
    known = {"Toit", "Thirdwave", "Third Wave", "Starbucks", "Zomato", "Swiggy", "Nykaa",
             "Myntra", "Blue Tokai", "Chai Point", "Taj", "Oberoi", "Mamaearth", "boAt"}
    names = {n for n in seeded | known if len(n) > 2}
    assert seeded, "the seed's brand names could not be read"
    text = " ".join(_code(s) for s in (DECK, SCREENS, MOCKS, HOME, CONTENT))
    hits = sorted(n for n in names if re.search(rf"\b{re.escape(n)}\b", text))
    assert not hits, hits


def test_the_sector_images_are_gone_and_nothing_points_at_them():
    folder = ROOT / "frontend" / "public" / "img" / "marketing"
    sectors = ("fnb", "hospitality", "retail", "real-estate", "fashion", "travel",
               "wellness", "lifestyle")
    for s in sectors:
        assert not (folder / f"hero-{s}.svg").exists(), s
    for p in SRC.rglob("*"):
        if p.suffix in (".js", ".jsx", ".css"):
            assert "/img/marketing/hero-" not in p.read_text(), p
    # Slide C's drawing is still served.
    assert (folder / "home-on-location.svg").exists()


def test_the_retired_deck_and_the_bands_it_replaced_are_gone():
    marketing = SRC / "components" / "marketing"
    for gone in ("HeroDeck.jsx", "heroScreens.jsx", "ComparisonBand.jsx", "BeforeAfterStrip.jsx"):
        assert not (marketing / gone).exists(), gone
    for p in SRC.rglob("*.js*"):
        text = p.read_text()
        for name in ("HeroDeck", "heroScreens", "ComparisonBand", "BeforeAfterStrip", "StepRail", "DeckStage"):
            assert name not in text, (p, name)
    assert "    deck: {" not in CONTENT


# ---------------------------------------------------------------------------
# The claims, checked against the product rather than trusted
# ---------------------------------------------------------------------------


def _slide_copy():
    """Every string the slides draw, from the content module."""
    parts = []
    for block, end in (("    card: {", "    swap: {"), ("    swap: {", "    processSpine: {"), ("    ai: {", "\n};")):
        chunk = CONTENT[CONTENT.index(block) :]
        parts.append(chunk[: chunk.index(end)])
    return " ".join(re.findall(r'"([^"]*)"', " ".join(parts)))


def test_the_slides_claim_only_what_the_product_does():
    """The fee is agreed before the shoot is booked — on every ladder; the
    terms are frozen at acceptance; nothing is held before a shoot, because
    no payment is raised until after approval; and the AI never prices,
    approves or pays."""
    text = _slide_copy().lower()
    assert "held before" not in text and "escrow" not in text
    for ladder in (server.COLLAB_STATE_ORDER,):
        assert ladder.index("commercial_agreed") < ladder.index("slot_booked")
    assert "fee agreed before the shoot" in text
    assert "frozen at acceptance" in text
    assert "fees, approvals and payments stay with people" in text


def test_the_ai_slide_shows_no_percentage():
    """The scorer's number ranks a shortlist; it is not a figure a brand is
    shown, so slide D carries no percentage anywhere — not in the copy and
    not drawn by the visual."""
    chunk = CONTENT[CONTENT.index("    ai: {") :]
    chunk = chunk[: chunk.index("\n};")]
    assert "%" not in chunk
    visual = _code(SCREENS)
    visual = visual[visual.index("const EXAMPLES") : visual.index("export const VISUALS")]
    assert "%" not in re.sub(r"\[[^\]]*%[^\]]*\]", "", visual)


# ---------------------------------------------------------------------------
# The field behind the hero, and the footer without its wordmark
# ---------------------------------------------------------------------------

FIELD = (SRC / "components" / "marketing" / "HeroField.jsx").read_text()
CSS = (SRC / "index.css").read_text()
FOOTER = (SRC / "components" / "marketing" / "MarketingFooter.jsx").read_text()
BEAM = (SRC / "components" / "ui" / "beam-wordmark-footer.jsx").read_text()


def _field_css() -> str:
    start = CSS.index("The hero's field (`components/marketing/HeroField.jsx`)")
    return CSS[start : CSS.index("The rail sliding left by one thumbnail")]


def test_the_field_is_mounted_behind_the_slider_and_out_of_the_way():
    """Inside the hero band, first, under content raised above it; decorative
    and click-through. The slider keeps its one timer and no frame loop of its
    own — the field's loop lives in the field's file."""
    code = _code(DECK)
    assert "<HeroField testid={IDS.field} />" in code
    assert code.index("<HeroField") < code.index("<Wrap")
    assert 'className="relative isolate overflow-hidden"' in code
    assert 'className="relative z-10 ' in code
    assert "requestAnimationFrame" not in code
    field = _code(FIELD)
    assert 'aria-hidden="true"' in field
    css = _field_css()
    rule = css[css.index(".hero-field {") : css.index("}", css.index(".hero-field {"))]
    assert "pointer-events: none" in rule and "position: absolute" in rule


def test_the_field_loop_is_one_loop_gated_on_view_and_visibility():
    """One `requestAnimationFrame` scheduler, started and stopped by an
    IntersectionObserver and `visibilitychange`; reduced motion stops it and
    writes nothing; only a mouse pulls the light; the rect is read in one
    function, off a stale flag set by a ResizeObserver and a passive scroll,
    never in a pointer handler."""
    code = _code(FIELD)
    assert code.count("requestAnimationFrame(tick)") == 2
    assert "setInterval" not in code and "setTimeout" not in code
    assert "new IntersectionObserver" in code and '"visibilitychange"' in code
    assert "new ResizeObserver(onScroll)" in code
    assert 'window.addEventListener("scroll", onScroll, { passive: true })' in code
    assert code.count("getBoundingClientRect") == 1
    assert "if (stale) read();" in code
    on_pointer = code[code.index("const onPointer") : code.index("const onScroll")]
    assert 'e.pointerType !== "mouse"' in on_pointer and "getBoundingClientRect" not in on_pointer
    sync = code[code.index("const sync") : code.index("const onPointer")]
    assert sync.index("if (reduced)") < sync.index("requestAnimationFrame")
    # Each frame: two custom properties on one layer, one transform on another.
    tick = code[code.index("const tick") : code.index("const stop")]
    assert tick.count("lit.style.setProperty(") == 2 and tick.count("glow.style.transform") == 1
    assert "FOLLOW_K = 0.12" in code


def test_the_field_paints_in_tokens_and_drifts_by_transform():
    css = _field_css()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bblack\b|\bwhite\b", css)
    colours = re.findall(r"color-mix\(in srgb, hsl\(var\(--([\w-]+)\)\)", css)
    assert set(colours) == {"brand-navy", "brand-red"}, colours
    assert "background-size: 24px 24px" in css
    assert "--lit: 260px" in css and "--lit: 180px" in css
    assert "width: 560px" in css
    assert "heroFieldDriftA 22s" in css and "heroFieldDriftB 26s" in css
    assert css.count("infinite alternate") == 2
    for frames in re.findall(r"@keyframes heroFieldDrift\w \{(.*?)\n\}", css, flags=re.S):
        props = set(re.findall(r"\{\s*([\w-]+):", frames))
        assert props == {"transform"}, props
    reduced = css[css.index("@media (prefers-reduced-motion: reduce)") :]
    assert ".hero-field-drift { animation: none;" in reduced
    # At rest with no script: 70% across, 30% down, for the lit dots and the glow.
    assert "--mx: 70%;" in css and "--my: 30%;" in css
    assert "left: 70%;" in css and "top: 30%;" in css


def test_the_marketing_footer_has_no_wordmark_and_measures_nothing():
    footer = _code(FOOTER)
    assert "word=" not in footer and "wordLabel" not in footer and "wordClassName" not in footer
    beam = _code(BEAM)
    fit = beam[beam.index("React.useLayoutEffect(") :]
    assert fit.index("if (!text) return undefined;") < fit.index("new ResizeObserver")
    assert fit.index("if (!text) return undefined;") < fit.index("document.fonts")
    assert '{text ? (\n                <div className="bwf-word-wrap">' in BEAM
    assert ".bwf[data-word='false'] .bwf-inner{padding-bottom:" in BEAM
