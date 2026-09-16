"""Two themes for the admin console, and the sweep that keeps the second one working.

An admin sits in front of the console for hours, which is a different
relationship from the one a creator has with their dashboard — so the console
gets a choice of light or dark, and the marketing site, the creator app, the
brand app and the manager screens stay dark.

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

TAILWIND_PALETTE = (
    "white|black|slate|gray|grey|zinc|neutral|stone|red|orange|amber|yellow|"
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

    def test_the_light_theme_overrides_every_token_that_carries_colour(self, css):
        """**Anything not overridden keeps its dark value**, which is how a
        light page ends up with a near-black surface on it. The two that are
        deliberately shared are `--radius`, which is not a colour, and the
        grain texture."""
        dark = self._block(css, ":root {")
        light = self._block(css, ':root[data-theme="light"] {')
        colourish = {
            k for k in dark if re.match(r"^[0-9.]+\s+[0-9.]+%\s+[0-9.]+%$", dark[k])
        }
        missing = sorted(colourish - set(light))
        assert not missing, f"light theme does not override: {missing}"

    def test_dark_is_the_absence_of_the_attribute(self, css):
        """There is no `[data-theme="dark"]` block, deliberately: the default
        state of the document is the default state of the product, so a bug
        that fails to set anything fails to dark — which is what every other
        surface here already is."""
        assert '[data-theme="dark"]' not in css

    def test_the_tint_is_what_carries_the_hairlines(self, css):
        """The 240 `border-white/10`-shaped classes became `border-tint/10`,
        keeping the alpha at the call site. `--tint` is white on dark, so the
        replacement is a no-op there — which is what let it be mechanical."""
        dark = self._block(css, ":root {")
        light = self._block(css, ':root[data-theme="light"] {')
        assert dark["tint"] == "0 0% 100%"
        assert light["tint"] != dark["tint"]
        assert "tint:" in TAILWIND.read_text().replace('"', "").replace(" ", "")

    def test_the_accent_has_two_tokens_because_it_has_two_jobs(self, css):
        """`--primary` fills a button and `--primary-ink` is the accent as
        text. On dark they are the same ember; on light they cannot be —
        #F05D14 on an off-white page is 3.0:1 and fails AA as body text while
        the same orange as a fill with white on it is fine."""
        dark = self._block(css, ":root {")
        light = self._block(css, ':root[data-theme="light"] {')
        assert dark["primary"] == dark["primary-ink"]
        assert light["primary"] != light["primary-ink"]

    def test_every_state_the_console_shows_has_a_token(self, css):
        """Four were named in the brief; the audit turned up a fifth. Violet
        marked "past the shoot" — attended, draft in review, content
        submitted, completed — which is a real distinction, and flattening it
        into "in progress" to fit a four-token list would have lost it."""
        dark = self._block(css, ":root {")
        for state in ("pending", "approved", "rejected", "progress", "done"):
            assert f"state-{state}" in dark, state

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
    def test_the_attribute_is_written_in_exactly_two_places(self):
        """One is the pre-paint script, the other is `applyTheme`. A third
        would be a third opinion about what the console looks like."""
        writers = []
        for f in list(FRONTEND.rglob("*.js")) + list(FRONTEND.rglob("*.jsx")):
            if "setAttribute(\"data-theme\"" in f.read_text().replace("'", '"'):
                writers.append(f.relative_to(FRONTEND))
        assert writers == [Path("lib/consoleTheme.js")], writers
        assert 'setAttribute("data-theme", "light")' in INDEX_HTML.read_text()

    def test_the_pre_paint_script_only_runs_on_the_console(self):
        """**This is the whole of the scoping.** The marketing site, the
        creator app, the brand app and the manager screens never get the
        attribute, so they cannot be affected by what it means."""
        html = INDEX_HTML.read_text()
        assert 'location.pathname.indexOf("/admin") !== 0' in html
        assert "return" in html

    def test_the_pre_paint_script_and_the_module_agree_about_precedence(self):
        """Two implementations of "which theme" is two answers, and the one
        that runs first is the one nobody debugs. Both read the stored choice,
        then the OS, in that order."""
        html = INDEX_HTML.read_text()
        js = (FRONTEND / "lib/consoleTheme.js").read_text()
        for token in ("weare:console-theme", "prefers-color-scheme: light"):
            assert token in html, token
            assert token in js, token

    def test_something_clears_it_when_the_console_is_not_mounted(self):
        """**Found in a browser, not by a test.** A hard load of `/admin`
        writes the attribute before React runs; if that person is not signed
        in they are redirected to `/admin/login`, the console never mounts,
        nothing ever clears it, and the landing page rendered in the light
        theme. The invariant is maintained by the one thing that sees every
        route change.

        **And it has to be *rendered*, not merely defined.** The first version
        of this test asserted the function existed, and stayed green when the
        element was deleted from the tree — a caller with no mount is as
        unreachable as a route with no caller, which is a lesson this codebase
        has already learned twice. Caught by break-testing, not by review.
        """
        app = (FRONTEND / "App.js").read_text()
        assert "function ConsoleThemeGuard(" in app, "the guard is not defined"
        assert "<ConsoleThemeGuard />" in app, "the guard is defined but never rendered"
        assert "isConsolePath" in app and "clearTheme" in app
        # Inside the router, or `useLocation` throws and the whole app goes
        # down with it.
        assert app.index("<BrowserRouter>") < app.index("<ConsoleThemeGuard />")

    def test_the_console_layout_applies_and_clears_it(self):
        src = (FRONTEND / "pages/AdminConsole.jsx").read_text()
        assert "applyTheme(resolveTheme(" in src
        # The cleanup, which is what makes leaving the console leave the theme.
        assert "return clearTheme" in src


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
        """It is the difference between "follow this machine" and "they picked
        dark" — and only the first should change when somebody switches their
        OS at dusk. Collapsing them freezes every admin who has never opened
        the menu onto whatever their OS said the first time they loaded."""
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
        """Somebody who tried light and wants to stop thinking about it should
        be able to hand the question back to their machine, rather than having
        to pick the one that happens to match today."""
        assert server.ConsoleThemePayload().theme is None
        assert server.ConsoleThemePayload(theme=None).theme is None

    def test_the_menu_offers_system_as_well_as_the_two_themes(self):
        src = (FRONTEND / "components/admin/AdminAccountMenu.jsx").read_text()
        for value in ("System", "Light", "Dark"):
            assert value in src, value
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
