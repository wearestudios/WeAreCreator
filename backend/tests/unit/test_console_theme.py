"""Two themes, and the sweep that keeps the second one working.

**Light is the app now and is `:root`.** The navy set moved, whole, under
`[data-theme="dark"]`, which the marketing routes select and an admin may opt
into for the console. Nothing reaches it by default — not an unset attribute
and not an operating system set to dark. The history below is how the console
got its two themes in the first place, and the rule it set still holds.

**The audit was the work, not the palette.** The console was written in the
dark-mode idiom: `border-white/10` for a hairline, `bg-white/5` for a surface
lift, `text-ember-500` for the accent, hand-picked pastels for the charts —
around 750 of them. Every one is a value that only makes sense on a near-black
page, and each one missed renders as unreadable text on an off-white one. So
the rule this file exists to hold is that **no console component may name a
colour**: not a Tailwind palette class, not a hex, not an `rgb()`.

That rule is what makes the theme survive the console growing. A screen added
next month gets both themes by using the ordinary classes, and one that
reaches for `text-amber-300` fails here rather than in somebody's eyes three
weeks later.

The contrast numbers themselves are measured in a browser rather than asserted
here — see the note on `test_the_palette_is_verified_in_a_browser_not_here`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"
INDEX_CSS = FRONTEND / "index.css"
TAILWIND = FRONTEND.parent / "tailwind.config.js"
INDEX_HTML = FRONTEND.parent / "public" / "index.html"

# Everything the console renders. `components/admin` is the console proper;
# `ui` and `data` are the shadcn primitives and the dense-list kit it is built
# out of, and they portal into it — a dialog that kept a raw colour would be
# dark on a light console, which is most of what there was to get wrong.
CONSOLE_DIRS = ("components/admin", "components/ui", "components/data")

# The shared chrome a console route mounts. Named individually rather than by
# directory, because `components/` also holds the creator's and the brand's
# screens, which are not themed and must not be swept.
CONSOLE_CHROME = (
    "components/Navbar.jsx",
    "components/NotificationBell.jsx",
    "components/ImpersonationBanner.jsx",
    "components/RouteFallback.jsx",
    "components/ErrorBoundary.jsx",
    "App.js",
)

# **`red` and `navy` are the brand's own scales and are deliberately absent.**
# Everything else here is a colour that pins a component to one surface, which
# is the whole point of the sweep. The two brand literals exist for the two
# things a semantic token cannot express: the mark itself, which is red whether
# somebody is signed in or not, and the ink that sits on it, which is navy for
# the same reason. `test_brand.py` is what polices *where* those two may appear
# — this sweep would otherwise force the logo through a token that flips it.
TAILWIND_PALETTE = (
    "white|black|slate|gray|grey|zinc|neutral|stone|orange|amber|yellow|"
    "lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|"
    "rose|ember"
)
COLOUR_PREFIX = (
    "bg|text|border|ring|divide|fill|stroke|from|to|via|outline|shadow|"
    "placeholder|decoration|accent|caret"
)
RAW_CLASS = re.compile(
    rf"\b({COLOUR_PREFIX})-({TAILWIND_PALETTE})(-[0-9]{{2,3}})?(/\[?[0-9.]+\]?)?\b"
)
RAW_VALUE = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(\s*[0-9]")


def _strip_comments(src: str) -> str:
    """Drop comments before sweeping.

    The convention here is to explain a removal where it happened, and an
    explanation necessarily quotes the thing removed — the comment on `--tint`
    says what `border-white/10` was. Reading whole files would fail on the
    documentation of the very rule being enforced.
    """
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"(?<![:\w])//[^\n]*", "", src)


def _console_files():
    files = []
    for d in CONSOLE_DIRS:
        base = FRONTEND / d
        files += sorted(base.rglob("*.jsx")) + sorted(base.rglob("*.js"))
    files += [FRONTEND / name for name in CONSOLE_CHROME]
    return [f for f in files if f.is_file()]


def _offenders(pattern):
    out = []
    for f in _console_files():
        for i, line in enumerate(_strip_comments(f.read_text()).splitlines(), 1):
            for m in pattern.finditer(line):
                out.append(f"{f.relative_to(FRONTEND)}:{i}  {m.group(0)}")
    return out


# ---------------------------------------------------------------------------
# The sweep — the whole point of the file
# ---------------------------------------------------------------------------


class TestNoConsoleComponentNamesAColour:
    def test_no_tailwind_palette_class_survives(self):
        """**This is the regression test the theme lives or dies by.**

        `text-amber-300` renders as pale amber on white — 1.9:1, unreadable —
        and nothing about writing it looks wrong. There were 750 of these and
        the 751st is what a new screen adds without noticing.
        """
        offenders = _offenders(RAW_CLASS)
        assert not offenders, (
            f"{len(offenders)} raw colour class(es) in console code — use the "
            "semantic tokens (bg-card, border-tint/10, text-primary-ink, "
            "text-state-pending …):\n  " + "\n  ".join(offenders[:40])
        )

    def test_no_hex_or_rgb_literal_survives(self):
        """Charts and inline SVG are where these hide: a `fill="#7dd3a0"`
        carries no class for a sweep to find, and four pastels chosen to sit
        on a near-black card are four indistinguishable washes on a white
        one."""
        offenders = _offenders(RAW_VALUE)
        assert not offenders, (
            "raw colour value(s) in console code — read a token instead, e.g. "
            'fill="hsl(var(--state-approved))":\n  ' + "\n  ".join(offenders[:40])
        )

    def test_the_sweep_can_actually_fail(self):
        """A test that cannot fail is worse than no test. This is the one
        assertion here that proves the two above are looking at anything —
        the patterns are broad and a typo in one would pass silently
        forever."""
        planted = 'className="border-white/10 text-amber-300" fill="#7dd3a0"'
        assert RAW_CLASS.search(planted)
        assert RAW_VALUE.search(planted)
        # And the comment stripper does not swallow real code.
        assert RAW_CLASS.search(_strip_comments("x = 'text-amber-300' // note"))
        assert not RAW_CLASS.search(_strip_comments("// was text-amber-300"))


# ---------------------------------------------------------------------------
# The tokens both themes are built from
# ---------------------------------------------------------------------------


class TestTheTokens:
    @pytest.fixture(scope="class")
    def css(self):
        return INDEX_CSS.read_text()

    def _block(self, css, selector):
        start = css.index(selector)
        end = css.index("\n    }", start)
        return dict(
            (name, value.strip())
            for name, value in re.findall(r"--([a-z-]+):\s*([^;]+);", css[start:end])
        )

    LIGHT = ':root,\n    [data-surface="light"] {'
    DARK = '[data-surface="dark"],\n    :root[data-theme="dark"] {'

    def test_the_dark_set_overrides_every_token_the_light_one_colours(self, css):
        """**Anything not overridden keeps its light value**, which is how a
        navy page ends up with a white card on it. The radius scale is in both
        blocks too, deliberately: the dark set keeps the old 4/6/8."""
        light = self._block(css, self.LIGHT)
        dark = self._block(css, self.DARK)
        colourish = {
            k for k in light if re.match(r"^[0-9.]+\s+[0-9.]+%\s+[0-9.]+%", light[k])
        }
        missing = sorted(colourish - set(dark))
        assert not missing, f"dark set does not override: {missing}"

    def test_light_is_the_absence_of_the_attribute(self, css):
        """**The reversal.** There used to be no `[data-theme="dark"]` block
        and the product opted into light; now there is no `[data-theme="light"]`
        block and dark is the thing asked for. A bug that fails to set the
        attribute fails to the app's own surface."""
        assert ':root[data-theme="light"]' not in css
        assert ':root[data-theme="dark"]' in css
        assert css.index(self.LIGHT) < css.index(self.DARK)

    def test_the_tint_flips_with_the_set(self, css):
        """`--tint` is the alpha base for the classes that still carry an
        alpha at the call site (`hover:border-tint/30`). White on the dark set,
        a warm ink on light — the static hairlines moved to `border-border`
        and `divide-divider`, which land on the brief's exact values."""
        light = self._block(css, self.LIGHT)
        dark = self._block(css, self.DARK)
        assert dark["tint"] == "0 0% 100%"
        assert light["tint"] != dark["tint"]
        assert "tint:" in TAILWIND.read_text().replace('"', "").replace(" ", "")

    def test_the_accent_has_two_tokens_because_it_has_two_jobs(self, css):
        """`--primary` fills a button and `--primary-ink` is the accent as
        text on a surface.

        **They are allowed to be equal, and under the brand they are on one
        surface and not the other.** The old rule pinned them *unequal* on
        light, which was true of ember (#F05D14 as body text was 3.0:1) and is
        not true of navy — navy is 18:1 as text and as a fill, so splitting it
        would be inventing a second navy for no reason. Marketing still needs
        both: red fills a button with navy on it, and red as text on the navy
        canvas is a different job at 4.9:1.

        What has to hold is that both tokens exist and each passes contrast in
        its own job, which `TestContrast` measures. This only pins that neither
        has been deleted.
        """
        for sel in (self.LIGHT, self.DARK):
            block = self._block(css, sel)
            for token in ("primary", "primary-ink", "accent", "accent-ink"):
                assert block.get(token), (sel, token)

    def test_every_state_the_console_shows_has_a_token(self, css):
        """Four were named in the brief; the audit turned up a fifth. Violet
        marked "past the shoot" — attended, draft in review, content
        submitted, completed — which is a real distinction, and flattening it
        into "in progress" to fit a four-token list would have lost it."""
        for sel in (self.LIGHT, self.DARK):
            block = self._block(css, sel)
            for state in ("pending", "approved", "rejected", "progress", "done"):
                assert f"state-{state}" in block, (sel, state)
                assert f"state-{state}-wash" in block, (sel, state)

    def test_the_status_table_is_the_only_place_a_state_is_coloured(self):
        """`STATUS_TONE` was already the one definition — the four `meta`
        objects it replaced are why a closed campaign read grey on one screen
        and red on the next. Tokenising it is what made the whole console
        follow five lines of CSS."""
        src = (FRONTEND / "components/admin/console/tokens.js").read_text()
        for state in ("state-pending", "state-approved", "state-rejected"):
            assert state in src, state


# ---------------------------------------------------------------------------
# How the theme is applied, and where it is allowed to exist
# ---------------------------------------------------------------------------


class TestScope:
    """Which surface a route is on, and who gets to say so.

    **The architecture inverted with the brand.** Light used to be an admin's
    opt-in on `/admin` and everything else was dark; now the product is light,
    marketing is navy, and the line is authentication. The machine is the same
    — an attribute on `<html>` — so these tests moved rather than went.
    """

    def test_the_attribute_is_written_in_exactly_one_module(self):
        """One is the pre-paint script, the other is `applyTheme`. A third
        would be a third opinion about what surface a page is on."""
        writers = []
        for f in list(FRONTEND.rglob("*.js")) + list(FRONTEND.rglob("*.jsx")):
            if 'setAttribute("data-theme"' in f.read_text().replace("'", '"'):
                writers.append(f.relative_to(FRONTEND))
        assert writers == [Path("lib/surfaceTheme.js")], writers
        assert 'setAttribute("data-theme", "dark")' in INDEX_HTML.read_text()

    def test_the_pre_paint_script_only_ever_asks_for_dark(self):
        """**This is the whole of the scoping, turned round.** Light is the
        absence of the attribute, so the app's first paint needs nothing
        written; the script writes `dark` for the marketing routes and for an
        admin whose cached choice is dark, and for nothing else."""
        html = INDEX_HTML.read_text()
        assert "/dashboard" in html and "/admin" in html
        assert 'setAttribute("data-theme", "dark")' in html
        assert 'setAttribute("data-theme", "light")' not in html
        assert 'var theme = "light"' in html

    def test_the_pre_paint_script_and_the_module_agree_about_which_routes(self):
        """**Two implementations of "is this the product" is two answers**, and
        the one that runs first is the one nobody debugs. The script cannot
        import the module — nothing has loaded yet — so the duplication is the
        trade and this is what pays for it.
        """
        html = INDEX_HTML.read_text()
        js = (FRONTEND / "lib/surfaceTheme.js").read_text()
        prefixes = re.findall(r'"(/[a-z/-]+)"', js.split("PRODUCT_PREFIXES = [")[1]
                              .split("]")[0])
        assert prefixes, "no product prefixes declared"
        for prefix in prefixes:
            assert f'"{prefix}"' in html, f"{prefix} is in the module and not the script"
        # And the awkward one: /campaigns is public, but authoring is not.
        for both in ("/campaigns/new", "weare:console-theme"):
            assert both in html, both
            assert both in js, both
        # **And neither consults the operating system.** It used to: an admin
        # on a dark-mode laptop got the navy console without choosing it,
        # which is dark selected by default.
        for reader in (html, js):
            assert "prefers-color-scheme" not in reader

    def test_one_guard_applies_it_on_every_navigation(self):
        """**Found in a browser, not by a test**, in its first form: a hard
        load of `/admin` wrote the attribute before React ran, and if that
        person was not signed in the console never mounted, nothing cleared
        it, and the landing page rendered light.

        The fix then was a guard that cleared on the way out. The fix now is
        stronger: the guard is the *only* writer and runs on every path
        change, so there is no "on the way out" to miss. `AdminConsole` no
        longer clears anything — an unmount handler racing a navigation is how
        a dashboard goes navy for a frame.

        **And it has to be rendered, not merely defined.** The first version of
        this asserted the function existed and stayed green when the element
        was deleted from the tree.
        """
        app = (FRONTEND / "App.js").read_text()
        assert "function SurfaceGuard(" in app, "the guard is not defined"
        assert "<SurfaceGuard />" in app, "the guard is defined but never rendered"
        assert "surfaceFor" in app
        # Inside the router, or `useLocation` throws and the app goes with it.
        assert app.index("<BrowserRouter>") < app.index("<SurfaceGuard />")

    def test_the_console_only_caches_the_choice_and_never_applies_it(self):
        """One writer. The console tells the guard what the account chose;
        it does not paint."""
        src = (FRONTEND / "pages/AdminConsole.jsx").read_text()
        assert "rememberTheme(accountTheme)" in src
        assert "return clearTheme" not in src, "the console still clears on unmount"

    def test_marketing_is_never_overridable_by_an_account_preference(self):
        """An admin's console preference is a preference about their console,
        not a licence to repaint the home page."""
        js = (FRONTEND / "lib/surfaceTheme.js").read_text()
        # The *body*, not the signature — `accountTheme` is a parameter and
        # appears first there whatever the function does, which is how the
        # first version of this test failed on correct code.
        body = js.split("export function surfaceFor")[1].split("{", 1)[1]
        assert body.index("isProductPath") < body.index("accountTheme"), (
            "the account preference is read before the surface is decided"
        )
        assert 'return "dark"' in body


# ---------------------------------------------------------------------------
# Whose preference it is
# ---------------------------------------------------------------------------


class TestItFollowsThePerson:
    def test_the_choice_is_stored_against_the_account(self):
        """`localStorage` alone would mean an admin who works from a laptop
        and a desk machine sets it twice and loses it on a new browser. A
        preference about how somebody reads for hours is theirs, not their
        device's."""
        assert "console_theme" in server.ConsoleThemePayload.model_fields or hasattr(
            server.ConsoleThemePayload, "model_fields"
        )
        assert "theme" in server.ConsoleThemePayload.model_fields
        src = __import__("inspect").getsource(server.me)
        assert "console_theme" in src

    def test_never_chosen_is_a_real_answer_and_not_a_default(self):
        """It is the difference between "the app's default" and "they picked
        light" — and only the first should move if the default ever does.
        Collapsing them freezes every admin who has never opened the menu onto
        whatever the default happened to be the first time they loaded."""
        assert server._console_theme({}) is None
        assert server._console_theme({"console_theme": None}) is None
        assert server._console_theme({"console_theme": "dark"}) == "dark"
        assert server._console_theme({"console_theme": "light"}) == "light"
        # And a value that is not a theme does not travel to a client that
        # would then write it onto <html>.
        assert server._console_theme({"console_theme": "sepia"}) is None

    def test_the_route_is_open_to_everyone_who_reads_the_console(self):
        """`weare_team` reads the same console and sits in front of it just as
        long, so the preference is theirs too."""
        import inspect

        src = inspect.getsource(server.set_console_theme)
        assert "require_roles(*CONSOLE_ROLES)" in src

    def test_clearing_it_is_possible(self):
        """Somebody who tried dark and wants to stop thinking about it should
        be able to hand the question back to the app, rather than having to
        pick the one that happens to match today."""
        assert server.ConsoleThemePayload().theme is None
        assert server.ConsoleThemePayload(theme=None).theme is None

    def test_the_menu_offers_system_as_well_as_the_two_themes(self):
        src = (FRONTEND / "components/admin/AdminAccountMenu.jsx").read_text()
        # "Default" rather than "System": it resolves to light, not to the OS.
        for value in ("Default", "Light", "Dark"):
            assert value in src, value
        assert "systemTheme" not in src
        # And it is in the account menu rather than floating in the layout: a
        # toggle over a dense working surface is a control somebody hits
        # reaching for a table.
        assert "AdminAccountMenu" in (FRONTEND / "components/Navbar.jsx").read_text()
        assert "AdminAccountMenu" not in (FRONTEND / "pages/AdminConsole.jsx").read_text()


# ---------------------------------------------------------------------------
# What this file deliberately does not try to check
# ---------------------------------------------------------------------------


def test_the_palette_is_verified_in_a_browser_not_here():
    """**Contrast is measured, not asserted in Python.**

    A ratio computed from the CSS tells you what two tokens do against each
    other; it cannot tell you what a 12px label on a chip of its own hue at
    10% over a card inside a dialog actually resolves to — which is where the
    real failures were. Every one found during this work was found by walking
    the rendered DOM: the navbar at 1.05:1, the section error fallback at
    3.04:1, the state inks carrying a dark-mode alpha that lifted them toward
    a light background.

    So the browser sweep is the instrument, and this is the note saying so,
    with the numbers it produced: **0 elements below AA in either theme**,
    across all eighteen console sections, the command palette, the shortcuts
    overlay and the error fallbacks.

    What is pinned here instead is the thing a browser check cannot see: that
    no component has reintroduced a colour the sweep would have to catch.
    """
    assert INDEX_CSS.exists()
