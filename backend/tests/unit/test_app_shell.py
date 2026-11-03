"""The app's shell and its visual system — "Option B · Warm".

Every signed-in surface navigates from one navy sidebar, built from one set
of parts (`components/app/SideNav.jsx`): `AppShell` assembles it for the
brand, the creator and the manager, and the console's `AdminSidebar`
assembles it around its own sections. The visual system under it is tokens —
the warm ground, the card shadow, five pill tones, three action tints, the
button's corner and weight — so the colour sweeps hold and the console's dark
set reads through the same components.

What is held here:

* the tokens exist, on both sets, and every ink is AA on its own wash;
* the app scope picks them up (ground, no grain, 12px/700 buttons, no top bar
  from `md`), and the public site keeps its own;
* the layout route wraps every app path outside the console and no public
  one; the shared `Navbar` renders nothing inside a shell;
* the sidebar links only to pages that exist, and the brand's has no
  creator directory;
* the red button is accent-ink, not the brand red, because white on the brand
  red is 3.76:1.
"""
from __future__ import annotations

import re

from app_surface import APP_DIR_REACHED_FROM_PUBLIC, SRC, code_of, is_app_path

FRONTEND = SRC.parent
CSS = (SRC / "index.css").read_text()
TAILWIND = (FRONTEND / "tailwind.config.js").read_text()
APP = (SRC / "App.js").read_text()
SIDENAV = code_of((SRC / "components" / "app" / "SideNav.jsx").read_text())
SHELL = code_of((SRC / "components" / "app" / "AppShell.jsx").read_text())
UI = code_of((SRC / "components" / "app" / "ui.jsx").read_text())


def _lum(hex_):
    def ch(c):
        c = int(c, 16) / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    h = hex_.lstrip("#")
    r, g, b = (ch(h[i:i + 2]) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _light_block():
    i = CSS.index(':root,\n    [data-surface="light"] {')
    return CSS[i:CSS.index("\n    }\n", i)]


def _dark_block():
    i = CSS.index('[data-surface="dark"],\n    :root[data-theme="dark"] {')
    return CSS[i:CSS.index("\n    }\n", i)]


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


class TestTokens:
    NEW = ("--state-due", "--state-due-wash", "--state-info", "--state-info-wash", "--app-ground",
           "--wash-red", "--wash-navy", "--wash-cream", "--wash-warm", "--shadow-card")

    def test_every_new_token_is_on_both_sets(self):
        light, dark = _light_block(), _dark_block()
        for token in self.NEW:
            assert f"{token}:" in light, f"{token} missing on light"
            assert f"{token}:" in dark, f"{token} missing on dark"

    def test_the_ground_is_the_boards_warm_one(self):
        assert "--app-ground: 40 27.3% 93.5%; /* #F3F0EA */" in _light_block()

    def test_each_pill_ink_is_aa_on_its_own_wash(self):
        """The boards' pills, measured. "Due soon" is the amber the payouts
        tile turns, and a word on it has to be readable."""
        pairs = {
            "due": ("#8A5A00", "#FFF1D6"),
            "info": ("#26344D", "#EBEFF6"),
            "good": ("#1C7A4A", "#E7F5EE"),
            "warn": ("#B3242C", "#FBE9EA"),
        }
        for name, (ink, wash) in pairs.items():
            assert ratio(ink, wash) >= 4.5, (name, round(ratio(ink, wash), 2))
        light = _light_block()
        assert "#8A5A00" in light and "#FFF1D6" in light
        assert "#26344D" in light and "#EBEFF6" in light

    def test_the_card_shadow_is_navy_and_a_token(self):
        line = re.search(r"--shadow-card:\s*([^;]+);", _light_block()).group(1)
        assert "hsl(var(--brand-navy) / 0.04)" in line and "hsl(var(--brand-navy) / 0.35)" in line
        assert 'card: "var(--shadow-card)"' in TAILWIND

    def test_tailwind_names_them(self):
        for name in ('"wash-red"', '"wash-navy"', '"wash-cream"', '"wash-warm"'):
            assert name in TAILWIND, name
        assert 'due: "hsl(var(--state-due) / <alpha-value>)"' in TAILWIND
        assert 'info: "hsl(var(--state-info) / <alpha-value>)"' in TAILWIND
        assert 'button: "var(--btn-radius)"' in TAILWIND


# ---------------------------------------------------------------------------
# The scope picks them up
# ---------------------------------------------------------------------------


class TestTheAppScope:
    def test_the_ground_is_redefined_on_the_light_set_only(self):
        m = re.search(r'html\[data-surface="app"\]:not\(\[data-theme="dark"\]\)\s*\{([^}]*)\}', CSS)
        assert m and "--background: var(--app-ground);" in m.group(1)

    def test_buttons_are_12px_and_700_in_the_app_and_unchanged_outside_it(self):
        app = re.search(r'\[data-surface="app"\]\s*\{\s*--btn-radius:[^}]*\}', CSS).group(0)
        assert "--btn-radius: 12px;" in app and "--btn-weight: 700;" in app
        assert "--btn-radius: var(--radius-md);" in CSS and "--btn-weight: 500;" in CSS
        button = (SRC / "components" / "ui" / "button.jsx").read_text()
        assert "rounded-button" in button and "font-[var(--btn-weight)]" in button
        assert "rounded-md" not in button.split("const buttonVariants")[1].split("variants:")[0]

    def test_no_grain_in_the_app(self):
        assert re.search(r'\[data-surface="app"\] \.grain-page\s*\{\s*background-image: none;', CSS)

    def test_there_is_no_top_bar_to_clear_from_md(self):
        """Everything sticky clears `--nav-h`, which is 0 inside the app from
        `md` — the navigation is a sidebar there. A literal `top-16` left
        behind would leave a 64px gap above a pinned bar."""
        assert re.search(r'@media \(min-width: 768px\)\s*\{\s*\[data-surface="app"\]\s*\{\s*--nav-h: 0px;', CSS)
        dense = (SRC / "components" / "data" / "DenseView.jsx").read_text()
        assert "top-16" not in code_of(dense)
        assert dense.count("top-[var(--nav-h)]") == 3
        assert "top-16" not in code_of((SRC / "components" / "admin" / "console" / "Sidebar.jsx").read_text())


# ---------------------------------------------------------------------------
# The layout route
# ---------------------------------------------------------------------------


def _shell_block():
    """From the shell's `<Route>` to the `</Route>` at its own indentation."""
    start = APP.index("                        <Route element={<AppShell />}>")
    end = APP.index("\n                        </Route>", start)
    return APP[start:end]


class TestTheLayoutRoute:
    def test_it_wraps_every_app_path_outside_the_console_and_nothing_public(self):
        block = _shell_block()
        inside = re.findall(r'path="([^"]+)"', block)
        assert inside, "nothing inside the shell"
        for path in inside:
            assert is_app_path(path), f"{path} is a public page inside the app's shell"
            assert not path.startswith("/admin"), "the console has its own shell"
        rest = APP.replace(block, "")
        for path in re.findall(r'^\s{24}path="([^"]+)"', rest, flags=re.M):
            if is_app_path(path):
                assert path.startswith("/admin"), f"{path} is an app page outside the shell"

    def test_it_is_lazy_and_its_own_chunk(self):
        assert re.search(r'const AppShell = load\(\(\) => import\(/\* webpackChunkName: "app-shell" \*/', APP)

    def test_it_holds_the_column_while_a_page_downloads(self):
        assert "<Suspense fallback={<ContentFallback />}>" in SHELL

    def test_the_shared_navbar_renders_nothing_inside_a_shell(self):
        nav = (SRC / "components" / "Navbar.jsx").read_text()
        assert "export const Navbar = (props) => (useInShell() ? null : <SiteNavbar {...props} />);" in nav
        assert "<ShellContext.Provider value={true}>" in SHELL
        console = (SRC / "pages" / "AdminConsole.jsx").read_text()
        assert "<ShellContext.Provider value={true}>" in console
        assert "<Navbar" not in code_of(console)

    def test_a_public_page_reaches_only_the_context(self):
        assert not APP_DIR_REACHED_FROM_PUBLIC, APP_DIR_REACHED_FROM_PUBLIC


# ---------------------------------------------------------------------------
# The sidebar
# ---------------------------------------------------------------------------


def _nav_targets():
    body = SHELL[SHELL.index("export function shellNavFor"):SHELL.index("export { useShellBadges }")]
    return body, re.findall(r'to: "([^"]+)"', body)


class TestTheSidebar:
    def test_it_links_only_to_pages_that_exist(self):
        """The boards draw "Campaigns", "Applicants", "Content" and
        "Payments" for a brand. None is a page here, so none is a link."""
        _, targets = _nav_targets()
        routed = set(re.findall(r'path="([^"]+)"', APP))
        for to in targets:
            assert to in routed or to == "/admin/queue", f"the sidebar links to {to}, which routes nowhere"

    def test_the_brand_has_no_creator_directory(self):
        body, targets = _nav_targets()
        brand = body[body.index("if (isBrandSide(role))"):body.index("return [", body.index("if (isBrandSide(role))") + 40)]
        assert "/brand/creators" not in brand and '"Creators"' not in brand
        assert "/brand/creators" not in targets

    def test_it_is_the_navy_frame_with_the_boards_details(self):
        frame = SIDENAV[SIDENAV.index("export function SideNavFrame"):SIDENAV.index("export function SideNavLogo")]
        assert 'data-surface="inverse"' in frame and "hidden" in frame and "md:flex" in frame
        item = SIDENAV[SIDENAV.index("export function SideNavItem"):SIDENAV.index("export function SideNavAccount")]
        assert "font-semibold" in item and "bg-tint/10" in item, "the white-10% pill on the current item"
        badge = SIDENAV[SIDENAV.index("export function SideNavBadge"):SIDENAV.index("export function SideNavItem")]
        assert "bg-urgent" in badge and "text-brand-white" in badge
        assert "export function SideNavHeading" in SIDENAV and "export function SideNavAccount" in SIDENAV

    def test_the_console_is_drawn_from_the_same_parts(self):
        console = code_of((SRC / "components" / "admin" / "console" / "Sidebar.jsx").read_text())
        for part in ("<SideNavFrame", "<SideNavLogo", "<SideNavHeading", "<SideNavAccount"):
            assert part in console, part
        assert "export const SECTION_GROUP" in console

    def test_a_count_comes_from_a_page_never_from_a_fetch_of_its_own(self):
        assert "api." not in SHELL and "api." not in SIDENAV
        context = (SRC / "components" / "app" / "shellContext.js").read_text()
        assert "export function useShellBadges" in context
        assert "api." not in code_of(context)


# ---------------------------------------------------------------------------
# The primitives
# ---------------------------------------------------------------------------


class TestThePrimitives:
    def test_the_red_button_is_the_urgent_fill_with_a_white_word(self):
        """White on the brand red is 3.76:1; on #C41E27 it is 5.90:1. A
        constant token rather than `accent-ink`, because the navy chrome
        redefines `accent-ink` to the brand red — a red button inside the
        navy panel would otherwise be the failing pair."""
        button = (SRC / "components" / "ui" / "button.jsx").read_text()
        urgent = re.search(r'urgent:\s*"([^"]+)"', button).group(1)
        assert "bg-urgent" in urgent and "text-brand-white" in urgent
        assert "--urgent: 356.7 73.5% 44.3%;" in CSS
        inverse = CSS[CSS.index('[data-surface="inverse"] {'):]
        inverse = inverse[:inverse.index("}")]
        assert "--urgent" not in inverse, "the navy chrome must not redefine the urgent fill"
        assert round(ratio("#FFFFFF", "#C41E27"), 2) >= 4.5
        assert round(ratio("#FFFFFF", "#FF2731"), 2) < 4.5

    def test_an_action_card_carries_one_button_tinted_by_urgency(self):
        card = UI[UI.index("export function ActionCard"):UI.index("export function ActionButton")]
        assert card.count("{action}") == 1
        assert '"bg-wash-red"' in card and '"bg-wash-navy"' in card
        btn = UI[UI.index("export function ActionButton"):UI.index("export function StatTile")]
        assert '"urgent"' in btn and '"solid"' in btn

    def test_pills_have_five_tones_and_due_is_amber(self):
        tones = UI[UI.index("export const PILL_TONE"):UI.index("};", UI.index("export const PILL_TONE"))]
        for tone in ("good:", "warn:", "info:", "due:", "neutral:"):
            assert tone in tones, tone
        assert "bg-state-due-wash text-state-due" in tones

    def test_the_card_is_white_20px_no_border_and_the_shadow_token(self):
        card = UI[UI.index("export function AppCard"):UI.index("export function CardHeading")]
        assert "rounded-lg bg-card" in card and "shadow-card" in card and "border" not in card

    def test_the_ai_card_needs_the_switch_and_a_summary(self):
        ai = UI[UI.index("export function AiSummaryCard"):]
        assert 'if (!aiLive("campaignSummary")) return null;' in ai
        assert "if (typeof text !== \"string\" || !text.trim()) return null;" in ai
        assert "bg-wash-cream" in ai and "Sparkles" in ai

    def test_the_sparkline_draws_once_and_invents_nothing(self):
        spark = UI[UI.index("export function Sparkline"):UI.index("export function AiSummaryCard")]
        assert "values.length < 2" in spark
        assert "dash-draw" in spark and "dash-after-line" in spark
        assert re.search(r"@media \(prefers-reduced-motion: reduce\)\s*\{\s*\.dash-rise,\s*\.dash-grow,\s*\.dash-draw,\s*\.dash-after-line", CSS)
