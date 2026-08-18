"""The brand behind the brief.

A creator could see a campaign and learn nothing about who was posting it — a
name, and that was all. `/brands/{id}` is the page that answers "who are
these people", built the same way and for the same reason as the brief's:
server-rendered, so it is shareable and something a search engine can read.

Three rules hold it up.

**It is a page about a business and nothing else.** The account behind a brand
belongs to a named person whose phone number is their WhatsApp and whose email
is their work address, and `registered_address` is frequently a director's
home — it is one of the things the verification documents carry, and those are
never publicly served. `_public_brand` is an allow-list for the same reason
`_brand_visible_creator` is: a deny-list is a list somebody forgets to add to.

**Only verified brands.** The same rule the brief's page uses: a business we
have not checked is not published under our name.

**An outlet is not a registered address.** They are two different things that
look like one. An outlet is a shopfront a creator turns up to; the registered
address is where the company is registered. Only the first is public, and the
brand types them separately for exactly that reason.
"""
import inspect
import re
from pathlib import Path

import pytest

import server

BACKEND = Path(server.__file__).resolve()
FRONTEND = BACKEND.parents[1] / "frontend" / "src"
REPO = BACKEND.parents[1]


def source(fn):
    return inspect.getsource(fn)


def profile(**kw):
    base = {
        "user_id": server.ObjectId(),
        "business_name": "Blue Tokai",
        "category": "fnb",
        "verified": True,
    }
    base.update(kw)
    return base


# --- Where it lives ---------------------------------------------------------


def test_it_is_served_outside_the_api_prefix():
    """A URL somebody can read out loud, like the brief's."""
    assert server.BRAND_PATH == "/brands"
    assert "/api" not in server.BRAND_PATH


def test_it_needs_no_account():
    params = inspect.signature(server.public_brand_page).parameters

    assert "user" not in params
    assert "require_roles" not in source(server.public_brand_page)


def test_it_is_server_rendered_html():
    """The whole reason it is here and not in the SPA: a preview crawler and a
    search crawler both read HTML, and neither runs JavaScript."""
    src = source(server.public_brand_page)

    assert "_brand_page_html" in src
    assert "text/html" in src


def test_only_verified_brands_are_public():
    src = source(server.public_brand_page)

    assert 'profile.get("verified")' in src


def test_a_bad_id_is_a_404_not_a_500():
    src = source(server.public_brand_page)

    assert "except Exception:" in src
    assert "404" in src


def test_it_is_keyed_on_the_same_id_campaigns_use():
    """`brand_id` on a campaign is the manager's user id. Keying this page on
    anything else would mean the link from a brief could not be built."""
    assert '{"user_id": oid}' in source(server.public_brand_page)


def test_the_url_is_built_from_the_same_origin_as_a_shared_brief():
    src = source(server._brand_page_url)

    assert "_share_base()" in src
    assert "BRAND_PATH" in src


# --- What a stranger may read -----------------------------------------------


def test_the_projection_is_an_allow_list():
    """A deny-list is a list somebody forgets to add to — the same reasoning
    `_BRAND_VISIBLE_CREATOR_FIELDS` is built on."""
    src = source(server._public_brand)

    assert "_PUBLIC_BRAND_FIELDS" in src
    assert "for k in _PUBLIC_BRAND_FIELDS" in src


@pytest.mark.parametrize(
    "field", ["business_name", "logo_url", "category", "about", "city", "outlets"]
)
def test_the_things_a_creator_is_deciding_on_are_public(field):
    assert field in server._PUBLIC_BRAND_FIELDS


@pytest.mark.parametrize(
    "field",
    ["contact_phone", "contact_email", "contact_person_name", "registered_address",
     "gst_number", "verification_reason"],
)
def test_the_person_and_the_paperwork_are_not(field):
    assert field not in server._PUBLIC_BRAND_FIELDS
    assert field in server.PUBLIC_BRAND_FORBIDDEN_FIELDS


def test_the_projection_drops_everything_else():
    """Not "does not render it" — is not in the dict at all, so the renderer
    cannot reach it even by accident."""
    out = server._public_brand(
        profile(contact_phone="+919812345678", registered_address="A director's house")
    )

    for banned in server.PUBLIC_BRAND_FORBIDDEN_FIELDS:
        assert banned not in out


def test_planted_contact_details_do_not_reach_the_html():
    """Run, not read. Source-reading catches the mistake somebody makes on
    purpose; running it catches the one where a value arrives through a spread
    from a document nobody remembered had one — the same reasoning
    tests/unit/test_exports.py is built on."""
    planted = {
        "contact_phone": "+919812345678",
        "contact_email": "priya@example.com",
        "contact_person_name": "Priya Raman",
        "registered_address": "No 4, 12th Cross, Bengaluru",
        "gst_number": "29ABCDE1234F1Z5",
        "verification_reason": "Licence illegible",
    }
    html = server._brand_page_html(server._public_brand(profile(**planted)), [])

    for field, value in planted.items():
        assert value not in html, f"{field} leaked onto the public page"


def test_an_outlet_is_public_and_a_registered_address_is_not():
    """The distinction the whole model turns on."""
    html = server._brand_page_html(
        server._public_brand(
            profile(
                registered_address="Flat 3, the founder's house",
                outlets=[{"name": "Indiranagar", "address": "12th Main"}],
            )
        ),
        [],
    )

    assert "12th Main" in html
    assert "founder's house" not in html


def test_the_outlet_model_says_why_it_is_not_the_registered_address():
    assert "registered" in (server.BrandOutlet.__doc__ or "").lower()


# --- What the page shows ----------------------------------------------------


@pytest.mark.parametrize(
    "shown", ["business_name", "logo", "category", "about", "city", "outlets"]
)
def test_the_page_carries_what_was_asked_for(shown):
    src = source(server._brand_page_html)

    assert shown in src


def test_it_lists_the_brand_s_open_briefs():
    src = source(server.public_brand_page)

    assert "LIVE_CAMPAIGN_STATUSES" in src
    assert '{"brand_id": oid' in src


def test_a_brand_with_nothing_open_says_so():
    """An empty area on a page somebody was linked to reads as broken."""
    html = server._brand_page_html(server._public_brand(profile()), [])

    assert "Nothing open right now" in html


def test_every_brief_links_to_its_own_page():
    src = source(server._brand_page_html)

    assert "_share_url(cid)" in src


def test_barter_is_never_shown_as_a_rupee_figure():
    src = source(server._brand_page_html)

    assert "_is_barter(c)" in src


def test_everything_typed_is_escaped():
    """A business name and an about paragraph are brand-supplied text on a
    public page."""
    html = server._brand_page_html(
        server._public_brand(
            profile(business_name="<script>alert(1)</script>", about="<img onerror=x>")
        ),
        [],
    )

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_the_logo_url_is_absolute():
    """A preview crawler is handed the tag and no page to resolve it against."""
    html = server._brand_page_html(
        server._public_brand(profile(logo_url="/uploads/brand-x.png")),
        [],
        media_base="https://api.example/",
    )

    assert "https://api.example/uploads/brand-x.png" in html


def test_a_brand_with_no_logo_gets_a_generated_mark():
    """The same idea as a brief with no cover: a hue from the id and the
    initial, so a page without a logo still looks like itself."""
    src = source(server._brand_page_html)

    assert "_cover_hue(" in src
    assert "monogram" in src


def test_it_has_a_way_in():
    src = source(server._brand_page_html)

    assert "/signup?role=creator" in src


# --- Findable ---------------------------------------------------------------


@pytest.mark.parametrize(
    "tag",
    ["og:title", "og:description", "og:url", "og:image", "og:type", "og:site_name",
     "twitter:card", "canonical", "application/ld+json"],
)
def test_the_page_is_readable_by_a_crawler(tag):
    assert tag in source(server._brand_page_html)


def test_the_structured_data_says_organisation():
    html = server._brand_page_html(server._public_brand(profile(city="Bengaluru")), [])

    assert '"@type": "Organization"' in html
    assert '"addressLocality": "Bengaluru"' in html


def test_the_structured_data_cannot_close_the_script_tag():
    """A business name containing `</script>` would otherwise end the block and
    everything after it becomes markup."""
    html = server._brand_page_html(
        server._public_brand(profile(business_name="a</script><script>alert(1)")), []
    )
    block = html[html.index("application/ld+json"):]

    assert "</script><script>alert(1)" not in block.split("</script>")[0]


def test_a_brand_page_is_not_marked_noindex():
    html = server._brand_page_html(server._public_brand(profile()), [])

    assert "noindex" not in html


def test_there_is_a_sitemap():
    """Nothing on the open internet links to a brand page except our own brief
    pages, and nothing links to those. Without this the public surface is
    reachable only by being sent the link."""
    src = source(server.public_sitemap)

    assert "_brand_page_url" in src
    assert "_share_url" in src
    assert "urlset" in src


def test_the_sitemap_lists_only_what_is_public():
    src = source(server.public_sitemap)

    assert '{"verified": True}' in src
    assert "LIVE_CAMPAIGN_STATUSES" in src


def test_robots_allows_the_public_pages_and_not_the_console():
    robots = (REPO / "frontend" / "public" / "robots.txt").read_text()

    assert "Disallow: /admin" in robots
    assert "Disallow: /brand/" in robots, "the brand's own console"
    # Prefixes match literally, so /brand/ does not cover /brands/{id}.
    assert "Disallow: /brands" not in robots.replace("Disallow: /brand/", "")
    assert "Sitemap:" in robots


def test_the_proxy_is_documented_for_every_server_rendered_path():
    """A rewrite that ships for /c/:id and not /brands/:id is a link into a
    page that does not exist."""
    vercel = (REPO / "frontend" / "vercel.json").read_text()

    for path in ("/c/:id", "/brands/:id", "/sitemap.xml"):
        assert f'"{path}"' in vercel


# --- The brand's half of the profile ----------------------------------------


@pytest.mark.parametrize("field", ["about", "city", "outlets"])
def test_the_brand_can_supply_it(field):
    assert field in server.BrandProfileUpdate.model_fields


def test_none_of_it_is_required_to_be_verified():
    """It is what a creator reads, not evidence of anything — demanding it
    before we will look at a business would be demanding ad copy."""
    required = {f for f, _ in server._BRAND_REQUIRED_FIELDS}

    assert not required & {"about", "city", "outlets"}


def test_the_city_goes_through_the_same_canonicaliser_as_everyone_else():
    """A brand's free-text city could never be compared with a creator's
    dropdown one."""
    src = source(server.update_brand_profile)

    assert "_canonical_city(payload.city)" in src


def test_an_outlet_city_is_canonicalised_too():
    assert "_canonical_city(row.city)" in source(server._clean_outlets)


def test_a_blank_outlet_row_is_dropped():
    """An empty row on the end is the normal shape of a repeater."""
    rows = [server.BrandOutlet(), server.BrandOutlet(name="Indiranagar")]

    assert len(server._clean_outlets(rows)) == 1


def test_half_a_coordinate_is_not_a_pin():
    """Both or neither, so nothing downstream has to ask whether a pin is
    really a pin."""
    [row] = server._clean_outlets([server.BrandOutlet(name="X", lat=12.97)])

    assert row["lat"] is None and row["lng"] is None


def test_a_pin_survives_intact():
    [row] = server._clean_outlets(
        [server.BrandOutlet(name="X", lat=12.97, lng=77.64, place_id="ChIJ")]
    )

    assert (row["lat"], row["lng"], row["place_id"]) == (12.97, 77.64, "ChIJ")


def test_the_maps_link_prefers_the_pin_over_the_text():
    """The pin is the thing the brand actually dropped; an autocomplete address
    routinely resolves to the street."""
    link = server._maps_link({"lat": 12.97, "lng": 77.64, "address": "12th Main"})

    # The comma is percent-encoded, which is what makes this a URL rather than
    # a string that happens to look like one.
    assert "12.97%2C77.64" in link
    assert "12th+Main" not in link and "12th Main" not in link


def test_an_outlet_with_no_pin_still_gets_somewhere_to_go():
    link = server._maps_link({"address": "12th Main", "city": "Bengaluru"})

    assert "google.com/maps" in link
    assert "12th" in link


def test_an_empty_outlet_gets_no_link_at_all():
    assert server._maps_link({}) == ""


def test_the_public_page_embeds_no_api_key():
    """It is an unauthenticated page anyone can load. A static map would mean
    publishing a key on it for decoration; a plain Maps URL needs none."""
    src = source(server._brand_page_html) + source(server._maps_link)

    assert "key=" not in src
    assert "AIza" not in src


# --- The links in ------------------------------------------------------------


def test_a_shared_brief_links_to_the_brand():
    """Also the only link between two public pages, so it is what gives a
    crawler a path from a shared brief into the rest."""
    src = source(server._share_page_html)

    assert "_brand_page_url" in src


def frontend(*parts):
    return FRONTEND.joinpath(*parts).read_text()


def test_the_url_helper_matches_the_share_one():
    src = frontend("lib", "brandPage.js")

    assert "/brands/${brandId}" in src
    assert "REACT_APP_SHARE_BASE_URL" in src


def test_there_is_one_component_naming_a_brand():
    """The twentieth place is the one that forgets."""
    assert (FRONTEND / "components" / "BrandName.jsx").is_file()


def test_it_renders_text_when_there_is_no_id():
    """A row whose brand we cannot identify should read as a name, not as a
    promise that 404s — the same rule components/admin/links.jsx follows."""
    src = frontend("components", "BrandName.jsx")

    assert "if (!href)" in src


@pytest.mark.parametrize(
    "page",
    [("pages", "Campaigns.jsx"), ("pages", "CampaignDetail.jsx"),
     ("pages", "Landing.jsx"),
     ("components", "application", "ApplicationDetail.jsx")],
)
def test_every_surface_that_names_a_brand_links_it(page):
    assert "BrandName" in frontend(*page)


def test_the_campaign_card_is_no_longer_an_anchor_around_an_anchor():
    """The brand's name inside the card is a link now. An <a> inside an <a> is
    invalid markup that browsers resolve however they like, so the card became
    an <article> with a stretched link on the title instead."""
    src = frontend("pages", "Campaigns.jsx")
    card = src[src.index("const CampaignCard"):src.index("export default function")]

    assert "<article" in card
    assert "after:absolute after:inset-0" in card, "the card is still clickable"
    assert "<Link\n            to={`/campaigns/" not in card


def test_the_share_button_stays_above_the_stretched_link():
    """Otherwise the overlay covers it and sharing opens the brief instead."""
    src = frontend("pages", "Campaigns.jsx")

    assert 'className="relative z-10"' in src


def test_the_application_page_links_to_both_the_campaign_and_the_brand():
    src = frontend("components", "application", "ApplicationDetail.jsx")

    assert "APPLICATION.campaignLink" in src
    assert "APPLICATION.brandLink" in src


def test_the_application_page_still_asks_nobody_what_role_they_are():
    """The destination differs by console; which one is decided by the route
    that mounted the component, never by a role check inside it."""
    src = frontend("components", "application", "ApplicationDetail.jsx")

    for smell in ('role === "admin"', "user?.role", 'user.role'):
        assert smell not in src


def test_the_brand_can_see_its_own_public_page():
    src = frontend("pages", "BrandOnboarding.jsx")

    assert "brandPageUrl" in src
    assert "View your public page" in src


@pytest.mark.parametrize("field", ["BRAND_PAGE.about", "BRAND_PAGE.city", "BRAND_PAGE.outletAdd"])
def test_onboarding_captures_it(field):
    assert field in frontend("pages", "BrandOnboarding.jsx")


def test_the_outlet_address_reuses_the_creator_s_picker():
    """Places autocomplete, a draggable pin, and a plain textarea when there is
    no key — all three already solved once."""
    src = frontend("pages", "BrandOnboarding.jsx")

    assert "<AddressPicker" in src


def test_the_picker_is_no_longer_filed_under_creator():
    """Two features use it now."""
    assert (FRONTEND / "components" / "AddressPicker.jsx").is_file()
    assert not (FRONTEND / "components" / "creator" / "AddressPicker.jsx").exists()


def test_the_form_offers_every_category_the_server_accepts():
    """It offered four of eight, so a fashion or travel brand had to file
    itself as "Lifestyle" — and that is the word its public page prints."""
    src = frontend("pages", "BrandOnboarding.jsx")
    block = src[src.index("const CATEGORY_OPTIONS"):src.index("const BUSINESS_TYPE_OPTIONS")]

    for value in server.CATEGORY_LITERAL.__args__:
        assert f'"{value}"' in block, f"the brand form cannot pick {value}"


def test_every_category_has_words_for_the_public_page():
    for value in server.CATEGORY_LITERAL.__args__:
        assert server.CATEGORY_LABELS.get(value), f"{value} would print as nothing"


def test_the_public_page_is_not_a_second_copy_of_the_app_s():
    """One page, the same one a stranger opens. A React route at /brands/:id
    would immediately start disagreeing with the server-rendered one — the
    same reasoning that put the admin and the brand on one ApplicationDetail."""
    app = frontend("App.js")

    assert 'path="/brands/' not in app


def test_the_address_note_says_who_sees_it():
    """The picker was written for a creator's delivery address, whose note says
    only our team reads it. On a brand's outlet that is the opposite of true —
    the whole point of an outlet is that it is on a public page."""
    picker = frontend("components", "AddressPicker.jsx")
    onboarding = frontend("pages", "BrandOnboarding.jsx")

    assert "note = PRIVATE_ADDRESS_NOTE" in picker, "the note is a prop with a default"
    assert "Only the WeAre team sees it" not in onboarding
    assert "Shown on your public page" in onboarding
