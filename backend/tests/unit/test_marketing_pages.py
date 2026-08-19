"""The marketing site: home, /for-creators, /for-brands, and the footer.

Three audiences, three pages. Home is the front door and routes people; the
two audience pages ask once, to one person, and do the selling.

**Server-rendered, like `/c/{id}` and `/brands/{id}` and for the same reason:**
the crawler that builds a WhatsApp preview does not run JavaScript, so Open
Graph tags injected by React are tags nobody ever sees. These are the links
that get pasted into a chat, so the preview is the product.

**The positioning is the thing these tests mostly protect.** What we are
against is *disorganisation* — campaigns run over DMs and spreadsheets, nobody
checked, no rate in writing, no proof of what it achieved. It is deliberately
**not agencies**: WeAre Studios is one, the managed service is a real offering,
and "without an agency" would be a page arguing against our own product. That
is a thing a copy edit could undo by accident, so it is pinned here.

**Every proof number is counted, never written down.** A hardcoded "500+
creators" is a claim that was true on the day somebody typed it, on the pages
whose whole job is to be believed by a stranger.
"""
import asyncio
import json
import inspect
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from mongomock_motor import AsyncMongoMockClient

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend"


def read(*parts):
    return FRONTEND.joinpath(*parts).read_text()


FULL = {"creators": 42, "campaigns": 18, "brands": 9}

PAGES = {
    "brands": lambda stats: server._for_brands_html(stats),
    "creators": lambda stats: server._for_creators_html(stats),
}


def both(stats=FULL):
    return {name: build(stats) for name, build in PAGES.items()}


# --- The positioning ----------------------------------------------------------


@pytest.mark.parametrize("name", list(PAGES))
def test_no_page_positions_us_against_agencies(name):
    """WeAre Studios *is* an agency and the managed service is a real
    offering. "Without an agency" would be a page arguing against our own
    product — and it is exactly the phrase a well-meaning copy edit reaches
    for."""
    html = PAGES[name](FULL).lower()
    for phrase in server._FORBIDDEN_MARKETING_PHRASES:
        assert phrase not in html, f"{name}: {phrase!r}"


def test_the_managed_service_reads_as_a_choice_not_a_fee():
    """"An option you choose, not a fee you're locked into." A brand that
    reads this as a retainer has read the opposite of the offering."""
    html = PAGES["brands"](FULL).lower()

    assert "run it yourself" in html or "run it yourself, or" in html
    assert "you choose per campaign" in html
    assert "no retainer" in html


def test_the_enemy_named_is_disorganisation_not_a_competitor():
    """The problem is campaigns with nobody checked, no rate in writing and no
    proof of what happened. Every page should be answering that."""
    for name, html in both().items():
        low = html.lower()
        assert "in writing" in low, name
        assert "verified" in low or "checked" in low, name


# --- What each audience has to come away knowing ------------------------------


def test_the_creator_page_says_the_six_things_a_creator_needs():
    html = PAGES["creators"](FULL).lower()

    assert "paid briefs" in html                       # real work, one place
    assert "in writing" in html                        # the rate, before shooting
    assert "our fee is charged to the brand" in html   # they keep all of it
    assert "never taken out of yours" in html
    assert "approve" in html                           # paid on delivery
    assert "checked" in html or "verified" in html     # brands are checked
    assert "free, and it stays free" in html           # and it is free


def test_the_creator_page_does_not_imply_a_cut_of_their_rate():
    """"You keep 100%" is the promise. Anything that reads as a deduction —
    even a stray "commission" — undoes it."""
    html = PAGES["creators"](FULL).lower()
    for wrong in ("commission", "our cut", "we take a", "minus our"):
        assert wrong not in html
    # And the promise itself is stated, not merely un-contradicted.
    assert "nothing deducted from your rate" in html


def test_the_brand_page_says_the_six_things_a_brand_needs():
    html = PAGES["brands"](FULL).lower()

    assert "read from instagram itself" in html        # real audience stats
    assert "what each of them quoted" in html          # every creator, every rate
    assert "no retainer" in html and "no markup" in html
    assert "nothing is published until you have said yes" in html
    assert "report" in html                            # proof at the end
    assert "weare studios" in html                     # the managed option


def test_the_headline_direction_is_carried():
    """"Your creator campaigns, handled properly" governs the copy. It does
    not have to be the H1 of every page, but the brand page is where it was
    asked for."""
    assert "handled properly" in PAGES["brands"](FULL)


# --- One ask per page ---------------------------------------------------------


@pytest.mark.parametrize("name,expected", [("brands", "Post a campaign"),
                                           ("creators", "Join as a creator")])
def test_each_page_asks_once_in_the_same_words_twice(name, expected):
    """Top and bottom, same words — the page asks once in two places rather
    than offering a choice of doors. The nav's own button is the same words
    again, which is why three rather than two."""
    html = PAGES[name](FULL)
    body = html[html.index("<body>") :]
    ctas = re.findall(r'<a class="btn"[^>]*>([^<]+)</a>', body)

    assert len(ctas) == 2, f"{name}: {ctas}"
    assert set(c.strip() for c in ctas) == {expected}
    assert f'class="navcta"' in body


def test_the_two_pages_do_not_ask_for_the_other_audience():
    """A creator reading the brand page is in the wrong place, and a second
    CTA offering to send them elsewhere is how a page stops asking once."""
    brands = PAGES["brands"](FULL)
    creators = PAGES["creators"](FULL)
    body_b = brands[brands.index('<div class="wrap">') :]
    body_c = creators[creators.index('<div class="wrap">') :]

    assert "signup?role=creator" not in body_b.split('class="foot"')[0]
    assert "signup?role=brand" not in body_c.split('class="foot"')[0]


# --- Previews -----------------------------------------------------------------


@pytest.mark.parametrize("name", list(PAGES))
def test_each_page_carries_its_own_open_graph_tags(name):
    html = PAGES[name](FULL)
    for tag in ("og:title", "og:description", "og:url", "og:image", "twitter:card"):
        assert f'property="{tag}"' in html or f'name="{tag}"' in html


def test_the_two_previews_are_different_and_each_speaks_to_its_reader():
    """One OG title for both would make the two links preview identically in
    a chat, which is the whole reason for two pages."""
    b = re.search(r'og:title" content="([^"]+)"', PAGES["brands"](FULL)).group(1)
    c = re.search(r'og:title" content="([^"]+)"', PAGES["creators"](FULL)).group(1)

    assert b != c
    assert "campaign" in b.lower()
    assert "paid" in c.lower() or "rate" in c.lower()


@pytest.mark.parametrize("name", list(PAGES))
def test_the_canonical_url_points_at_the_page_itself(name):
    html = PAGES[name](FULL)
    path = server.FOR_BRANDS_PATH if name == "brands" else server.FOR_CREATORS_PATH
    assert f'<link rel="canonical" href="{server._share_base()}{path}">' in html


def test_both_are_in_the_sitemap():
    src = inspect.getsource(server.public_sitemap)
    assert "FOR_BRANDS_PATH" in src and "FOR_CREATORS_PATH" in src


@pytest.mark.parametrize("name", list(PAGES))
def test_nothing_blocks_the_first_paint(name):
    """"Loads fast" and "same dark premium system" pull against each other:
    Fraunces is the most recognisable part of that system and a page in
    Georgia is visibly not the brand. So the font loads on `media="print"`
    with an onload swap — fetched at low priority, applied only once it
    arrives, with text painting immediately in the fallback."""
    html = PAGES[name](FULL)

    assert 'media="print"' in html and "this.media='all'" in html
    assert "display=swap" in html
    assert '<noscript><link rel="stylesheet"' in html
    assert '<link rel="stylesheet" href=' not in html.split("<noscript>")[0]
    for offsite in ("cdn.", "<script src", "unpkg", "jsdelivr"):
        assert offsite not in html


# --- The design system --------------------------------------------------------


@pytest.mark.parametrize("name", list(PAGES))
def test_each_page_wears_the_design_system(name):
    html = PAGES[name](FULL)

    assert "Fraunces" in html and "Inter Tight" in html
    assert "Roboto" not in html and "'Inter'" not in html, "banned heading faces"
    assert "#F05D14" in html
    assert "#000000" not in html
    assert "feTurbulence" in html, "no grain"


@pytest.mark.parametrize("name", list(PAGES))
def test_each_page_has_the_navigation_bar_the_guidelines_require(name):
    """"MUST have a visible navigation bar on desktop with Logo, 3-5 links,
    and CTA. DO NOT use completely transparent background." """
    html = PAGES[name](FULL)
    nav = html[html.index('<nav class="nav"') : html.index("</nav>")]

    assert 'class="mark"' in nav, "no logo"
    assert 3 <= nav.count('class="navlink"') + nav.count('class="navcta"') <= 5
    assert "backdrop-filter" in html, "glassmorphism, never transparent"


@pytest.mark.parametrize("name", list(PAGES))
def test_each_page_links_to_the_other(name):
    """A creator who landed on the brand page should be one tap from the page
    that is actually for them."""
    html = PAGES[name](FULL)
    assert server.FOR_BRANDS_PATH in html and server.FOR_CREATORS_PATH in html


# --- The footer ---------------------------------------------------------------


@pytest.mark.parametrize("name", list(PAGES))
def test_every_page_carries_the_footer(name):
    html = PAGES[name](FULL)
    foot = html[html.index('<footer class="foot"') :]

    assert "/terms" in foot and "/privacy" in foot
    assert server.MARKETING_CONTACT in foot
    assert "offering" in foot, "the studio endorsement"
    assert str(datetime.now(timezone.utc).year) in foot, "copyright"


def test_the_footer_columns_match_the_react_one():
    """The footer exists twice — a React component for the SPA and this HTML
    twin. Two copies of a link list is how a footer ends up advertising a page
    that moved."""
    js = read("src", "lib", "siteNav.js")

    for heading, links in server.FOOTER_COLUMNS:
        assert f'heading: "{heading}"' in js, heading
        for label, to in links:
            assert f'label: "{label}"' in js, label
            # The JS builds the contact link as `mailto:${CONTACT_EMAIL}`, so
            # compare the address rather than the assembled href.
            needle = to.removeprefix("mailto:") if to.startswith("mailto:") else to
            assert needle in js, needle


def test_the_studio_endorsement_degrades_without_a_url():
    """The same rule `StudioEndorsement` follows: plain text rather than a
    link that goes nowhere, and never an invented domain."""
    src = inspect.getsource(server._marketing_footer)
    assert "if studio_url" in src
    assert "<span class=\"studio\">" in src


def test_the_copyright_names_the_entity_that_was_already_there():
    """Who owns the thing is a fact, not a copy decision."""
    assert "WeAre Monk" in PAGES["brands"](FULL)


# --- The numbers --------------------------------------------------------------


@pytest.mark.parametrize("name", list(PAGES))
def test_no_page_carries_a_figure_of_its_own(name):
    """Every number arrives in `stats`, which comes out of the database. This
    catches a "500+" typed into a value prop, where no stats check would look."""
    html = PAGES[name]({})
    body = html[html.index("<body>") :]
    body = re.sub(r'<span class="n">\d+</span>', " ", body)   # step numbering
    body = re.sub(r"&copy; \d{4}", " ", body)                  # the copyright year
    text = re.sub(r"<[^>]+>", " ", body)
    numerals = re.findall(r"\b\d[\d,]*\+?\b", text)

    assert numerals == [], f"{name}: hardcoded {numerals}"


@pytest.mark.parametrize("name", list(PAGES))
def test_the_strip_is_absent_when_there_is_nothing_worth_saying(name):
    """A strip reading "3 creators" is a reason to close the tab."""
    html = PAGES[name]({})
    assert 'class="proof"' not in html
    assert "Where we are today" not in html


def test_a_figure_below_its_floor_is_not_shown():
    server.db = AsyncMongoMockClient()["t"]

    async def build():
        now = datetime.now(timezone.utc)
        await server.db.creator_profiles.insert_many([
            {"user_id": ObjectId(), "verification_status": "verified", "created_at": now}
            for _ in range(3)
        ])
        await server.db.campaigns.insert_one(
            {"brand_id": ObjectId(), "status": "completed", "created_at": now}
        )

    asyncio.run(build())
    assert asyncio.run(server._platform_proof()) == {}


def test_the_figures_appear_once_there_is_enough_behind_them():
    server.db = AsyncMongoMockClient()["t"]

    async def build():
        now = datetime.now(timezone.utc)
        await server.db.creator_profiles.insert_many([
            {"user_id": ObjectId(), "verification_status": "verified", "created_at": now}
            for _ in range(12)
        ])
        await server.db.campaigns.insert_many([
            {"brand_id": ObjectId(), "status": "completed", "created_at": now}
            for _ in range(6)
        ])
        await server.db.brand_profiles.insert_many([
            {"user_id": ObjectId(), "verified": True, "created_at": now} for _ in range(7)
        ])

    asyncio.run(build())
    stats = asyncio.run(server._platform_proof())

    assert stats == {"creators": 12, "campaigns": 6, "brands": 7}


def test_a_draft_nobody_ever_ran_is_not_a_campaign_run():
    """"Campaigns run" has to mean somebody shot something, or the number is a
    count of abandoned drafts."""
    server.db = AsyncMongoMockClient()["t"]

    async def build():
        now = datetime.now(timezone.utc)
        await server.db.campaigns.insert_many(
            [{"brand_id": ObjectId(), "status": "draft", "created_at": now} for _ in range(20)]
        )

    asyncio.run(build())
    assert "campaigns" not in asyncio.run(server._platform_proof())


# --- Claims we can stand behind -----------------------------------------------


@pytest.mark.parametrize("name", list(PAGES))
def test_no_page_claims_a_reach_the_operation_does_not_have(name):
    html = PAGES[name](FULL).lower()
    assert "bengaluru" in html


@pytest.mark.parametrize("name", list(PAGES))
def test_everything_interpolated_is_escaped(name):
    """No brand-supplied text reaches these pages, but the habit is the point:
    the next person to add a field here inherits it."""
    src = inspect.getsource(
        server._for_brands_html if name == "brands" else server._for_creators_html
    )
    assert "e = html_escape" in src
    assert src.count("e(") >= 6


# --- Getting there ------------------------------------------------------------


SERVER_RENDERED_PATHS = (
    "/c/:id",
    "/brands/:id",
    "/for-brands",
    "/for-creators",
    "/sitemap.xml",
)


def _rewrites():
    return json.loads(read("vercel.json"))["rewrites"]


def test_vercel_has_a_rewrite_for_every_server_rendered_path():
    """Shipping a page without its rewrite is a nav link into the SPA's
    catch-all — the trap /c/:id and /brands/:id already document.

    The destinations still point at `/index.html`, which is what the catch-all
    does anyway: these are placeholders waiting to be repointed at the API
    host. PREVIEW.md is where that decision is written down, and the test
    below keeps it there."""
    sources = [r["source"] for r in _rewrites()]
    for path in SERVER_RENDERED_PATHS:
        assert path in sources, path


def test_every_server_rendered_rewrite_sits_above_the_catch_all():
    """Vercel takes the first match. Below the catch-all a rewrite is dead
    config that looks live."""
    sources = [r["source"] for r in _rewrites()]
    catch_all = sources.index("/((?!api/).*)")
    for path in SERVER_RENDERED_PATHS:
        assert sources.index(path) < catch_all, path


def test_no_rewrite_carries_a_comment_key():
    """`vercel.json` is JSON, which has no comments, and Vercel rejects
    unknown properties on a rewrite object — a `"//"` key explaining the entry
    fails validation and the whole deploy with it. The explanation belongs in
    PREVIEW.md, which is checked for below."""
    for rule in _rewrites():
        assert set(rule) <= {"source", "destination", "has", "missing", "statusCode"}, rule


def test_the_pending_proxy_decision_is_written_down():
    """These five entries are inert until somebody repoints them, and an inert
    rewrite is indistinguishable from a working one by reading the file. If
    the note goes, the next person sees five configured proxies and wonders
    why link previews are broken."""
    preview = (FRONTEND.parent / "PREVIEW.md").read_text()
    assert "pending decision" in preview.lower()
    for path in SERVER_RENDERED_PATHS:
        assert path in preview, path


def test_the_spa_links_to_them_with_real_anchors():
    """A <Link> would be intercepted by the router and land on the SPA, which
    does not have these pages."""
    nav = read("src", "components", "Navbar.jsx")
    site = read("src", "lib", "siteNav.js")

    assert '{ href: "/for-brands"' in nav
    assert '{ to: "/for-brands"' not in nav
    # The footer marks them so its own renderer picks <a> over <Link>.
    assert 'to: "/for-creators", external: true' in site
    assert 'to: "/for-brands", external: true' in site


# --- Home, held to the same rules ---------------------------------------------
#
# Home is the third page of the set and the only one the SPA renders, so it
# sits outside every test above — which is exactly how it came to carry claims
# the two new pages are forbidden to make. The audience pages were written
# clean; home was inherited, and a front door that overclaims is not fixed by
# two honest pages behind it.

LANDING = read("src", "pages", "Landing.jsx")


def _landing_copy():
    """Landing's source with `//` comment lines removed.

    Every rule below is about what a reader sees. The comments explaining why
    a claim was removed necessarily contain the claim, so leaving them in makes
    each of these tests fail on its own justification.
    """
    return "\n".join(
        line for line in LANDING.splitlines() if not line.lstrip().startswith("//")
    )


def test_home_does_not_list_cities_we_do_not_operate_in():
    """There was a strip of eight city names beside a paragraph explaining
    that the network is really only deep in one of them. The paragraph was
    right and the strip was the claim people read."""
    copy = _landing_copy()
    for city in ("Mumbai", "Delhi NCR", "Hyderabad", "Chennai", "Kolkata"):
        assert city not in copy, city


def test_home_still_names_bengaluru_and_still_opens_signup_to_india():
    """The correction is not "say less" — it is "say the true thing". Dropping
    the geography altogether would lose the part a creator in Pune needs,
    which is that they can sign up today."""
    copy = _landing_copy()
    assert "Bengaluru" in copy
    assert "anywhere in India" in copy


@pytest.mark.parametrize("phrase", ["every city", "pan-india", "across india", "nationwide"])
def test_home_makes_no_claim_the_audience_pages_are_banned_from_making(phrase):
    assert phrase not in _landing_copy().lower()


def test_home_names_only_real_campaign_categories():
    """A slide headed "Tech & gadgets" is an invitation to filter the brief
    list by a category that does not exist. `CampaignCategory` is the list.

    The ban is on categories with no enum behind them, not on wording: "Beauty
    & Wellness" and "Food & Drink" are `wellness` and `fnb` said the way a
    brand would say them, and a brief really can be filed under both."""
    copy = _landing_copy().lower()
    for absent in ("tech & gadgets", "gadgets", "fitness &", "automotive", "gaming"):
        assert absent not in copy, absent


def test_home_states_the_payment_rule_the_audience_pages_lead_with():
    """"You keep 100% of your rate because the fee sits on the brand" is the
    single most load-bearing thing we tell a creator, and home said it
    nowhere — it described the payout mechanism and skipped the economics."""
    copy = _landing_copy()
    assert "100%" in copy
    assert "charged to the brand on top" in copy


def test_home_does_not_imply_a_cut_of_the_creators_rate():
    copy = _landing_copy().lower()
    for phrase in ("commission", "deducted from what you", "our cut"):
        # "Nothing is deducted from what you agreed" is the sentence that says
        # this correctly, so the ban is on the claim, not the word.
        assert f"we take {phrase}" not in copy
    assert "commission" not in copy


def test_home_does_not_promise_that_every_brief_pays_money():
    """Barter briefs are real and admin-arranged. "No free product or
    'exposure' standing in for money" is contradicted by the first one
    somebody opens."""
    copy = _landing_copy().lower()
    assert "no free product" not in copy
    assert "barter" in copy


def test_home_describes_the_draft_step():
    """"Shoot, publish, submit" is the flow from before the review gate. A
    creator reading it would meet the draft step for the first time as a
    button they were not expecting."""
    copy = _landing_copy()
    assert "send the draft for approval" in copy


def test_the_only_remote_fetch_on_the_marketing_site_is_flagged_as_such():
    """The two server-rendered pages fetch nothing, which is why they paint in
    tens of milliseconds; home hotlinks stock photography from a CDN. That is
    a decision needing owned photography rather than a code change, so what is
    pinned here is that it stays written down instead of settling in."""
    assert "NEEDS A DECISION" in LANDING
    assert "self-hosted" in LANDING


@pytest.mark.parametrize("name", list(PAGES))
def test_the_audience_pages_still_fetch_nothing(name):
    """The counterpart of the test above: whatever home does, these two do not
    reach a third party. `test_nothing_blocks_the_first_paint` covers the font;
    this covers images."""
    html = PAGES[name](FULL)
    assert "images.unsplash.com" not in html
    assert "<img" not in html


def test_the_dev_server_proxies_the_same_paths_vercel_does():
    """`src/setupProxy.js` is the dev server's half of the rewrites above.

    Without it webpack-dev-server answers all five with `index.html`, the SPA
    loads, and the router's catch-all redirects to `/` — so the navbar and
    footer links to the two audience pages silently bounced off home for
    anybody running the stack the way PREVIEW.md says to. Two lists of the
    same five paths is the usual drift, so they are compared rather than
    trusted."""
    proxy = read("src", "setupProxy.js")

    # The patterns are regexes there and ":id" paths here, so compare on the
    # literal segment each pair has in common.
    for path in SERVER_RENDERED_PATHS:
        stem = path.split("/:")[0].replace(".", r"\.")
        assert stem in proxy, path


# --- The screens nobody was checking ------------------------------------------
#
# Every copy rule above applied to the three marketing pages. The login and
# signup screens carry a headline and a standfirst each and were covered by
# none of them, which is how "Every city that matters" survived on the login
# page long after the claim was removed everywhere it was being tested.

AUTH_SCREENS = ["Login.jsx", "Signup.jsx"]


def _screen(page):
    """One auth screen's source with its comments removed.

    JSX comments are `{/* … */}` blocks spanning several lines, not `//`
    prefixes — and the comment explaining why a claim was removed necessarily
    quotes the claim, so a line-prefix filter leaves every one of these tests
    failing on its own justification."""
    src = read("src", "pages", page)
    src = re.sub(r"\{/\*.*?\*/\}", "", src, flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


@pytest.mark.parametrize("page", AUTH_SCREENS)
@pytest.mark.parametrize("phrase", ["every city", "pan-india", "across india", "nationwide"])
def test_the_auth_screens_make_no_geography_claim_either(page, phrase):
    assert phrase not in _screen(page).lower(), f"{page}: {phrase}"


def test_signup_does_not_describe_a_waitlist_we_do_not_have():
    """Signup is open — a name and a WhatsApp number, no invite, no queue.
    "Invite-only" and "get on the list" describe a different product, and the
    form itself is the worst place to tell somebody they are queueing."""
    copy = _screen("Signup.jsx").lower()
    for wrong in ("invite-only", "get on the list", "waitlist", "join the waitlist"):
        assert wrong not in copy, wrong


def test_signup_still_says_what_is_actually_true_about_review():
    """The correction is not to remove the claim — a creator really is
    reviewed before they can apply, and finding that out afterwards is worse
    than being told."""
    assert "reviewed by our team" in _screen("Signup.jsx")
