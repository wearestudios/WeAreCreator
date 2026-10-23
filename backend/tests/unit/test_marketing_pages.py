"""The marketing site: home, /for-brands and /for-creators, plus /contact and the 404.

**Three pages now, where there were five.** Home is brands-first with one
band for creators; /for-brands and /for-creators each argue to one reader.
The old /how-it-works and /why-weare were folded into /for-brands as sections
and redirect there. The audience pages kept their paths, because changing a
path breaks every link and search result pointing at it.

**The copy lives in `frontend/src/content/marketing.js`, not in the pages.**
These tests read the content module evaluated in node, so the strings are the
ones the page renders rather than a regex's guess at them. The pages hold
layout and nothing else, which `test_site_foundations.py` and the sweeps
below hold them to.

**The positioning is the thing these tests mostly protect.** What we are
against is *disorganisation* — campaigns run over DMs and spreadsheets, nobody
checked, no rate in writing, no proof of what it achieved. It is deliberately
**not agencies**: WeAre Studios is one, the managed service is a real
offering, and "without an agency" would be a page arguing against our own
product.

**Every claim is one the product keeps, and the ones it does not were taken
out rather than shipped.** The rewrite's brief asked for money held before
the shoot, a review that clears itself, an exportable creator statement, a
revision cap, counter-offers, a self-serve column and "you only pay when a
deal is agreed". None of those is true of the tree this ships on.
`test_site_claims.py` pins each replacement to the code that makes it true
and refuses the original wording.
"""
import asyncio
import functools
import json
import re
import subprocess
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
    """A source file with its comments stripped and its whitespace folded.

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
    src = re.sub(r'"\s*\+\s*\n\s*"', "", src)
    return re.sub(r"\s+", " ", src)


PAGES = {
    "contact": ("src", "pages", "Contact.jsx"),
    "brands": ("src", "pages", "ForBrands.jsx"),
    "creators": ("src", "pages", "ForCreators.jsx"),
    "home": ("src", "pages", "Home.jsx"),
}

CONTENT = ("src", "content", "marketing.js")

# Which export in the content module holds each page's words.
CONTENT_EXPORT = {"home": "HOME", "brands": "BRANDS", "creators": "CREATORS"}

# The two that argue to one reader. Home is both-sides with brands first; the
# contact page argues for nothing.
ARGUING = ["brands", "creators"]
AUDIENCE = ["brands", "creators"]

# The three rebuilt pages carry photo slots. **`/contact` has none on
# purpose**: it is a form, two numbers and an address.
PAGES_WITH_IMAGERY = ["home", "brands", "creators"]

# Drawn product UI: mock screens, a spreadsheet, chat bubbles. Their words are
# illustration rather than argument — the same footing the scroll film's drawn
# interfaces had — so they are swept for claims and names like everything
# else, but they do not count against a page's word budget.
ILLUSTRATION_KEYS = {"card", "screen", "sheetHead", "sheetRows", "bubbles", "hereRows"}


@functools.lru_cache(maxsize=1)
def content():
    """The content module, evaluated. It imports nothing, so node can run it
    as it stands."""
    script = read(*CONTENT) + (
        "\nconsole.log(JSON.stringify({HOME, BRANDS, CREATORS, ASK, FACTS, WHATSAPP_HREF}));"
    )
    out = subprocess.run(
        ["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=60
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def _walk(node, path=()):
    """Every string under `node`, with the key path that leads to it."""
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from _walk(v, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, path + (i,))


def _page_strings(name, *, illustration=True, meta=True):
    block = content()[CONTENT_EXPORT[name]]
    out = []
    for path, text in _walk(block):
        keys = {p for p in path if isinstance(p, str)}
        if not illustration and keys & ILLUSTRATION_KEYS:
            continue
        if not meta and "meta" in keys:
            continue
        out.append(text)
    return out


def page_text(name):
    """Everything a reader of the page can see, as one string: its content
    block, the asks it spreads, the hero screens on home, and the page source
    itself with comments stripped."""
    if name not in CONTENT_EXPORT:
        return copy_of(*PAGES[name])
    c = content()
    parts = list(_page_strings(name))
    src = copy_of(*PAGES[name])
    for key in set(re.findall(r"ASK\.(\w+)", src)):
        parts += [c["ASK"][key]["label"], c["ASK"][key].get("to") or c["ASK"][key].get("href")]
    if name == "home":
        parts += list(c["FACTS"]["confirmedClients"])
    return " ".join(parts) + " " + src


# --- The positioning ----------------------------------------------------------


@pytest.mark.parametrize("name", list(PAGES))
def test_no_page_positions_us_against_agencies(name):
    """WeAre Studios *is* an agency and the managed service is a real
    offering. "Without an agency" would be a page arguing against our own
    product — and it is exactly the phrase a well-meaning copy edit reaches
    for."""
    text = page_text(name).lower()
    for phrase in server._FORBIDDEN_MARKETING_PHRASES:
        assert phrase not in text, f"{name}: {phrase!r}"


# --- Geography -----------------------------------------------------------------
#
# **A geographic claim is rendered from `_platform_proof` or it is not made.**
# The rebuilt pages make none: the counted-geography section lived on the two
# pages this rewrite retired, and the brief's section lists do not include it.
# `CountedGeography` stays in the tree, unmounted, for the day a page wants a
# depth claim again — and that claim will have to come through it.

_CITIES_COPY_MUST_NOT_NAME = ("bengaluru", "bangalore", "mumbai", "delhi", "blr")

# **The one place a city may be typed, and why it is not a claim.** /brands
# carries exactly six questions, and one of them is "Is this only for
# Bengaluru?" — a question a brand asks, answered "No". Naming the city in
# order to say the product is *not* limited to it is the opposite of the local
# claim this rule exists to stop, so that one question, verbatim, is exempt.
# Its answer is not.
_CITY_QUESTION = "Is this only for Bengaluru?"


@pytest.mark.parametrize("name", list(PAGES))
def test_no_page_names_a_city_in_its_copy(name):
    """A city in the copy is a geographic claim nobody re-checks."""
    strings = _page_strings(name) if name in CONTENT_EXPORT else [copy_of(*PAGES[name])]
    for text in strings:
        if text == _CITY_QUESTION:
            continue
        low = text.lower()
        for city in _CITIES_COPY_MUST_NOT_NAME:
            assert city not in low, f"{name}: {city!r} typed in copy — {text!r}"


def test_the_city_exemption_is_one_question_and_its_answer_says_no():
    """The exemption is exactly one string, it is a question, and the answer
    beside it opens with "No" — so the exemption cannot be stretched into a
    claim by rewording either half."""
    items = content()["BRANDS"]["faq"]["items"]
    hits = [i for i in items if i["q"] == _CITY_QUESTION]
    assert len(hits) == 1
    assert hits[0]["a"].startswith("No.")
    for city in _CITIES_COPY_MUST_NOT_NAME:
        assert city not in hits[0]["a"].lower()


@pytest.mark.parametrize("name", list(PAGES))
def test_no_page_names_a_city_in_its_title_or_description(name):
    """The meta description is the longest-lived copy on the site: written
    once and read by strangers for years."""
    if name in CONTENT_EXPORT:
        meta = content()[CONTENT_EXPORT[name]]["meta"]
        found = [meta["title"], meta["description"]]
    else:
        src = copy_of(*PAGES[name])
        found = re.findall(r'(?:title|description)=\{?"((?:[^"\\]|\\.)*)"', src)
    for text in found:
        for city in _CITIES_COPY_MUST_NOT_NAME:
            assert city not in text.lower(), f"{name}: {city!r} in page meta — {text!r}"


def test_no_rebuilt_page_makes_an_uncounted_depth_claim():
    """Replaces `test_the_geography_sentence_is_rendered_from_the_counted_city`
    and `test_geography_is_stated_as_depth_rather_than_identity`.

    Both pinned the mechanism on /for-brands and /why-weare: the deepest city
    arrived as an argument from `CountedGeography`. Those pages are gone and
    the new ones make no depth claim at all — so what is pinned now is that
    none of them types one, because a "deepest" with no count behind it is the
    exact claim the mechanism existed to prevent."""
    for name in CONTENT_EXPORT:
        assert "deepest" not in page_text(name).lower(), name
        assert "CountedGeography" not in read(*PAGES[name]), name


# --- The managed offer, and the money ------------------------------------------


def test_the_managed_offer_is_stated_rather_than_offered_as_a_choice():
    """**The product is managed-only, so there is no choice to describe.**

    The rewrite's brief asked, twice, for a table headed "Run it yourself"
    against "Have us run it". A brand cannot invite creators or reach a raw
    application, so that column describes something that does not exist. The
    table compares running it over DMs with running it here, and the banned
    phrases stay banned on /for-brands, where /why-weare's half of this rule
    now lives. (Home's closing button says "Have us run it" — it opens a
    WhatsApp chat, and there it is an invitation rather than a column.)"""
    text = page_text("brands").lower()
    for gone in ("run it yourself", "self-serve", "hand it over", "you choose per campaign",
                 "have us run it"):
        assert gone not in text, gone
    assert "no retainer" in text
    assert "creators keep 100% of their fee" in text
    assert "we shortlist" in text and "run the shoot day" in text


def test_the_brand_page_states_the_two_commercial_terms():
    """Where our margin sits, and the refund with the one thing that
    forfeits it. Formerly asserted across /for-brands and /why-weare."""
    text = page_text("brands").lower()
    assert "creators keep 100% of their fee" in text and "ours is separate" in text
    assert "campaign fee comes back if we can't fill it" in text
    assert "unless you turned down everyone we shortlisted" in text


def test_the_pages_use_the_marketing_chrome_not_the_shared_chrome():
    """The shared `Navbar` and `Footer` are on nineteen authenticated
    surfaces. Marketing got variants rather than edits."""
    shell = read("src", "components", "marketing", "Sections.jsx")
    assert "MarketingNavbar" in shell and "MarketingFooter" in shell
    assert 'from "@/components/Navbar"' not in shell
    assert 'from "@/components/Footer"' not in shell
    for name in CONTENT_EXPORT:
        src = read(*PAGES[name])
        assert "<MarketingPage" in src, name
        assert 'from "@/components/Navbar"' not in src, name
        assert 'from "@/components/Footer"' not in src, name


def test_the_enemy_named_is_disorganisation_not_a_competitor():
    """The problem is campaigns with nobody checked, no rate in writing and no
    proof of what happened. Every page that argues has to be answering it.

    Home's third assertion moved: it pinned "report", which home no longer
    carries — the report is promised on /brands, where the reader who pays
    for it is. Home names the disorganisation itself instead, in the swap
    band: a spreadsheet and sixty DMs."""
    for name in ARGUING:
        low = page_text(name).lower()
        assert "in writing" in low or "before anyone shoots" in low or "before you shoot" in low, name
        assert "verified" in low or "checked" in low, name
    home = page_text("home").lower()
    assert "verified" in home
    assert "in writing" in home
    assert "sixty dms" in home
    assert "report" in page_text("brands").lower()


def test_the_headline_direction_is_carried():
    """The H1 says what the product takes off a brand's hands, and the
    category term the business needs to rank for is in home's title."""
    home = content()["HOME"]
    assert home["hero"]["title"] == "Creator campaigns, minus the chasing."
    assert "influencer marketing" in home["meta"]["title"].lower()


# --- What each audience has to come away knowing ------------------------------


def test_the_creator_page_says_the_six_things_a_creator_needs():
    """Looks for the idea rather than the sentence it sits in. "Before you
    shoot" became "before you travel", which is the same moment said from the
    creator's side of it."""
    text = page_text("creators").lower()
    assert "paid briefs" in text                         # real work, one place
    assert "agreed in writing before you travel" in text # the rate, first
    assert "brands pay our fee, not you" in text         # they keep all of it
    assert "you keep 100%" in text
    assert "within 7 days of approval" in text           # paid on approval
    assert "a brand we have checked" in text             # brands are checked
    assert "free to join" in text                        # and it is free


def test_the_creator_page_does_not_imply_a_cut_of_their_rate():
    """"You keep all of it" is the promise. Anything that reads as a deduction
    — even a stray "commission" — undoes it."""
    text = page_text("creators").lower()
    for wrong in ("commission", "our cut", "we take a", "minus our"):
        assert wrong not in text, wrong
    assert "you keep 100% of it" in text


def test_the_brand_page_says_the_six_things_a_brand_needs():
    """**One of the six changed, because it was not true.** This pinned
    "nothing goes live until you say yes". On a campaign we run — which is
    every brand-posted brief — the draft gate defaults off, so a brand's yes
    comes on the delivered work. What is true, and what the comparison says,
    is that approving the work stays the brand's."""
    text = page_text("brands").lower()
    assert "read from instagram" in text                # real audience stats
    assert "quote" in text and "match" in text          # every creator, every rate
    assert "no retainer" in text and "creators keep 100% of their fee" in text
    assert "approving the work" in text and "this one stays yours" in text
    assert "nothing goes live until you say yes" not in text
    assert "report" in text                             # proof at the end
    assert "we shortlist" in text                       # the managed offer


# --- One ask per page ---------------------------------------------------------


@pytest.mark.parametrize(
    "name,ask,label",
    [("brands", "postBrief", "Post a brief"), ("creators", "joinFree", "Join free")],
)
def test_each_audience_page_asks_once_in_the_same_words_twice(name, ask, label):
    """Top and bottom, same words: both buttons (and the phone's sticky bar)
    spread one constant, which is what makes "the same words" structural
    rather than remembered."""
    src = read(*PAGES[name])
    assert content()["ASK"][ask]["label"] == label
    assert src.count(f"ask={{ASK.{ask}}}") == 3, name
    assert f"<StickyCta ask={{ASK.{ask}}}" in src
    assert "testid={IDS.ctaTop}" in src and "testid={IDS.ctaBottom}" in src


def test_the_audience_pages_do_not_ask_for_the_other_audience():
    """A creator reading the brand page is in the wrong place, and a second
    CTA offering to send them elsewhere is how a page stops asking once."""
    assert "ASK.joinFree" not in read(*PAGES["brands"])
    assert "role=creator" not in page_text("brands")
    assert "ASK.postBrief" not in read(*PAGES["creators"])
    assert "role=brand" not in page_text("creators")


def test_home_is_brands_first_with_one_door_for_creators():
    """Replaces `test_the_two_audience_pages_do_not_route_to_each_other_mid_page`
    and `test_the_both_sides_pages_offer_two_paths_rather_than_inventing_one_ask`.

    Home used to end on `TwoPaths`, two equal doors. It is brands-first now —
    the hero, the close and the phone's sticky bar all ask a brand to post a
    brief, in the same words — and creators get one band of their own, with
    one door to /for-creators. The audience pages still never route to each
    other."""
    src = read(*PAGES["home"])
    assert src.count("ask={ASK.postBrief}") == 3
    assert src.count("ask={ASK.talkWhatsapp}") == 1 and src.count("ask={ASK.haveUsRunIt}") == 1
    assert "TwoPaths" not in src
    assert content()["ASK"]["forCreators"]["to"] == "/for-creators"
    assert src.count("ASK.forCreators") == 1
    for name in AUDIENCE:
        assert "TwoPaths" not in read(*PAGES[name]), name
    assert "export function TwoPaths" not in read("src", "components", "marketing", "Sections.jsx")


# --- Previews and routing -----------------------------------------------------


@pytest.mark.parametrize("name", list(CONTENT_EXPORT))
def test_each_page_sets_its_own_title_description_and_path(name):
    """`PageMeta`, through `MarketingPage`, writes the title, the description,
    the canonical and the Open Graph tags. The three rebuilt pages take their
    title and description from the content module and name their own path."""
    src = read(*PAGES[name])
    meta = content()[CONTENT_EXPORT[name]]["meta"]
    assert len(meta["title"]) >= 8 and len(meta["description"]) >= 20
    assert re.search(rf"const \{{ meta[^}}]*\}} = {CONTENT_EXPORT[name]};", src), name
    assert "title={meta.title}" in src and "description={meta.description}" in src
    path = {"home": "/", "brands": "/for-brands", "creators": "/for-creators"}[name]
    assert f'path="{path}"' in src


def test_the_contact_page_sets_its_own_title_description_and_path():
    """/contact was left as it is and still writes its own literals. It used
    to be a case of the parametrised test above, which now reads the content
    module the three rebuilt pages take their meta from."""
    src = read(*PAGES["contact"])
    assert "MarketingPage" in src or "PageMeta" in src
    assert re.search(r'title="[^"]{8,}"', src)
    assert re.search(r'description="[^"]{20,}"', src)
    assert 'path="/contact"' in src


def test_no_two_pages_share_a_preview_title():
    """One title for two pages makes two links preview identically in a chat."""
    titles = [content()[e]["meta"]["title"] for e in CONTENT_EXPORT.values()]
    m = re.search(r'\btitle="([^"]+)"', read(*PAGES["contact"]))
    assert m
    titles.append(m.group(1))
    assert len(set(titles)) == len(titles), titles


@pytest.mark.parametrize("path,element", [
    ("/", "<Home />"), ("/for-brands", "<ForBrands />"), ("/for-creators", "<ForCreators />"),
    ("/contact", "<Contact />"),
])
def test_every_marketing_page_is_a_registered_route(path, element):
    app = read("src", "App.js")
    assert f'<Route path="{path}" element={{{element}}} />' in app, path


RETIRED = {
    "/how-it-works": "/for-brands",
    "/why-weare": "/for-brands",
}


def test_every_retired_path_redirects_in_all_three_places():
    """The old paths are in the footers of WhatsApp forwards and in search
    indexes. **Three lists, one answer**: the SPA's `<Navigate replace>` for a
    click inside the app, Vercel's **301** for everybody else (a real 301,
    `statusCode`, not `permanent`, which Vercel answers with a 308), and the
    server's mirror that keeps them out of the sitemap."""
    site = read("src", "lib", "siteNav.js")
    block = site[site.index("export const RETIRED_MARKETING_PATHS") :]
    block = block[: block.index("];")]
    assert dict(re.findall(r'\["([^"]+)", "([^"]+)"\]', block)) == RETIRED
    app = read("src", "App.js")
    assert "RETIRED_MARKETING_PATHS.map" in app
    assert "<Navigate to={to} replace />" in app
    redirects = json.loads(read("vercel.json"))["redirects"]
    assert {r["source"]: r["destination"] for r in redirects} == RETIRED
    assert all(r.get("statusCode") == 301 and "permanent" not in r for r in redirects)
    assert dict(server.RETIRED_MARKETING_PATHS) == RETIRED
    for old in RETIRED:
        assert f'path="{old}"' not in app, f"{old} still renders a page"


def test_the_retired_pages_are_gone_rather_than_unrouted():
    """Deleted, not left in the tree with nothing pointing at them. The two
    audience pages are rewritten in place, at the paths they always had."""
    pages = FRONTEND / "src" / "pages"
    for gone in ("Landing.jsx", "HowItWorks.jsx", "WhyWeAre.jsx", "Brands.jsx", "Creators.jsx"):
        assert not (pages / gone).exists(), gone
    for kept in ("Home.jsx", "ForBrands.jsx", "ForCreators.jsx"):
        assert (pages / kept).exists(), kept


def test_the_marketing_links_are_router_links_not_anchors():
    """An anchor to a route the SPA owns is a full page load. The only `<a>`s
    the public parts write are an in-page anchor and the WhatsApp link."""
    nav = read("src", "components", "Navbar.jsx")
    for path in ("/for-brands", "/for-creators"):
        assert f'to: "{path}"' in nav, path
        assert f'href: "{path}"' not in nav, path
    parts = copy_of("src", "components", "marketing", "SiteParts.jsx")
    assert "<Link" in parts and '<a href="/' not in parts
    for name in CONTENT_EXPORT:
        assert '<a href="/' not in copy_of(*PAGES[name]), name


def test_the_navbar_offers_the_pages_and_both_auth_actions():
    """The logged-out menu and the mobile sheet that has to match it — the
    sheet is the only navigation below md. Two pages and a person, now that
    How it works and Why WeAre Creators are sections of /brands."""
    nav = read("src", "components", "Navbar.jsx")
    for label in ("For brands", "For creators", "Contact"):
        assert f'label: "{label}"' in nav, label
    for gone in ("How it works", "Why WeAre Creators"):
        assert f'label: "{gone}"' not in nav, gone
    assert 'data-testid="nav-login-link"' in nav
    assert 'data-testid="nav-signup-link"' in nav
    assert 'data-testid="nav-login-link-mobile"' in nav
    assert 'data-testid="nav-signup-link-mobile"' in nav
    assert nav.count("MARKETING_LINKS") >= 3
    assert "MARKETING_LINKS).map" in nav
    assert "MARKETING_LINKS.map" in nav


# --- The design system --------------------------------------------------------


@pytest.mark.parametrize("name", list(CONTENT_EXPORT))
def test_each_page_wears_the_marketing_scale(name):
    """Replaces `test_each_page_wears_the_design_system`. The pages used to
    borrow the product's fluid scale; they are set on the marketing scale now,
    which carries Fraunces with it, and the overline is the `mkt-label`."""
    src = read(*PAGES[name])
    parts = read("src", "components", "marketing", "SiteParts.jsx")
    assert re.search(r"\bmkt-(?:display|h1)\b", src), name
    assert "mkt-h2" in parts and "mkt-label" in parts
    assert "bg-primary" in parts, "the primary ask is the semantic token, never a colour"


@pytest.mark.parametrize("name", list(CONTENT_EXPORT))
def test_no_heading_uses_a_flat_text_size(name):
    """A heading on a public page is on the marketing scale; a flat `text-*`
    size on one is the product's type leaking back in."""
    for rel in (PAGES[name], ("src", "components", "marketing", "SiteParts.jsx")):
        src = read(*rel)
        for m in re.finditer(r"<h[123][^>]*className=\{?[`\"]([^`\"]+)[`\"]", src):
            classes = m.group(1)
            assert "mkt-" in classes, f"{rel[-1]}: heading off the marketing scale — {classes}"
            flat = re.findall(r"\btext-(xs|sm|base|lg|xl|\dxl)\b", classes)
            assert not flat, f"{rel[-1]}: {flat} in {classes}"


@pytest.mark.parametrize("name", PAGES_WITH_IMAGERY + ["contact", "notfound"])
def test_every_page_carries_the_footer(name):
    parts = PAGES.get(name, ("src", "pages", "NotFound.jsx"))
    assert "MarketingPage" in read(*parts), name


# --- Photographs --------------------------------------------------------------


def _slot_ids(name):
    src = read(*PAGES[name]) + read("src", "components", "marketing", "SiteParts.jsx")
    ids = set(re.findall(r'slot="([\w-]+)"', read(*PAGES[name])))
    ids |= set(re.findall(r'<PhotoSlot id="([\w-]+)"', src))
    return ids


@pytest.mark.parametrize("name", PAGES_WITH_IMAGERY)
def test_every_page_has_a_photo_slot_and_every_slot_is_briefed(name):
    """Replaces the three `PlaceholderImage` rules for the rebuilt pages
    (`test_every_page_has_deliberate_image_slots`,
    `test_every_image_slot_says_what_belongs_in_it`,
    `test_every_image_slot_is_marked_for_the_photographer`). The slot is a
    `PhotoSlot` naming an id; its brief lives in the manifest beside the `src`
    that will fill it (shown on previews only), and so does the headline a
    visitor sees in production until a photograph exists."""
    ids = _slot_ids(name)
    assert ids, name
    manifest = read("src", "content", "photoSlots.js")
    for sid in ids:
        m = re.search(rf'"{re.escape(sid)}": \{{(.*?)\n    \}},', manifest, flags=re.S)
        assert m, f"{name}: slot {sid!r} is not in the manifest"
        brief = re.search(r'brief: SHOW_BRIEFS\s*\?\s*"([^"]+)"', m.group(1))
        assert brief and len(brief.group(1)) > 40, f"{name}: {sid} has no real brief"
        assert re.search(r'fallbackHeadline: "[^"]{10,}"', m.group(1)), f"{name}: {sid} has no fallback"


@pytest.mark.parametrize("name", PAGES_WITH_IMAGERY)
def test_no_image_path_is_written_in_a_page(name):
    """Adding a photograph is a file drop and one manifest line. A path in
    JSX is a second place it has to be changed."""
    for rel in (PAGES[name], ("src", "components", "marketing", "SiteParts.jsx"),
                ("src", "components", "marketing", "siteMocks.jsx"),
                ("src", "components", "marketing", "ComparisonBand.jsx")):
        code = copy_of(*rel)
        assert not re.search(r"\.(?:png|jpe?g|webp|avif|svg)\b|/img/", code), rel


def test_every_full_bleed_band_is_the_two_to_one_slot():
    """Each page has one full-bleed photograph at 2400×1200, under the id the
    brief names."""
    manifest = read("src", "content", "photoSlots.js")
    for name, sid in (("home", "home-on-location"), ("brands", "brands-full-room"),
                      ("creators", "creators-on-shoot")):
        assert f'slot="{sid}"' in read(*PAGES[name]), name
        block = manifest[manifest.index(f'"{sid}"') :]
        assert "width: 2400," in block[:400] and "height: 1200," in block[:400], sid


# --- The numbers --------------------------------------------------------------


@pytest.mark.parametrize("name", list(PAGES))
def test_no_page_writes_a_proof_figure_into_its_copy(name):
    """A hardcoded "500+ creators" is a claim that was true on the day
    somebody typed it."""
    text = page_text(name)
    text = re.sub(r'className="[^"]*"', "", text)
    text = re.sub(r"\b(24 hours|100%|one|two|three|four|six)\b", "", text)
    for claim in re.findall(r"\b\d[\d,]*\+", text):
        pytest.fail(f"{name}: hardcoded figure {claim!r}")


@pytest.mark.parametrize("name", list(PAGES))
def test_no_page_claims_more_than_the_operation_does(name):
    """Read off `_FORBIDDEN_MARKETING_PHRASES`, so the server's list and this
    sweep cannot disagree. "Guarantee" is on it — which is why the section
    the brief calls "the guarantees" is headed "What is always true" on the
    page."""
    text = page_text(name).lower()
    for phrase in server._FORBIDDEN_MARKETING_PHRASES:
        assert phrase not in text, f"{name}: {phrase}"


@pytest.mark.parametrize("word", ["vets", "vetted", "vetting"])
def test_no_page_reintroduces_the_old_vocabulary(word):
    for name in PAGES:
        assert word not in page_text(name).lower(), f"{name}: {word}"


def test_home_names_only_real_campaign_categories():
    text = page_text("home").lower()
    for absent in ("tech & gadgets", "gadgets", "automotive", "gaming"):
        assert absent not in text, absent


def test_home_does_not_promise_that_every_brief_pays_money():
    """Barter briefs are real."""
    assert "no free product" not in page_text("home").lower()


# --- Home ---------------------------------------------------------------------


def test_home_is_the_eight_sections_in_order():
    """Replaces `test_home_keeps_only_what_routes`. Home is brands-first and
    eight sections long: hero, the problem, a photograph, the four steps, the
    navy band, who built it, the creator door, the close — in that order, and
    nothing else. The proof strip, the brand wall, the scroll film, the case
    studies and the leaderboard are not on it; the three server-backed ones
    stay in the tree, unmounted."""
    src = copy_of(*PAGES["home"])
    body = src[src.index("export default function Home") :]
    order = ["<Hero />", "<ComparisonBand", '<PhotoBand slot="home-on-location"', "<HowItWorks",
             "<PromiseBand", "<WhoBuiltIt", "<CreatorDoor", "<Closing"]
    positions = [body.index(tag) for tag in order]
    assert positions == sorted(positions), order
    for gone in ("ProofStrip", "BrandWall", "CampaignFilm", "CaseStudyStrip", "CreatorLeaderboard",
                 "TwoPaths", "HandshakeBand", "HeroSlider", "KineticHeadline"):
        assert gone not in src, gone


def test_every_section_opens_on_the_numbered_rule():
    """**"(02)", a hairline, the section's name, then the heading.** Every
    numbered section goes through `SectionHead`/`SectionRule`, and the numbers
    run in order down each page — a reader scanning the rules is reading a
    contents list, so a skipped or repeated number is a broken one."""
    parts = copy_of("src", "components", "marketing", "SiteParts.jsx")
    rule = parts[parts.index("export function SectionRule") : parts.index("export function SectionHead")]
    assert "{sectionNumber(n)}" in rule and 'h-px flex-1 bg-border' in rule and "{label}" in rule
    expected = {"home": [2, 4, 5, 6, 7, 8], "brands": [1, 2, 3, 5, 6, 7, 8], "creators": [1, 2, 3, 5, 6, 7]}
    for name, numbers in expected.items():
        src = copy_of(*PAGES[name])
        got = [int(n) for n in re.findall(r"\bn=\{(\d+)\}", src)]
        assert got == numbers, (name, got)
    out = subprocess.run(
        ["node", "--input-type=module", "-e", read(*CONTENT) + "\nconsole.log(sectionNumber(2));"],
        capture_output=True, text=True, timeout=60,
    )
    assert out.stdout.strip() == "(02)"


def test_home_sends_readers_on_rather_than_telling_them_everything():
    """A brand to signup, anybody to a person on WhatsApp, a creator to
    /for-creators."""
    text = page_text("home")
    for dest in ("/signup?role=brand", "https://wa.me/", "/for-creators"):
        assert dest in text, dest


def test_step_three_is_the_one_we_handle():
    """The managed service sells itself on the step it takes off a brand's
    hands, quietly, without a section of its own — and the hero's rail links
    to each step by anchor rather than sliding between them."""
    how = content()["HOME"]["how"]
    assert [i["title"] for i in how["items"]] == [s["label"] for s in content()["HOME"]["steps"]]
    assert [bool(i.get("weHandle")) for i in how["items"]] == [False, False, True, False]
    assert how["weHandle"] == "We handle this part"
    src = read(*PAGES["home"])
    assert "href={`#step-${s.key}`}" in src and "id={`step-${step.key}`}" in src
    # "you only touch two": the brand's own steps are exactly two.
    assert sum(1 for i in how["items"] if i["yours"]) == 2


def test_who_built_it_names_only_the_confirmed_clients():
    """Replaces `test_who_built_it_is_absent_until_three_real_names_are_supplied`.
    The three real names arrived, so the section is on: the marquee reads
    `FACTS.confirmedClients` and nothing else, and no other page or drawn
    screen carries a real client's name. No WeAre Studios team member is
    named in it."""
    clients = content()["FACTS"]["confirmedClients"]
    assert clients == ["The Brew Factory", "9889", "The Rameshwaram Cafe"]
    home = copy_of(*PAGES["home"])
    assert "items={FACTS.confirmedClients}" in home
    for name in ("brands", "creators"):
        for real in clients:
            assert real not in page_text(name), (name, real)
    drawn = " ".join(_page_strings("home"))
    for real in ("The Brew Factory", "Rameshwaram"):
        assert real not in drawn, real


# --- /brands: what /how-it-works and /why-weare used to argue -----------------


def test_the_brand_page_carries_the_trust_mechanics_the_journey_page_did():
    """Replaces `test_how_it_works_carries_the_four_trust_mechanics` and
    `test_how_it_works_states_the_payment_flow_the_way_the_product_works`.

    The journey page is a section of /for-brands now. Of its four mechanics,
    three survive as true and are here: creators checked, the terms frozen in
    writing, payment on approved work. The fourth — "approval before it is
    public" — is not true by default on a campaign we run, and is not
    carried. The payment flow is the product's own: fees are invoiced to the
    brand and we pay the creator after approval."""
    text = page_text("brands").lower()
    assert "checked by a person" in text
    assert "frozen into the terms" in text
    assert "after you approve the work" in text
    assert "invoiced to you" in text and "we pay the creator" in text
    assert "approval before it is public" not in text


def test_the_brand_page_makes_the_standalone_case_why_weare_did():
    """Replaces `test_why_weare_makes_the_standalone_case`."""
    text = page_text("brands").lower()
    assert "we shortlist" in text                         # the managed offer
    assert "checked by a person" in text                  # verified people
    assert "creators keep 100% of their fee" in text      # money handled properly
    assert "report" in text                               # results reported


def test_the_brand_faq_is_the_questions_the_brief_names():
    """Replaces `test_the_brand_faq_is_exactly_the_six_questions`: eight now,
    and the GST one renders only once `gstInvoiceConfirmed` is true."""
    items = content()["BRANDS"]["faq"]["items"]
    assert [i["q"] for i in items] == [
        "What if nobody applies?",
        "What if the content is bad?",
        "Can I use creators I already work with?",
        "Who owns the content?",
        "Is this only for Bengaluru?",
        "Do I have to use escrow?",
        "Do I get a GST invoice?",
        "Can you run a launch night?",
    ]
    assert [i.get("showIf") for i in items].count("gstInvoiceConfirmed") == 1
    assert items[-1]["a"] == (
        "Yes. That's the managed side — the venue plan, the creator list, the run of show and the night itself."
    )
    src = copy_of(*PAGES["brands"])
    assert "items.filter((item) => !item.showIf || FACTS[item.showIf] === true)" in src
    assert content()["FACTS"]["gstInvoiceConfirmed"] is None


def test_the_comparison_keeps_the_row_that_makes_it_credible():
    """The sign-off reads "You — this one stays yours", word for word, on our
    side. The row is labelled *the work* rather than *drafts*: on a campaign
    we run, drafts on the way may be reviewed by our manager, and the final
    approval of what is delivered is the brand's step."""
    compare = content()["BRANDS"]["compare"]
    heads = [r[0] for r in compare["rows"]]
    assert heads == ["Writing the brief", "Shortlisting", "Shoot day", "Launch night or influencer event",
                     "Approving the work", "Cost"]
    assert compare["rows"][4][2] == "You — this one stays yours"
    assert compare["rows"][3][2] == "We run it, guest list to the night itself"
    assert compare["columns"][1:] == ["Over DMs and a spreadsheet", "With WeAre Creators"]


def test_the_comparison_is_two_cards_on_a_phone():
    """A table from `md` up and two stacked cards below it."""
    parts = copy_of("src", "components", "marketing", "SiteParts.jsx")
    table = parts[parts.index("export function CompareTable") : parts.index("export function Faq")]
    assert "hidden overflow-hidden rounded-lg border border-border bg-card md:block" in table
    assert "md:hidden" in table and "<dl" in table


def test_the_fee_is_read_from_the_one_fact():
    """The fee card shows `platformFeeText()` through `<Known>`: while the
    fact is null nothing is printed in its place — no "TBC", no made-up
    figure."""
    src = read(*PAGES["brands"])
    assert "<Known value={platformFeeText()} name=\"platformFeePercent\">" in src
    assert content()["FACTS"]["platformFeePercent"] is None
    assert not re.search(r"\d\s?%", " ".join(_page_strings("brands", illustration=False)).replace("100%", ""))


def test_our_payout_window_is_the_platform_default_and_said_as_one():
    """Replaces `test_our_payout_window_is_read_rather_than_typed`. The
    brief makes "within 7 days of approval" a public promise. It is the
    platform default (`creator_payout_days`), so the copy may say 7 — and
    every place that says it says the same thing, so changing the promise is
    one search."""
    assert server._CREATOR_PAYOUT_SETTINGS_ID == "creator_payout_days"
    text = " ".join(_page_strings("creators")).lower()
    for m in re.finditer(r"within (\d+) days of approval", text):
        assert m.group(1) == "7"
    assert "automatically" not in text, "a payout is made by a person"


# --- /creators ----------------------------------------------------------------


def test_the_money_band_counts_once_and_names_the_amount_once():
    """The amount counts, once, through the existing `CountUp`. A screen
    reader reads the figure, not the count."""
    src = copy_of(*PAGES["creators"])
    band = src[src.index("function MoneyBand") : src.index("export default function ForCreators")]
    assert "<CountUp value={money.amount} />" in band
    assert 'className="sr-only"' in band and 'aria-hidden className="mkt-display' in band
    assert 'data-surface="dark"' in band
    assert src.count('data-surface="dark"') == 1, "the money band is the page's one navy section"


# --- The copy budget ----------------------------------------------------------
#
# **Raised for this rebuild, and by the copy the rewrite brief itself wrote.**
# The brief specifies home's eight sections and /for-brands' seven nearly word
# for word — the hero's lead and its "built for" line, four steps each with a
# line, three cards in "who built it", a scroll-inked sentence, eight FAQ
# answers — and that copy measures 374 and 600. The budgets are those figures
# plus a little headroom, so a section added next month still has to argue
# with a number; /for-creators (313) fits its old one. The per-headline (12) and
# per-line (32) caps did not move. Drawn product UI is illustration and does
# not count; the meta title and description are held by the meta tests.
BUDGET = {
    "home": 390,
    "brands": 620,
    "creators": 330,
    "contact": 200,
}

HEADLINE_WORDS = 12
LINE_WORDS = 32

_HEADLINE_KEYS = {"title", "label", "q", "eyebrow"}
_LINE_KEYS = {"line", "a", "closing"}


def _block_strings(src, marker):
    """Every string literal inside one top-level object literal."""
    start = src.index(marker)
    depth, i = 0, start
    while i < len(src):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    return _literals(src[start : i + 1])


def _literals(block):
    """Double-quoted strings and template literals, comment lines dropped
    first — a backticked identifier in a comment is not page copy."""
    block = "\n".join(
        line for line in block.splitlines() if not line.lstrip().startswith("//")
    )
    out = re.findall(r'"((?:[^"\\]|\\.)*)"', block)
    out += [
        re.sub(r"\$\{[^}]*\}", "city", t)
        for t in re.findall(r"`((?:[^`\\]|\\.)*)`", block)
    ]
    return out


def _copy_strings(name):
    if name in CONTENT_EXPORT:
        return _page_strings(name, illustration=False, meta=False)
    return _block_strings(read(*PAGES[name]), "const COPY = {")


def _words(text):
    return [w for w in re.split(r"\s+", text.strip()) if re.search(r"[A-Za-z0-9]", w)]


@pytest.mark.parametrize("name", list(BUDGET))
def test_every_page_stays_inside_its_word_budget(name):
    total = sum(len(_words(t)) for t in _copy_strings(name))
    assert total <= BUDGET[name], f"{name}: {total} words, budget {BUDGET[name]}"


def _keyed(name, keys):
    block = content()[CONTENT_EXPORT[name]]
    for path, text in _walk(block):
        named = [p for p in path if isinstance(p, str)]
        if named and named[-1] in keys and not (set(named) & ILLUSTRATION_KEYS) and "meta" not in named:
            yield text


@pytest.mark.parametrize("name", list(CONTENT_EXPORT))
def test_no_headline_runs_past_the_headline_cap(name):
    """Titles, labels, questions and eyebrows."""
    heads = list(_keyed(name, _HEADLINE_KEYS))
    assert heads
    for text in heads:
        n = len(_words(text))
        assert n <= HEADLINE_WORDS, f"{name}: {n} words — {text!r}"


@pytest.mark.parametrize("name", list(CONTENT_EXPORT))
def test_no_supporting_line_runs_past_the_line_cap(name):
    """Lines, closing lines and FAQ answers."""
    lines = list(_keyed(name, _LINE_KEYS))
    assert lines
    for text in lines:
        n = len(_words(text))
        assert n <= LINE_WORDS, f"{name}: {n} words — {text!r}"


def test_the_contact_page_keeps_its_own_caps():
    """/contact was left as it is; its `COPY` block is still held to the same
    two caps."""
    src = read(*PAGES["contact"])
    block = src[src.index("const COPY = {") :]
    for m in re.finditer(r'(\w*[Tt]itle|label):\s*"((?:[^"\\]|\\.)*)"', block):
        assert len(_words(m.group(2))) <= HEADLINE_WORDS, m.group(2)
    for m in re.finditer(r'\b(line|\w+Line|footnote):\s*"((?:[^"\\]|\\.)*)"', block):
        assert len(_words(m.group(2))) <= LINE_WORDS, m.group(2)


def _code(*parts):
    """Source with comments removed."""
    src = read(*parts)
    src = re.sub(r"\{/\*.*?\*/\}", "", src, flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(
        l for l in src.splitlines() if not l.lstrip().startswith("//")
    )


def test_the_primitives_have_no_prop_that_accepts_a_paragraph():
    """The shape is what enforces the copy rules: a section takes a title and
    one `line`. Extended to `SiteParts.jsx`, which is the furniture now."""
    for name in ("Sections.jsx", "SiteParts.jsx"):
        shell = _code("src", "components", "marketing", name)
        assert not re.search(r"\bbody\b\s*[,}:=]", shell), name
        assert not re.search(r"\bbody\b\s*\}", shell), name


def test_the_hover_is_colour_border_and_transform_at_the_interactive_duration():
    """Replaces `test_the_hover_lift_is_not_on_the_element_framer_animates`.
    That rule existed because `Point` hovered the element framer animated;
    `Point` is gone and nothing on these pages is framer-animated. What holds
    now is the band: a hover transitions colour, border and transform only,
    at `--mkt-interactive`, and never `transition-all`."""
    parts = _code("src", "components", "marketing", "SiteParts.jsx")
    assert "transition-[color,background-color,border-color,transform]" in parts
    assert "[transition-duration:var(--mkt-interactive)]" in parts
    for rel in (("src", "components", "marketing", "SiteParts.jsx"),
                ("src", "components", "marketing", "siteMocks.jsx"),
                *(PAGES[n] for n in CONTENT_EXPORT)):
        assert "transition-all" not in _code(*rel), rel


# --- The footer, and the sitemap ----------------------------------------------


def test_the_footer_links_every_marketing_page():
    """Three pages and a person, and no link to a retired path."""
    site = read("src", "lib", "siteNav.js")
    cols = site[site.index("export const FOOTER_COLUMNS") : site.index("export const MARKETING_LINKS")]
    for path in ("/for-brands", "/for-creators", "/contact"):
        assert f'"{path}"' in cols, path
    for old in RETIRED:
        assert f'"{old}"' not in cols, old


def test_the_sitemap_lists_every_marketing_page():
    """Built from `MARKETING_PATHS`, so adding a page cannot quietly leave it
    out — and the retired paths are out of it, because a sitemap listing a
    redirect asks a crawler to index a page that does not exist."""
    import inspect as _inspect

    src = _inspect.getsource(server.public_sitemap)
    assert "MARKETING_PATHS" in src
    assert set(server.MARKETING_PATHS) == {"/", "/for-brands", "/for-creators", "/contact"}
    assert not set(server.MARKETING_PATHS) & set(RETIRED)


# --- The hero ----------------------------------------------------------------
#
# **These eight replaced the kinetic headline's eight, one for one.** The
# headline morphed between the eight sectors in `CATEGORY_OPTIONS` over a
# photo slider; the hero is now one static product card and one word revealed
# once. Each test keeps the rule its predecessor held and points it at the new
# contract; the docstring names what it replaced.


def _h1():
    src = read(*PAGES["home"])
    return src[src.index("<h1") : src.index("</h1>")]


def test_the_hero_names_no_sector_and_the_slider_is_gone():
    """Replaces `test_the_headline_morphs_between_real_campaign_categories`.

    **Inverted on purpose.** That test pinned the hero's phrases to
    `CATEGORY_OPTIONS`. The hero no longer rotates anything: it is one static
    product card and one word drawn once, so nothing in it reads the category
    list, and the slider, its sector phrases, its drifts and its eight
    drawings are deleted rather than left unmounted."""
    home = copy_of(*PAGES["home"])
    assert "CATEGORY_OPTIONS" not in home and "categories" not in home
    marketing = FRONTEND / "src" / "components" / "marketing"
    for gone in ("HeroSlider.jsx", "KineticHeadline.jsx", "sectorCycle.jsx", "HeroDeck.jsx", "heroScreens.jsx"):
        assert not (marketing / gone).exists(), gone
    assert not (FRONTEND / "src" / "lib" / "heroDeck.js").exists()
    illus = FRONTEND / "public" / "img" / "marketing"
    for sector in ("fnb", "hospitality", "retail", "real-estate", "fashion", "travel", "wellness", "lifestyle"):
        assert not (illus / f"hero-{sector}.svg").exists(), sector


def test_the_h1_is_static_and_whole_from_the_first_paint():
    """Replaces `test_the_constant_half_of_the_headline_never_animates`.

    The whole `h1` is constant now — "Creator campaigns, minus the chasing."
    — and is in the DOM complete from the first paint. Nothing in it holds
    state or reads a timer; its only motion is one word's reveal."""
    assert content()["HOME"]["hero"]["title"] == "Creator campaigns, minus the chasing."
    h1 = _h1()
    assert "{title.slice(0, at)}" in h1 and "{title.slice(at + accent.length)}" in h1
    for moving in ("useState", "index", "Reveal", "motion.", "setTimeout"):
        assert moving not in h1, moving


def test_one_word_is_drawn_once_in_true_italic():
    """Replaces `test_the_morph_is_per_letter_rather_than_a_fade`. "chasing"
    is Fraunces true italic at weight 400 in the accent's ink, revealed left to
    right once at load by `WipeWord` over 520ms — a clip on a word that is
    already in the DOM, so the heading's text and name are whole throughout."""
    assert content()["HOME"]["hero"]["accent"] == "chasing"
    h1 = _h1()
    assert "<WipeWord" in h1
    assert 'className="font-normal italic text-accent-ink"' in h1
    css = read("src", "index.css")
    assert re.search(r"--mkt-wipe:\s*520ms;", css)
    assert "aria-live" not in copy_of(*PAGES["home"])


def test_the_hero_has_no_timer_at_all():
    """Replaces `test_the_picture_and_the_word_change_on_one_timer`. That rule
    existed because two clocks drifted apart. There is no clock now: the card
    writes its rows once when it comes into view, and nothing in the hero, the
    drawn screens or the problem band starts a timer."""
    for rel in (PAGES["home"], ("src", "components", "marketing", "siteMocks.jsx"),
                ("src", "components", "marketing", "ComparisonBand.jsx")):
        code = copy_of(*rel)
        assert "setTimeout" not in code and "setInterval" not in code, rel
    mocks = copy_of("src", "components", "marketing", "siteMocks.jsx")
    assert "<RowWriter rows={rows}" in mocks


def test_the_h1_is_display_scale():
    """Replaces `test_the_headline_is_poster_scale`. The h1 is `mkt-display`,
    which climbs from 52px to 104px — the brief's clamp."""
    h1 = _h1()
    assert 'className="mkt-display' in h1
    css = read("src", "index.css")
    display = re.search(r"\.mkt-display \{(.*?)\}", css, flags=re.S).group(1)
    assert "clamp(3.25rem, 1.6rem + 5vw, 6.5rem)" in display


def test_the_hero_card_reserves_its_box():
    """Replaces `test_the_headline_reserves_its_box_by_rendered_width`. The
    card's rows wait at opacity 0 in boxes they already occupy, so writing
    them moves nothing; and the chip row reserves two lines on a phone, where
    the fallback face and the webfont wrap it differently."""
    css = read("src", "index.css")
    assert re.search(r"\.mkt-row \{\s*opacity: 0;\s*\}", css)
    mocks = copy_of("src", "components", "marketing", "siteMocks.jsx")
    deal = mocks[mocks.index("export function DealCard") : mocks.index("export function StepScreen")]
    assert "min-h-[3.75rem]" in deal and "sm:min-h-0" in deal


def test_the_hero_is_still_under_reduced_motion():
    """Replaces `test_the_headline_is_static_under_reduced_motion`. The wipe
    and the row writer resolve to their end state in `index.css`; nothing in
    the hero carries a motion branch of its own."""
    css = read("src", "index.css")
    reduced = "\n".join(re.findall(r"@media \(prefers-reduced-motion: reduce\) \{(.*?)\n\}", css, flags=re.S))
    assert ".mkt-wipe" in reduced and ".mkt-row" in reduced
    assert "useReducedMotion" not in copy_of(*PAGES["home"])


def test_the_h1_has_one_stable_accessible_name():
    """Replaces `test_the_headline_has_one_stable_accessible_name`. One `h1`,
    its text the sentence; the rail under it is a `nav` of anchors, each named
    by its number and label, with a visible focus ring."""
    src = read(*PAGES["home"])
    assert src.count("<h1") == 1
    h1 = _h1()
    assert "aria-label" not in h1 and "aria-live" not in h1
    hero = src[src.index("function Hero()") : src.index("function HowItWorks")]
    rail = hero[hero.index("<nav") : hero.index("</nav>")]
    assert "aria-label={hero.railLabel}" in rail and "<ol" in rail
    assert "{s.n}" in rail and "{s.label}" in rail
    assert "focus-visible:ring-2" in rail and "focus-visible:ring-offset-background" in rail


def test_the_phone_gets_a_sticky_ask_between_the_hero_and_the_close():
    """Below `md`, once the hero has scrolled away and until the close is on
    screen. Hidden — not just invisible — while it is not wanted, so a
    keyboard cannot land on it; a 48px target; no animation."""
    sticky = copy_of("src", "components", "marketing", "StickyCta.jsx")
    assert "const shown = pastHero && !atClose;" in sticky
    assert "hidden={!shown}" in sticky and "md:hidden" in sticky
    assert "min-h-[3rem]" in sticky
    assert "animation" not in sticky and "transition" not in sticky
    for name in CONTENT_EXPORT:
        src = read(*PAGES[name])
        assert 'heroId="hero" closeId="close"' in src, name
        assert 'id="hero"' in src and 'id="close"' in src, name


def test_the_mobile_menu_traps_focus_and_closes_on_navigation():
    """The sheet is a Radix dialog — focus trapped while open, Escape closes —
    and a route change closes it too."""
    nav = copy_of("src", "components", "marketing", "MarketingNavbar.jsx")
    assert "<Sheet open={open} onOpenChange={setOpen}>" in nav
    assert "useEffect(() => { setOpen(false); }, [pathname, hash]);" in re.sub(r"\s+", " ", nav)


# --- Kept as they were: the server's proof figures, routing, motion, chrome -----


def test_the_counted_geography_component_says_nothing_without_a_city():
    """Absent and in-flight are drawn the same way, and neither invents copy.

    The component returns `null` unless there is a city, so a page below the
    proof floor has no geography section rather than one with a hole in it.
    """
    src = read("src", "components", "marketing", "CountedGeography.jsx")
    assert "if (!city) return null;" in src
    # Three states, not two: `undefined` in flight is not `null` resolved.
    assert "useState(undefined)" in src


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


def test_the_catch_all_renders_a_404_rather_than_redirecting_home():
    """A mistyped URL, a link from an old post and a brief that has since
    closed all used to land silently on the front page, which is
    indistinguishable from the link having worked."""
    app = read("src", "App.js")
    assert '<Route path="*" element={<NotFound />} />' in app
    assert '<Route path="*" element={<Navigate to="/" replace />} />' not in app


def test_signed_in_users_keep_their_role_navigation():
    """The marketing strip renders only when nobody is signed in. A brand
    clearing its applicant board does not need "Why WeAre"."""
    nav = read("src", "components", "Navbar.jsx")
    assert "checking || signedIn ? [] : MARKETING_LINKS" in nav
    assert "linksFor(user.role)" in nav


def test_the_marketing_shell_mounts_both_marketing_bars():
    sections = read("src", "components", "marketing", "Sections.jsx")
    assert "<MarketingNavbar />" in sections
    assert "<MarketingFooter />" in sections


# --- The tinted slots that outlived the rebuild ---------------------------------


@pytest.mark.parametrize("page", ["NotFound.jsx", "Login.jsx", "Signup.jsx"])
def test_every_tinted_slot_is_briefed_and_marked(page):
    """The 404 and the two auth asides still draw `PlaceholderImage`. These
    three used to sit in `test_every_page_has_deliberate_image_slots`,
    `test_every_image_slot_says_what_belongs_in_it` and
    `test_every_image_slot_is_marked_for_the_photographer`, parametrised over
    the old marketing pages plus the 404; the marketing pages moved to
    `PhotoSlot` and the rule moved with them, so what is left of those three
    is here. A slot names its brief by id, resolved against
    `PLACEHOLDER_BRIEFS`, where it compiles out of a production build."""
    src = read("src", "pages", page)
    manifest = read("src", "content", "photoSlots.js")
    ids = re.findall(r'<PlaceholderImage\b[^>]*?\bslot="([\w-]+)"', src, flags=re.S)
    assert ids, f"{page}: no tinted slot"
    for sid in ids:
        found = re.search(rf'"{re.escape(sid)}":\s*SHOW_BRIEFS\s*\?\s*"([^"]+)"', manifest)
        assert found, f"{page}: slot {sid!r} has no brief in PLACEHOLDER_BRIEFS"
        assert len(found.group(1)) > 25, f"{page}: {found.group(1)!r} is not a brief"
    assert "PLACEHOLDER IMAGE:" in src, page


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


def test_the_floors_are_a_table_rather_than_three_inline_comparisons():
    """One table, so the strip's rule can be read rather than reconstructed
    from three `if`s — and so a fourth figure cannot be added without a floor
    for it."""
    assert set(server.PROOF_FLOORS) == {"cities", "creators", "campaigns"}
    assert all(v >= 1 for v in server.PROOF_FLOORS.values())


def _proof_db(*, creators=0, campaigns=0, cities=(), campaign_status="open"):
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
            await db.campaigns.insert_one(
                {"status": campaign_status, "visibility": "public"}
            )

    asyncio.get_event_loop().run_until_complete(build())
    return db


def _proof(db, monkeypatch):
    monkeypatch.setattr(server, "db", db)
    return asyncio.get_event_loop().run_until_complete(server._platform_proof())


def test_nothing_at_all_below_the_floors(monkeypatch):
    assert _proof(_proof_db(creators=4, campaigns=2), monkeypatch) == {}


def test_all_three_appear_once_every_one_of_them_clears(monkeypatch):
    out = _proof(
        _proof_db(creators=12, campaigns=7, cities=("Bengaluru", "Mumbai", "Pune")),
        monkeypatch,
    )
    # `deepest_city` rides along so the marketing pages can render a
    # geographic claim instead of typing one. Twelve creators over three
    # cities is four each, a three-way tie, which `_id`-ascending breaks
    # deterministically — a figure that flipped between requests would make
    # the sentence it feeds flicker.
    assert out == {
        "cities": 3,
        "creators": 12,
        "campaigns": 7,
        "deepest_city": "Bengaluru",
    }


def _deepest(monkeypatch, by_city, campaigns=7):
    """Seed an explicit creator count per city and read the deepest back."""
    db = AsyncMongoMockClient()["proof"]

    async def build():
        for city, n in by_city.items():
            for _ in range(n):
                await db.creator_profiles.insert_one(
                    {
                        "user_id": ObjectId(),
                        "verification_status": "verified",
                        "city": city,
                    }
                )
        for _ in range(campaigns):
            await db.campaigns.insert_one({"status": "open", "visibility": "public"})

    asyncio.get_event_loop().run_until_complete(build())
    return _proof(db, monkeypatch)


def test_the_deepest_city_is_the_one_with_the_most_verified_creators(monkeypatch):
    """**Counted, so the sentence survives the operation moving.**

    The pages said "deepest in Bengaluru" as a literal. It was true when it
    was written, which is exactly the property that makes it dangerous — the
    copy outlives the fact. Here Mumbai is deepest and the page has to say
    so without anybody editing it.
    """
    out = _deepest(monkeypatch, {"Bengaluru": 5, "Mumbai": 9, "Pune": 4})
    assert out["deepest_city"] == "Mumbai"
    assert out["cities"] == 3


def test_an_unverified_crowd_does_not_make_a_city_deepest(monkeypatch):
    """Supply means creators a brand can actually book.

    A city full of half-finished signups is not depth, and the geography
    claim is the one place that difference is load-bearing: we would be
    telling brands to post there.
    """
    db = AsyncMongoMockClient()["proof"]

    async def build():
        for _ in range(30):
            await db.creator_profiles.insert_one(
                {"user_id": ObjectId(), "verification_status": "pending",
                 "city": "Jaipur"}
            )
        for city, n in {"Bengaluru": 7, "Mumbai": 5}.items():
            for _ in range(n):
                await db.creator_profiles.insert_one(
                    {"user_id": ObjectId(), "verification_status": "verified",
                     "city": city}
                )
        # A third verified city so the `cities` floor of 3 is cleared.
        await db.creator_profiles.insert_one(
            {"user_id": ObjectId(), "verification_status": "verified", "city": "Pune"}
        )
        for _ in range(7):
            await db.campaigns.insert_one({"status": "open", "visibility": "public"})

    asyncio.get_event_loop().run_until_complete(build())
    out = _proof(db, monkeypatch)
    assert out["deepest_city"] == "Bengaluru"


def test_below_the_floor_there_is_no_city_either(monkeypatch):
    """**The city is inside the same gate as the figures, deliberately.**

    `_platform_proof` returns `{}` as a set, so a page cannot name a city
    while the counts that would give that name a denominator are absent. "We
    are deepest in Kochi" with nothing beside it is a smaller claim than
    silence, not a bigger one — and `CountedGeography` renders nothing without
    a city, so the section disappears rather than losing its noun.
    """
    out = _deepest(monkeypatch, {"Kochi": 2}, campaigns=1)
    assert out == {}
    assert "deepest_city" not in out


def test_a_creator_with_no_city_is_not_a_city(monkeypatch):
    """City is optional on a profile that is built over several sittings, so
    blank is the ordinary state of a half-finished one. Grouping on it would
    make the empty string the deepest "city" on the platform."""
    db = AsyncMongoMockClient()["proof"]

    async def build():
        for blank in ("", None):
            for _ in range(20):
                await db.creator_profiles.insert_one(
                    {"user_id": ObjectId(), "verification_status": "verified",
                     "city": blank}
                )
        for city, n in {"Bengaluru": 3, "Mumbai": 2, "Pune": 2}.items():
            for _ in range(n):
                await db.creator_profiles.insert_one(
                    {"user_id": ObjectId(), "verification_status": "verified",
                     "city": city}
                )
        for _ in range(7):
            await db.campaigns.insert_one({"status": "open", "visibility": "public"})

    asyncio.get_event_loop().run_until_complete(build())
    out = _proof(db, monkeypatch)
    assert out["deepest_city"] == "Bengaluru"
    # And the blanks are not counted as a city in the figure either.
    assert out["cities"] == 3


@pytest.mark.parametrize(
    "short,kwargs",
    [
        ("creators", dict(creators=9, campaigns=7,
                          cities=("Bengaluru", "Mumbai", "Pune"))),
        ("campaigns", dict(creators=12, campaigns=4,
                           cities=("Bengaluru", "Mumbai", "Pune"))),
        ("cities", dict(creators=12, campaigns=7, cities=("Bengaluru", "Mumbai"))),
    ],
)
def test_one_figure_short_takes_the_whole_strip_with_it(short, kwargs, monkeypatch):
    """**All three or none**, which is the change. The old rule returned
    whichever figures passed their own floor, so real data rendered "7 cities"
    alone — a single number with no denominator, which reads as the one
    statistic we could find. A visitor draws the obvious conclusion about the
    missing ones and is right to.

    Parametrised over which figure is short, because a gate that only checks
    the first one is the version somebody writes by accident.
    """
    assert _proof(_proof_db(**kwargs), monkeypatch) == {}, short


def test_a_draft_nobody_ever_published_is_not_an_open_brief(monkeypatch):
    """The figure is briefs somebody could apply to today. Counting drafts
    would count everything anybody abandoned."""
    db = _proof_db(
        creators=12, campaigns=20, cities=("Bengaluru", "Mumbai", "Pune"),
        campaign_status="draft",
    )
    assert _proof(db, monkeypatch) == {}


def test_a_finished_campaign_is_not_an_open_brief(monkeypatch):
    """It counts what is live, not a lifetime total — so a page that says
    "open briefs" is describing something a visitor can go and look at."""
    db = _proof_db(
        creators=12, campaigns=20, cities=("Bengaluru", "Mumbai", "Pune"),
        campaign_status="completed",
    )
    assert _proof(db, monkeypatch) == {}


def test_an_invite_only_brief_is_not_counted_in_a_public_figure(monkeypatch):
    """A private brief's page 404s to a stranger. Counting it in the number we
    ask them to believe would be a figure they cannot check."""
    db = AsyncMongoMockClient()["proof"]

    async def build():
        for i, city in enumerate(["Bengaluru", "Mumbai", "Pune"] * 4):
            await db.creator_profiles.insert_one(
                {"user_id": ObjectId(), "verification_status": "verified",
                 "city": city}
            )
        for _ in range(20):
            await db.campaigns.insert_one({"status": "open", "visibility": "private"})

    asyncio.get_event_loop().run_until_complete(build())
    assert _proof(db, monkeypatch) == {}


def test_the_footer_columns_match_the_react_one():
    """Two renderers with two copies of the link list is how a footer ends up
    advertising a page that moved. The backend's copy builds the sitemap."""
    site = read("src", "lib", "siteNav.js")

    def points_at(to):
        """Whether the React list carries this destination.

        Three spellings are allowed, and the third is the interesting one: a
        path can be written inline, interpolated into a template, **or named
        by a constant defined in the same file**. `/work` is the last —
        `WORK_PATH`, because the footer and both proof strips link to it and a
        path written out three times is a path that moves twice. Resolving the
        constant here keeps the drift check honest rather than forcing the
        source to inline a value it deliberately names once.
        """
        if f'to: "{to}"' in site or f"to: `{to}" in site:
            return True
        for name in re.findall(r'to: ([A-Z_][A-Z0-9_]*)', site):
            if f'export const {name} = "{to}";' in site:
                return True
        return False

    for heading, links in server.FOOTER_COLUMNS:
        assert f'heading: "{heading}"' in site, heading
        for label, to in links:
            assert f'label: "{label}"' in site, label
            if to.startswith("mailto:"):
                assert to.split(":", 1)[1] in site
            else:
                assert points_at(to), to


def test_the_copyright_names_the_studio_and_links_to_it():
    """The copyright names WeAre Studios, linked — **which overrides a note
    that argued the other way, and the override is the point.**

    This asserted "WeAre Monk", on the reasoning that who owns the thing is a
    fact rather than a copy decision and so is carried over verbatim. That
    reasoning was sound and it was not the test's to settle: the entity named
    in a copyright line belongs to the owner, and the owner asked for WeAre
    Studios directly. A test cannot out-argue that, so it pins the new string
    instead.

    The link is pinned with it because the line now absorbs the studio credit
    `StudioEndorsement` used to carry in six places — the relationship
    belongs where ownership is already being stated, not as a standalone line
    repeated down the page. Both footers, because they are variants of one
    thing and a credit on one is a credit missing from the other.
    """
    for name in ("Footer.jsx", "marketing/MarketingFooter.jsx"):
        src = read("src", "components", *name.split("/"))
        assert "WeAre Monk" not in src, f"{name} still names the old entity"
        assert "STUDIO_NAME" in src, f"{name} does not name the studio"
        # The href specifically, not just the symbol: `STUDIO_URL` also
        # appears in the guard that renders plain text when it is unset, so
        # asserting the name alone passes with the link pointing anywhere.
        assert "href={STUDIO_URL}" in src, f"{name} does not link to it"
        assert "copyrightYear" in src, f"{name} stopped reading the year"


# **Five now.** `/work` and `/work/:slug` joined the list when case studies
# shipped, for both of the reasons `/c/:id` is on it: they are links we send a
# brand directly, so the preview is the pitch, *and* they are the one part of
# this site written to be **found** rather than sent — which needs a page that
# exists without JavaScript. A rewrite that never reaches the backend is the
# failure `/for-brands` and `/for-creators` already had, and it is silent:
# the catch-all answers with the SPA and the page looks like it works.
SERVER_RENDERED_PATHS = (
    "/c/:id",
    "/brands/:id",
    "/sitemap.xml",
    "/work",
    "/work/:slug",
    # The landing page matrix — four shapes off one route, generated from
    # live supply. See `LANDING_PATH` in server.py for why a slug that parses
    # can still 404.
    "/influencer-marketing/:slug",
    # The anonymous creator research survey. Server-rendered because it has to
    # work with no JavaScript — the form posts back to the same path.
    "/survey",
)


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


def test_the_proxy_decision_is_written_down_and_is_no_longer_pending():
    """**Inverted, because the decision was taken.**

    This used to require the words "pending decision" in `PREVIEW.md`: the
    rewrites pointed at `/index.html`, which is what the catch-all does
    anyway, so they were placeholders and an inert rewrite is
    indistinguishable from a working one by reading the file.

    The arrangement chosen is `PUBLIC_SHARE_BASE_URL` rather than the
    rewrites, for a reason that is a property of the platform rather than a
    preference: **Vercel parses `vercel.json` at deploy time, before the build
    runs**, so a rewrite destination cannot come from an environment variable
    and has to be a literal hostname committed here. So the assertion moves
    from "say this is unfinished" to "say which way it went, and what it
    costs" — and the paths are still all named, because a page added to the
    server-rendered set with no line in the record is the next silent one.
    """
    preview = (FRONTEND.parent / "PREVIEW.md").read_text()
    low = preview.lower()
    # Which way it went, and the cost stated rather than glossed.
    assert "public_share_base_url" in low
    assert "deploy time" in low
    # The static file nothing can template, named where somebody will read it.
    assert "robots.txt" in low
    # And every server-rendered path still appears, the half worth keeping.
    for path in SERVER_RENDERED_PATHS:
        assert path in preview, path


def test_robots_txt_does_not_claim_the_site_origin_serves_the_sitemap():
    """Under `PUBLIC_SHARE_BASE_URL` the sitemap is served by the API host.

    A `Sitemap:` line pointing at the site origin sends a crawler to the SPA's
    catch-all, which answers 200 with HTML — the worst shape of failure,
    because nothing looks broken. The file is static, so no environment
    variable can fix it; the comment above the line has to say so.
    """
    robots = (FRONTEND.parent / "frontend" / "public" / "robots.txt").read_text()
    assert "PUBLIC_SHARE_BASE_URL" in robots
    assert "static file" in robots, path


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


def test_the_image_zoom_scales_a_layer_rather_than_the_frame():
    """The frame clips and reserves the space; scaling it would grow the hole
    in the layout. The tint and the <img> are what move."""
    slot = read("src", "components", "marketing", "PlaceholderImage.jsx")
    assert "IMAGE_ZOOM" in slot
    container = slot[slot.index("data-testid={testid}") : slot.index("aria-hidden")]
    assert "IMAGE_ZOOM" not in container


def test_the_marketing_navbar_carries_the_pages_and_both_actions():
    """**The studio endorsement is gone from the bar**, which is a reversal.

    This required `StudioEndorsement` here. The credit moved into the
    copyright line, where ownership is already being stated, rather than
    being repeated beside the nav logo, in the mobile sheet, in both footers
    and at the foot of the closing band. One statement of a relationship is a
    statement; five is furniture.

    What the test is actually for is unchanged and still asserted: one link
    list feeding both the bar and the sheet.
    """
    nav = read("src", "components", "marketing", "MarketingNavbar.jsx")
    assert "MARKETING_LINKS" in nav
    assert "Sign in" in nav and "Join" in nav
    assert "StudioEndorsement" not in nav, "the endorsement is back in the bar"
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


def test_the_floating_cards_span_the_categories():
    src = read("src", "components", "marketing", "FloatingCards.jsx")
    keys = re.findall(r'key: "([\w-]+)"', src)
    for expected in ("launch", "fashion", "travel", "fitness"):
        assert expected in keys, expected


def test_the_floating_cards_are_placeholders_not_photographs():
    src = read("src", "components", "marketing", "FloatingCards.jsx")
    assert "PlaceholderImage" in src
    assert "http" not in re.sub(r"//.*", "", src)


def test_the_floating_cards_drift_with_transforms_only():
    """Rotation is set once; the drift is `y` off the scroll position. Nothing
    animates a layout property, which is what keeps this composited."""
    src = read("src", "components", "marketing", "FloatingCards.jsx")
    assert "useTransform" in src
    assert "style={{ y, rotate: card.rotate }}" in src
    for banned in ("top:", "left:", "height:", "width:"):
        assert banned not in _code("src", "components", "marketing", "FloatingCards.jsx"), banned


def test_the_floating_cards_freeze_under_reduced_motion():
    """The tilt and the shadow are static design, not animation — so the
    composition stays and only the drift stops."""
    src = read("src", "components", "marketing", "FloatingCards.jsx")
    assert "reduced ? 0 : -card.depth" in src


def test_the_floating_cards_thin_out_on_a_phone():
    """Four overlapping compositing layers on a 390px screen sit behind text
    nobody can read through them."""
    src = read("src", "components", "marketing", "FloatingCards.jsx")
    hidden = src.count('className: "hidden md:block')
    assert hidden >= 2, hidden


def test_the_only_shadow_on_the_marketing_site_is_the_floating_card():
    """Elevation is a hairline plus a surface tint; `box-shadow` is reserved
    for what genuinely floats. A tilted card drifting at a different rate from
    the page behind it is the one inline element that really does — and the
    exception is written down where it is taken."""
    marketing = FRONTEND.joinpath("src", "components", "marketing")
    for path in list(marketing.glob("*.js*")) + [
        FRONTEND.joinpath("src", "pages", p[2]) for p in PAGES.values()
    ]:
        text = re.sub(r"//.*", "", path.read_text())
        for m in re.findall(r"shadow-\[[^\]]+\]|\bshadow-(?:sm|md|lg|xl|2xl)\b", text):
            assert path.name == "FloatingCards.jsx", f"{path.name}: {m}"


def test_the_proof_strip_reserves_its_height_while_loading():
    """It used to render nothing until the figures landed and then appear,
    pushing every section below it down — measured at 0.0798 CLS on home, the
    entire layout-shift budget of the page in one event. Reserved, it is
    0.0002."""
    src = read("src", "components", "marketing", "ProofStrip.jsx")
    assert "const RESERVED" in src
    assert "if (stats === null)" in src
    # Both widths, because the figures wrap below `md` and a single value was
    # wrong by 52px on a phone.
    assert "md:min-h-" in src

