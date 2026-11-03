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
    """h-28 on a phone rising to h-40 — a portrait, not a thumbnail. **4:5
    now, not square**: board 26 draws a portrait, and the box is one constant
    used by both branches, because most creators start without a photo and the
    monogram must hold the same space."""
    src = read("components", "creator", "Hero.jsx")

    assert 'const PHOTO_BOX = "h-28 w-[5.6rem] flex-none rounded-xl md:h-40 md:w-32"' in src
    assert src.count("PHOTO_BOX") >= 3, "the monogram fallback stopped sharing the box"


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
    src = read("pages", "CreatorHome.jsx")

    assert src.index("<ActiveCampaigns") < src.index("<Tabs ")


def test_the_drawers_are_tabs_not_a_stack():
    src = read("pages", "CreatorHome.jsx")

    for drawer in ('value="suggested"', 'value="applications"', 'value="earnings"'):
        assert drawer in src
    assert "TabsContent" in src


def test_each_drawer_keeps_its_own_error_boundary():
    """A bad earnings row must not blank the suggestions next to it — the rule
    the stacked layout already lived by, carried into the tabs."""
    src = read("pages", "CreatorHome.jsx")
    tabs = src[src.index("<Tabs ") :]

    assert tabs.count("SafeSection") >= 3


def test_the_tab_strip_scrolls_rather_than_wraps():
    """Three labels with counts at 390px: wrapping stacks the strip and eats
    the fold this redesign exists to protect."""
    src = read("pages", "CreatorHome.jsx")

    assert "overflow-x-auto" in src


def test_status_banners_stay_outside_the_tabs():
    """A blocked account is not a section, it is the situation."""
    src = read("pages", "CreatorHome.jsx")

    assert src.index("<StatusBanners") < src.index("<Tabs ")


def test_the_completeness_nudge_stays_outside_too():
    src = read("pages", "CreatorHome.jsx")

    assert src.index("<Completeness") < src.index("<Tabs ")


# --- Texture -----------------------------------------------------------------


def test_the_active_card_carries_the_campaign_cover():
    """A slim 16:5 slice, capped at 118px from `md` (board 26's strip) —
    aspect-ratio yields to max-height, which is what stops a wide card growing
    a wall of tint."""
    src = read("components", "creator", "ActiveCampaigns.jsx")

    assert "<CampaignCover" in src
    assert "aspect-[16/5]" in src
    assert "md:max-h-[7.375rem]" in src


def test_the_suggested_tiles_carry_covers_too():
    assert "<CampaignCover" in read("components", "creator", "Suggested.jsx")


def test_the_brand_mark_travels_with_the_brand_name():
    for name in ("ActiveCampaigns.jsx", "Suggested.jsx"):
        assert "BrandAvatar" in read("components", "creator", name)


# --- Motion ------------------------------------------------------------------


def test_entrances_are_staggered_and_reduced_motion_is_respected():
    """**The rule is the same; where it is enforced moved.**

    `Reveal` used to be this file's own framer-motion tween, asking
    `useReducedMotion` for itself and computing its own delay — at 450ms with
    a 70ms stagger, which made the creator's home the one authenticated screen
    settling at a different speed from every other. It is the shared CSS
    settle now, so the stagger comes from `settleDelay` and reduced motion is
    handled once in `index.css`, where the fallback is the end state rather
    than a faster animation.

    So this asserts the two properties rather than the old implementation of
    them: still staggered by position, still answering the preference. The
    band, the cap and the reduced-motion fallback are pinned in
    `test_ui_fluidity.py`, which is where the shared layer lives.
    """
    shared = read("components", "creator", "shared.jsx")
    reveal = shared[shared.index("export const Reveal"):shared.index("export const CountUp")]

    # Staggered by its position in the page.
    assert "index={index}" in reveal
    assert "Settle" in reveal

    # And the preference is answered — once, for the whole product.
    settle = read("components", "motion", "Settle.jsx")
    assert "settleDelay" in settle
    css = (FRONTEND / "index.css").read_text()
    assert ".weare-settle" in css
    block = css[css.index("@media (prefers-reduced-motion: reduce) {\n    *,"):]
    assert "animation: none !important" in block

    # `CountUp` is still a JS tween on the creator's money, so it still has to
    # ask for itself.
    assert "useReducedMotion" in shared


def test_the_card_draws_the_shared_process_flow_rather_than_its_own_bar():
    """**This replaces a rule about the old tracker.** The card used to draw a
    six-stage rail with an animated fill — its own copy of the lifecycle, and
    the third in the repository. The brand and the admin had the other two, so
    "where has this got to" had a different picture depending on who was asked.
    One component now, fed by the server."""
    src = read("components", "creator", "ActiveCampaigns.jsx")

    assert "<ProcessFlow" in src
    assert "scaleX" not in src, "the old animated rail is gone"
    assert "lifecycleFor" not in src


def test_nothing_on_the_page_loops():
    """Entrance-only: no infinite repeat anywhere on the creator home."""
    for name in ("Hero.jsx", "ActiveCampaigns.jsx", "Suggested.jsx", "shared.jsx"):
        src = read("components", "creator", name)
        assert "repeat: Infinity" not in src


# --- Loading and empty -------------------------------------------------------


def test_the_skeleton_matches_the_new_arrangement():
    """The portrait box and the three tiles, two active cards with their cover
    strips, the tab pills — the shapes that now occupy the space."""
    src = read("components", "creator", "shared.jsx")
    skeleton = src[src.index("const ActiveCardSkeleton"):]

    assert "md:h-40 md:w-32" in skeleton, "the photo box kept its old size"
    assert "aspect-[16/5]" in skeleton and "md:max-h-[7.375rem]" in skeleton, "no cover strip reserved"
    assert "lg:grid-cols-[1.25fr_1fr]" in skeleton, "the cards are two up now"
    assert skeleton.count("rounded-pill") >= 3, "no tab pills reserved"


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


# --- Board 26 ----------------------------------------------------------------


def test_the_next_step_comes_before_the_reference_half():
    """**The fold is the reason for the order.** The card used to draw the
    terms, the checklist and the fee's history above its button, so on a
    laptop the button of the first card sat below the fold. The next step and
    its button now follow the tracker, and the reference half folds into a
    native `<details>` after them — still in the DOM, so nothing is fetched
    on opening it."""
    src = read("components", "creator", "ActiveCampaigns.jsx")
    card = src[src.index("    return (\n        <li"):]

    nxt = card.index("IDS.nextAction(collab.id)")
    fold = card.index("<details")
    assert card.index("variant=\"bars\"") < nxt < fold
    for reference in ("<BriefChecklist", "<NegotiationHistory", "DRAFT_IDS.block"):
        assert card.index(reference) > fold, reference


def test_the_box_is_red_only_when_the_move_is_the_creators():
    """One red button per card at most, and only on the creator's own move —
    every other wait is navy. Whose move it is reads the server's process
    owner, which is mapped through `execution_owner`."""
    src = read("components", "creator", "ActiveCampaigns.jsx")

    assert 'const owner = collab.process?.next_action?.owner' in src
    assert 'const buttonVariant = mine ? "urgent" : "solid"' in src
    assert '(mine ? "bg-wash-red" : "bg-wash-navy")' in src
    assert "bg-primary text-primary-foreground" not in src, "a hand-styled button skipped the variants"


def test_the_tracker_is_a_variant_of_the_shared_flow():
    flow = read("components", "application", "ProcessFlow.jsx")

    assert 'variant === "bars"' in flow
    assert "function Bars(" in flow
    # Done navy, current red, still to come a warm track.
    assert '"bg-accent"' in flow and '"bg-primary"' in flow


def test_the_drawers_are_named_as_the_board_names_them():
    """"Finished" stays as the fourth: it holds the takedown answers, which
    are the one thing in there to act on."""
    src = read("pages", "CreatorHome.jsx")

    for label in ('"Briefs for you"', '"My pitches"', '"Finished"', '"Payments"'):
        assert label in src
    assert "data-[state=active]:bg-primary" in src, "the active pill is navy"


def test_the_sidebar_count_is_the_open_invitations_from_this_payload():
    src = read("pages", "CreatorHome.jsx")

    assert "useShellBadges({ invitations:" in src
    assert src.index("useShellBadges(") < src.index("if (untouched && !alreadySteered)"), (
        "a hook after the early return"
    )


def test_the_header_names_where_the_follower_count_came_from():
    """"from Instagram" only when the count was read from it; "self-reported"
    otherwise. A count with no provenance beside it is the thing
    `_follower_provenance` exists to prevent."""
    src = read("components", "creator", "Hero.jsx")

    assert "profile.follower_count_verified ?" in src
    assert "from Instagram" in src and "self-reported" in src


def test_the_profile_nudge_is_one_row():
    """It sits between the header and the live work; as a 290px panel it put
    the first card's button below the fold."""
    src = read("components", "creator", "Completeness.jsx")

    assert "p-6 md:p-7" not in src
    assert "h-[52px] w-[52px]" in src
