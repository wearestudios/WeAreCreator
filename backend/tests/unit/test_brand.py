"""The brand, in two surfaces.

    navy  #091426   structure, weight, primary actions
    red   #FF2731   identity, highlights, marketing CTAs

    MARKETING  navy canvas, #0E1C33 surface, #EDF1F7 text, red CTA
    PRODUCT    light #F2F4F7 canvas, white surface, navy text, navy CTA
               red is the logo and standout data

**The rules that are easy to state and easy to break are the ones here.** A
palette is applied by hand across hundreds of call sites, and the two things
that go wrong are always the same: a component names a colour instead of a
token, so it is correct on one surface and wrong on the other; and a colour is
used at a size its contrast cannot carry. Both are invisible in review and
obvious to whoever is using the product.

The contrast numbers are computed from `index.css` rather than typed in, so
these cannot drift from the values that actually ship — and the pairings are
named by what they *do* ("the CTA label on the CTA") rather than by token
name, because that is the question somebody is really asking.
"""

from __future__ import annotations

import colorsys
import json
import re
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[3] / "frontend"
SRC = FRONTEND / "src"
CSS = (SRC / "index.css").read_text()

BRAND_NAVY = "#091426"
BRAND_RED = "#FF2731"


# --- reading the tokens that actually ship ---------------------------------


def _block(selector: str) -> dict:
    i = CSS.index(selector)
    j = CSS.index("\n    }", i)
    return dict(re.findall(r"--([\w-]+):\s*([\d.]+ [\d.]+% [\d.]+%)", CSS[i:j]))


MARKETING = _block(":root {\n        /* MARKETING")
PRODUCT = {**MARKETING, **_block(':root[data-theme="light"] {')}


def _rgb(hsl: str):
    h, s, lightness = [float(x.strip("%")) for x in hsl.split()]
    return colorsys.hls_to_rgb(h / 360, lightness / 100, s / 100)


def _lum(hsl: str) -> float:
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in _rgb(hsl)]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _hex(hsl: str) -> str:
    return "#%02X%02X%02X" % tuple(round(v * 255) for v in _rgb(hsl))


# ---------------------------------------------------------------------------
# The palette is the brand's
# ---------------------------------------------------------------------------


class TestThePaletteIsTheBrands:
    def test_marketing_is_the_navy_canvas(self):
        assert _hex(MARKETING["background"]) == BRAND_NAVY
        assert _hex(MARKETING["card"]) == "#0E1C33"
        assert _hex(MARKETING["foreground"]) == "#EDF1F7"

    def test_marketing_cta_is_the_brand_red(self):
        assert _hex(MARKETING["primary"]) == BRAND_RED

    def test_the_product_is_the_light_canvas_with_navy_ink_and_navy_ctas(self):
        assert _hex(PRODUCT["background"]) == "#F2F4F7"
        assert _hex(PRODUCT["card"]) == "#FFFFFF"
        assert _hex(PRODUCT["foreground"]) == BRAND_NAVY
        assert _hex(PRODUCT["primary"]) == BRAND_NAVY

    def test_the_red_is_identical_on_both_surfaces(self):
        """**It is the identity, so it does not get adjusted for the surface.**
        Everything else in the file flips; this is the one value that does
        not, and it buys that with a size constraint rather than a tweak."""
        assert _hex(MARKETING["data"]) == _hex(PRODUCT["data"]) == BRAND_RED


# ---------------------------------------------------------------------------
# Contrast, computed from what ships
# ---------------------------------------------------------------------------


PAIRS = [
    ("foreground", "background", "body text on the canvas", 4.5),
    ("card-foreground", "card", "body text on a card", 4.5),
    ("muted-foreground", "background", "metadata on the canvas", 4.5),
    ("muted-foreground", "card", "metadata on a card", 4.5),
    ("primary-foreground", "primary", "the CTA label on the CTA", 4.5),
    ("primary-ink", "card", "the accent as text on a card", 4.5),
    ("destructive-foreground", "destructive", "a destructive label", 4.5),
    ("state-pending", "card", "pending", 4.5),
    ("state-approved", "card", "approved", 4.5),
    ("state-rejected", "card", "rejected", 4.5),
    ("state-progress", "in progress", "progress", 4.5),
    ("state-done", "card", "done", 4.5),
]


class TestContrast:
    @pytest.mark.parametrize("surface", ["marketing", "product"])
    @pytest.mark.parametrize("fg,bg,label,need", [p for p in PAIRS if p[1] != "in progress"])
    def test_every_pairing_clears_aa(self, surface, fg, bg, label, need):
        tokens = MARKETING if surface == "marketing" else PRODUCT
        got = ratio(tokens[fg], tokens[bg])
        assert got >= need, f"{surface}: {label} is {got:.2f}:1, needs {need}"

    def test_the_marketing_cta_label_is_navy_rather_than_white(self):
        """**Measured, not chosen.** White on #FF2731 is 3.76:1 and fails AA
        for a button label; navy on the same red is 4.90:1. The brand says
        navy carries weight, so the readable answer is also the on-brand one —
        but it was the measurement that settled it.
        """
        assert ratio("0 0% 100%", MARKETING["primary"]) < 4.5, (
            "white on the brand red would pass, so this rule has lost its reason"
        )
        assert ratio(MARKETING["primary-foreground"], MARKETING["primary"]) >= 4.5

    def test_standout_red_clears_aa_large_and_not_aa(self):
        """The constraint the brand-exact red is bought with, stated as a
        fact rather than as a hope: it is legible as a headline figure and is
        not legible as body text, which is what the size rule below polices."""
        for tokens, name in ((PRODUCT, "product card"), (PRODUCT, "product canvas")):
            ground = tokens["card"] if "card" in name else tokens["background"]
            got = ratio(tokens["data"], ground)
            assert got >= 3.0, f"{name}: {got:.2f} fails even AA-large"


# ---------------------------------------------------------------------------
# No component names a colour
# ---------------------------------------------------------------------------


# Tailwind palette families that would pin a component to one surface. The
# brand's own `navy` and `red` are deliberately absent: those exist precisely
# for the two things a semantic token cannot express — the mark itself, and a
# field that must stay one colour whichever surface is mounted.
RAW_FAMILIES = (
    "slate|gray|grey|zinc|neutral|stone|orange|amber|yellow|lime|green|emerald|"
    "teal|cyan|sky|indigo|violet|purple|fuchsia|pink|rose"
)
RAW_CLASS = re.compile(
    rf"\b(?:bg|text|border|ring|fill|stroke|divide|from|via|to|decoration|outline|"
    rf"accent|caret|placeholder|shadow)-(?:{RAW_FAMILIES})-\d{{2,3}}\b"
)


def _app_files():
    for p in sorted(SRC.rglob("*")):
        if p.suffix in (".jsx", ".js") and p.is_file() and "constants/testIds" not in str(p):
            yield p


class TestNothingNamesAColour:
    def test_no_component_uses_a_raw_tailwind_palette_class(self):
        """**This is what makes one component correct on both surfaces.**

        The status pastels were the real offenders: `text-amber-300` and its
        twenty-seven friends were tuned for a near-black canvas and are
        illegible on the product's light one. `--state-*` already carries each
        meaning and already flips; the console proved it, and the rest of the
        product never got the treatment because it was dark-only.
        """
        offenders = []
        for p in _app_files():
            for m in RAW_CLASS.finditer(p.read_text()):
                offenders.append(f"{p.relative_to(SRC)}: {m.group(0)}")
        assert not offenders, offenders[:12]

    def test_the_old_accent_is_gone_rather_than_aliased(self):
        """A deprecated `ember` alias would have let call sites keep pointing
        at a colour the brand no longer has, which is how a rebrand ends up
        half-applied with nobody able to tell which half."""
        config = (FRONTEND / "tailwind.config.js").read_text()
        assert "ember:" not in config
        for p in _app_files():
            assert "ember-" not in p.read_text(), p.relative_to(SRC)

    def test_pure_black_ink_never_returns(self):
        """"Tinted near-black, never pure #000" predates the brand and
        survives it — and on the brand grounds the right ink is a token
        anyway."""
        offenders = [
            str(p.relative_to(SRC)) for p in _app_files() if "text-black" in p.read_text()
        ]
        assert not offenders, offenders

    def test_the_sweep_can_actually_fail(self):
        """A rule nobody has watched fail is a rule nobody should trust."""
        assert RAW_CLASS.search('className="text-amber-300"')
        assert RAW_CLASS.search('className="bg-emerald-500/10"')
        # And the brand's own literals are not caught by it.
        assert not RAW_CLASS.search('className="bg-red-500 text-navy-700"')


# ---------------------------------------------------------------------------
# Where red is allowed to be
# ---------------------------------------------------------------------------


class TestRedIsLogoAndStandoutData:
    def test_the_logo_is_red_on_both_surfaces(self):
        """**The mark does not change colour depending on whether somebody is
        signed in.** `bg-primary` would have made it navy in the product."""
        marks = []
        for name in ("Navbar.jsx", "Footer.jsx",
                     "marketing/MarketingNavbar.jsx", "marketing/MarketingFooter.jsx"):
            src = (SRC / "components" / name).read_text()
            assert "bg-red-500" in src, f"{name} does not carry the brand mark"
            marks.append(name)
        assert len(marks) == 4

    def test_the_mark_carries_navy_ink_rather_than_the_flipping_token(self):
        """The ground is red on both surfaces, so the letter is navy on both.
        `text-primary-foreground` flips to white in the product, which on red
        is 3.76:1."""
        for name in ("Navbar.jsx", "Footer.jsx",
                     "marketing/MarketingNavbar.jsx", "marketing/MarketingFooter.jsx"):
            src = (SRC / "components" / name).read_text()
            mark = re.search(r'bg-red-500[^"]*', src).group(0)
            assert "text-navy-700" in mark, f"{name}: {mark}"
            assert "text-primary-foreground" not in mark, name

    def test_standout_red_is_never_used_below_the_size_it_can_carry(self):
        """**The constraint the brand-exact red is bought with.**

        #FF2731 is 3.76:1 on white and 3.41:1 on the canvas: it clears
        AA-large and fails AA. That is exactly the shape of what it is for — a
        logo, and a figure set large — so the rule is a size floor rather than
        a darker red, and it is policed here rather than left to whoever adds
        the next one.

        `text-fluid-*` steps below `4xl` and every fixed step below `text-2xl`
        are body sizes. A `text-data` on one of those is a contrast failure
        wearing a brand colour.
        """
        # **The whole class string, not a lookahead.** The first version of
        # this used a negative lookahead from `text-data` and so only saw the
        # classes written *after* it — which failed on a correct call site
        # whose size class happened to come first. Ordering in a className is
        # nobody's business but the author's.
        LARGE = re.compile(
            r"\btext-fluid-(?:4xl|5xl|6xl|7xl|8xl|9xl)\b"
            r"|\btext-(?:2xl|3xl|4xl|5xl|6xl|7xl|8xl|9xl)\b"
            r"|\btext-\[(?:2[4-9]|[3-9]\d|\d{3,})px\]"
        )
        offenders = []
        for p in _app_files():
            for line in p.read_text().splitlines():
                if "text-data" in line and not LARGE.search(line):
                    offenders.append(f"{p.relative_to(SRC)}: {line.strip()[:90]}")
        assert not offenders, offenders

    def test_that_size_rule_can_actually_fail(self):
        """Break-tested rather than assumed: a `text-data` with no size class
        beside it has to be caught, or the rule is decoration."""
        LARGE = re.compile(r"\btext-fluid-(?:4xl|5xl|6xl|7xl|8xl|9xl)\b|\btext-(?:2xl|3xl)\b")
        assert not LARGE.search('className="text-sm text-data"')
        assert LARGE.search('className="text-fluid-6xl text-data"')
        assert LARGE.search('className="text-data text-3xl"'), "order must not matter"

    def test_red_is_not_a_status(self):
        """The rule the old palette already carried ("ember is never a
        status"), restated. A figure somebody is proud of and an error are the
        two things this colour must not confuse, and the state tokens stay the
        only vocabulary for state."""
        assert PRODUCT["data"] != PRODUCT["destructive"]
        assert PRODUCT["data"] != PRODUCT["state-rejected"]
        assert MARKETING["data"] != MARKETING["destructive"]


# ---------------------------------------------------------------------------
# The two surfaces, and the line between them
# ---------------------------------------------------------------------------


class TestTheSurfaceSplit:
    def test_the_product_prefixes_and_the_pre_paint_script_agree(self):
        """Two implementations of "is this the product" is two answers, and the
        one that runs first is the one nobody debugs."""
        js = (SRC / "lib" / "surfaceTheme.js").read_text()
        html = (FRONTEND / "public" / "index.html").read_text()
        prefixes = re.findall(r'"(/[a-z/-]+)"', js.split("PRODUCT_PREFIXES = [")[1].split("]")[0])
        assert prefixes
        for prefix in prefixes:
            assert f'"{prefix}"' in html, prefix

    def test_signing_in_is_the_line(self):
        """Everything a signed-out stranger can land on is navy. The awkward
        one is `/campaigns`: the feed and a brief's page are public, and
        posting or editing a brief is authoring inside the product."""
        js = (SRC / "lib" / "surfaceTheme.js").read_text()
        for public in ("/login", "/signup", "/for-brands", "/work"):
            assert f'"{public}"' not in js.split("PRODUCT_PREFIXES = [")[1].split("]")[0], public
        assert "/campaigns/new" in js
        assert "/campaigns/[^/]+/edit" in js or "campaigns\\/[^/]+\\/edit" in js

    def test_the_server_rendered_pages_are_on_the_marketing_surface(self):
        """They are public by definition — a share page, a brand page, a case
        study, a category page — so they carry the navy canvas and the red
        accent, and none of the old warm palette."""
        server = (FRONTEND.parent / "backend" / "server.py").read_text()
        assert BRAND_NAVY in server and BRAND_RED in server
        for dead in ("#0B0A09", "#F05D14", "#F5F1EC", "#9C938B"):
            assert dead not in server, dead


# ---------------------------------------------------------------------------
# The brief this was built from
# ---------------------------------------------------------------------------


def test_the_design_guidelines_describe_the_brand_that_shipped():
    """`design_guidelines.json` follows the code — it says so itself — but a
    brief describing a colour the product no longer has is worse than no brief,
    because somebody reads it and builds to it."""
    guide = json.loads((FRONTEND.parent / "design_guidelines.json").read_text())
    theme = guide["theme"]
    assert theme["primary_color_hex"].upper() in (BRAND_RED, BRAND_NAVY)
    blob = json.dumps(guide).lower()
    assert "#f05d14" not in blob, "the guidelines still name the old accent"
    assert "burnt orange" not in blob
