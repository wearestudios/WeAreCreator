"""The authenticated product's motion layer.

The complaint these answer is that the app was *snappy in a bad way*: screens
cut rather than settled, lists appeared all at once the instant a fetch landed,
and a button did nothing until the server replied. None of that is slow — it is
abrupt, which reads as cheap and, on a bad connection, as broken.

**What can honestly be tested from here, and what cannot.** These read sources
and run the pure arithmetic. They can hold the rules that actually rot: one
easing curve rather than six, a duration band, a stagger cap, transforms and
opacity only, a reduced-motion fallback that is the end state rather than a
faster animation, and the two traps below that were found by breaking things
rather than by reading them. They cannot tell you it *looks* right — that was
measured in a browser and the numbers are in the commit.

Two traps worth stating at the top, because both are invisible in review:

- **A CSS entrance animation fires when an element is created**, so a list that
  re-renders with new contents in reused DOM nodes never replays it. That is
  every filter and sort change — the one moment a reader most needs telling the
  set in front of them is different. `settleKey` is what remounts them.

- **`animation-delay` survives a `prefers-reduced-motion` backstop that only
  collapses `animation-duration`.** With `animation-fill-mode: both` the
  element then holds `opacity: 0` through its whole stagger, so a reader who
  asked for less motion gets exactly what they asked not to have: rows
  invisible and then popping in, one after another.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"
MOTION = FRONTEND / "lib" / "motion.js"
CSS = FRONTEND / "index.css"


def read(*parts):
    return FRONTEND.joinpath(*parts).read_text()


def code_of(*parts):
    """A source file with its comments stripped.

    Every rule here is about what the code does. The comments explaining a
    removed approach necessarily name it, so leaving them in makes a rule fail
    on its own justification — the arrangement `test_marketing_pages.py` and
    `test_admin_console.py` both use.
    """
    src = read(*parts)
    src = re.sub(r"\{/\*.*?\*/\}", "", src, flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


# The marketing site, which has its own motion layer and is excluded from all
# of this. `components/marketing/` is a directory; the five pages are not —
# they live in `pages/` beside the authenticated ones, so they have to be named.
MARKETING_PAGES = {
    "Landing.jsx", "ForBrands.jsx", "ForCreators.jsx",
    "HowItWorks.jsx", "WhyWeAre.jsx", "NotFound.jsx",
}


def app_sources():
    """Every authenticated source file."""
    for path in sorted(FRONTEND.rglob("*")):
        if path.suffix not in (".js", ".jsx") or not path.is_file():
            continue
        if "marketing" in path.relative_to(FRONTEND).parts:
            continue
        if path.name in MARKETING_PAGES:
            continue
        yield path


def const(name, src=None):
    src = src if src is not None else MOTION.read_text()
    return re.search(rf"{name} = (\d+)", src).group(1)


def durations():
    block = re.search(r"export const DUR = \{(.*?)\};", MOTION.read_text(), re.S).group(1)
    return {k: int(v) for k, v in re.findall(r"(\w+):\s*(\d+)", block)}


# ---------------------------------------------------------------------------
# 9 & 14. One curve, one band
# ---------------------------------------------------------------------------


def test_there_is_one_easing_curve_and_it_is_defined_once():
    """Six easings read as six different products.

    The curve lives in `index.css` as `--weare-ease` and is mirrored in
    `motion.js` for anything that needs the string. A second cubic-bezier
    anywhere under the authenticated product is a second answer.
    """
    curve = "cubic-bezier(0.22, 1, 0.36, 1)"
    assert f"--weare-ease: {curve}" in CSS.read_text()
    assert curve in MOTION.read_text()

    offenders = []
    for path in app_sources():
        if path in (MOTION,):
            continue
        for found in re.findall(r"cubic-bezier\([^)]*\)", code_of(*path.relative_to(FRONTEND).parts)):
            if found.replace(" ", "") != curve.replace(" ", ""):
                offenders.append(f"{path.name}: {found}")
    assert not offenders, f"a second easing curve: {offenders}"


@pytest.mark.parametrize("name", ["settle", "route"])
def test_every_duration_is_in_the_band(name):
    """180–220ms. Below 180 an entrance reads as a flicker; above 220 the
    reader is waiting for the screen rather than reading it — and on a list
    that wait is paid forty times a day."""
    ms = durations()[name]
    assert 180 <= ms <= 220, f"{name}: {ms}ms"


def test_the_css_and_the_constants_agree():
    """`motion.js` exports the durations so a test can read them without
    parsing a stylesheet, which makes them a second copy. A drift test is the
    price of that, the same arrangement `followerTiers.js` pays."""
    css = CSS.read_text()
    for name, ms in durations().items():
        assert f"--weare-{name}: {ms}ms" in css, name


def test_only_transforms_and_opacity_are_animated():
    """Height, width, top and colour force layout or paint on every frame. The
    audience is a mid-range Android on Indian mobile data."""
    block = re.search(r"@keyframes weare-settle \{(.*?)\n\}", CSS.read_text(), re.S).group(1)
    animated = set(re.findall(r"^\s*([a-z-]+):", block, re.M))
    assert animated <= {"opacity", "transform"}, animated
    # translate3d rather than translateY: it promotes to a layer on every
    # engine, including the ones that will not composite a 2D translate.
    assert "translate3d" in block


# ---------------------------------------------------------------------------
# 10. The stagger, and the cap that makes it safe on a list
# ---------------------------------------------------------------------------


def test_the_stagger_is_small_and_capped():
    """**The cap is the whole reason a stagger is safe on a list.**

    Without it a 200-row table cascades for six seconds and the rows somebody
    scrolled to are the last to exist. With it the list has finished settling
    at 440ms however long it is.
    """
    step, cap = int(const("STAGGER_MS")), int(const("STAGGER_CAP"))
    assert step <= 40, "a stagger this wide assembles a list rather than settling it"
    assert cap <= 12, "past a screenful nobody is watching rows arrive"
    assert cap * step + max(durations().values()) <= 500


def test_the_delay_is_clamped_at_both_ends():
    """Driven rather than read. A negative index would produce a negative
    delay, which starts the animation part-way through — the row appears
    already half faded."""
    src = code_of("lib", "motion.js")
    assert "Math.min(Math.max(index, 0), STAGGER_CAP)" in src


def test_index_zero_adds_no_inline_style():
    """`animationDelay: "0ms"` on every first row is an attribute on every
    list in the product that does nothing."""
    assert "return steps ? {" in code_of("lib", "motion.js")


def test_a_list_settles_again_when_the_set_is_replaced():
    """**The trap this layer exists around.**

    A CSS entrance animation fires when an element is *created*. React reuses a
    row's DOM node across a re-render, so a filter change swaps the contents of
    rows that never move — and the one moment a reader most needs to be told
    the set is different is the moment nothing happens. `settleKey` remounts
    them.

    Item 10 asks for this on first load *and* on filter or sort changes, and
    those are the same event as far as a reader is concerned.
    """
    settle = code_of("components", "motion", "Settle.jsx")
    assert "key={settleKey}" in settle

    table = code_of("components", "admin", "console", "DataTable.jsx")
    # The stamp carries the caller's filters *and* the sort, and row identity
    # within one stamp is preserved so an optimistic patch does not remount.
    assert "[settleKey, sort?.key, sort?.dir].join" in table
    assert "key={`${stamp}:${rowKey(row, index)}`}" in table


def test_the_feed_passes_everything_that_changes_the_set():
    """The brief feed is the screen this matters most on: seven filters, a
    search box and a sort. A stamp missing one of them is a filter that
    silently does not settle."""
    src = code_of("pages", "Campaigns.jsx")
    stamp = re.search(r"const settleStamp = \[(.*?)\]", src, re.S).group(1)
    for field in ("city", "area", "category", "campaignType", "compensation", "budget", "sort"):
        assert field in stamp, field
    # The *debounced* query, not the live one: a settle per keystroke is the
    # flicker this whole layer exists to remove.
    assert "debouncedQ" in stamp and re.search(r"\bq\b,", stamp) is None


def test_a_windowed_table_does_not_settle():
    """Rows mount as you scroll into them, so a settle there is not content
    arriving — it is every row fading in under the reader's eye as they move,
    which is the popping this exists to remove."""
    table = code_of("components", "admin", "console", "DataTable.jsx")
    assert "const settles = !virtual" in table


# ---------------------------------------------------------------------------
# 9. Route transitions, and the remount that would have cost a refetch
# ---------------------------------------------------------------------------


def test_the_route_settle_does_not_remount_the_tree():
    """**The version that works in a demo and is wrong here.**

    `<div key={pathname}>` replays a CSS entrance for free. It also unmounts
    and rebuilds whatever is inside it — and `/admin` is a *layout* route
    owning the sidebar, the badge counts and eighteen sections rendered into an
    `<Outlet>`. Keying on the path would refetch all of it every time somebody
    pressed a section, and drop the collapse preference, for a fade.

    So the wrapper is stable and the animation is restarted by hand: remove the
    class, force a reflow, add it back.
    """
    src = code_of("components", "motion", "RouteFade.jsx")
    assert "key={pathname}" not in src
    assert 'classList.remove("weare-route")' in src
    assert "void el.offsetWidth" in src, "without a reflow the class swap coalesces"
    assert 'classList.add("weare-route")' in src
    # Layout effect, or the new route paints at full opacity for a frame and
    # the fade starts from it — a flash rather than an arrival.
    assert "useLayoutEffect" in src


def test_the_route_settle_is_keyed_on_the_surface_not_the_path():
    """Moving between surfaces is a new screen. Moving between console
    sections is not — fading the sidebar and the header every time somebody
    presses a section animates the navigation they are trying to use."""
    src = code_of("components", "motion", "RouteFade.jsx")
    assert "surfaceOf" in src
    assert 'split("/")[1]' in src
    # And the console's own half, on the Outlet, where only content changes.
    console = code_of("pages", "AdminConsole.jsx")
    assert "<Settle settleKey={pathname}>" in console


def test_the_marketing_pages_keep_the_cut():
    """They stagger every section in on scroll already. Two motion layers on
    one page is the same pixels animated twice at two durations, on the page
    most likely to be opened on mobile data."""
    src = code_of("components", "motion", "RouteFade.jsx")
    assert "MARKETING_PATHS" in src
    assert "isAnimatedRoute" in src


def test_the_route_settle_sits_inside_suspense_and_the_boundary():
    """Inside Suspense, so the animation lands on the route somebody navigated
    to rather than on the skeleton standing in for it. Inside the route
    boundary, so a chunk that fails to load reaches a page saying so rather
    than a fading blank — and never takes the impersonation banner with it."""
    app = code_of("App.js")
    order = [app.index(x) for x in ("<ImpersonationBanner />", "<RouteBoundary>",
                                    "<Suspense", "<RouteFade>", "<Routes>")]
    assert order == sorted(order), "RouteFade is nested in the wrong place"


# ---------------------------------------------------------------------------
# 13. Numbers that travel
# ---------------------------------------------------------------------------


def test_a_number_never_renders_a_partial_value():
    """Every formatter rounds, because `value` is a float on every frame but
    the last. `format={String}` is the obvious mistake and it prints
    "3.7142857" in a badge — which is why the two formatters are exported
    rather than written per call site."""
    src = code_of("lib", "motion.js")
    assert "export const INT = (n) => String(Math.round(n));" in src
    assert "GROUPED = (n) => Math.round(n).toLocaleString" in src
    for path in app_sources():
        code = code_of(*path.relative_to(FRONTEND).parts)
        assert "format={String}" not in code, path.name


def test_a_count_writes_text_rather_than_calling_setstate():
    """The lesson `CampaignFilm` records: a state update per frame re-renders
    the whole subtree sixty times a second to change four characters, and on a
    dashboard that subtree is the card the number sits in."""
    src = code_of("components", "motion", "AnimatedNumber.jsx")
    assert "useState" not in src
    assert "requestAnimationFrame" in src
    assert "cancelAnimationFrame" in src
    # **Inside the frame loop, not only on the first paint.** Break-testing
    # found this: there are two writes, and asserting the string appears at
    # all is satisfied by the landing branch alone — so the tween could stop
    # writing anything and the number would simply snap, which is the exact
    # behaviour this component exists to remove.
    step = re.search(r"const step = \(now\) => \{(.*?)\n        \};", src, re.S)
    assert step, "the frame loop moved"
    assert "textContent = format(at)" in step.group(1)


def test_the_first_paint_is_the_real_value():
    """Counting up from zero on arrival is the marketing site's `CountUp`,
    which is right for a proof figure somebody is being sold and wrong for a
    working screen — an admin opening the queue should not watch "0 of 14"
    become "14"."""
    src = code_of("components", "motion", "AnimatedNumber.jsx")
    assert "from === null" in src, "no first-paint branch"
    assert 'typeof value === "number" ? format(value) : "—"' in src


def test_the_tween_arithmetic():
    """Pure, so it can be checked without a browser."""
    path = MOTION.read_text()
    # Ends land exactly, and nothing overshoots in between — an ease that
    # overshoots on a count shows a number the data never had.
    assert "const clamped = t <= 0 ? 0 : t >= 1 ? 1 : t;" in path
    assert "1 - Math.pow(1 - clamped, 3)" in path

    def tween(a, b, t):
        c = 0 if t <= 0 else 1 if t >= 1 else t
        return a + (b - a) * (1 - (1 - c) ** 3)

    assert tween(0, 100, 0) == 0
    assert tween(0, 100, 1) == 100
    assert tween(0, 100, -5) == 0 and tween(0, 100, 5) == 100
    assert all(0 <= tween(0, 100, t / 20) <= 100 for t in range(21))
    # Monotonic: a count that goes backwards mid-travel is a glitch.
    seq = [tween(10, 90, t / 20) for t in range(21)]
    assert seq == sorted(seq)


def test_a_count_lands_inside_the_second():
    """`countDuration` is not a constant, because 0→3 and 0→48,000 are
    different journeys — a flat 600ms makes a three-step counter look broken
    and a long one look slow. It still has a ceiling: this is a number
    settling, not a slot machine."""
    src = MOTION.read_text()
    assert "Math.min(700" in src

    def dur(a, b):
        d = abs(b - a)
        return 0 if d == 0 else 260 if d <= 3 else min(700, 300 + d * 6)

    assert dur(5, 5) == 0
    assert dur(0, 2) == 260
    assert dur(0, 500_000) == 700


# ---------------------------------------------------------------------------
# 12. Optimistic mutations
# ---------------------------------------------------------------------------


def test_the_control_goes_pending_before_the_request():
    """Not when the request is sent, not when the first byte comes back. On
    the connection a campaign manager actually has, a button that waits reads
    as dead, and the second press is a second row in somebody's queue."""
    src = code_of("lib", "useOptimistic.js")
    pending_at = src.index("setPending((p) => ({ ...p, [id]: true }))")
    request_at = src.index("await request()")
    assert pending_at < request_at


def test_a_failure_rolls_back_and_says_so():
    """Silently reverting is worse than never having moved: somebody who
    watched a row change and looked away believes it changed."""
    src = code_of("lib", "useOptimistic.js")
    assert "flashFailure" in src
    assert "ROLLBACK_FLASH_MS" in src
    # The patch comes off in the catch, not in the finally — a success has to
    # keep it until the refetch lands, or the row flicks back to its old value
    # in the gap between the response and the new list.
    catch_at = src.index("} catch (err) {")
    finally_at = src.index("} finally {")
    drop_at = src.index("setPatches((s) => {")
    assert catch_at < drop_at < finally_at


def test_a_refetch_beats_an_optimistic_patch():
    """An override that outlived its refetch would pin a stale value on screen
    forever, which is the failure mode of every hand-rolled version of this."""
    src = code_of("lib", "useOptimistic.js")
    assert "setPatches((current) => (Object.keys(current).length ? {} : current));" in src
    assert "}, [rows]);" in src


def test_it_never_rethrows():
    """Every caller would have to catch it to avoid an unhandled rejection,
    and `globalErrors.js` would toast the ones that forgot — on top of the
    message the caller already showed."""
    src = code_of("lib", "useOptimistic.js")
    assert "throw" not in src
    assert "return false;" in src


def test_the_action_queue_settles_its_row_on_the_click():
    """The exemplar, and the highest-traffic decision surface in the product:
    working the queue is "decide, next, decide, next", and the old shape put a
    network round trip between those two words."""
    src = code_of("components", "admin", "ActionQueue.jsx")
    assert "useOptimisticRows" in src
    assert "{ settled: true }" in src
    assert "!i.settled" in src, "the patch is applied but nothing reads it"
    # The rollback, visible on the row rather than only in a toast.
    assert "rowClass=" in src and "failed[i.id]" in src
    # A 409 means somebody else moved it, so putting the row back would be a
    # lie — it is gone.
    assert "e?.response?.status === 409" in src


def test_no_full_page_blocking_spinner_was_reintroduced():
    """Skeletons are the rule here and have been since `PageSkeleton.jsx`: a
    centred spinner in its own full-viewport box means the page does not
    arrive so much as replace a different one."""
    offenders = []
    for path in app_sources():
        code = code_of(*path.relative_to(FRONTEND).parts)
        for line in code.splitlines():
            if "min-h-screen" in line and "animate-spin" in line:
                offenders.append(path.name)
    assert not offenders, f"full-page spinners: {offenders}"


# ---------------------------------------------------------------------------
# 14. Reduced motion, and the delay trap
# ---------------------------------------------------------------------------


def test_reduced_motion_lands_on_the_end_state_not_a_faster_animation():
    css = CSS.read_text()
    # The *backstop* block, not the marquee's own one two rules above it — it
    # is the one that opens with the universal selector.
    block = re.search(
        r"@media \(prefers-reduced-motion: reduce\) \{\s*\*,(.*?)\n\}", css, re.S
    )
    assert block, "the backstop moved"
    body = block.group(1)
    assert ".weare-settle" in body and ".weare-route" in body
    assert "animation: none !important" in body
    assert "opacity: 1" in body and "transform: none" in body


def test_the_backstop_zeroes_the_delay_as_well_as_the_duration():
    """**The trap, and it is invisible in review.**

    The backstop collapses `animation-duration` and said nothing about delay.
    A staggered list sets an inline `animation-delay` per row, and with
    `animation-fill-mode: both` the element holds its `from` state — opacity 0
    — for the whole of it. A reader who asked for less motion would get
    precisely what they asked not to have: rows invisible and then popping in,
    one after another, with no tween in between.
    """
    css = CSS.read_text()
    backstop = re.search(
        r"@media \(prefers-reduced-motion: reduce\) \{\s*\*,.*?\n    \}", css, re.S
    ).group(0)
    assert "animation-delay: 0ms !important" in backstop
    assert "transition-delay: 0ms !important" in backstop


def test_the_reduced_motion_check_is_synchronous():
    """Read on first render so nothing animates for a frame before being told
    not to — the same reason `useWide` reads `matchMedia` synchronously."""
    src = code_of("lib", "motion.js")
    assert "window.matchMedia" in src
    assert "useEffect" not in src
    # A test renderer or an old browser has no matchMedia, and that reads as
    # "no preference expressed" rather than throwing on every screen.
    assert "catch {" in src


def test_will_change_is_released_when_the_animation_ends():
    """A promise to the compositor that costs memory per element. Left on,
    twenty rows keep twenty layers alive for the life of the screen."""
    css = CSS.read_text()
    assert "will-change: opacity, transform" in css
    assert ".weare-settle-done" in css
    settle = code_of("components", "motion", "Settle.jsx")
    assert "onAnimationEnd" in settle
    assert "weare-settle-done" in settle
    # Only the element's own animation, or a child finishing releases the
    # parent's layer mid-flight.
    assert "event.currentTarget === event.target" in settle


def test_transition_all_is_not_used_in_the_new_motion_layer():
    """It animates properties nobody chose, including layout ones. The design
    guidelines say so and the console already had this rule; the motion layer
    is where it would first be broken."""
    for name in ("Settle.jsx", "RouteFade.jsx", "AnimatedNumber.jsx"):
        assert "transition-all" not in code_of("components", "motion", name), name
    assert "transition-all" not in code_of("lib", "motion.js")


# ---------------------------------------------------------------------------
# The layering rule
# ---------------------------------------------------------------------------


def test_the_app_does_not_import_the_marketing_motion_layer():
    """Two layers, deliberately. The marketing one is framer-motion,
    scroll-driven and written for a page somebody reads once; this one is for
    screens somebody works in for an hour. A shared import is how the two
    budgets become one."""
    offenders = []
    for path in app_sources():
        if "motion" in path.parts and "components" in path.parts:
            continue
        code = code_of(*path.relative_to(FRONTEND).parts)
        if "marketing/motion" in code or "marketing/Reveal" in code:
            offenders.append(path.name)
    assert not offenders, f"marketing motion in the app: {offenders}"


def test_the_settle_is_css_rather_than_a_second_motion_library():
    """A CSS animation on transform and opacity is composited; a JS tween runs
    on the main thread next to React, which is where the jank on a mid-range
    Android comes from. It also keeps framer-motion out of the brand, manager
    and admin chunks, which the code-splitting work took down 33–58%."""
    for name in ("Settle.jsx", "RouteFade.jsx"):
        src = code_of("components", "motion", name)
        assert "framer-motion" not in src, name
    assert "framer-motion" not in code_of("lib", "motion.js")


def test_the_brief_feed_no_longer_carries_framer_motion():
    """It is the screen most likely to be opened on mobile data, and its cards
    were the one thing pulling the library into that path."""
    assert "framer-motion" not in code_of("pages", "Campaigns.jsx")
