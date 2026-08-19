"""The admin console's working surface.

The console is the one screen somebody sits in front of for an hour at a time,
and it used to be built like the rest of the product: cards, grain, entrance
motion, a horizontal tab strip, a filter set you lost every time you opened a
record. Those are right for a page a creator reads once and wrong for a tool.

What these tests hold:

- **Every list view is a table**, through one shared component. Cards are for
  things you look *at*; rows are for things you look *across*, and you cannot
  compare a follower count in card three with the one in card eleven.
- **One density scale, one row height.** 44px everywhere, `text-sm` for
  content and `text-xs` only for genuine metadata — which in practice means an
  uppercase eyebrow.
- **One semantic colour per state, with a word beside it.** Never colour
  alone, and never ember: ember is the primary action, and a status that
  borrowed it would make every row look like a call to action.
- **The console is calm.** No grain, no entrance animation, 150ms transitions.
- **The keyboard is a faster way to the same actions, never a way around a
  confirmation.** A rejection carries a reason the other person is told.

These read the frontend sources. Comments are stripped first, for the reason
`test_marketing_pages.py` gives: a rule about what must not appear fails on the
comment explaining why it must not appear.
"""
import re
from pathlib import Path

import pytest

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend"
ADMIN = FRONTEND / "src" / "components" / "admin"
CONSOLE = ADMIN / "console"


def read(path: Path) -> str:
    return path.read_text()


def code_of(path: Path) -> str:
    """A source file with its comments stripped."""
    src = read(path)
    src = re.sub(r"\{/\*.*?\*/\}", "", src, flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


def admin_sources():
    """Every admin console source, the shared kit included.

    Both extensions: the kit's tokens and hooks are `.js`, and a `.jsx`-only
    sweep let a 300ms transition through the calm rule — checked, by putting
    one there and watching this pass.
    """
    return sorted(
        p for p in ADMIN.rglob("*") if p.suffix in (".js", ".jsx") and p.is_file()
    )


# The list views. Each one used to be a grid of cards or a hand-rolled list.
LIST_VIEWS = [
    "AdminCreators.jsx",
    "AdminBrands.jsx",
    "AdminCampaigns.jsx",
    "AdminAudit.jsx",
    "Reviews.jsx",
    "ActionQueue.jsx",
    "Overview.jsx",
]


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", LIST_VIEWS)
def test_every_list_view_uses_the_shared_table(name):
    code = code_of(ADMIN / name)
    assert "console/DataTable" in code, f"{name} must render through DataTable"
    assert "<DataTable" in code


@pytest.mark.parametrize("name", LIST_VIEWS)
def test_no_list_view_hand_rolls_a_table(name):
    """A second table is a second set of decisions about sticky headers, row
    height and what a focused row looks like — and the console had five."""
    code = code_of(ADMIN / name)
    assert "<table" not in code, f"{name} builds its own <table>"


def test_overview_keeps_cards_only_for_its_stat_tiles():
    """The one place cards survive, because a stat tile is a thing you look at."""
    code = code_of(ADMIN / "Overview.jsx")
    grids = re.findall(r"grid grid-cols-\d[^\"]*", code)
    assert grids, "the stat tiles are a grid"
    for g in grids:
        assert "lg:grid-cols-6" in g, f"unexpected card grid on Overview: {g}"


def test_the_table_sorts_on_values_not_on_what_it_prints():
    """"24k" sorts as 24000, or "9k" ends up above it."""
    code = code_of(CONSOLE / "DataTable.jsx")
    assert "col.value || ((r) => r[col.key])" in code
    # An unmeasured value is not the smallest thing; it is unknown.
    assert "if (x == null) return 1;" in code
    assert "if (y == null) return -1;" in code


def test_long_lists_are_virtualised_and_short_ones_are_not():
    code = code_of(CONSOLE / "DataTable.jsx")
    assert "VIRTUALISE_ABOVE" in code
    assert "rows.length > VIRTUALISE_ABOVE" in code


def test_numeric_columns_are_right_aligned_with_tabular_figures():
    """Digits that do not line up cannot be compared down a column."""
    code = code_of(CONSOLE / "DataTable.jsx")
    assert "text-right tabular-nums" in code


def test_the_table_has_a_skeleton_shaped_like_itself():
    code = code_of(CONSOLE / "DataTable.jsx")
    assert "TableSkeleton" in code
    assert "if (loading) return <TableSkeleton" in code


# ---------------------------------------------------------------------------
# Density
# ---------------------------------------------------------------------------


def test_one_row_height_and_the_two_forms_of_it_agree():
    """`ROW_PX` is what virtualisation measures with; `ROW_H` is what renders."""
    code = code_of(CONSOLE / "tokens.js")
    assert 'ROW_H = "h-11"' in code
    assert "ROW_PX = 44" in code  # h-11 is 2.75rem is 44px


def test_text_xs_in_the_console_is_only_ever_metadata():
    """158 uses of `text-xs` was a console set in 12px. It is `text-sm` now,
    except for the uppercase eyebrows, which really are metadata."""
    offenders = []
    for path in admin_sources():
        # `tokens.js` is where the metadata step is defined; it is the one
        # place the string is the rule rather than a use of it.
        if path.name == "tokens.js":
            continue
        for i, line in enumerate(code_of(path).splitlines(), 1):
            if "text-xs" in line and "uppercase" not in line:
                offenders.append(f"{path.name}:{i}")
    assert not offenders, f"text-xs on non-metadata: {offenders[:10]}"


def test_the_density_scale_is_one_object():
    code = code_of(CONSOLE / "tokens.js")
    assert "export const DENSITY" in code
    for key in ("tight", "row", "panel"):
        assert f"{key}:" in code


# ---------------------------------------------------------------------------
# Colour
# ---------------------------------------------------------------------------


def test_status_colour_never_borrows_ember():
    """Ember is the primary action. A status wearing it makes every row look
    like a button."""
    tones = code_of(CONSOLE / "tokens.js")
    tones = tones[tones.index("STATUS_TONE") : tones.index("TONE_BY_STATE")]
    assert "ember" not in tones


def test_a_state_is_never_colour_alone():
    """Roughly one man in twelve cannot separate the amber from the green, and
    a screenshot pasted into a message loses whatever legend the screen had."""
    code = code_of(CONSOLE / "StatusTag.jsx")
    assert "labelFor" in code
    # The dot is decoration beside the word, so it is hidden from a reader.
    assert code.count("aria-hidden") >= 2


def test_one_tone_table_rather_than_one_per_screen():
    """A closed campaign read grey on one screen and red on the next because
    four files each decided for themselves."""
    code = code_of(CONSOLE / "tokens.js")
    for state in ("pending_review", "in_progress", "declined", "cancelled", "paid"):
        assert f"{state}:" in code, f"{state} has no tone"


# The lists with a state column. The audit log is the exception: an entry has
# no state of its own, only the change it recorded.
STATEFUL_VIEWS = [n for n in LIST_VIEWS if n != "AdminAudit.jsx"]


@pytest.mark.parametrize("name", STATEFUL_VIEWS)
def test_list_views_render_status_through_the_one_component(name):
    code = code_of(ADMIN / name)
    assert "StatusTag" in code, f"{name} draws its own status pill"
    # The four `meta` objects are what let a closed campaign read grey on one
    # screen and red on the next.
    assert "<Pill" not in code, f"{name} still has a hand-toned pill"


# ---------------------------------------------------------------------------
# Calm
# ---------------------------------------------------------------------------


def test_no_grain_anywhere_in_the_console():
    """The marketing site is printed paper; the console is a working surface."""
    offenders = [p.name for p in admin_sources() if "grain-" in code_of(p)]
    assert not offenders, f"grain in the console: {offenders}"


def test_the_console_shell_does_not_grain_the_page():
    code = code_of(FRONTEND / "src" / "pages" / "AdminConsole.jsx")
    assert "grain-page" not in code


def test_transitions_are_150ms_at_most():
    offenders = []
    for path in admin_sources():
        for i, line in enumerate(code_of(path).splitlines(), 1):
            for d in re.findall(r"duration-(\d+)", line):
                if int(d) > 150:
                    offenders.append(f"{path.name}:{i} duration-{d}")
    assert not offenders, f"slow transitions in the console: {offenders[:10]}"


def test_nothing_in_the_console_animates_in():
    """A list that animates in is a list you cannot read until it has finished,
    and an admin loads it forty times a day."""
    offenders = []
    for path in admin_sources():
        code = code_of(path)
        for marker in ("<Reveal", "<CountUp", "framer-motion", "animate-in"):
            if marker in code:
                offenders.append(f"{path.name}: {marker}")
    assert not offenders, f"entrance motion in the console: {offenders}"


def test_transition_all_is_never_used():
    """It animates properties nobody chose, including layout ones."""
    offenders = [p.name for p in admin_sources() if "transition-all" in code_of(p)]
    assert not offenders, offenders


# ---------------------------------------------------------------------------
# The keyboard
# ---------------------------------------------------------------------------


def test_typing_is_never_intercepted():
    """"j" in a search box is a letter, not a navigation."""
    code = code_of(CONSOLE / "useTableKeys.js")
    assert "export function isTyping" in code
    assert 'TYPING = new Set(["INPUT", "TEXTAREA", "SELECT"])' in code
    assert "isContentEditable" in code
    # A Radix dialog owns the keyboard while it is open.
    assert "role='dialog'" in code


def test_the_bindings_the_overlay_advertises_are_the_bindings_that_exist():
    hook = code_of(CONSOLE / "useTableKeys.js")
    overlay = code_of(CONSOLE / "ShortcutsOverlay.jsx")
    for key in ("ArrowDown", "ArrowUp", "Enter", "Escape"):
        assert key in hook
    for shown in ("Enter", "Esc", "A", "R", "?"):
        assert f'"{shown}"' in overlay
    # j/k are the vi pair, advertised as an alternative to the arrows.
    assert '"j"' in hook and '"k"' in hook
    assert '"j"' in overlay and '"k"' in overlay


def test_reject_by_keyboard_still_opens_the_reason_dialog():
    """The keyboard is a faster way to the reason box, never a way past it."""
    for name in ("Reviews.jsx", "AdminBrands.jsx", "AdminCampaigns.jsx"):
        code = code_of(ADMIN / name)
        assert "onReject:" in code, f"{name} binds no R"
        assert "ConfirmDialog" in code, f"{name} rejects without a dialog"
        # R reaches the same handler the button does, rather than a second one.
        after = code[code.index("onReject:") : code.index("onReject:") + 400]
        assert "reject(" in after, f"{name} binds R to something else"


def test_the_shortcuts_overlay_is_reachable_from_a_screen_with_no_table():
    """Overview and the detail pages have no list to bind "?" for them."""
    code = code_of(FRONTEND / "src" / "pages" / "AdminConsole.jsx")
    assert 'e.key === "?"' in code
    assert "isTyping(e)" in code


# ---------------------------------------------------------------------------
# State that survives
# ---------------------------------------------------------------------------


def test_working_filters_are_session_state_and_named_sets_are_not():
    """A filter set is a working context and should be gone tomorrow. A named
    one is a deliberate act and should still be there next week."""
    code = code_of(CONSOLE / "useListState.js")
    assert "window.sessionStorage" in code
    assert "window.localStorage" in code
    assert re.search(r"readJson\(window\.sessionStorage, SESSION_KEY", code)
    assert re.search(r"readJson\(window\.localStorage, SAVED_KEY", code)


@pytest.mark.parametrize(
    "name", ["AdminCreators.jsx", "AdminBrands.jsx", "AdminCampaigns.jsx", "AdminAudit.jsx"]
)
def test_every_filtered_list_remembers_its_filters(name):
    code = code_of(ADMIN / name)
    assert "useListState(" in code, f"{name} loses its filters on navigation"


def test_the_sidebar_and_the_router_read_one_section_list():
    """The strip was also the route table; the sidebar is too, or a section
    appears in one and not the other."""
    sidebar = code_of(CONSOLE / "Sidebar.jsx")
    shell = code_of(FRONTEND / "src" / "pages" / "AdminConsole.jsx")
    assert "export const ADMIN_SECTIONS" in sidebar
    assert "ADMIN_TABS = ADMIN_SECTIONS" in shell


def test_every_sidebar_section_has_a_route():
    sidebar = code_of(CONSOLE / "Sidebar.jsx")
    app = code_of(FRONTEND / "src" / "App.js")
    block = sidebar[sidebar.index("ADMIN_SECTIONS = [") : sidebar.index("\n];")]
    routes = re.findall(r'to: "([a-z-]*)"', block)
    assert len(routes) >= 10, f"the section list did not parse: {routes}"
    for to in routes:
        if not to:
            continue  # the index route
        assert f'path="{to}"' in app, f"sidebar section {to} routes nowhere"


# ---------------------------------------------------------------------------
# The peek panel
# ---------------------------------------------------------------------------


def test_the_peek_panel_always_offers_the_full_page():
    """A peek that quietly became the only way to see something would be a
    detail page with less in it."""
    code = code_of(CONSOLE / "PeekPanel.jsx")
    assert "Open full page" in code
    assert "href" in code


@pytest.mark.parametrize("name", LIST_VIEWS)
def test_row_click_opens_a_panel_rather_than_leaving_the_list(name):
    code = code_of(ADMIN / name)
    if name == "Overview.jsx":
        # Overview's row opens the campaign's applicants inline, which is the
        # panel it already had.
        assert "setOpenCampaign" in code
        return
    assert "PeekPanel" in code, f"{name} has no peek panel"


# ---------------------------------------------------------------------------
# Test ids
# ---------------------------------------------------------------------------


def test_the_new_controls_carry_ids():
    ids = read(FRONTEND / "src" / "constants" / "testIds" / "admin.js")
    for group in ("ADMIN_SIDEBAR", "ADMIN_TABLE", "ADMIN_PEEK", "ADMIN_SHORTCUTS"):
        assert f"export const {group}" in ids


def test_a_row_keeps_the_id_its_screen_already_had():
    """Changing the layout is not a reason to break "the element for creator X
    on the creator list"."""
    table = code_of(CONSOLE / "DataTable.jsx")
    assert "rowTestId" in table
    for name, expected in (
        ("AdminCreators.jsx", "IDS.tile("),
        ("AdminBrands.jsx", "IDS.row("),
        ("AdminCampaigns.jsx", "IDS.row("),
        ("AdminAudit.jsx", "IDS.row("),
    ):
        code = code_of(ADMIN / name)
        assert f"rowTestId={{(", f"{name} does not name its rows"
        assert expected in code, f"{name} changed its row id"
