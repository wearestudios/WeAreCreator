"""The public site's foundations: fonts, type, numerals, colour, motion,
photographs and copy — the layer the three marketing pages are built on.

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
# 2a — Fonts, self-hosted
# ---------------------------------------------------------------------------

FONTS_DIR = FRONTEND / "public" / "fonts"
FONT_FILES = {
    # family, style → file
    ("Fraunces", "normal"): "fraunces-latin-normal.woff2",
    ("Fraunces", "italic"): "fraunces-latin-italic.woff2",
    ("Inter Tight", "normal"): "inter-tight-latin.woff2",
    ("JetBrains Mono", "normal"): "jetbrains-mono-latin-400.woff2",
}


def _faces():
    out = {}
    for body in re.findall(r"@font-face\s*\{(.*?)\}", CSS, flags=re.S):
        fam = re.search(r'font-family:\s*"([^"]+)"', body).group(1)
        style = (re.search(r"font-style:\s*(\w+)", body) or [None, "normal"])[1]
        out[(fam, style)] = body
    return out


class TestFonts:
    def test_no_font_request_leaves_for_a_third_party(self):
        """Self-hosted: no stylesheet host, no file host, no preconnect to
        either. The old request cost two extra origins before a glyph."""
        for text in (CSS, INDEX_HTML.read_text()):
            assert "fonts.googleapis.com" not in text
            assert "fonts.gstatic.com" not in text
        assert not re.search(r"@import\s+url\(", _code(CSS))

    @pytest.mark.parametrize("key", sorted(FONT_FILES))
    def test_each_face_is_a_file_we_serve(self, key):
        face = _faces()[key]
        name = FONT_FILES[key]
        assert f'url("/fonts/{name}") format("woff2")' in face
        assert (FONTS_DIR / name).is_file(), name
        assert "font-display: swap;" in face
        # Latin only: the range starts at Basic Latin and stops short of
        # Latin Extended.
        assert "unicode-range: U+0000-00FF," in face

    def test_the_weights_declared_are_the_weights_loaded(self):
        faces = _faces()
        assert "font-weight: 400 700;" in faces[("Fraunces", "normal")]
        assert "font-weight: 400 700;" in faces[("Fraunces", "italic")]
        assert "font-weight: 400 600;" in faces[("Inter Tight", "normal")]
        assert "font-weight: 400;" in faces[("JetBrains Mono", "normal")]

    def test_the_fraunces_files_carry_wonk_and_not_soft(self):
        """**ital, opsz, wght and WONK — and no SOFT axis at all.** Read from
        the files themselves, where fontTools is installed."""
        ttlib = pytest.importorskip("fontTools.ttLib")
        for style in ("normal", "italic"):
            font = ttlib.TTFont(FONTS_DIR / FONT_FILES[("Fraunces", style)])
            axes = {a.axisTag: (a.minValue, a.maxValue) for a in font["fvar"].axes}
            assert set(axes) == {"opsz", "wght", "WONK"}, axes
            assert axes["wght"] == (400, 700)
        inter = ttlib.TTFont(FONTS_DIR / FONT_FILES[("Inter Tight", "normal")])
        assert {a.axisTag: (a.minValue, a.maxValue) for a in inter["fvar"].axes} == {"wght": (400, 600)}

    def test_soft_is_set_nowhere(self):
        """The axis is not loaded, so a `"SOFT"` setting would be a no-op that
        reads as if it did something."""
        assert '"SOFT"' not in _code(CSS)
        for p in _src_files():
            assert "SOFT" not in _code(p.read_text()), p

    def test_one_preload_and_it_is_the_hero_face(self):
        html = INDEX_HTML.read_text()
        preloads = re.findall(r"<link\s+rel=\"preload\"(.*?)/>", html, flags=re.S)
        fonts = [p for p in preloads if 'as="font"' in p]
        assert len(fonts) == 1, fonts
        assert "/fonts/fraunces-latin-normal.woff2" in fonts[0]
        assert 'type="font/woff2"' in fonts[0] and "crossorigin" in fonts[0]

    def test_every_family_has_a_metric_matched_fallback(self):
        """The swap from the local face to the webfont must move nothing; the
        hero headline is the LCP element and the place a swap shifts a page."""
        faces = _faces()
        for key in (
            ("Fraunces Fallback", "normal"), ("Fraunces Fallback Android", "normal"),
            ("Fraunces Display Fallback", "normal"), ("Fraunces Display Fallback Android", "normal"),
            ("Fraunces Display Large Fallback", "normal"),
            # The hero's italic word: a browser-slanted upright is a different
            # width from the real italic, and the line after it moved.
            ("Fraunces Display Fallback", "italic"), ("Fraunces Display Large Fallback", "italic"),
            ("Inter Tight Fallback", "normal"), ("Inter Tight Fallback Android", "normal"),
            ("JetBrains Mono Fallback", "normal"),
        ):
            face = faces[key]
            assert "local(" in face and "url(" not in face, key
            for d in ("size-adjust", "ascent-override", "descent-override", "line-gap-override"):
                assert re.search(rf"{d}:\s*[\d.]+%;", face), (key, d)
        for fam in ("Fraunces Display Fallback", "Fraunces Display Large Fallback"):
            assert "Italic" in faces[(fam, "italic")], "an italic fallback names an italic local face"

    def test_the_display_fallback_is_matched_at_the_size_it_renders(self):
        """Fraunces is far wider at the phone headline's optical size than at
        the desktop one, so one set of metrics cannot serve both: matched at
        the desktop end, the fallback set the phone headline on two lines
        where Fraunces needs four. The Large face takes over at 1024px."""
        media = re.search(r"@media \(min-width: 1024px\)\s*\{\s*:root\s*\{([^}]*)\}", CSS)
        assert media, "the large display fallback is switched in at 1024px"
        assert '"Fraunces", "Fraunces Display Large Fallback"' in media.group(1)
        script = (ROOT / "scripts" / "build-fonts.py").read_text()
        assert '"opsz": 52' in script and '"opsz": 100' in script

    def test_each_stack_names_its_fallbacks(self):
        def stack(name):
            return re.search(rf"--{name}:\s*([^;]+);", CSS).group(1)
        assert stack("font-serif").startswith('"Fraunces", "Fraunces Fallback", "Fraunces Fallback Android"')
        assert stack("font-display").startswith(
            '"Fraunces", "Fraunces Display Fallback", "Fraunces Display Fallback Android"'
        )
        assert stack("font-sans").startswith('"Inter Tight", "Inter Tight Fallback", "Inter Tight Fallback Android"')
        assert stack("font-label").startswith('"JetBrains Mono", "JetBrains Mono Fallback"')
        tw = TAILWIND.read_text()
        assert 'serif: ["var(--font-serif)"]' in tw and 'sans: ["var(--font-sans)"]' in tw
        assert ".mkt-display" in CSS and "font-family: var(--font-display);" in _rule(".mkt-display")

    def test_jetbrains_mono_is_the_label_and_nothing_else(self):
        """11–13px uppercase labels only. Wired through one class, so a page
        without a label never fetches the file, and `font-mono` (which the
        product uses) is untouched."""
        users = re.findall(r"(\.[\w-]+)\s*\{[^{}]*var\(--font-label\)", CSS)
        assert users == [".mkt-label"]
        assert "JetBrains" not in TAILWIND.read_text()

    def test_no_weight_is_asked_for_that_is_not_loaded(self):
        """Inter Tight is loaded at 400–600 and Fraunces at 400–700. A
        `font-bold` or `font-light` would be synthesised by the browser — the
        fake-weight version of the fake-italic problem this fixes."""
        banned = re.compile(r"\bfont-(?:thin|extralight|light|bold|extrabold|black)\b")
        offenders = [
            str(p.relative_to(SRC)) for p in _src_files() if banned.search(_code(p.read_text()))
        ]
        assert not offenders, offenders

    def test_the_build_script_is_in_the_repository(self):
        script = (ROOT / "scripts" / "build-fonts.py").read_text()
        assert "instantiateVariableFont" in script and "size-adjust" in script
        readme = (FONTS_DIR / "README.md").read_text()
        for name in FONT_FILES.values():
            assert name in readme, name
        assert "SIL Open Font License" in readme


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
    def test_the_token_is_wonk_alone(self):
        m = re.search(r"--mkt-wonk:\s*([^;]+);", CSS)
        assert m and m.group(1).strip() == '"WONK" 1'

    def test_wonk_appears_only_on_classes_that_never_go_below_40px(self):
        """Below 40px the leaning n and m read as a rendering fault, so the
        product's 24–32px headings must never get it. Every rule that uses the
        token has a clamp whose *minimum* is 40px or more."""
        users = re.findall(r"(\.[\w-]+)\s*\{[^{}]*var\(--mkt-wonk\)", CSS)
        assert set(users) == {".mkt-display", ".mkt-h1", ".mkt-h2"}
        for sel in users:
            lo, *_ = _clamp(_rule(sel))
            assert lo >= 40, f"{sel} carries wonk at {lo}px"

    def test_wonk_is_off_everywhere_else_explicitly(self):
        """**The file's default instance has WONK on**, so leaving it unset is
        not leaving it off. The document turns it off (inherited, for every
        `font-serif` that is not a heading), the product's heading rule turns
        it off, and the h3 step turns it off."""
        html = re.search(r"\n    html \{(.*?)\}", CSS, flags=re.S).group(1)
        assert 'font-variation-settings: "WONK" 0;' in html
        base = re.search(r"h5 \{(.*?)\}", CSS, flags=re.S).group(1)
        assert 'font-variation-settings: "opsz" 144, "WONK" 0;' in base
        assert 'font-variation-settings: "WONK" 0;' in _rule(".mkt-h3")
        # Turned on in exactly one place: the token.
        assert len(re.findall(r'"WONK" 1', _code(CSS))) == 1
        for p in _src_files():
            assert "WONK" not in _code(p.read_text()), p

    def test_the_h3_step_is_never_wonky(self):
        assert "var(--mkt-wonk)" not in _rule(".mkt-h3")
        assert _clamp(_rule(".mkt-h3"))[0] < 40


# ---------------------------------------------------------------------------
# 1b — The marketing scale, and the app's left alone
# ---------------------------------------------------------------------------

MKT_SCALE = {
    # selector: (clamp exactly as briefed, line-height, tracking)
    ".mkt-display": ("clamp(3.25rem, 1.6rem + 5vw, 6.5rem)", "0.95", "-0.04em"),
    ".mkt-h1": ("clamp(2.75rem, 2.1rem + 3.1vw, 5.25rem)", "0.96", "-0.035em"),
    ".mkt-h2": ("clamp(2.5rem, 1.95rem + 2.6vw, 4.25rem)", "1.02", "-0.035em"),
    ".mkt-h3": ("clamp(1.75rem, 1.5rem + 1.2vw, 2.5rem)", "1.1", "-0.02em"),
}


class TestMarketingScale:
    @pytest.mark.parametrize("sel", sorted(MKT_SCALE))
    def test_each_step_is_the_briefed_clamp(self, sel):
        clamp, lh, tracking = MKT_SCALE[sel]
        body = _rule(sel)
        assert f"font-size: {clamp};" in body
        assert f"line-height: {lh};" in body
        assert f"letter-spacing: {tracking};" in body

    def test_the_ranges_are_what_the_brief_says(self):
        """52→104, 44→84, 40→68, 28→40, read back off the clamps."""
        got = {sel: (_clamp(_rule(sel))[0], _clamp(_rule(sel))[3]) for sel in MKT_SCALE}
        assert got == {
            ".mkt-display": (52, 104), ".mkt-h1": (44, 84),
            ".mkt-h2": (40, 68), ".mkt-h3": (28, 40),
        }

    def test_the_lead_body_and_label(self):
        assert "font-size: clamp(1.125rem, 1.05rem + 0.35vw, 1.3125rem);" in _rule(".mkt-lead")
        assert "font-size: 1.125rem;" in _rule(".mkt-body")
        label = _rule(".mkt-label")
        assert "font-family: var(--font-label);" in label
        assert "font-size: 0.75rem;" in label
        assert "letter-spacing: 0.14em;" in label
        assert "text-transform: uppercase;" in label

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
MKT_CLASS = re.compile(r"(?<![\w-])mkt-(?:display|h1|h2|h3|lead|body|label)(?![\w-])")


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
        html_rule = re.search(r"\n    html \{\s*font-variant-numeric: tabular-nums;", CSS)
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
# 2d — Motion: one curve, two bands, five primitives
# ---------------------------------------------------------------------------

PRIMITIVES = SRC / "components/marketing/primitives.js"
ENTRANCES = SRC / "components/marketing/Entrances.jsx"
FILL = SRC / "components/marketing/FillText.jsx"
MARQUEE = SRC / "components/marketing/Marquee.jsx"


def _reduced() -> str:
    return "\n".join(re.findall(r"@media \(prefers-reduced-motion: reduce\) \{(.*?)\n\}", CSS, flags=re.S))


class TestMarketingMotion:
    def test_there_are_exactly_five_primitives(self):
        exports = re.findall(r"export \{([^}]+)\}", PRIMITIVES.read_text())
        names = {n.strip() for group in exports for n in group.split(",")}
        assert names == {"WipeWord", "RowWriter", "CountUp", "FillText", "Marquee"}

    def test_one_curve(self):
        """`--weare-ease` is the curve, and no other `cubic-bezier` is written
        in the stylesheet."""
        curves = set(re.findall(r"cubic-bezier\(([^)]+)\)", _code(CSS)))
        assert curves == {"0.22, 1, 0.36, 1"}
        for sel in (".mkt-wipe", '[data-written="true"] .mkt-row'):
            assert "var(--weare-ease)" in _rule(sel)

    def test_linear_only_where_a_constant_speed_is_the_point(self):
        """The marquee loops, and an eased loop stalls at its seam; the fill's
        frame-to-frame smoothing follows a finger. Nothing else on a public
        page runs linear."""
        mkt_rules = re.findall(r"(\.mkt-[\w-]+)\s*\{([^{}]*)\}", _code(CSS))
        linear = sorted({sel for sel, body in mkt_rules if re.search(r"\blinear\b", body)})
        assert linear == [".mkt-fill-word", ".mkt-marquee-track"], linear

    def test_two_bands_and_nothing_between(self):
        def ms(name):
            return int(re.search(rf"--{name}:\s*(\d+)ms;", CSS).group(1))
        assert ms("mkt-interactive") == 200
        assert ms("mkt-wipe") == 520
        assert 400 <= ms("mkt-row") <= 600 and ms("mkt-row-gap") == 70

    def test_the_wipe_leaves_no_clip_behind(self):
        """`backwards`, so once it ends the clip is gone rather than held — an
        italic's overhang is never trimmed by a finished animation."""
        body = _rule(".mkt-wipe")
        assert "animation: mkt-wipe var(--mkt-wipe) var(--weare-ease) backwards;" in body
        assert "display: inline-block;" in body

    def test_the_component_gap_agrees_with_the_stylesheet(self):
        assert re.search(r"ROW_GAP_MS = 70;", ENTRANCES.read_text())

    def test_reduced_motion_is_the_end_state_and_lives_in_the_stylesheet(self):
        """**Never a shortened animation.** In `index.css` so a primitive
        cannot forget it; the four CSS primitives carry no motion branch of
        their own to disagree with it. (`CountUp` predates this and checks
        for itself, landing on the final value at first paint.)"""
        reduced = _reduced()
        rule = re.search(r"\.mkt-wipe,\s*\.mkt-row,[^{]*\{(.*?)\}", reduced, flags=re.S).group(1)
        for decl in ("animation: none !important", "opacity: 1 !important",
                     "transform: none !important", "clip-path: none !important"):
            assert decl in rule
        assert re.search(r"\.mkt-fill-word \{\s*opacity: 1 !important;", reduced)
        assert re.search(r"\.mkt-marquee-track \{\s*animation: none !important;", reduced)
        assert re.search(r"\.mkt-marquee-dup,[^{]*\{\s*display: none !important;", reduced)
        for f in (ENTRANCES, FILL, MARQUEE):
            code = _code(f.read_text())
            assert "useReducedMotion" not in code and "matchMedia" not in code, f.name

    def test_the_entrances_play_once(self):
        code = _code(ENTRANCES.read_text())
        assert "io.disconnect()" in code
        assert "setWritten(false)" not in code
        assert "scroll" not in code.lower()

    def test_the_fill_is_derived_from_scroll_and_never_re_renders(self):
        """A function of where the sentence sits, written onto each word from
        a ref — scrolling back un-inks it by the same function, and the
        sentence never re-renders per frame."""
        code = _code(FILL.read_text())
        assert "useState" not in code
        assert "getBoundingClientRect" in code and "requestAnimationFrame" in code
        assert "s.style.opacity" in code
        # Listening only while visible.
        assert "IntersectionObserver" in code and 'removeEventListener("scroll"' in code

    def test_the_fill_ink_function(self):
        out = _node(
            _module(FILL).replace("export function FillText", "function FillText").replace(
                "export default FillText;", ""
            ).split("function FillText")[0]
            + "\nconsole.log(JSON.stringify([inkFor(0,0,5), inkFor(1,4,5), inkFor(0.5,0,5), inkFor(0.5,4,5)]));"
        )
        first, last, early, late = json.loads(out)
        assert first == pytest.approx(0.18) and last == 1
        assert early > late, "earlier words ink first"

    def test_the_marquee_pauses_and_is_read_once(self):
        assert re.search(
            r"\.mkt-marquee:hover \.mkt-marquee-track,\s*\.mkt-marquee:focus-within \.mkt-marquee-track \{\s*animation-play-state: paused;",
            CSS,
        )
        code = _code(MARQUEE.read_text())
        assert 'aria-hidden={hidden ? true : undefined}' in code
        assert "aria-label={label}" in code


# ---------------------------------------------------------------------------
# 2e — Photographs arrive as a file and one manifest line
# ---------------------------------------------------------------------------

MANIFEST = SRC / "content/photoSlots.js"
PHOTO_SLOT = SRC / "components/marketing/PhotoSlot.jsx"
SLOT_KEYS = {
    "src", "alt", "focal", "width", "height", "brief",
    "fallbackHeadline", "fallbackAccent", "fallbackLine",
}


def _manifest(env=None):
    import os
    script = _module(MANIFEST) + "\nconsole.log(JSON.stringify(PHOTO_SLOTS));"
    full = {k: v for k, v in os.environ.items() if k not in ("NODE_ENV", "REACT_APP_VERCEL_ENV")}
    full.update(env or {})
    out = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True, text=True, timeout=60, env=full,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


class TestPhotoSlots:
    def test_every_slot_is_sized_and_has_a_finished_fallback(self):
        slots = _manifest({"NODE_ENV": "development"})
        assert set(slots) >= {"home-on-location", "brands-full-room", "creators-on-shoot"}
        for sid, slot in slots.items():
            assert set(slot) == SLOT_KEYS, sid
            assert isinstance(slot["width"], int) and isinstance(slot["height"], int), sid
            assert re.fullmatch(r"\d+% \d+%", slot["focal"]), sid
            assert slot["src"] is None or slot["src"].startswith("/img/photos/"), sid
            if slot["src"]:
                assert slot["alt"], f"{sid}: a photograph with no alt text"
            assert len(slot["brief"]) > 40, f"{sid}: a slot nobody can brief stays empty"
            assert len(slot["fallbackHeadline"]) > 10, sid
            if slot["fallbackAccent"]:
                assert slot["fallbackAccent"] in slot["fallbackHeadline"], sid

    def test_the_brief_exists_in_development_and_on_a_preview_only(self):
        """**The photographer's notes never reach production.** Evaluated the
        way the build evaluates it, with the three environments a Vercel CRA
        build actually sees."""
        dev = _manifest({"NODE_ENV": "development"})
        preview = _manifest({"NODE_ENV": "production", "REACT_APP_VERCEL_ENV": "preview"})
        prod = _manifest({"NODE_ENV": "production", "REACT_APP_VERCEL_ENV": "production"})
        bare = _manifest({"NODE_ENV": "production"})
        for sid in dev:
            assert dev[sid]["brief"] and preview[sid]["brief"]
            assert prod[sid]["brief"] is None and bare[sid]["brief"] is None, sid
            # The fallback the visitor sees is there in every environment.
            assert prod[sid]["fallbackHeadline"] == dev[sid]["fallbackHeadline"]

    def test_every_brief_is_compiled_out_rather_than_hidden(self):
        """Written `SHOW_BRIEFS ? "…" : null` inline, so the minifier drops
        the string itself on a production build. A brief written any other
        way would be in the bundle even if it were never rendered."""
        code = _code(MANIFEST.read_text())
        briefs = re.findall(r"brief:\s*([^\n]+)", code)
        assert briefs and all(b.strip().startswith("SHOW_BRIEFS") for b in briefs), briefs
        assert re.search(
            r'export const SHOW_BRIEFS =\s*process\.env\.NODE_ENV !== "production" \|\| '
            r'process\.env\.REACT_APP_VERCEL_ENV === "preview";',
            code,
        )

    def test_the_tinted_slots_briefs_compile_out_too(self):
        """The auth asides and the 404 draw `PlaceholderImage`, whose notes are
        photographer briefs as well. They were literal `note` props at each
        call site and shipped to production as a `data-placeholder`
        attribute on the sign-in screen, so they live in the manifest now
        under the same inline guard, and no page passes a literal note."""
        import os
        def briefs(env):
            script = _module(MANIFEST) + "\nconsole.log(JSON.stringify(PLACEHOLDER_BRIEFS));"
            full = {k: v for k, v in os.environ.items() if k not in ("NODE_ENV", "REACT_APP_VERCEL_ENV")}
            full.update(env)
            out = subprocess.run(["node", "--input-type=module", "-e", script],
                                 capture_output=True, text=True, timeout=60, env=full)
            assert out.returncode == 0, out.stderr
            return json.loads(out.stdout)
        dev = briefs({"NODE_ENV": "development"})
        prod = briefs({"NODE_ENV": "production"})
        assert set(dev) == {"auth-login", "auth-signup", "not-found"}
        assert all(len(v) > 20 for v in dev.values()) and all(v is None for v in prod.values())
        block = _code(MANIFEST.read_text()).split("PLACEHOLDER_BRIEFS = {", 1)[1].split("};", 1)[0]
        values = re.findall(r'"[\w-]+":\s*([^\n]+)', block)
        assert values and all(v.strip().startswith("SHOW_BRIEFS") for v in values), values
        for p in _src_files():
            code = _code(p.read_text())
            for tag in re.findall(r"<PlaceholderImage\b[^>]*>", code, flags=re.S):
                assert not re.search(r'\bnote="', tag), f"{p}: a literal brief ships in the bundle"
        slot = (SRC / "components/marketing/PlaceholderImage.jsx").read_text()
        assert "data-placeholder={src || !brief ? undefined : brief}" in slot

    def test_the_component_holds_no_path_of_its_own(self):
        code = _code(PHOTO_SLOT.read_text())
        assert "photoSlot(id)" in code
        assert not re.search(r"\.(?:png|jpe?g|webp|avif)\b|/img/", code)

    def test_lazy_unless_above_the_fold(self):
        code = _code(PHOTO_SLOT.read_text())
        assert 'loading={eager ? "eager" : "lazy"}' in code
        assert "eager = false" in code

    def test_the_ratio_is_on_the_box_in_every_state(self):
        code = _code(PHOTO_SLOT.read_text())
        assert "aspectRatio: `${slot.width} / ${slot.height}`" in code
        assert "objectPosition: slot.focal" in code
        assert code.count("style={box}") == 3

    def test_the_placeholder_is_development_only_and_the_fallback_is_navy(self):
        code = _code(PHOTO_SLOT.read_text())
        placeholder = code.split('data-empty="placeholder"', 1)[1].split("return", 1)[0]
        before = code.split('data-empty="placeholder"', 1)[0]
        assert "if (SHOW_BRIEFS && slot.brief)" in before.rsplit("return", 1)[0]
        assert "border-dashed" in placeholder and "{slot.brief}" in placeholder
        assert "{id}" in placeholder and "{slot.width}×{slot.height}" in placeholder
        fallback = code.split('data-empty="fallback"', 1)[1]
        assert 'data-surface="inverse"' in fallback, "the production fallback is the navy panel"
        assert "slot.fallbackHeadline" in fallback and "mkt-h1" in fallback
        assert "slot.brief" not in fallback

    def test_the_inverse_surface_is_the_brand_navy(self):
        m = re.search(r"--inverse:\s*([\d.]+)\s+([\d.]+)%\s+([\d.]+)%", CSS)
        assert _hsl_hex(*(float(x) for x in m.groups())) == NAVY

    def test_a_misspelt_slot_fails_loudly(self):
        out = _node(
            _module(MANIFEST)
            + '\ntry { photoSlot("no-such-slot"); console.log("silent"); }'
            + ' catch (e) { console.log("threw"); }'
        )
        assert out == "threw"


# ---------------------------------------------------------------------------
# 2f — Copy lives in one module, and an unknown is null
# ---------------------------------------------------------------------------

CONTENT = SRC / "content/marketing.js"
KNOWN = SRC / "components/marketing/Known.jsx"


def _facts():
    return json.loads(_node(_module(CONTENT) + "\nconsole.log(JSON.stringify(FACTS));"))


class TestContentModule:
    def test_the_known_nulls_are_null(self):
        facts = _facts()
        for key in ("platformFeePercent", "budgetRangesByCreatorSize",
                    "verifiedCreatorCount", "gstInvoiceConfirmed"):
            assert facts[key] is None, key

    def test_the_fee_says_why_it_is_null(self):
        """**A pricing decision, not a layout value** — written beside it, so
        the next person does not "fill it in"."""
        text = CONTENT.read_text()
        before = text.split("platformFeePercent: null", 1)[0].rsplit("/**", 1)[1]
        assert "pricing decision" in before.lower()
        assert "never invent" in before.lower()

    def test_the_confirmed_clients_are_the_three_and_only_the_three(self):
        assert _facts()["confirmedClients"] == ["The Brew Factory", "9889", "The Rameshwaram Cafe"]

    def test_a_null_fee_prints_nothing_and_a_set_one_prints_the_figure(self):
        out = _node(
            _module(CONTENT)
            + "\nconsole.log(JSON.stringify([platformFeeText(), platformFeeText(null), platformFeeText(12),"
            + " known(0), known(false), known(null), known(undefined)]));"
        )
        unset, explicit, set_, zero, false_, null_, undef = json.loads(out)
        assert unset is None and explicit is None
        assert set_ == "12% of the creator's fee"
        assert (zero, false_, null_, undef) == (True, True, False, False)

    def test_known_renders_nothing_in_production(self):
        """The development marker is written inline behind an environment
        test **computed in this file** — not `SHOW_BRIEFS` imported from the
        manifest. The build substitutes `process.env.*` per module, so an
        expression here folds to `false` and the minifier drops the branch; an
        imported constant is a reference it does not fold. Measured: with the
        import, the marker's text was in the production bundle."""
        code = _code(KNOWN.read_text())
        assert "if (known(value)) return children(value);" in code
        assert re.search(
            r'const SHOW_MISSING =\s*process\.env\.NODE_ENV !== "production" \|\| '
            r'process\.env\.REACT_APP_VERCEL_ENV === "preview";',
            code,
        )
        assert re.search(r"return SHOW_MISSING \? \(", code) and ") : null;" in code
        assert "SHOW_BRIEFS" not in code

    def test_no_public_file_says_tbc(self):
        offenders = []
        for p in _src_files():
            if not _public(p):
                continue
            if re.search(r"\bTBC\b|\bTBD\b|\bto be confirmed\b", _code(p.read_text()), re.I):
                offenders.append(str(p.relative_to(SRC)))
        assert not offenders, offenders

    def test_no_other_file_quotes_a_fee_percentage(self):
        """One fact means one place. A percentage typed into a page is the
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
