"""The public site's foundations: type, numerals, colour, motion, photographs
and copy — the layer the three marketing pages are built on.

None of this changes a page by itself. What it pins is the set of rules a page
is *allowed* to be built from, so that the pages that use them cannot quietly
drift back to the product's scale, a second easing curve, a hardcoded image
path or a made-up fee.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
FRONTEND = ROOT / "frontend"
SRC = FRONTEND / "src"
INDEX_CSS = SRC / "index.css"
INDEX_HTML = FRONTEND / "public" / "index.html"
TAILWIND = FRONTEND / "tailwind.config.js"

CSS = INDEX_CSS.read_text()


def _code(text: str) -> str:
    """Source with comments removed — block comments, and whole `//` lines.

    Not everything after `//`, which would cut a `https://` inside a string.
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"\{/\*.*?\*/\}", "", text, flags=re.S)
    return "\n".join(l for l in text.splitlines() if not l.strip().startswith("//"))


def _src_files():
    for p in sorted(SRC.rglob("*")):
        if p.suffix in (".js", ".jsx") and "node_modules" not in p.parts:
            yield p


def _node(script: str) -> str:
    out = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True, text=True, timeout=60,
    )
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def _module(path: Path) -> str:
    """A module's text with its `@/` imports removed, runnable in node."""
    return re.sub(r"^import .*?;\s*$", "", path.read_text(), flags=re.M)


# ---------------------------------------------------------------------------
# 1a — Fonts
# ---------------------------------------------------------------------------

FONT_URL = (
    "https://fonts.googleapis.com/css2?"
    "family=Fraunces:ital,opsz,wght,SOFT,WONK@0,9..144,400..700,0..100,0..1;"
    "1,9..144,400..700,0..100,0..1"
    "&family=Inter+Tight:wght@400;500;600"
    "&display=swap"
)


class TestFonts:
    def test_the_request_loads_every_axis_the_site_uses(self):
        """**The ital axis is the fix for every fake italic on the site.**
        Without it a Fraunces italic is a browser-slanted roman; WONK and SOFT
        are what the display sizes are drawn from."""
        first = CSS.splitlines()[0]
        assert first == f'@import url("{FONT_URL}");'

    def test_there_is_one_font_stylesheet_and_it_swaps(self):
        assert CSS.count("fonts.googleapis.com/css2") == 1
        assert "display=swap" in CSS.splitlines()[0]
        html = INDEX_HTML.read_text()
        assert "fonts.googleapis.com/css" not in html, "a second font stylesheet in index.html"

    def test_both_font_hosts_are_preconnected(self):
        html = INDEX_HTML.read_text()
        assert re.search(r'<link rel="preconnect" href="https://fonts.googleapis.com"\s*/>', html)
        assert re.search(
            r'<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin\s*/>', html
        ), "gstatic must be preconnected with crossorigin or the socket is wasted"

    def test_no_weight_is_asked_for_that_the_request_does_not_load(self):
        """Inter Tight is loaded at 400, 500 and 600, and Fraunces from 400.
        A `font-bold` or `font-light` would be synthesised by the browser —
        the fake-weight version of the fake-italic problem this fixes."""
        banned = re.compile(r"\bfont-(?:thin|extralight|light|bold|extrabold|black)\b")
        offenders = [
            str(p.relative_to(SRC)) for p in _src_files() if banned.search(_code(p.read_text()))
        ]
        assert not offenders, offenders


# ---------------------------------------------------------------------------
# 1a — Wonk at display sizes only
# ---------------------------------------------------------------------------

def _rule(selector: str) -> str:
    """The rule that sizes `selector` — the selector alone on its line, and
    the block that sets a size where a grouped rule only sets the family."""
    bodies = re.findall(r"(?m)^[ \t]*" + re.escape(selector) + r"\s*\{(.*?)\}", CSS, flags=re.S)
    assert bodies, f"no rule for {selector}"
    sized = [b for b in bodies if "font-size" in b or "animation" in b]
    return (sized or bodies)[-1]


def _clamp(body: str):
    m = re.search(
        r"font-size:\s*clamp\(([\d.]+)rem,\s*([\d.]+)rem\s*\+\s*([\d.]+)vw,\s*([\d.]+)rem\)", body
    )
    if not m:
        return None
    lo, inter, slope, hi = (float(x) for x in m.groups())
    return lo * 16, inter * 16, slope / 100, hi * 16


class TestWonk:
    def test_the_token_is_wonk_and_soft(self):
        m = re.search(r"--mkt-wonk:\s*([^;]+);", CSS)
        assert m and m.group(1).strip() == '"WONK" 1, "SOFT" 30'

    def test_wonk_appears_only_on_classes_that_never_go_below_40px(self):
        """Below 40px the leaning n and m read as a rendering fault, so the
        product's 24–32px headings must never get it. Every rule that uses the
        token has a clamp whose *minimum* is 40px or more."""
        users = re.findall(r"(\.[\w-]+)\s*\{[^{}]*var\(--mkt-wonk\)", CSS)
        assert set(users) == {".mkt-display", ".mkt-h1", ".mkt-h2"}
        for sel in users:
            lo, *_ = _clamp(_rule(sel))
            assert lo >= 40, f"{sel} carries wonk at {lo}px"

    def test_wonk_is_spelled_nowhere_else(self):
        """Not as a raw axis on some other rule, and not in a component's
        inline style — the token is the only door."""
        assert len(re.findall(r'"WONK"', CSS)) == 1
        for p in _src_files():
            assert "WONK" not in _code(p.read_text()), p
        base = re.search(r"h5 \{(.*?)\}", CSS, flags=re.S).group(1)
        assert "WONK" not in base, "the product's headings must not get wonk"

    def test_the_h3_step_is_soft_but_not_wonky(self):
        body = _rule(".mkt-h3")
        assert "var(--mkt-soft)" in body and "wonk" not in body.lower()
        assert _clamp(body)[0] < 40


# ---------------------------------------------------------------------------
# 1b — The marketing scale, and the app's left alone
# ---------------------------------------------------------------------------

MKT_SCALE = {
    # selector: (min px, max px, line-height, tracking)
    ".mkt-display": (52, 120, "0.93", "-0.04em"),
    ".mkt-h1": (44, 84, "0.96", "-0.035em"),
    ".mkt-h2": (40, 68, "1.02", "-0.035em"),
    ".mkt-h3": (28, 40, "1.1", "-0.02em"),
}


class TestMarketingScale:
    @pytest.mark.parametrize("sel", sorted(MKT_SCALE))
    def test_each_step_spans_a_phone_to_a_large_monitor(self, sel):
        """**Minimum at a 375px viewport, maximum at 1600px.** The app's
        clamps stop near 1280, so a large monitor got laptop type; these keep
        climbing. The endpoints are re-derived here from the clamp itself."""
        lo, hi, lh, tracking = MKT_SCALE[sel]
        body = _rule(sel)
        c_lo, inter, slope, c_hi = _clamp(body)
        assert (c_lo, c_hi) == (lo, hi)
        assert abs(inter + slope * 375 - lo) < 0.5, f"{sel} is not at its minimum at 375px"
        assert abs(inter + slope * 1600 - hi) < 0.5, f"{sel} is not at its maximum at 1600px"
        assert f"line-height: {lh};" in body
        assert f"letter-spacing: {tracking};" in body

    def test_the_lead_body_and_eyebrow(self):
        lo, inter, slope, hi = _clamp(_rule(".mkt-lead"))
        assert (lo, hi) == (18, 24)
        assert abs(inter + slope * 1600 - 24) < 0.5
        assert "font-size: 1.125rem;" in _rule(".mkt-body")
        eyebrow = _rule(".mkt-eyebrow")
        assert "font-size: 0.8125rem;" in eyebrow
        assert "letter-spacing: 0.2em;" in eyebrow
        assert "text-transform: uppercase;" in eyebrow

    def test_the_apps_fluid_steps_are_untouched(self):
        """The product depends on every one of these, so the marketing scale
        is a parallel set rather than an edit. Pinned to the values the
        product shipped with."""
        expected = {
            "fluid-2xl": "clamp(1.25rem, 1.146rem + 0.442vw, 1.5rem)",
            "fluid-3xl": "clamp(1.5rem, 1.345rem + 0.663vw, 1.875rem)",
            "fluid-4xl": "clamp(1.875rem, 1.72rem + 0.663vw, 2.25rem)",
            "fluid-5xl": "clamp(2.25rem, 1.939rem + 1.326vw, 3rem)",
            "fluid-5xl-wide": "clamp(1.875rem, 1.409rem + 1.989vw, 3rem)",
            "fluid-6xl": "clamp(3rem, 2.689rem + 1.326vw, 3.75rem)",
            "fluid-6xl-wide": "clamp(2.25rem, 1.628rem + 2.652vw, 3.75rem)",
            "fluid-hero": "clamp(2.5rem, 1.775rem + 3.094vw, 4.25rem)",
        }
        tw = TAILWIND.read_text()
        found = dict(re.findall(r'"(fluid-[\w-]+)":\s*\["([^"]+)"', tw))
        assert found == expected


# The public pages, by file. Everything else in `src/` is part of the product
# or shared with it, and may not reach for the marketing scale.
PUBLIC_PAGES = {
    "pages/Landing.jsx", "pages/ForBrands.jsx", "pages/ForCreators.jsx",
    "pages/HowItWorks.jsx", "pages/WhyWeAre.jsx", "pages/Contact.jsx",
    "pages/NotFound.jsx", "pages/Legal.jsx",
    "pages/Home.jsx", "pages/Brands.jsx", "pages/Creators.jsx",
}
MKT_CLASS = re.compile(r"(?<![\w-])mkt-(?:display|h1|h2|h3|lead|body|eyebrow)(?![\w-])")


def _public(path: Path) -> bool:
    rel = str(path.relative_to(SRC))
    return rel in PUBLIC_PAGES or rel.startswith("components/marketing/") or rel.startswith("content/")


def _imports(path: Path):
    """Files under `src/` that this one imports, resolved."""
    text = _code(path.read_text())
    for spec in re.findall(r"""(?:from|import\()\s*["']([^"']+)["']""", text):
        if spec.startswith("@/"):
            base = SRC / spec[2:]
        elif spec.startswith("."):
            base = (path.parent / spec).resolve()
        else:
            continue
        for cand in (base, base.with_suffix(".jsx"), base.with_suffix(".js"),
                     base / "index.js", base / "index.jsx"):
            if cand.is_file():
                yield cand
                break


def _signed_in_pages():
    """Every page App.js mounts inside a `<ProtectedRoute>`."""
    app = (SRC / "App.js").read_text()
    names = {}
    for name, spec in re.findall(
        r"const (\w+) = load\(\(\)\s*=>\s*import\(\s*/\*[^*]*\*/\s*\"(@/[^\"]+)\"", app, flags=re.S
    ):
        names[name] = spec
    for name, spec in re.findall(r'import (?:\{\s*)?(\w+)(?:\s*\})? from "(@/[^"]+)"', app):
        names.setdefault(name, spec)
    guarded = set()
    for block in re.findall(r"<ProtectedRoute\b.*?</ProtectedRoute>", app, flags=re.S):
        guarded |= set(re.findall(r"<([A-Z]\w+)", block)) - {"ProtectedRoute"}
    files = set()
    for name in guarded:
        spec = names.get(name)
        if not spec:
            continue
        for f in _imports_spec(spec):
            files.add(f)
    return files


def _imports_spec(spec):
    base = SRC / spec[2:]
    for cand in (base.with_suffix(".jsx"), base.with_suffix(".js"), base / "index.js"):
        if cand.is_file():
            yield cand
            return


class TestMarketingScaleStaysPublic:
    def test_no_signed_in_page_reaches_a_marketing_class(self):
        """**Walked from the router, not guessed from a folder.** Every page
        App.js puts behind `<ProtectedRoute>`, and everything it imports
        transitively, is searched for an `mkt-*` class. A shared component
        that grew one would put marketing type inside the console."""
        seen, queue, offenders = set(), list(_signed_in_pages()), []
        assert len(queue) >= 10, "the router walk found too few guarded pages to mean anything"
        while queue:
            f = queue.pop()
            if f in seen:
                continue
            seen.add(f)
            if MKT_CLASS.search(_code(f.read_text())):
                offenders.append(str(f.relative_to(SRC)))
            queue.extend(_imports(f))
        assert not offenders, offenders

    def test_nothing_outside_the_public_pages_uses_one(self):
        """The belt to the walk's braces: a component nobody routes to yet
        cannot hold marketing type either, or it is one import away from a
        signed-in screen."""
        offenders = [
            str(p.relative_to(SRC))
            for p in _src_files()
            if not _public(p) and MKT_CLASS.search(_code(p.read_text()))
        ]
        assert not offenders, offenders

    def test_the_rule_can_fail(self):
        assert MKT_CLASS.search('className="mkt-h2 text-foreground"')
        assert MKT_CLASS.search("className={`mkt-display ${x}`}")
        assert not MKT_CLASS.search('className="text-h2"')
        assert not MKT_CLASS.search('data-x="mkt-h2-ish"')


# ---------------------------------------------------------------------------
# 1a — Tabular figures
# ---------------------------------------------------------------------------

class TestNumerals:
    def test_every_figure_on_the_site_is_tabular(self):
        """Set on the document, so every rupee amount, every table cell and
        every countdown inherits it without anybody remembering to."""
        html_rule = re.search(r"\n    html \{\s*font-variant-numeric: tabular-nums;\s*\}", CSS)
        assert html_rule, "the document-wide tabular-nums rule is missing"

    def test_nothing_opts_back_out(self):
        """A `proportional-nums` on a fee column is the jitter coming back."""
        offenders = [
            str(p.relative_to(SRC))
            for p in _src_files()
            if re.search(r"\bproportional-nums\b|font-variant-numeric:\s*(?:normal|proportional)",
                         _code(p.read_text()))
        ]
        assert not offenders, offenders
        assert not re.search(r"font-variant-numeric:\s*(?:normal|proportional)", _code(CSS))


# ---------------------------------------------------------------------------
# 1c — Colour: the red as a fill, its ink as a word
# ---------------------------------------------------------------------------

def _lum(hex_):
    hex_ = hex_.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(hex_[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = out
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


BRAND_RED = "#FF2731"
ACCENT_INK = "#C41E27"
DANGER = "#B3242C"
NAVY = "#091426"
WHITE = "#FFFFFF"


class TestColourRules:
    def test_the_measured_ratios(self):
        """Measured, and the numbers the PR quotes. The brand red clears 3:1
        (fills, UI boundaries, type at 24px and up) and fails 4.5:1; its ink
        clears 4.5:1; navy carries a white label at well over 7:1."""
        assert round(ratio(BRAND_RED, WHITE), 2) == 3.76
        assert round(ratio(ACCENT_INK, WHITE), 2) == 5.90
        assert round(ratio(DANGER, WHITE), 2) == 6.55
        assert round(ratio(NAVY, WHITE), 2) == 18.43
        assert 3.0 <= ratio(BRAND_RED, WHITE) < 4.5
        assert ratio(ACCENT_INK, WHITE) >= 4.5

    def test_the_tokens_carry_those_values(self):
        light = re.search(r":root,\s*\[data-surface=\"light\"\]\s*\{(.*?)\n    \}", CSS, flags=re.S).group(1)

        def hsl(name):
            m = re.search(rf"--{name}:\s*([\d.]+)\s+([\d.]+)%\s+([\d.]+)%", light)
            return _hsl_hex(*(float(x) for x in m.groups()))

        assert hsl("accent") == BRAND_RED
        assert hsl("accent-ink") == ACCENT_INK
        assert hsl("destructive") == DANGER
        assert hsl("primary") == NAVY, "a primary button on a light ground is navy, never red"

    def test_danger_reads_as_a_different_red(self):
        """Deeper and browner than the brand red, so an error is never read as
        a highlight beside it."""
        assert DANGER != BRAND_RED
        assert ratio(DANGER, WHITE) > ratio(BRAND_RED, WHITE) + 2

    def test_no_state_is_ever_the_brand_red(self):
        """Rule 1: the red is a fill or a mark, never a status. Every state
        token on both surfaces resolves to something else."""
        for name, h, s, l in re.findall(r"--(state-[\w-]+):\s*([\d.]+)\s+([\d.]+)%\s+([\d.]+)%", CSS):
            assert _hsl_hex(float(h), float(s), float(l)) != BRAND_RED, name

    def test_the_red_is_never_text_on_a_chip(self):
        """A state chip is a state token on its own wash. `accent` on one is
        the red pretending to be a status."""
        chip_files = [SRC / "components/admin/console/StatusTag.jsx"]
        chip_files += [p for p in _src_files() if re.search(r"\bfunction (?:Chip|StatusTag|StatePill)\b", p.read_text())]
        for p in chip_files:
            if not p.exists():
                continue
            code = _code(p.read_text())
            assert not re.search(r"\b(?:text|bg|border)-(?:accent|data|brand-red)(?![\w-])", code), p

    def test_the_red_as_a_raw_hex_never_colours_a_word(self):
        """The token rule in `test_brand.py` polices the class names; this
        closes the door around it — an arbitrary `text-[#FF2731]` or an inline
        `color: "#FF2731"` is the same failure with the name filed off."""
        pat = re.compile(r"text-\[#ff2731\]|color:\s*[\"']?#ff2731", re.I)
        offenders = [str(p.relative_to(SRC)) for p in _src_files() if pat.search(_code(p.read_text()))]
        assert not offenders, offenders


def _hsl_hex(h, s, l):
    import colorsys
    r, g, b = colorsys.hls_to_rgb(h / 360, l / 100, s / 100)
    return "#" + "".join(f"{round(c * 255):02X}" for c in (r, g, b))


# ---------------------------------------------------------------------------
# 1d — Motion: one curve, two bands, three primitives
# ---------------------------------------------------------------------------

PRIMITIVES = SRC / "components/marketing/primitives.js"
ENTRANCES = SRC / "components/marketing/Entrances.jsx"


class TestMarketingMotion:
    def test_there_are_exactly_three_primitives(self):
        exports = re.findall(r"export \{([^}]+)\}", PRIMITIVES.read_text())
        names = {n.strip() for group in exports for n in group.split(",")}
        assert names == {"LineEntrance", "RowWriter", "CountUp"}

    def test_one_curve(self):
        """`--weare-ease` is the curve; the marketing keyframes use it and no
        other `cubic-bezier` is written in the stylesheet."""
        curves = set(re.findall(r"cubic-bezier\(([^)]+)\)", _code(CSS)))
        assert curves == {"0.22, 1, 0.36, 1"}
        for sel in (".mkt-line", '[data-written="true"] .mkt-row'):
            assert "var(--weare-ease)" in _rule(sel)

    def test_two_bands_and_nothing_between(self):
        def ms(name):
            return int(re.search(rf"--{name}:\s*(\d+)ms;", CSS).group(1))
        assert ms("mkt-interactive") == 200
        assert 450 <= ms("mkt-line") <= 600
        # A row is 400ms and four of them land 70ms apart, so the written
        # block as a whole arrives inside the entrance band.
        assert ms("mkt-row") == 400 and ms("mkt-row-gap") == 70
        assert 450 <= ms("mkt-row") + 3 * ms("mkt-row-gap") <= 620
        assert ms("mkt-line-gap") == 90

    def test_the_component_gaps_agree_with_the_stylesheet(self):
        text = ENTRANCES.read_text()
        assert re.search(r"LINE_GAP_MS = 90;", text)
        assert re.search(r"ROW_GAP_MS = 70;", text)

    def test_reduced_motion_is_the_end_state_and_lives_in_the_stylesheet(self):
        """**Never a shortened animation.** The rule is in `index.css` so a
        primitive cannot forget it, and the primitives carry no motion branch
        of their own to disagree with it."""
        reduced = re.search(r"@media \(prefers-reduced-motion: reduce\) \{(.*?)\n\}", CSS, flags=re.S)
        blocks = re.findall(r"@media \(prefers-reduced-motion: reduce\) \{(.*?)\n\}", CSS, flags=re.S)
        joined = "\n".join(blocks)
        assert ".mkt-line" in joined and ".mkt-row" in joined
        rule = re.search(r"\.mkt-line,\s*\.mkt-row,[^{]*\{(.*?)\}", joined, flags=re.S).group(1)
        assert "animation: none !important" in rule
        assert "opacity: 1 !important" in rule
        assert "transform: none !important" in rule
        code = _code(ENTRANCES.read_text())
        assert "useReducedMotion" not in code and "matchMedia" not in code
        assert reduced

    def test_the_entrances_play_once(self):
        """Neither is wired to scroll position. The writer stops observing the
        moment it has written, and never clears the flag."""
        code = _code(ENTRANCES.read_text())
        assert "io.disconnect()" in code
        assert "setWritten(false)" not in code
        assert "scroll" not in code.lower()


# ---------------------------------------------------------------------------
# 1e — Photographs arrive as a file and one manifest line
# ---------------------------------------------------------------------------

MANIFEST = SRC / "content/photoSlots.js"
PHOTO_SLOT = SRC / "components/marketing/PhotoSlot.jsx"


def _manifest():
    out = _node(_module(MANIFEST) + "\nconsole.log(JSON.stringify(PHOTO_SLOTS));")
    return json.loads(out)


class TestPhotoSlots:
    def test_every_slot_is_briefed_and_sized(self):
        slots = _manifest()
        assert slots, "an empty manifest"
        for sid, slot in slots.items():
            assert set(slot) == {"src", "alt", "focal", "width", "height", "brief"}, sid
            assert isinstance(slot["width"], int) and isinstance(slot["height"], int), sid
            assert len(slot["brief"]) > 40, f"{sid}: a slot nobody can brief stays empty"
            assert re.fullmatch(r"\d+% \d+%", slot["focal"]), sid
            assert slot["src"] is None or slot["src"].startswith("/img/photos/"), sid
            if slot["src"]:
                assert slot["alt"], f"{sid}: a photograph with no alt text"

    def test_the_component_holds_no_path_of_its_own(self):
        code = _code(PHOTO_SLOT.read_text())
        assert "photoSlot(id)" in code
        assert not re.search(r"\.(?:png|jpe?g|webp|avif)\b|/img/", code)

    def test_the_first_loads_and_the_rest_wait(self):
        code = _code(PHOTO_SLOT.read_text())
        assert 'loading={eager ? "eager" : "lazy"}' in code
        assert "eager = false" in code

    def test_the_ratio_is_on_the_box(self):
        code = _code(PHOTO_SLOT.read_text())
        assert "aspectRatio: `${slot.width} / ${slot.height}`" in code
        assert "objectPosition: slot.focal" in code

    def test_the_empty_slot_shows_its_id_its_size_and_its_brief(self):
        code = _code(PHOTO_SLOT.read_text())
        empty = code.split('data-empty="true"', 1)[1]
        assert "border-dashed" in empty
        assert "{id}" in empty and "{slot.width}×{slot.height}" in empty and "{slot.brief}" in empty

    def test_a_misspelt_slot_fails_loudly(self):
        out = _node(
            _module(MANIFEST)
            + '\ntry { photoSlot("no-such-slot"); console.log("silent"); }'
            + ' catch (e) { console.log("threw"); }'
        )
        assert out == "threw"


# ---------------------------------------------------------------------------
# 1f — Copy lives in one module, and the fee is not invented
# ---------------------------------------------------------------------------

CONTENT = SRC / "content/marketing.js"


class TestContentModule:
    def test_the_fee_is_one_constant_and_it_is_not_set(self):
        """**A pricing decision, not a layout value.** Nobody has decided the
        published figure, so it is `null` — and the reason sits beside it, so
        the next person does not "fill it in"."""
        text = CONTENT.read_text()
        assert len(re.findall(r"export const PLATFORM_FEE_PERCENT\b", text)) == 1
        assert re.search(r"export const PLATFORM_FEE_PERCENT = null;", text)
        before = text.split("export const PLATFORM_FEE_PERCENT", 1)[0]
        assert "pricing decision" in before.lower()

    def test_an_unset_fee_reads_as_shown_before_you_accept(self):
        out = _node(
            _module(CONTENT)
            + "\nconsole.log(JSON.stringify([platformFeeLabel(), platformFeeLabel(null),"
            + " platformFeeLabel(12)]));"
        )
        unset, explicit_null, set_ = json.loads(out)
        assert unset == explicit_null == "Shown before you accept"
        assert set_ == "12% of the creator's fee"

    def test_no_other_file_quotes_a_fee_percentage(self):
        """One constant means one place. A percentage typed into a page is the
        made-up figure this exists to prevent."""
        pat = re.compile(r"(?:fee|commission)[^\n]{0,40}\b\d{1,2}(?:\.\d)?\s?%", re.I)
        offenders = []
        for p in _src_files():
            if not _public(p) or p == CONTENT:
                continue
            for line in _code(p.read_text()).splitlines():
                if pat.search(line):
                    offenders.append(f"{p.relative_to(SRC)}: {line.strip()[:80]}")
        assert not offenders, offenders
