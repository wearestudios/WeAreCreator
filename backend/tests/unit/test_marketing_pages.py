"""The marketing site: home, the two audience pages, /how-it-works, /why-weare.

Five pages and a 404, all React routes. **They used to be two FastAPI handlers
rendering hand-written HTML**, which is why these tests once ran the renderer
and searched its output. They read the page sources now, because that is where
the copy lives — and because the thing most worth protecting here is the copy,
not the markup.

What moving them cost, and why it was still right: a page the backend renders
cannot be reached with a `<Link>`, so /how-it-works and /why-weare could not
exist at all, and the two audience pages depended on a Vercel rewrite that was
never repointed — in production both answered with the SPA's catch-all. The
loss is that WhatsApp and other non-JS crawlers now see the site-wide card
rather than each page's own. `frontend/src/components/marketing/PageMeta.jsx`
states that plainly and says how to buy it back; a test below keeps that note
in place rather than letting it be forgotten.

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


def copy_of(*parts):
    """A page's source with its comments stripped.

    Every rule below is about what a reader sees. The comments explaining why a
    claim was removed necessarily quote the claim, so leaving them in makes each
    of these tests fail on its own justification. JSX comments are `{/* … */}`
    blocks spanning lines, so a line-prefix filter is not enough.
    """
    src = read(*parts)
    src = re.sub(r"\{/\*.*?\*/\}", "", src, flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )
    # The copy is written as adjacent string literals joined with `+` across
    # lines, so a sentence is routinely split mid-phrase.
    src = re.sub(r'"\s*\+\s*\n\s*"', "", src)
    return re.sub(r"\s+", " ", src)


PAGES = {
    "brands": ("src", "pages", "ForBrands.jsx"),
    "creators": ("src", "pages", "ForCreators.jsx"),
    "how": ("src", "pages", "HowItWorks.jsx"),
    "why": ("src", "pages", "WhyWeAre.jsx"),
    "home": ("src", "pages", "Landing.jsx"),
}

# The four that argue. Home routes rather than sells, and the 404 is neither.
ARGUING = ["brands", "creators", "how", "why"]

# The audience pages, which are the ones held to the single-ask rule.
AUDIENCE = ["brands", "creators"]


# --- The positioning ----------------------------------------------------------


@pytest.mark.parametrize("name", list(PAGES))
def test_no_page_positions_us_against_agencies(name):
    """WeAre Studios *is* an agency and the managed service is a real
    offering. "Without an agency" would be a page arguing against our own
    product — and it is exactly the phrase a well-meaning copy edit reaches
    for."""
    text = copy_of(*PAGES[name]).lower()
    for phrase in server._FORBIDDEN_MARKETING_PHRASES:
        assert phrase not in text, f"{name}: {phrase!r}"


def test_the_managed_service_reads_as_a_choice_not_a_fee():
    """"An option you choose, not a fee you're locked into." A brand that
    reads this as a retainer has read the opposite of the offering."""
    for name in ("brands", "why"):
        text = copy_of(*PAGES[name]).lower()
        assert "run it yourself" in text, name
        assert "no retainer" in text, name
    assert "you choose per campaign" in copy_of(*PAGES["brands"]).lower()
    assert "not a fee you are locked into" in copy_of(*PAGES["why"]).lower()


def test_the_pages_use_the_marketing_chrome_not_the_shared_chrome():
    """The shared `Navbar` and `Footer` are on nineteen authenticated
    surfaces. Marketing needed a different bar, so it got a variant rather
    than an edit — the strict version of "do not touch a logged-in view"."""
    shell = read("src", "components", "marketing", "Sections.jsx")
    assert "MarketingNavbar" in shell and "MarketingFooter" in shell
    assert 'from "@/components/Navbar"' not in shell
    assert 'from "@/components/Footer"' not in shell

    home = read("src", "pages", "Landing.jsx")
    assert "MarketingNavbar" in home and "MarketingFooter" in home
    assert 'from "@/components/Navbar"' not in home
    assert 'from "@/components/Footer"' not in home


def test_the_enemy_named_is_disorganisation_not_a_competitor():
    """The problem is campaigns with nobody checked, no rate in writing and no
    proof of what happened. Every arguing page should be answering that."""
    for name in ARGUING:
        low = copy_of(*PAGES[name]).lower()
        assert "in writing" in low or "before anyone shoots" in low or "before you shoot" in low, name
        assert "verified" in low or "checked" in low, name
    # And home names it outright, since it is the only argument home keeps.
    home = copy_of(*PAGES["home"]).lower()
    assert "dms and spreadsheets" in home
    assert "nobody checked" in home


def test_the_headline_direction_is_carried():
    """"Your creator campaigns, handled properly" governs the copy. Home is
    where it leads, and /why-weare is the page that argues it."""
    assert "handled properly" in copy_of(*PAGES["home"])
    assert "handled properly" in copy_of(*PAGES["why"])


# --- What each audience has to come away knowing ------------------------------


def test_the_creator_page_says_the_six_things_a_creator_needs():
    """The six survived the compression; the paragraphs around them did not.
    Each is now a four-word label and one line, so these look for the idea
    rather than the sentence it used to sit in."""
    text = copy_of(*PAGES["creators"]).lower()

    assert "real paid briefs" in text                  # real work, one place
    assert "before you shoot" in text                  # the rate, before shooting
    assert "charged to the brand on top" in text       # they keep all of it
    assert "never taken out of yours" in text
    assert "payment follows approval" in text          # paid on delivery
    assert "checked" in text or "verified" in text     # brands are checked
    assert "free to join" in text                      # and it is free


def test_the_creator_page_does_not_imply_a_cut_of_their_rate():
    """"You keep all of it" is the promise. Anything that reads as a deduction
    — even a stray "commission" — undoes it."""
    text = copy_of(*PAGES["creators"]).lower()
    for wrong in ("commission", "our cut", "we take a", "minus our"):
        assert wrong not in text, wrong
    assert "you keep all of it" in text


def test_the_brand_page_says_the_six_things_a_brand_needs():
    text = copy_of(*PAGES["brands"]).lower()

    assert "read from instagram" in text               # real audience stats
    assert "what each creator quoted" in text          # every creator, every rate
    assert "no retainer" in text and "no markup" in text
    assert "nothing goes live until you say yes" in text
    assert "report" in text                            # proof at the end
    assert "weare studios" in text                     # the managed option


# --- One ask per page ---------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [("brands", "Post a campaign"), ("creators", "Join as a creator")],
)
def test_each_audience_page_asks_once_in_the_same_words_twice(name, expected):
    """Top and bottom, same words — the page asks once in two places rather
    than offering a choice of doors. Both CTAs are spread from one `ASK`
    constant, which is what makes "the same words" structural rather than a
    thing somebody has to remember."""
    src = read(*PAGES[name])
    assert f'label: "{expected}"' in src
    assert src.count("const ASK =") == 1
    assert "{ ...ASK, testid: IDS.ctaTop }" in src
    assert "{ ...ASK, testid: IDS.ctaBottom }" in src


def test_the_audience_pages_do_not_ask_for_the_other_audience():
    """A creator reading the brand page is in the wrong place, and a second
    CTA offering to send them elsewhere is how a page stops asking once. The
    footer is where somebody in the wrong place finds the right page."""
    assert "signup?role=creator" not in copy_of(*PAGES["brands"])
    assert "signup?role=brand" not in copy_of(*PAGES["creators"])


def test_the_two_audience_pages_do_not_route_to_each_other_mid_page():
    """`TwoPaths` is the component that offers both doors. It belongs on the
    pages that cannot know who arrived — home and /how-it-works — and nowhere
    a page has already been given one reader."""
    for name in AUDIENCE + ["why"]:
        assert "TwoPaths" not in read(*PAGES[name]), name
    for name in ("home", "how"):
        assert "TwoPaths" in read(*PAGES[name]), name


def test_the_both_sides_pages_offer_two_paths_rather_than_inventing_one_ask():
    """Home and /how-it-works are read by both audiences. Picking one CTA for
    the visitor puts half of them through the wrong door.

    The two destinations live in `TwoPaths`, not on the pages — which is the
    point: one component means the pair cannot end up saying different things
    in two places."""
    paths = read("src", "components", "marketing", "Sections.jsx")
    assert 'to="/for-creators"' in paths
    assert 'to="/for-brands"' in paths
    for name in ("home", "how"):
        assert "TwoPaths" in read(*PAGES[name]), name


# --- Previews and routing -----------------------------------------------------


@pytest.mark.parametrize("name", list(PAGES))
def test_each_page_sets_its_own_title_description_and_path(name):
    """`PageMeta` writes the title, the description, the canonical and the
    Open Graph tags. One page missing it inherits whichever page was open
    before it, which is worse than a generic tag."""
    src = read(*PAGES[name])
    # Home mounts PageMeta itself; the rest pass the same three props to
    # MarketingPage, which mounts it for them.
    assert "PageMeta" in src or "MarketingPage" in src
    assert re.search(r'title="[^"]{8,}"', src), name
    assert re.search(r'description="[^"]{20,}"', src), name
    assert re.search(r'path="/[^"]*"', src), name


def test_no_two_pages_share_a_preview_title():
    """One title for two pages makes two links preview identically in a chat,
    which is the whole reason for separate pages."""
    titles = []
    for parts in PAGES.values():
        m = re.search(r'\btitle="([^"]+)"', read(*parts))
        assert m, parts
        titles.append(m.group(1))
    assert len(set(titles)) == len(titles), titles


def test_page_meta_writes_the_open_graph_tags_a_preview_needs():
    meta = read("src", "components", "marketing", "PageMeta.jsx")
    for tag in ("og:title", "og:description", "og:url", "og:type", "twitter:card"):
        assert tag in meta, tag
    assert 'link("canonical"' in meta


def test_the_limit_of_runtime_meta_is_written_down_rather_than_glossed():
    """Google renders JavaScript; WhatsApp does not. Moving these pages into
    the SPA traded the chat preview for pages that are reachable, linkable and
    able to exist at all — a real trade, and one somebody will need explained
    the first time a pasted link previews as the site card."""
    meta = read("src", "components", "marketing", "PageMeta.jsx")
    flat = re.sub(r"\s+", " ", meta.replace("//", " ").replace("*", " "))
    assert "WhatsApp does not" in flat
    assert "prerender" in meta


@pytest.mark.parametrize(
    "path",
    ["/for-brands", "/for-creators", "/how-it-works", "/why-weare"],
)
def test_every_marketing_page_is_a_registered_route(path):
    """The complaint that started this restructure: two of these were not
    routes at all, and two did not exist."""
    app = read("src", "App.js")
    assert f'path="{path}"' in app, path


def test_the_catch_all_renders_a_404_rather_than_redirecting_home():
    """A mistyped URL, a link from an old post and a brief that has since
    closed all used to land silently on the front page, which is
    indistinguishable from the link having worked."""
    app = read("src", "App.js")
    assert '<Route path="*" element={<NotFound />} />' in app
    assert '<Route path="*" element={<Navigate to="/" replace />} />' not in app


def test_the_marketing_links_are_router_links_not_anchors():
    """They were real <a>s while the backend rendered them. An anchor now is a
    full page load for a route the SPA owns."""
    nav = read("src", "components", "Navbar.jsx")
    for path in ("/for-brands", "/for-creators", "/how-it-works", "/why-weare"):
        assert f'to: "{path}"' in nav, path
        assert f'href: "{path}"' not in nav, path
    home = read("src", "pages", "Landing.jsx")
    assert 'href="/for-creators"' not in home
    assert 'to="/for-creators"' in home


def test_the_navbar_offers_the_four_pages_and_both_auth_actions():
    """The logged-out menu, and the mobile sheet that has to match it — the
    sheet is the only navigation below md, so anything missing there is
    unreachable on a phone."""
    nav = read("src", "components", "Navbar.jsx")
    for label in ("For brands", "For creators", "How it works", "Why WeAre"):
        assert f'label: "{label}"' in nav, label
    assert 'data-testid="nav-login-link"' in nav
    assert 'data-testid="nav-signup-link"' in nav
    assert 'data-testid="nav-login-link-mobile"' in nav
    assert 'data-testid="nav-signup-link-mobile"' in nav
    # One list feeds both, which is what stops them drifting.
    assert nav.count("MARKETING_LINKS") >= 3  # the definition, plus both maps
    assert "MARKETING_LINKS).map" in nav      # desktop bar
    assert "MARKETING_LINKS.map" in nav       # mobile sheet


def test_signed_in_users_keep_their_role_navigation():
    """The marketing strip renders only when nobody is signed in. A brand
    clearing its applicant board does not need "Why WeAre"."""
    nav = read("src", "components", "Navbar.jsx")
    assert "checking || signedIn ? [] : MARKETING_LINKS" in nav
    assert "linksFor(user.role)" in nav


# --- The design system --------------------------------------------------------


@pytest.mark.parametrize("name", ARGUING)
def test_each_page_wears_the_design_system(name):
    """Fraunces headings, the ember accent, fluid type, and the uppercase
    wide-tracked overline. All four are guideline rules, and all four are what
    a bespoke page quietly stops doing."""
    src = read(*PAGES[name])
    shell = read("src", "components", "marketing", "Sections.jsx")
    # The shell carries the type and colour rules for the pages that use it;
    # a page states its own overlines through the `eyebrow` prop.
    assert "font-serif" in src or "font-serif" in shell
    assert "text-fluid-" in src or "text-fluid-" in shell
    assert "ember-500" in src or "ember-500" in shell
    assert "Eyebrow" in src or "eyebrow=" in src or "tracking-[0.2em]" in src
    for rule in ("font-serif", "text-fluid-", "ember-500", "tracking-[0.2em]"):
        assert rule in shell, rule


@pytest.mark.parametrize("name", ARGUING)
def test_no_heading_uses_a_flat_text_size(name):
    """"No heading uses a flat `text-*` size" is a foundation rule — headings
    are on the fluid scale so they stop jumping between breakpoints."""
    src = read(*PAGES[name])
    for m in re.finditer(r"<h[123][^>]*className=\"([^\"]+)\"", src):
        classes = m.group(1)
        flat = re.findall(r"\btext-(xs|sm|base|lg|xl|\dxl)\b", classes)
        assert not flat, f"{name}: {flat} in {classes}"


@pytest.mark.parametrize("name", list(PAGES) + ["notfound"])
def test_every_page_carries_the_footer(name):
    parts = PAGES.get(name, ("src", "pages", "NotFound.jsx"))
    src = read(*parts)
    # Home mounts it directly; the rest inherit it from MarketingPage.
    assert "<MarketingFooter />" in src or "MarketingPage" in src


def test_the_marketing_shell_mounts_both_marketing_bars():
    sections = read("src", "components", "marketing", "Sections.jsx")
    assert "<MarketingNavbar />" in sections
    assert "<MarketingFooter />" in sections


# --- Image slots --------------------------------------------------------------


@pytest.mark.parametrize("name", list(PAGES) + ["notfound"])
def test_every_page_has_deliberate_image_slots(name):
    parts = PAGES.get(name, ("src", "pages", "NotFound.jsx"))
    src = read(*parts)
    assert "PlaceholderImage" in src or "image={{" in src, name


@pytest.mark.parametrize("name", list(PAGES) + ["notfound"])
def test_every_image_slot_says_what_belongs_in_it(name):
    """A slot nobody can brief is a slot that stays empty. Every `note` is a
    sentence somebody could hand to a photographer, and it rides on the
    element as `data-placeholder` as well as sitting in the source."""
    parts = PAGES.get(name, ("src", "pages", "NotFound.jsx"))
    src = read(*parts)
    notes = re.findall(r'note[:=]\s*"([^"]+)"', src)
    assert notes, name
    for n in notes:
        assert len(n) > 25, f"{name}: {n!r} is not a brief"


@pytest.mark.parametrize("name", list(PAGES) + ["notfound"])
def test_every_image_slot_is_marked_for_the_photographer(name):
    """The `PLACEHOLDER IMAGE:` comment is what makes these findable — real
    photography is meant to be dropped in one slot at a time."""
    parts = PAGES.get(name, ("src", "pages", "NotFound.jsx"))
    src = read(*parts)
    assert "PLACEHOLDER IMAGE:" in src, name


def test_nothing_on_the_site_fetches_a_third_party_image():
    """The hero hotlinked four stock photographs and the two auth screens one
    each — somebody else's pictures of nowhere in particular, from a CDN we do
    not control, on the pages arguing that the work is real and local."""
    for path in FRONTEND.joinpath("src").rglob("*.js*"):
        text = path.read_text()
        assert "images.unsplash.com" not in text, path
        assert "pexels.com" not in text, path


def test_a_slot_reserves_its_space_so_real_photography_drops_in_cleanly():
    """The ratio is on the container, never on the <img> — the whole point of
    the slot is that filling it moves nothing."""
    src = read("src", "components", "marketing", "PlaceholderImage.jsx")
    assert "aspect-[16/9]" in src
    assert "absolute inset-0 h-full w-full object-cover" in src
    assert 'src ? (' in src


def test_the_placeholder_does_not_put_grain_on_its_own_gradient():
    """A foundation rule: `.grain-surface` sets `background-image` and so does
    a gradient, and one of the two silently wins. The overlay variant exists
    for exactly this."""
    src = read("src", "components", "marketing", "PlaceholderImage.jsx")
    # The comment explaining why `.grain-surface` is wrong here necessarily
    # names it, so strip block comments as well as line ones.
    code = re.sub(r"\{/\*.*?\*/\}", "", src, flags=re.S)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    code = "\n".join(
        l for l in code.splitlines() if not l.lstrip().startswith("//")
    )
    assert "grain-surface" not in code
    assert 'className="grain pointer-events-none absolute inset-0"' in code


# --- The numbers --------------------------------------------------------------


@pytest.mark.parametrize("name", list(PAGES))
def test_no_page_writes_a_proof_figure_into_its_copy(name):
    """A hardcoded "500+ creators" is a claim that was true on the day
    somebody typed it. Home carried exactly that, beside "48h" and "₹0", until
    the counted strip replaced it."""
    text = copy_of(*PAGES[name])
    # Strip the parts that are legitimately numeric: class names, ratios and
    # the one figure that is a rule rather than a boast.
    text = re.sub(r'className="[^"]*"', "", text)
    text = re.sub(r'(ratio|note)[:=]\s*"[^"]*"', "", text)
    text = re.sub(r"\b(24 hours|100%|one|two|three|four|six)\b", "", text)
    for claim in re.findall(r"\b\d[\d,]*\+", text):
        pytest.fail(f"{name}: hardcoded figure {claim!r}")


def test_the_proof_strip_reads_counted_figures_from_the_server():
    strip = read("src", "components", "marketing", "ProofStrip.jsx")
    assert '"/public/proof"' in strip
    assert "creators" in strip and "campaigns" in strip and "cities" in strip


def test_the_proof_strip_shows_nothing_rather_than_an_unconvincing_number():
    """A strip reading "3 creators" is not proof, it is a reason to close the
    tab, and the honest move at that size is silence rather than rounding up.
    The floors are on the server so every surface agrees."""
    strip = read("src", "components", "marketing", "ProofStrip.jsx")
    assert "if (!keys.length) return null;" in strip
    # And a failed request says nothing at all rather than drawing dashes.
    assert ".catch(() => {})" in strip


def test_the_floors_are_enforced_where_the_figures_are_counted():
    src = server.inspect.getsource(server._platform_proof) if hasattr(server, "inspect") else None
    import inspect as _inspect

    src = _inspect.getsource(server._platform_proof)
    assert "creators >= 10" in src
    assert "campaigns >= 5" in src
    assert "cities >= 3" in src


def _proof_db(*, creators=0, campaigns=0, brands=0, cities=()):
    db = AsyncMongoMockClient()["proof"]

    async def build():
        for i in range(creators):
            await db.creator_profiles.insert_one(
                {
                    "user_id": ObjectId(),
                    "verification_status": "verified",
                    "city": list(cities)[i % len(cities)] if cities else "Bengaluru",
                }
            )
        for _ in range(campaigns):
            await db.campaigns.insert_one({"status": "completed"})
        for _ in range(brands):
            await db.brand_profiles.insert_one({"user_id": ObjectId(), "verified": True})

    asyncio.get_event_loop().run_until_complete(build())
    return db


def test_a_figure_below_its_floor_is_not_returned(monkeypatch):
    db = _proof_db(creators=4, campaigns=2, brands=1)
    monkeypatch.setattr(server, "db", db)
    out = asyncio.get_event_loop().run_until_complete(server._platform_proof())
    assert out == {}


def test_the_figures_appear_once_there_is_enough_behind_them(monkeypatch):
    db = _proof_db(
        creators=12,
        campaigns=7,
        brands=6,
        cities=("Bengaluru", "Mumbai", "Pune"),
    )
    monkeypatch.setattr(server, "db", db)
    out = asyncio.get_event_loop().run_until_complete(server._platform_proof())
    assert out["creators"] == 12
    assert out["campaigns"] == 7
    assert out["brands"] == 6
    assert out["cities"] == 3


def test_one_city_is_not_a_footprint(monkeypatch):
    """"1 city" is a sentence that argues against itself, and this product is
    Bengaluru-first by design rather than by accident."""
    db = _proof_db(creators=12, campaigns=7, cities=("Bengaluru",))
    monkeypatch.setattr(server, "db", db)
    out = asyncio.get_event_loop().run_until_complete(server._platform_proof())
    assert "cities" not in out


def test_a_draft_nobody_ever_ran_is_not_a_campaign_run(monkeypatch):
    """"Campaigns run" counts campaigns that reached `in_progress` or beyond.
    A count of posted briefs would be a count of abandoned drafts."""
    db = AsyncMongoMockClient()["proof"]

    async def build():
        for _ in range(20):
            await db.campaigns.insert_one({"status": "draft"})

    asyncio.get_event_loop().run_until_complete(build())
    monkeypatch.setattr(server, "db", db)
    out = asyncio.get_event_loop().run_until_complete(server._platform_proof())
    assert "campaigns" not in out


# --- Claims we can stand behind -----------------------------------------------


@pytest.mark.parametrize("name", list(PAGES))
def test_no_page_claims_a_reach_the_operation_does_not_have(name):
    """Bengaluru is evidence of network depth, never identity — so the pages
    that mention geography say where the network is deepest, and none of them
    claims more."""
    text = copy_of(*PAGES[name]).lower()
    for phrase in ("every city", "pan-india", "across india", "nationwide"):
        assert phrase not in text, f"{name}: {phrase}"


def test_geography_is_stated_as_depth_rather_than_identity():
    for name in ("brands", "why"):
        text = copy_of(*PAGES[name]).lower()
        assert "bengaluru" in text, name
        assert "anywhere in india" in text, name


@pytest.mark.parametrize("word", ["vets", "vetted", "vetting"])
def test_no_page_reintroduces_the_old_vocabulary(word):
    """"Vetted" is what this concept was called before it settled on
    `verification_status`. The mismatch once hid every approved creator from
    every brand."""
    for name, parts in PAGES.items():
        assert word not in copy_of(*parts).lower(), f"{name}: {word}"


def test_home_names_only_real_campaign_categories():
    """A slide headed "Tech & gadgets" is an invitation to filter the brief
    list by a category that does not exist. `CampaignCategory` is the list."""
    text = copy_of(*PAGES["home"]).lower()
    for absent in ("tech & gadgets", "gadgets", "automotive", "gaming"):
        assert absent not in text, absent


def test_home_does_not_promise_that_every_brief_pays_money():
    """Barter briefs are real and admin-arranged."""
    assert "no free product" not in copy_of(*PAGES["home"]).lower()


# --- Home is a router, not a story --------------------------------------------


def test_home_keeps_only_what_routes():
    """Hero, proof, one problem-and-promise section, the close. Everything
    else moved to its own page — and the live brief feed went to /campaigns,
    which is a better version of it and was always one tap away."""
    src = read(*PAGES["home"])
    code = "\n".join(
        l for l in src.splitlines() if not l.lstrip().startswith("//")
    )
    assert "<Hero />" in code
    assert "<ProofStrip" in code
    assert "<Problem />" in code
    assert "TwoPaths" in code
    for gone in ("LiveBriefs", "function Reach", "TRUST_POINTS", "verticals"):
        assert gone not in code, gone


def test_home_sends_readers_on_rather_than_telling_them_everything():
    src = read(*PAGES["home"])
    for dest in ("/for-creators", "/for-brands", "/how-it-works"):
        assert dest in src, dest


# --- The parallel tracks ------------------------------------------------------


def test_how_it_works_shows_both_sides_against_each_other():
    """A creator's step and the brand's step opposite it happen at the same
    moment, and that is the argument. Two separate lists would lose it."""
    src = read(*PAGES["how"])
    tracks = re.findall(r"moment:", src)
    assert len(tracks) >= 5, tracks
    # Every row carries both sides; a blank one reads as a step somebody
    # forgot to write.
    assert src.count("creator: {") == src.count("brand: {") == len(tracks)


def test_how_it_works_carries_the_four_trust_mechanics():
    """Four labels and four lines where there were four paragraphs. The
    mechanics are the point, not the wording — but all four have to be here,
    because they are what makes this a process rather than a group chat."""
    text = copy_of(*PAGES["how"]).lower()
    assert "verified both ways" in text
    assert "rate in writing" in text
    assert "approval before public" in text
    assert "paid on approved delivery" in text


def test_how_it_works_states_the_payment_flow_the_way_the_product_works():
    """Rate agreed and recorded before the shoot, the brand pays us, we
    release on approved delivery. The middle step is the one most easily lost
    in compression, and losing it makes us sound like a directory."""
    text = copy_of(*PAGES["how"]).lower()
    assert "you pay us" in text
    assert "the brand pays us" in text
    assert "recorded against the booking" in text


def test_why_weare_makes_the_standalone_case():
    text = copy_of(*PAGES["why"]).lower()
    assert "weare studios" in text                      # the pedigree
    assert "run it yourself, or hand it over" in text   # the choice
    assert "a person reviews every creator" in text     # verified people
    assert "plus our fee" in text                       # money handled properly
    assert "reach and cost per thousand" in text        # results reported


# --- The footer, and the sitemap ----------------------------------------------


def test_the_footer_columns_match_the_react_one():
    """Two renderers with two copies of the link list is how a footer ends up
    advertising a page that moved. The backend's copy builds the sitemap."""
    site = read("src", "lib", "siteNav.js")
    for heading, links in server.FOOTER_COLUMNS:
        assert f'heading: "{heading}"' in site, heading
        for label, to in links:
            assert f'label: "{label}"' in site, label
            if to.startswith("mailto:"):
                assert to.split(":", 1)[1] in site
            else:
                assert f'to: "{to}"' in site or f"to: `{to}" in site, to


def test_the_footer_links_every_marketing_page():
    """Six pages and one footer. A page nothing links to is a page nobody
    finds."""
    site = read("src", "lib", "siteNav.js")
    for path in ("/for-brands", "/for-creators", "/how-it-works", "/why-weare"):
        assert f'"{path}"' in site, path


def test_the_sitemap_lists_every_marketing_page():
    """Built from `MARKETING_PATHS` rather than a hand-written list, so adding
    a page cannot quietly leave it out."""
    import inspect as _inspect

    src = _inspect.getsource(server.public_sitemap)
    assert "MARKETING_PATHS" in src
    assert set(server.MARKETING_PATHS) == {
        "/",
        "/for-brands",
        "/for-creators",
        "/how-it-works",
        "/why-weare",
    }


def test_the_copyright_names_the_entity_that_was_already_there():
    """Who owns the thing is a fact, not a copy decision."""
    assert "WeAre Monk" in read("src", "components", "Footer.jsx")


# --- Getting there ------------------------------------------------------------

SERVER_RENDERED_PATHS = ("/c/:id", "/brands/:id", "/sitemap.xml")


def _rewrites():
    return json.loads(read("vercel.json"))["rewrites"]


def test_vercel_has_a_rewrite_for_every_server_rendered_path():
    """Three now, not five: /for-brands and /for-creators are React routes, so
    a rewrite pointing them at the backend would shadow the pages."""
    sources = [r["source"] for r in _rewrites()]
    for path in SERVER_RENDERED_PATHS:
        assert path in sources, path
    assert "/for-brands" not in sources
    assert "/for-creators" not in sources


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
    fails validation and the whole deploy with it."""
    for rule in _rewrites():
        assert set(rule) <= {"source", "destination", "has", "missing", "statusCode"}, rule


def test_the_dev_server_proxies_the_same_paths_vercel_does():
    """`src/setupProxy.js` is the dev server's half of the rewrites. Without
    it webpack-dev-server answers them with `index.html` and the SPA takes
    over, so a shared brief link opens the app rather than the page it
    names."""
    proxy = read("src", "setupProxy.js")
    for path in SERVER_RENDERED_PATHS:
        stem = path.split("/:")[0].replace(".", r"\.")
        assert stem in proxy, path
    # And not the pages the SPA now owns.
    assert "/^\\/for-brands" not in proxy


def test_the_pending_proxy_decision_is_written_down():
    """The rewrites point at /index.html, which is what the catch-all does
    anyway — they are placeholders waiting to be repointed at the API host,
    and an inert rewrite is indistinguishable from a working one by reading
    the file."""
    preview = (FRONTEND.parent / "PREVIEW.md").read_text()
    assert "pending decision" in preview.lower()
    for path in SERVER_RENDERED_PATHS:
        assert path in preview, path


# --- The copy budget ----------------------------------------------------------
#
# "One idea per screen-height. Headlines up to eight words, supporting lines up
# to twenty, no paragraph over three rendered lines." Those are rules about a
# rendered page, and most of them can only be checked in a browser — but the
# word counts can be checked here, and the word counts are the ones that drift.
#
# Every page keeps its copy in one `COPY` object for exactly this reason: the
# budget can be read rather than reconstructed by walking JSX. A section that
# wants to say more has to argue with a number.

BUDGET = {"home": 120, "brands": 250, "creators": 250, "how": 300, "why": 300}


def _copy_strings(name):
    """Every string literal inside the page's COPY object."""
    src = read(*PAGES[name])
    start = src.index("const COPY = {")
    depth, i = 0, start
    while i < len(src):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    block = src[start : i + 1]
    return re.findall(r'"((?:[^"\\]|\\.)*)"', block)


def _words(text):
    return [w for w in re.split(r"\s+", text.strip()) if re.search(r"[A-Za-z0-9]", w)]


@pytest.mark.parametrize("name", list(BUDGET))
def test_every_page_stays_inside_its_word_budget(name):
    total = sum(len(_words(t)) for t in _copy_strings(name))
    assert total <= BUDGET[name], f"{name}: {total} words, budget {BUDGET[name]}"


@pytest.mark.parametrize("name", list(BUDGET))
def test_no_headline_runs_past_eight_words(name):
    """Keys ending in `title` or named `label` are the headings and the
    four-word labels that replaced the paragraphs."""
    src = read(*PAGES[name])
    start = src.index("const COPY = {")
    block = src[start:]
    for m in re.finditer(r'(\w*[Tt]itle|label|moment):\s*"((?:[^"\\]|\\.)*)"', block):
        n = len(_words(m.group(2)))
        assert n <= 8, f"{name}: {n} words — {m.group(2)!r}"


@pytest.mark.parametrize("name", list(BUDGET))
def test_no_supporting_line_runs_past_twenty_words(name):
    src = read(*PAGES[name])
    start = src.index("const COPY = {")
    block = src[start:]
    for m in re.finditer(r'\b(line|\w+Line|footnote):\s*"((?:[^"\\]|\\.)*)"', block):
        n = len(_words(m.group(2)))
        assert n <= 20, f"{name}: {n} words — {m.group(2)!r}"


def _code(*parts):
    """Source with comments removed.

    Several rules below ban a token that the comment explaining the rule has
    to use. Stripping first is the difference between a test that checks the
    code and one that fails on its own justification.
    """
    src = read(*parts)
    src = re.sub(r"\{/\*.*?\*/\}", "", src, flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(
        l for l in src.splitlines() if not l.lstrip().startswith("//")
    )


def test_the_primitives_have_no_prop_that_accepts_a_paragraph():
    """The shape is what enforces the copy rules. `Point`, `Steps` and
    `TextImageSection` take a label and one `line`; none takes a `body`, which
    is what the prose versions called it. A section that wants to make two
    points has to become two sections."""
    shell = _code("src", "components", "marketing", "Sections.jsx")
    assert not re.search(r"\bbody\b\s*[,}:=]", shell)
    assert not re.search(r"\bbody\b\s*\}", shell)


# --- The motion layer ---------------------------------------------------------


def test_there_is_one_easing_curve_and_it_is_used_everywhere():
    """Six sections animated by six people is six easings, which reads as six
    different sites. `EASE` is the only curve on the marketing pages."""
    motion = read("src", "components", "marketing", "motion.js")
    assert "export const EASE" in motion

    curves = set()
    for path in FRONTEND.joinpath("src", "components", "marketing").glob("*.js*"):
        curves |= set(re.findall(r"\[0\.\d+,\s*[\d.]+,\s*[\d.]+,\s*[\d.]+\]", path.read_text()))
    assert len(curves) == 1, curves


def test_every_duration_sits_between_200_and_400ms():
    motion = read("src", "components", "marketing", "motion.js")
    for value in re.findall(r"(?:fast|base|slow):\s*([\d.]+)", motion):
        assert 0.2 <= float(value) <= 0.4, value
    # And the CSS-side transitions the hover treatments use.
    for ms in re.findall(r"duration-(\d+)", motion):
        assert 200 <= int(ms) <= 400, ms
    for ms in re.findall(r"transition-duration:(\d+)ms", motion):
        assert 200 <= int(ms) <= 400, ms


def test_motion_is_transforms_and_opacity_only():
    """Animating height, width or a position forces layout on every frame;
    transform and opacity are composited, which is what keeps this smooth on
    the mid-range Android most creators arrive on.

    Checked against the variants themselves rather than the whole file —
    `VIEWPORT`'s `margin` is the intersection-observer's root margin, not a
    property anything animates, and a blanket string ban would fail on it."""
    code = _code("src", "components", "marketing", "motion.js")

    animated = set()
    for name in ("rise", "fade", "still"):
        block = code[code.index(f"export const {name} =") :]
        block = block[: block.index("};") + 2]
        animated |= set(re.findall(r"^\s*(\w+):", block, re.M))
    assert animated <= {"opacity", "y", "transition", "hidden", "show"}, animated

    # The one colour change is a CSS transition on named properties, never an
    # animated value — and never `transition-all`, which would also animate
    # the background, the shadow and anything a future edit adds.
    assert "transition-[transform,border-color]" in code
    assert "transition-all" not in code


def test_reduced_motion_is_handled_once_rather_than_at_each_call_site():
    """`Reveal` decides; nothing below it repeats the check. The failure mode
    of per-site handling is one component that forgets and animates anyway."""
    reveal = read("src", "components", "marketing", "Reveal.jsx")
    assert "useReducedMotion" in reveal
    assert "still" in reveal


def test_reduced_motion_shows_the_content_rather_than_withholding_it():
    """Under `reduce` the element renders at its final state. Gating an
    entrance on a media query and forgetting the fallback is how a page ends
    up blank for the people who asked for less movement."""
    motion = read("src", "components", "marketing", "motion.js")
    assert "export const still" in motion
    block = motion[motion.index("export const still") :]
    assert "opacity: 1" in block
    assert "duration: 0" in block


def test_the_count_up_does_not_count_under_reduced_motion():
    """Not a faster count: no count. A number ticking is motion whatever its
    duration, and somebody who asked for less of it did not ask for a shorter
    version."""
    src = read("src", "components", "marketing", "CountUp.jsx")
    assert "useReducedMotion" in src
    assert "useState(reduced ? value : 0)" in src


def test_the_hover_lift_is_not_on_the_element_framer_animates():
    """Framer Motion writes `transform` as an inline style, and an inline
    style beats a class — so `hover:-translate-y-*` on the node the entrance
    animates is silently dead once the entrance settles at `transform: none`.
    Measured: the border warmed and the card did not move."""
    shell = read("src", "components", "marketing", "Sections.jsx")
    point = shell[shell.index("export function Point("):shell.index("export function Points(")]
    reveal_line = [l for l in point.splitlines() if "<Reveal" in l][0]
    assert "CARD_HOVER" not in reveal_line


def test_the_image_zoom_scales_a_layer_rather_than_the_frame():
    """The frame clips and reserves the space; scaling it would grow the hole
    in the layout. The tint and the <img> are what move."""
    slot = read("src", "components", "marketing", "PlaceholderImage.jsx")
    assert "IMAGE_ZOOM" in slot
    container = slot[slot.index("data-testid={testid}") : slot.index("aria-hidden")]
    assert "IMAGE_ZOOM" not in container


# --- The marketing chrome -----------------------------------------------------


def test_the_marketing_navbar_carries_the_four_pages_and_both_actions():
    nav = read("src", "components", "marketing", "MarketingNavbar.jsx")
    assert "MARKETING_LINKS" in nav
    assert "Sign in" in nav and "Join" in nav
    assert "StudioEndorsement" in nav
    # One list feeds the bar and the sheet, because the sheet is the only
    # navigation below md and anything missing there is unreachable on a phone.
    assert nav.count("MARKETING_LINKS.map") == 2


def test_the_marketing_navbar_does_not_reach_for_the_session():
    """It has one audience. A second mode is how a variant drifts back into
    being the shared component it was created to avoid editing."""
    nav = _code("src", "components", "marketing", "MarketingNavbar.jsx")
    assert "useAuth" not in nav


def test_the_shared_navbar_and_footer_are_untouched_by_marketing():
    """The strict version of "do not modify an authenticated surface": the
    shared bar is on nineteen of them, so marketing got variants instead."""
    shared_nav = read("src", "components", "Navbar.jsx")
    assert "useAuth" in shared_nav          # still the session-aware one
    assert "NotificationBell" in shared_nav
    assert "CreatorAvatarMenu" in shared_nav
    shared_footer = read("src", "components", "Footer.jsx")
    assert "FOOTER_COLUMNS" in shared_footer


def test_the_two_link_lists_agree():
    """`lib/siteNav.js` holds the marketing menu and the shared navbar keeps
    its own copy, because editing the shared one was out of scope. Two copies
    is exactly how one of them ends up pointing at a page that moved."""
    site = read("src", "lib", "siteNav.js")
    nav = read("src", "components", "Navbar.jsx")
    block = site[site.index("export const MARKETING_LINKS") :]
    block = block[: block.index("];")]
    for to, label in re.findall(r'to: "([^"]+)", label: "([^"]+)"', block):
        assert f'to: "{to}"' in nav, to
        assert f'label: "{label}"' in nav, label


def test_the_marketing_footer_names_terms_privacy_and_a_human():
    footer = read("src", "components", "marketing", "MarketingFooter.jsx")
    assert "StudioEndorsement" in footer
    assert "CONTACT_EMAIL" in footer
    assert "copyrightYear" in footer
    site = read("src", "lib", "siteNav.js")
    assert '"/terms"' in site and '"/privacy"' in site
