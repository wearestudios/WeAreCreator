"""The creator's home, after the redesign.

The rule the layout answers to: **status, active work and the next action are
visible without scrolling.** The header opens with a photo big enough to say
whose page this is, the money counts up once, the live work sits directly
below and never goes behind a tab, and everything a creator consults rather
than acts on — suggestions, past pitches, the ledger — lives in tabbed drawers
under it.

These are source pins on the frontend, the same way the design-foundation
tests work: they hold the decisions, and the rendered behaviour (skeleton,
empty states, reduced motion, CLS 0.0000 at 390 and 1280) was verified by
driving the built page in a browser.
"""
from pathlib import Path

import pytest

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"


def read(*parts):
    return FRONTEND.joinpath(*parts).read_text()


# --- The header --------------------------------------------------------------


def test_the_photo_is_the_anchor_of_the_page():
    """h-28 on a phone rising to h-40 — a portrait, not a thumbnail. Both
    branches, because most creators start without a photo and the monogram
    must hold the same space."""
    src = read("components", "creator", "Hero.jsx")

    assert "h-28 w-28" in src and "md:h-40 md:w-40" in src
    assert src.count("md:h-40 md:w-40") >= 2, "the monogram fallback shrank"


def test_the_photo_box_is_reserved():
    """media-frame on the image branch: a slow photo is a surface, not a hole."""
    src = read("components", "creator", "Hero.jsx")

    assert "media-frame" in src


def test_the_headline_stats_are_all_here():
    """Lifetime earned, campaigns completed, pending — the three numbers the
    brief names, each with its stable testid."""
    src = read("components", "creator", "Hero.jsx")

    assert "IDS.lifetime" in src
    assert "IDS.completed" in src
    assert "IDS.pending" in src


def test_the_money_counts_up_and_respects_reduced_motion():
    hero = read("components", "creator", "Hero.jsx")
    shared = read("components", "creator", "shared.jsx")

    assert "<CountUp" in hero
    count_up = shared[shared.index("export const CountUp"):]

    assert "useReducedMotion" in count_up.split("export const Money")[0]
    assert "played" in count_up, "a background refresh must not restart it"


# --- The shape of the page ---------------------------------------------------


def test_active_work_never_goes_behind_a_tab():
    """The tabs hold what a creator consults; the live work is why the page
    gets opened, and a venue address in a drawer is a creator lost on a
    footpath. Structurally: ActiveCampaigns mounts before the Tabs block."""
    src = read("pages", "Dashboard.jsx")

    assert src.index("<ActiveCampaigns") < src.index("<Tabs ")


def test_the_drawers_are_tabs_not_a_stack():
    src = read("pages", "Dashboard.jsx")

    for drawer in ('value="suggested"', 'value="applications"', 'value="earnings"'):
        assert drawer in src
    assert "TabsContent" in src


def test_each_drawer_keeps_its_own_error_boundary():
    """A bad earnings row must not blank the suggestions next to it — the rule
    the stacked layout already lived by, carried into the tabs."""
    src = read("pages", "Dashboard.jsx")
    tabs = src[src.index("<Tabs ") :]

    assert tabs.count("SafeSection") >= 3


def test_the_tab_strip_scrolls_rather_than_wraps():
    """Three labels with counts at 390px: wrapping stacks the strip and eats
    the fold this redesign exists to protect."""
    src = read("pages", "Dashboard.jsx")

    assert "overflow-x-auto" in src


def test_status_banners_stay_outside_the_tabs():
    """A blocked account is not a section, it is the situation."""
    src = read("pages", "Dashboard.jsx")

    assert src.index("<StatusBanners") < src.index("<Tabs ")


def test_the_completeness_nudge_stays_outside_too():
    src = read("pages", "Dashboard.jsx")

    assert src.index("<Completeness") < src.index("<Tabs ")


# --- Texture -----------------------------------------------------------------


def test_the_active_card_carries_the_campaign_cover():
    """A slim 16:5 slice, capped on desktop — aspect-ratio yields to
    max-height, which is what stops a full-width card growing a 350px wall of
    tint."""
    src = read("components", "creator", "ActiveCampaigns.jsx")

    assert "<CampaignCover" in src
    assert "aspect-[16/5]" in src
    assert "md:max-h-44" in src


def test_the_suggested_tiles_carry_covers_too():
    assert "<CampaignCover" in read("components", "creator", "Suggested.jsx")


def test_the_brand_mark_travels_with_the_brand_name():
    for name in ("ActiveCampaigns.jsx", "Suggested.jsx"):
        assert "BrandAvatar" in read("components", "creator", name)


# --- Motion ------------------------------------------------------------------


def test_entrances_are_staggered_and_reduced_motion_is_respected():
    shared = read("components", "creator", "shared.jsx")
    reveal = shared[shared.index("export const Reveal"):shared.index("export const CountUp")]

    assert "useReducedMotion" in reveal
    assert "delay" in reveal and "index" in reveal


def test_the_tracker_fill_animates_as_one_stroke():
    src = read("components", "creator", "ActiveCampaigns.jsx")

    assert "scaleX" in src
    assert "useReducedMotion" in src


def test_nothing_on_the_page_loops():
    """Entrance-only: no infinite repeat anywhere on the creator home."""
    for name in ("Hero.jsx", "ActiveCampaigns.jsx", "Suggested.jsx", "shared.jsx"):
        src = read("components", "creator", name)
        assert "repeat: Infinity" not in src


# --- Loading and empty -------------------------------------------------------


def test_the_skeleton_matches_the_new_arrangement():
    """Big photo box, cover strip on the active card, tab strip — the shapes
    that now occupy the space."""
    src = read("components", "creator", "shared.jsx")
    skeleton = src[src.index("export const HomeSkeleton"):]

    assert "md:h-40 md:w-40" in skeleton, "the photo box kept its old size"
    assert "aspect-[16/5]" in skeleton, "no cover strip reserved"
    assert "rounded-full" in skeleton, "no tab strip reserved"


def test_every_drawer_has_an_empty_state():
    for name, marker in (
        ("ActiveCampaigns.jsx", "EmptyState"),
        ("Suggested.jsx", "EmptyState"),
        ("Applications.jsx", "EmptyState"),
    ):
        assert marker in read("components", "creator", name)


def test_the_next_action_is_one_button():
    """Each active card resolves its next step to a single primary control —
    IDS.primary — never a row of options."""
    src = read("components", "creator", "ActiveCampaigns.jsx")

    assert src.count("IDS.primary(collab.id)") >= 3, "the action variants share one slot"
    assert "waiting_on" in src, "and the card says whose move it is"
