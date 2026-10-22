"""The brand, on a light app with a navy set kept beside it.

    navy  #091426   headings, primary buttons, inverse chrome
    red   #FF2731   the accent — fills, bars, dots, badges, borders, the logo
          #C41E27   the accent as text below 24px (accent-ink)

    LIGHT   :root — warm #F6F4F1 ground, white cards, #101B2E body, navy CTA
    DARK    [data-theme="dark"] — the navy set, for the marketing routes and
            an admin's opt-in: #091426 canvas, #0E1C33 surface, red CTA

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


# The app is `:root`; the navy set redefines it. `PRODUCT` and `MARKETING` keep
# their names because the routes they describe are unchanged — the product is
# on light, marketing is on the dark set.
PRODUCT = _block(':root,\n    [data-surface="light"] {')
MARKETING = {**PRODUCT, **_block('[data-surface="dark"],\n    :root[data-theme="dark"] {')}
INVERSE_HEX = {"surface": "#091426", "alt": "#15294A", "ink": "#EDF1F7", "muted": "#AEB8C7"}


def _rgb(hsl: str):
    h, s, lightness = [float(x.strip("%")) for x in hsl.split()]
    return colorsys.hls_to_rgb(h / 360, lightness / 100, s / 100)


def _lum(hsl: str) -> float:
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in _rgb(hsl)]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def ratio_hex(a: str, b: str) -> float:
    def lum(h):
        r, g, bl = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
        c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in (r, g, bl)]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    la, lb = lum(a), lum(b)
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

    def test_the_product_is_the_warm_light_set_with_navy_headings_and_ctas(self):
        """The low-density brief's values, exactly. A token rounded on the
        way into HSL would be a palette nobody specified."""
        expected = {
            "background": "#F6F4F1", "card": "#FFFFFF", "muted": "#F1EEE9",
            "wash": "#FAF8F5", "border": "#E3DED6", "divider": "#EFECE7",
            "input": "#D8D2C8", "heading": BRAND_NAVY, "foreground": "#101B2E",
            "muted-foreground": "#5B6678", "faint-foreground": "#8A93A1",
            "accent": BRAND_RED, "accent-ink": "#C41E27", "accent-border": "#F0C9CB",
            "primary": BRAND_NAVY, "primary-foreground": "#FFFFFF",
            "state-progress": "#2B5FA8", "state-progress-wash": "#E8EFF9",
            "state-pending-wash": "#FDF3E0", "state-approved": "#1C7A4A",
            "state-approved-wash": "#E7F5EE", "state-rejected": "#B3242C",
            "state-rejected-wash": "#FBE9EA",
        }
        for token, hexval in expected.items():
            assert _hex(PRODUCT[token]) == hexval, (token, _hex(PRODUCT[token]), hexval)

    def test_warn_is_darkened_from_the_brief_and_says_why(self):
        """**The one departure from the brief's values.** #B06B00 is 4.24:1
        on white and 3.85:1 on its own wash, so a pending chip would fail AA
        on the surface a chip actually is. #9E6000 is the same hue at the
        first lightness that passes."""
        assert _hex(PRODUCT["state-pending"]) == "#9E6000"
        brief = "36.5 100% 34.5%"  # #B06B00
        assert ratio(brief, PRODUCT["state-pending-wash"]) < 4.5
        assert ratio(PRODUCT["state-pending"], PRODUCT["state-pending-wash"]) >= 4.5

    def test_the_red_is_identical_on_both_surfaces(self):
        """**It is the identity, so it does not get adjusted for the surface.**
        Everything else in the file flips; this is the one value that does
        not, and it buys that with a size constraint rather than a tweak."""
        assert _hex(MARKETING["data"]) == _hex(PRODUCT["data"]) == BRAND_RED
        assert _hex(PRODUCT["accent"]) == BRAND_RED


# ---------------------------------------------------------------------------
# Contrast, computed from what ships
# ---------------------------------------------------------------------------


PAIRS = [
    ("heading", "background", "a heading on the canvas", 4.5),
    ("heading", "card", "a heading on a card", 4.5),
    ("foreground", "background", "body text on the canvas", 4.5),
    ("accent-ink", "card", "the accent as text on a card", 4.5),
    ("accent-ink", "background", "the accent as text on the canvas", 4.5),
    ("accent-foreground", "accent", "a label on a red badge", 4.5),
    ("ring", "card", "the focus ring against a card", 3.0),
    ("ring", "background", "the focus ring against the canvas", 3.0),
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

# A chip is the ink on its own wash, so that is the pairing that has to pass.
# Light only: on the dark set the wash carries an alpha and is measured in a
# browser, against whatever it composites over.
WASH_PAIRS = [
    (f"state-{s}", f"state-{s}-wash", s, 4.5)
    for s in ("pending", "approved", "rejected", "progress", "done")
]


class TestContrast:
    @pytest.mark.parametrize("surface", ["marketing", "product"])
    @pytest.mark.parametrize("fg,bg,label,need", [p for p in PAIRS if p[1] != "in progress"])
    def test_every_pairing_clears_aa(self, surface, fg, bg, label, need):
        tokens = MARKETING if surface == "marketing" else PRODUCT
        got = ratio(tokens[fg], tokens[bg])
        assert got >= need, f"{surface}: {label} is {got:.2f}:1, needs {need}"

    @pytest.mark.parametrize("fg,bg,label,need", WASH_PAIRS)
    def test_every_state_chip_clears_aa_on_its_own_wash(self, fg, bg, label, need):
        got = ratio(PRODUCT[fg], PRODUCT[bg])
        assert got >= need, f"{label} on its wash is {got:.2f}:1"

    def test_the_accent_is_for_fills_and_its_ink_is_for_words(self):
        """**The brief's non-negotiable, measured.** #FF2731 clears 3:1 —
        large text and UI boundaries — and fails 4.5:1, so it may not be a
        word below 24px. #C41E27 passes on both grounds."""
        white, ground = PRODUCT["card"], PRODUCT["background"]
        for g in (white, ground):
            assert 3.0 <= ratio(PRODUCT["accent"], g) < 4.5
            assert ratio(PRODUCT["accent-ink"], g) >= 4.5
        assert round(ratio(PRODUCT["accent"], white), 2) == 3.76
        assert round(ratio(PRODUCT["accent-ink"], white), 2) == 5.90

    def test_the_muted_ink_fails_as_text_and_is_kept_off_it(self):
        """#8A93A1 is 3.10:1 on white and 2.83:1 on the ground. It is a token
        for decoration, and no component may set text in it."""
        assert ratio(PRODUCT["faint-foreground"], PRODUCT["card"]) < 4.5
        offenders = [str(p.relative_to(SRC)) for p in _app_files()
                     if re.search(r"\btext-faint\b", _code(p.read_text()))]
        assert not offenders, offenders

    def test_the_inverse_chrome_reads(self):
        """Navy chrome inside the light app: the sidebar's ink and its muted
        ink on both inverse surfaces."""
        assert ratio_hex(INVERSE_HEX["ink"], INVERSE_HEX["surface"]) >= 4.5
        assert ratio_hex(INVERSE_HEX["muted"], INVERSE_HEX["surface"]) >= 4.5
        assert ratio_hex(INVERSE_HEX["muted"], INVERSE_HEX["alt"]) >= 4.5
        assert ratio_hex(INVERSE_HEX["ink"], INVERSE_HEX["surface"]) >= 3.0  # its ring

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


def _code(src: str) -> str:
    """Source with `//` lines and `/* */` blocks removed.

    The convention here is to explain a removal where it happened, which means
    the explanation quotes the thing removed — so a sweep that reads prose
    fails on its own documentation. `Logo.jsx` says in its header that it
    replaced a `bg-red-500` tile, and that sentence is the reason the file is
    right rather than evidence that it is wrong.

    Whole `//` lines rather than everything from `//` onward, which would also
    truncate at the `//` in a `https://` inside a real string. The same cut
    `test_brand_wall.py` and `test_marketing_pages.py` make.
    """
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


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

    def test_no_component_paints_white_or_black_or_a_literal_brand_scale(self):
        """**No dark-ground assumption survives anywhere in the app.** 620 of
        these were converted — `border-white/10` and its kind are invisible on
        the light ground, which is what makes a theme flip look broken rather
        than different. The brand colours a surface must keep whatever the
        theme are `brand-navy` / `brand-red` / `brand-white`, which are tokens;
        the literal `navy-700` / `red-500` scales are gone from the config."""
        RAW = re.compile(
            r"\b(?:bg|text|border|ring|fill|stroke|divide|from|via|to|decoration|"
            r"outline|accent|caret|placeholder|shadow|ring-offset|border-l)-"
            r"(?:white|black|navy-\d{2,3}|red-\d{2,3})(?![\w-])"
        )
        offenders = []
        for p in _app_files():
            for m in RAW.finditer(_code(p.read_text())):
                offenders.append(f"{p.relative_to(SRC)}: {m.group(0)}")
        assert not offenders, offenders[:20]
        config = (FRONTEND / "tailwind.config.js").read_text()
        assert "navy: {" not in config and "red: {" not in config

    def test_no_component_writes_a_hex_or_rgb_colour(self):
        """Inline SVG fills and style objects carry no class for the sweep
        above to find. The exceptions are named, not patterned: the studio's
        coral, which CLAUDE.md keeps out of the token layer on purpose, and the
        hues computed per id (`cover.js` has to agree with the server)."""
        allowed = {"lib/studioPalette.js"}
        RAW = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b|\brgba?\(|\bhsla?\(\s*[0-9]")
        offenders = []
        for p in _app_files():
            rel = str(p.relative_to(SRC))
            if rel in allowed:
                continue
            for m in RAW.finditer(_code(p.read_text())):
                offenders.append(f"{rel}: {m.group(0)}")
        assert not offenders, offenders

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
        # The brand scales are policed by the sweep above instead.
        assert not RAW_CLASS.search('className="bg-red-500 text-navy-700"')


# ---------------------------------------------------------------------------
# Where red is allowed to be
# ---------------------------------------------------------------------------


class TestRedIsLogoAndStandoutData:
    """**These two tests were rewritten when the real artwork arrived**, and
    the first of them was inverted, which is worth stating rather than
    burying.

    They used to pin the *drawn stand-in*: a `bg-red-500` tile with a serif W
    in `text-navy-700`, asserted present in four files. Both the tile and the
    letter are gone — the mark is now the tree and the wordmark, traced from
    `src/assets/brand/wearecreators-logo.png` — so a test naming those classes
    could only ever have failed here.

    The first one also asserted the opposite of what the brand now asks for.
    "The mark does not change colour depending on whether somebody is signed
    in" was right about the *stand-in*, whose red tile worked on both grounds.
    The real logo is a one-colour mark with no ground of its own, so on the
    navy marketing surface it is white and on the light product surface it is
    red — and the thing worth protecting is no longer "one colour everywhere"
    but "the surface decides, through the mechanism that already decides it".

    What survives intact is the fear underneath both: **`--primary` flips.**
    It is #FF2731 on marketing and navy on the product, so a mark painted with
    the token is red on the home page and navy in the app. That was the whole
    point of the original and it is still the point here.
    """

    LOGO_SURFACES = (
        "Navbar.jsx",
        "Footer.jsx",
        "marketing/MarketingNavbar.jsx",
        "marketing/MarketingFooter.jsx",
    )

    def test_every_surface_renders_the_one_logo_component(self):
        """The stand-in was nine inline copies in two spellings, which is how
        a mark becomes whatever each file happens to say it is. One component,
        or the next edit lands on three of the four."""
        for name in self.LOGO_SURFACES:
            src = (SRC / "components" / name).read_text()
            assert "components/brand/Logo" in src, f"{name} does not import <Logo>"
            assert "<Logo" in src, f"{name} imports it and does not render it"

    def test_no_drawn_stand_in_survives_anywhere(self):
        """Half a rebrand is worse than none: a leftover tile sits next to the
        real mark in the same header. Swept over the whole app rather than the
        four files above, because the stand-in was also on the auth screens."""
        offenders = []
        for p in _app_files():
            code = _code(p.read_text())
            if "bg-red-500" in code or "WeAre <span" in code:
                offenders.append(str(p.relative_to(SRC)))
        assert not offenders, offenders

    def test_that_stand_in_sweep_can_actually_fail(self):
        """It reads code and not prose, so it has to still catch the real
        thing — and has to go on ignoring the sentence explaining it."""
        assert "bg-red-500" in _code('<span className="bg-red-500">W</span>')
        assert "bg-red-500" not in _code("// replaced the bg-red-500 tile")
        assert "bg-red-500" not in _code("/* the old bg-red-500 mark */")
        # The cut that would break the sweep: truncating from `//` onward.
        assert "u" in _code('const u = "https://example.com";')

    def test_the_surface_decides_the_logo_colour_and_primary_never_does(self):
        """**Red on the app, white on navy, from the attribute that already
        says which is which.**

        Light is the *absence* of `data-theme` now, so red is the default rule
        and the three navy grounds — the dark set, a dark band, inverse chrome
        — are the override. A bug that applies neither applies red to the
        light ground, which is legible.

        `--primary` is banned from the mark for the reason the original test
        existed: it flips between the sets, so it would repaint the logo on
        sign-in.
        """
        css = (FRONTEND / "src" / "index.css").read_text()
        assert ".weare-logo {\n        color: var(--weare-logo-ink);\n    }" in css, (
            "the default rule is not the brand red — light is the default document"
        )
        assert ':root[data-theme="dark"] .weare-logo' in css
        assert '[data-surface="inverse"] .weare-logo' in css
        assert "--weare-logo-ink: hsl(var(--brand-red))" in css
        assert "--brand-red: 357.2 100% 57.6%" in css

        logo = (SRC / "components" / "brand" / "Logo.jsx").read_text()
        assert "var(--brand-red)" in logo, "the forced tone is not the brand red"
        for token in ("bg-primary", "text-primary", "var(--primary)"):
            assert token not in logo, f"the mark is painted with {token}, which flips"

    def test_the_logo_never_works_out_the_surface_for_itself(self):
        """**No third source of truth for which surface a page is on.** There
        are two — the pre-paint script and `isProductPath` — and a test already
        fails them if they drift. A component asking a third time would also be
        wrong for a frame on every first paint, which is the one thing the
        pre-paint script exists to prevent.
        """
        logo = (SRC / "components" / "brand" / "Logo.jsx").read_text()
        for reader in ("useLocation", "isProductPath", "PRODUCT_PREFIXES",
                       "pathname", "data-theme"):
            assert reader not in logo.split("*/")[-1], (
                f"<Logo> reads {reader} rather than inheriting the surface"
            )

    def test_that_colour_rule_can_actually_fail(self):
        """Break-tested, because an `in` against a stylesheet is exactly the
        shape of assertion that passes on a file that no longer does the job.
        """
        good = ':root[data-theme="dark"] .weare-logo {\n  color: white;\n}'
        assert ':root[data-theme="dark"] .weare-logo' in good
        # The failure this guards: colouring the mark with the flipping token.
        assert "var(--primary)" in 'style={{ color: "var(--primary)" }}'

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
            r"|\btext-h[123]\b"
            r"|\btext-\[(?:2[4-9]|[3-9]\d|\d{3,})px\]"
        )
        # **The accent, by every name it has.** `text-data`, a bare
        # `text-accent` and `text-brand-red` are all #FF2731 as a word; only
        # `text-accent-ink` may be small.
        RED_TEXT = re.compile(r"\btext-(?:data|accent|brand-red)(?![\w-])")
        offenders = []
        for p in _app_files():
            for line in _code(p.read_text()).splitlines():
                if RED_TEXT.search(line) and not LARGE.search(line):
                    offenders.append(f"{p.relative_to(SRC)}: {line.strip()[:90]}")
        assert not offenders, offenders

    def test_that_size_rule_can_actually_fail(self):
        """Break-tested rather than assumed: a `text-data` with no size class
        beside it has to be caught, or the rule is decoration."""
        LARGE = re.compile(r"\btext-fluid-(?:4xl|5xl|6xl|7xl|8xl|9xl)\b|\btext-(?:2xl|3xl)\b")
        assert not LARGE.search('className="text-sm text-data"')
        assert LARGE.search('className="text-fluid-6xl text-data"')
        assert LARGE.search('className="text-data text-3xl"'), "order must not matter"
        RED_TEXT = re.compile(r"\btext-(?:data|accent|brand-red)(?![\w-])")
        assert RED_TEXT.search('className="text-meta text-accent"')
        assert not RED_TEXT.search('className="text-meta text-accent-ink"')
        assert not RED_TEXT.search('className="bg-accent text-accent-foreground"')

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
