"""The four-step hero, driven where it can be and read where it cannot.

The hero rotates the stage of the job — Offer, Agree, Deliver, Get paid — and
each step shows the product screen it happens on. The rules that would
regress quietly are behavioural, so they are **run**: `lib/heroDeck.js` is
pure, and these load it into node and drive the reducer the provider uses.

- the rail advances the slide;
- at most two slides are ever mounted, whatever sequence of rail presses,
  timer ticks and crossfade endings arrives;
- reduced motion never auto-advances, and never paints a second layer;
- the counter history writes itself the first time Agree is shown and never
  again;
- the `h1` is the same text on every step.

The rest — screens that are pure presentation, names that are invented,
assets nothing references — is read off the source, because that is where
it lives. What the screens *claim* is in `test_site_claims.py`.
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
DECK = (SRC / "components" / "marketing" / "HeroDeck.jsx").read_text()
SCREENS = (SRC / "components" / "marketing" / "heroScreens.jsx").read_text()
BAND = (SRC / "components" / "marketing" / "ComparisonBand.jsx").read_text()
MOCKS = (SRC / "components" / "marketing" / "siteMocks.jsx").read_text()
CONTENT = (SRC / "content" / "marketing.js").read_text()


def _code(src: str) -> str:
    src = re.sub(r"\{/\*.*?\*/\}", "", src, flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("//"))


def _content():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    done = subprocess.run(
        [node, "--input-type=module", "-e",
         CONTENT + "\nconsole.log(JSON.stringify({HOME, HERO_SCREENS}));"],
        capture_output=True, text=True, timeout=30,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


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
    trace.push({ active: s.active, leaving: s.leaving, painted: deck.painted(s), fresh: s.fresh });
  }
  out[name] = trace;
}
out.auto = {
  running: deck.autoAdvances({ reduced: false, paused: false }),
  reduced: deck.autoAdvances({ reduced: true, paused: false }),
  paused: deck.autoAdvances({ reduced: false, paused: true }),
};
out.hold = deck.HOLD_MS;
out.fade = deck.FADE_MS;
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


def _shape(s):
    return {k: s[k] for k in ("active", "leaving", "painted")}


def test_the_rail_advances_the_slide(tmp_path):
    out = _drive({
        "rail": [
            {"type": "go", "to": 2, "reduced": False},
            {"type": "settle"},
            {"type": "go", "to": 2, "reduced": False},  # pressing the active step
            {"type": "go", "to": 0, "reduced": False},
        ],
    }, tmp_path)
    t = [_shape(s) for s in out["rail"]]
    assert t[0] == {"active": 2, "leaving": 0, "painted": [0, 2]}
    assert t[1] == {"active": 2, "leaving": None, "painted": [2]}
    assert t[2] == t[1], "pressing the step already showing is a no-op, not a crossfade"
    assert t[3]["active"] == 0 and t[3]["painted"] == [2, 0]


def test_the_timer_advances_and_wraps_after_step_four(tmp_path):
    out = _drive({
        "timer": [{"type": "advance", "count": 4, "reduced": False}, {"type": "settle"}] * 5,
    }, tmp_path)
    actives = [s["active"] for s in out["timer"][::2]]
    assert actives == [1, 2, 3, 0, 1]
    assert out["hold"] == 7000 and out["fade"] == 600


def test_never_more_than_two_slides_are_mounted(tmp_path):
    """The two-layer budget, held under any order of rail presses, ticks and
    crossfade endings — including a press landing mid-fade, which is the case
    that would stack a third layer if `leaving` were a list rather than one
    slot."""
    import random

    rng = random.Random(20261022)
    actions = []
    for _ in range(600):
        kind = rng.choice(["go", "go", "advance", "settle"])
        if kind == "go":
            actions.append({"type": "go", "to": rng.randrange(4), "reduced": False})
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
            {"type": "go", "to": 3, "reduced": True},
            {"type": "go", "to": 1, "reduced": True},
        ],
    }, tmp_path)
    assert out["auto"] == {"running": True, "reduced": False, "paused": False}
    for s in out["reduced"]:
        assert s["leaving"] is None and len(s["painted"]) == 1
    assert [s["active"] for s in out["reduced"]] == [3, 1], "the rail still switches"


def test_the_counter_history_writes_itself_once(tmp_path):
    """The second of the site's three moments. Agree (step 02) is `fresh` the
    first time it is shown and never after — so the rows write themselves on
    the first lap and are simply there on every lap after it. Step 01 is seen
    at load, so it is never fresh."""
    out = _drive({
        "laps": [{"type": "advance", "count": 4, "reduced": False}, {"type": "settle"}] * 8,
    }, tmp_path)
    shown = out["laps"][::2]
    assert [s["active"] for s in shown] == [1, 2, 3, 0, 1, 2, 3, 0]
    assert [s["fresh"] for s in shown] == [1, 2, 3, None, None, None, None, None]
    stage = _code(DECK)[_code(DECK).index("export function DeckStage") :]
    assert "fresh={i === state.active && state.fresh === i}" in stage
    agree = _code(SCREENS)[_code(SCREENS).index("export function AgreeScreen") :]
    assert "<RowWriter rows={rows} written={write} animate={write} />" in agree


def test_the_stage_renders_exactly_what_painted_returns():
    """The driven rule only holds if the component renders through it: the
    stage maps `painted(state)`, never the whole step list."""
    stage = _code(DECK)[_code(DECK).index("export function DeckStage") :]
    stage = stage[: stage.index("export function StepRail")]
    assert "const mounted = painted(state);" in stage
    assert "mounted.map(" in stage and "steps.map(" not in stage
    assert "aria-hidden={active ? undefined : true}" in _code(DECK)


def test_the_h1_text_is_the_same_on_every_step():
    """The `h1` is the content module's two lines rendered outside the deck.
    Nothing the deck provides reaches it, the deck renders no heading of its
    own, and no step's line repeats it — so there is one heading on all four
    steps."""
    c = _content()
    title = " ".join(c["HOME"]["hero"]["titleLines"])
    assert title == "One place for the whole job"
    h1 = HOME[HOME.index("<h1") : HOME.index("</h1>")]
    assert "lines={hero.titleLines}" in h1
    assert "<h1" not in DECK and "<h1" not in SCREENS
    assert title not in [s["line"] for s in c["HOME"]["hero"]["steps"]]


# ---------------------------------------------------------------------------
# Read: what the source has to be
# ---------------------------------------------------------------------------


def test_every_screen_is_pure_presentation():
    """No state, no effects, no data, no context — which is what keeps a DOM
    screen as cheap to mount as a picture. The same holds for the audience
    pages' drawn UI."""
    for name, src in (("heroScreens", SCREENS), ("siteMocks", MOCKS)):
        code = _code(src)
        for banned in ("useState", "useEffect", "useLayoutEffect", "useReducer", "useContext",
                       "useRef", "useMemo", "useCallback", "useHeroDeck", "fetch(", "api.",
                       "@/lib/api", "<img"):
            assert banned not in code, (name, banned)
    code = _code(SCREENS)
    assert set(re.findall(r"^export function (\w+)", code, re.M)) >= {
        "OfferScreen", "AgreeScreen", "DeliverScreen", "GetPaidScreen",
    }
    keys = re.findall(r"^\s+(offer|agree|deliver|paid): \w+Screen,", code, re.M)
    assert keys == ["offer", "agree", "deliver", "paid"]


def test_the_screens_hold_no_copy_of_their_own():
    """Every word on a screen comes from `HERO_SCREENS`; the file is layout.
    A string literal rendered as text would be copy the content module
    cannot reach."""
    code = _code(SCREENS)
    jsx_text = re.findall(r">\s*([A-Za-z][^<>{}]{2,})\s*<", code)
    assert not jsx_text, jsx_text


def test_the_hero_and_the_band_use_no_image_and_name_no_colour():
    """No `<img>`, and tokens only — so this follows whichever surface it is
    on, light or the navy band."""
    palette = re.compile(
        r"\b(?:bg|text|border|ring|from|to|via|divide|fill|stroke|shadow|outline)-"
        r"(?:white|black|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|green|"
        r"emerald|teal|cyan|sky|blue|indigo|violet|purple|pink|rose|navy)(?:-\d{2,3})?\b"
    )
    literal = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(\s*\d")
    hero = HOME[HOME.index("function Hero()") : HOME.index("function Steps()")]
    for name, src in (("HeroDeck", DECK), ("heroScreens", SCREENS), ("ComparisonBand", BAND),
                      ("siteMocks", MOCKS), ("Hero()", hero)):
        code = _code(src)
        assert "<img" not in code and "PlaceholderImage" not in code, name
        assert not palette.search(code), (name, palette.search(code).group(0))
        assert not literal.search(code), (name, literal.search(code).group(0))


def test_no_real_brand_is_named_in_public_product_ui():
    """A real business in product UI on a public page reads as an
    endorsement from somebody who is not a customer. The demo seed is where
    real-sounding names live in this repo, so none of them may appear in the
    drawn UI or the copy — plus a handful of the market's best-known names.
    (The one section where a real client name is correct, "Who built it",
    reads `CLIENTS`, which ships empty.)"""
    seed = (ROOT / "backend" / "seed_demo.py").read_text()
    seeded = set(re.findall(r'"business": "([^"]+)"', seed))
    known = {"Toit", "Thirdwave", "Third Wave", "Starbucks", "Zomato", "Swiggy", "Nykaa",
             "Myntra", "Blue Tokai", "Chai Point", "Taj", "Oberoi", "Mamaearth", "boAt"}
    names = {n for n in seeded | known if len(n) > 2}
    assert seeded, "the seed's brand names could not be read"
    text = " ".join(_code(s) for s in (DECK, SCREENS, BAND, MOCKS, HOME, CONTENT))
    hits = sorted(n for n in names if re.search(rf"\b{re.escape(n)}\b", text))
    assert not hits, hits


def test_no_team_member_is_named_on_the_rebuilt_pages():
    """Nobody from WeAre Studios is named on the three pages or in the drawn
    UI. The two partners named on /contact were left as they are — the brief
    kept that page unchanged, and the PR raises the conflict."""
    from_site = (SRC / "lib" / "siteNav.js").read_text()
    people = re.findall(r'\{ name: "([^"]+)", role:', from_site)
    assert people, "the partner list could not be read"
    text = " ".join(_code(s) for s in (DECK, SCREENS, BAND, MOCKS, HOME, CONTENT))
    for page in ("Brands.jsx", "Creators.jsx"):
        text += _code((SRC / "pages" / page).read_text())
    for person in people:
        for part in person.split():
            assert not re.search(rf"\b{re.escape(part)}\b", text), person


def test_the_sector_images_are_gone_and_nothing_points_at_them():
    folder = ROOT / "frontend" / "public" / "img" / "marketing"
    sectors = ("fnb", "hospitality", "retail", "real-estate", "fashion", "travel",
               "wellness", "lifestyle")
    for s in sectors:
        assert not (folder / f"hero-{s}.svg").exists(), s
    for p in SRC.rglob("*"):
        if p.suffix in (".js", ".jsx", ".css"):
            assert "/img/marketing/hero-" not in p.read_text(), p
    # The other families are out of scope and still there.
    for kept in ("home-on-location.svg", "home-venue-wide.svg"):
        assert (folder / kept).exists(), kept


# ---------------------------------------------------------------------------
# The comparison band
# ---------------------------------------------------------------------------


def test_the_band_sits_directly_under_the_hero_and_stacks_today_first():
    page = _code(HOME)
    body = page[page.index("export default function Home") :]
    hero, band = body.index("<Hero />"), body.index("<ComparisonBand")
    between = body[hero + len("<Hero />") : band]
    assert hero < band and "<" not in between.strip(), "nothing sits between the hero and the band"
    assert _content()["HOME"]["swap"]["title"] == "A campaign is not a spreadsheet and sixty DMs"
    code = _code(BAND)
    assert code.index("<Spreadsheet") < code.index("<Board")
    assert "grid-cols-1" in code and "md:grid-cols-[1fr_auto_1fr]" in code


def test_the_band_does_not_cost_first_paint():
    code = _code(BAND)
    assert "[content-visibility:auto]" in code and "[contain-intrinsic-size:" in code
    for banned in ("useEffect", "useState", "fetch(", "api."):
        assert banned not in code, banned
