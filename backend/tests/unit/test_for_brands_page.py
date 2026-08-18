"""The page we send a venue owner on WhatsApp.

The landing page speaks to both sides at once because it has to. `/for-brands`
has one audience and asks once.

**Server-rendered, like `/c/{id}` and `/brands/{id}` and for the same reason:**
the crawler that builds the WhatsApp preview does not run JavaScript, so Open
Graph tags injected by React are tags nobody ever sees. It is also the page a
person lands on, not a crawler-only shim — and it loads no third-party asset,
because "loads fast on a phone at a venue" was the requirement.

**Every proof number is counted, never written down.** A hardcoded "500+
creators" is a claim that was true on the day somebody typed it, on the one
page whose whole job is to be believed by a stranger. Each figure appears only
when it is worth saying out loud: a strip reading "3 creators" is not proof,
it is a reason to close the tab, and the honest move at that size is silence
rather than rounding up.
"""
import asyncio
import inspect
import re
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from mongomock_motor import AsyncMongoMockClient

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend"


def read(*parts):
    return FRONTEND.joinpath(*parts).read_text()


def page(stats=None):
    return server._for_brands_html(stats if stats is not None else {})


FULL = {"creators": 42, "campaigns": 18, "cities": 3}


# --- It is a page, not a shim -------------------------------------------------


def test_it_is_served_outside_the_api_prefix_with_no_account():
    """A link on WhatsApp opens for somebody who has never signed in."""
    route = next(
        r for r in server.app.routes
        if getattr(r, "path", None) == server.FOR_BRANDS_PATH
    )
    assert "GET" in route.methods
    assert "Depends" not in inspect.getsource(server.for_brands_page)


def test_it_carries_its_own_open_graph_tags():
    """The whole reason it is rendered here. React-injected tags are tags no
    crawler ever sees."""
    html = page(FULL)
    for tag in ("og:title", "og:description", "og:image", "og:url", "twitter:card"):
        assert f'property="{tag}"' in html or f'name="{tag}"' in html


def test_the_preview_speaks_to_brands_not_to_creators():
    """It is the same site, but this link is sent to a venue owner. A card
    reading "join as a creator" is a card for the wrong person."""
    html = page(FULL)
    title = re.search(r'og:title" content="([^"]+)"', html).group(1)
    desc = re.search(r'og:description" content="([^"]+)"', html).group(1)

    assert "creator" not in title.lower() or "with creators" in title.lower()
    assert "brief" in desc.lower() or "campaign" in desc.lower()


def test_it_loads_nothing_from_a_third_party():
    """"Must preview well and load fast" — a render-blocking font request on
    a venue's wifi is the opposite. The other two server-rendered pages make
    the same trade, so all three agree."""
    html = page(FULL)
    for offsite in ("fonts.googleapis", "fonts.gstatic", "cdn.", "<script src"):
        assert offsite not in html


def test_it_is_in_the_sitemap():
    """The one public page here a stranger might search for rather than be
    sent. Nothing else links to it from outside."""
    assert "FOR_BRANDS_PATH" in inspect.getsource(server.public_sitemap)


# --- The structure the brief asked for ----------------------------------------


def test_the_hero_names_both_ways_of_working_with_us():
    html = page(FULL)
    hero = html[html.index("<h1>") : html.index("</section>")]

    assert "post a brief" in hero.lower()
    assert "weare team" in hero.lower()


def test_there_are_exactly_three_value_props():
    html = page(FULL)
    assert len(server._FOR_BRANDS_VALUE_PROPS) == 3
    assert html.count('<li><h3>') == 3


def test_the_value_props_are_ours_and_not_generic():
    """Anything here that could sit on a competitor's page unchanged is not a
    reason to choose us."""
    joined = " ".join(t + " " + b for t, b in server._FOR_BRANDS_VALUE_PROPS).lower()

    assert "reviewed by a person" in joined          # hand-checked, not automated
    assert "instagram" in joined                     # live stats where connected
    assert "before anybody turns up" in joined       # the rate, settled first
    assert "weare studios" in joined                 # the agency behind it


def test_there_are_four_steps_in_the_brand_s_order():
    steps = [t.lower() for t, _ in server._FOR_BRANDS_STEPS]
    assert len(steps) == 4
    assert "brief" in steps[0]
    assert "shortlist" in steps[1]
    assert "shoot" in steps[2]
    assert "approve" in steps[3]


def test_draft_review_is_named_now_that_it_exists():
    """The brief said to mention it once the feature shipped. It has."""
    joined = " ".join(b for _, b in server._FOR_BRANDS_STEPS).lower()
    assert "draft review" in joined
    assert "published until you have said yes" in joined


def test_the_expectation_line_answers_when_not_soon():
    html = page(FULL)
    block = html[html.index('class="expect"') : html.index("</section>", html.index('class="expect"'))]

    assert "working day" in block
    assert "day or two" in block and "first week" in block


def test_there_is_one_ask_per_section_and_it_is_always_the_same_one():
    """"No stacked CTAs" — one in the hero, one at the close, and both say
    the same thing, so the page asks once in two places rather than offering
    a choice of doors."""
    html = page(FULL)
    ctas = re.findall(r'<a class="btn"[^>]*>([^<]+)</a>', html)

    assert len(ctas) == 2
    assert len(set(c.strip() for c in ctas)) == 1
    assert "signup?role=brand" in html


# --- The numbers --------------------------------------------------------------


def test_the_page_carries_no_figure_of_its_own():
    """Nothing numeric in the copy — every number on this page arrives in
    `stats`, which the two tests below drive out of a real database. This one
    catches the other half: a "500+ creators" typed into a value prop or a
    step, where no stats check would ever look."""
    html = page({})
    body = html[html.index("<body>") :]
    # The step markers are 1–4 and are the numbering, not a claim.
    body = re.sub(r'<span class="n">\d+</span>', " ", body)
    text = re.sub(r"<[^>]+>", " ", body)
    numerals = re.findall(r"\b\d[\d,]*\+?\b", text)

    assert numerals == [], f"a hardcoded figure: {numerals}"


def test_the_strip_is_absent_when_there_is_nothing_worth_saying():
    """A proof strip reading "3 creators" is a reason to close the tab. The
    honest move at that size is silence, not rounding up."""
    html = page({})
    assert 'class="proof"' not in html
    assert "Where we are today" not in html


def test_a_figure_below_its_floor_is_not_shown():
    server.db = AsyncMongoMockClient()["t"]

    async def build():
        now = datetime.now(timezone.utc)
        # Three verified creators, one finished campaign, one city — none of
        # it enough.
        await server.db.creator_profiles.insert_many([
            {"user_id": ObjectId(), "verification_status": "verified",
             "city": "Bengaluru", "created_at": now}
            for _ in range(3)
        ])
        await server.db.campaigns.insert_one(
            {"brand_id": ObjectId(), "status": "completed", "created_at": now}
        )

    asyncio.run(build())
    stats = asyncio.run(server._for_brands_stats())

    assert stats == {}


def test_the_figures_appear_once_there_is_enough_behind_them():
    server.db = AsyncMongoMockClient()["t"]

    async def build():
        now = datetime.now(timezone.utc)
        await server.db.creator_profiles.insert_many([
            {"user_id": ObjectId(), "verification_status": "verified",
             "city": "Bengaluru" if i % 2 else "Mumbai", "created_at": now}
            for i in range(12)
        ])
        await server.db.campaigns.insert_many([
            {"brand_id": ObjectId(), "status": "completed", "created_at": now}
            for _ in range(6)
        ])

    asyncio.run(build())
    stats = asyncio.run(server._for_brands_stats())

    assert stats["creators"] == 12
    assert stats["campaigns"] == 6
    assert stats["cities"] == 2


def test_a_draft_nobody_ever_ran_is_not_a_campaign_run():
    """"Campaigns run" has to mean somebody shot something, or the number is
    a count of abandoned drafts."""
    server.db = AsyncMongoMockClient()["t"]

    async def build():
        now = datetime.now(timezone.utc)
        await server.db.campaigns.insert_many(
            [{"brand_id": ObjectId(), "status": "draft", "created_at": now} for _ in range(20)]
        )

    asyncio.run(build())
    assert "campaigns" not in asyncio.run(server._for_brands_stats())


def test_a_partial_set_renders_only_what_it_has():
    html = page({"creators": 42})
    assert html.count('class="fig"') == 1
    assert "verified creators" in html and "campaigns run" not in html


# --- Claims we can stand behind -----------------------------------------------


def test_it_does_not_claim_a_reach_the_operation_does_not_have():
    """Bengaluru-first is the standing rule for user-facing copy: the city
    field is open for later, the claims are not."""
    html = page(FULL).lower()
    for overclaim in (
        "every city", "across india", "pan-india", "nationwide",
        "thousands", "guarantee", "guaranteed", "#1", "leading",
    ):
        assert overclaim not in html
    assert "bengaluru" in html


def test_everything_interpolated_is_escaped():
    """Brand-supplied text does not reach this page, but the escaping habit
    is the point — the next person to add a field here inherits it."""
    src = inspect.getsource(server._for_brands_html)
    assert "e = html_escape" in src
    assert src.count("e(") >= 8


# --- Getting there ------------------------------------------------------------


def test_vercel_proxies_it_like_the_other_two_rendered_pages():
    """Shipping the page without the rewrite is a nav link into the SPA's
    catch-all — the same trap /c/:id and /brands/:id already document."""
    config = read("vercel.json")
    assert '"/for-brands"' in config


def test_the_nav_link_is_a_real_anchor():
    """A <Link> would be intercepted by the router and land on the SPA, which
    does not have this page."""
    src = read("src", "components", "Navbar.jsx")
    assert '{ href: "/for-brands"' in src
    assert '{ to: "/for-brands"' not in src


def test_the_landing_s_brand_toggle_links_to_it():
    src = read("src", "pages", "Landing.jsx")
    assert 'href: "/for-brands"' in src
    # Brand mode only — a creator has no use for it, and the closing section's
    # whole rule is that it asks once.
    brand_block = src[src.index("brand: {") : src.index("};", src.index("brand: {"))]
    assert "learnMore" in brand_block
    creator_block = src[src.index("creator: {") : src.index("brand: {")]
    assert "learnMore" not in creator_block
