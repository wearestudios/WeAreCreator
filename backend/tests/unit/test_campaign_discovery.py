"""Finding a brief, and sending one to somebody.

Two halves.

**The list shows everything live, and narrows on request.** No filter is
applied by default. `city` is new — campaigns carried only `area`, the free-text
neighbourhood, so "briefs in my city" was a question the data could not answer
even though a creator's own city is a canonical dropdown.

**A brief has a link that previews.** The app is a static SPA and the crawlers
that build a WhatsApp or Instagram preview do not run JavaScript, so Open Graph
tags injected by React are tags no crawler ever sees. The shareable page is
therefore server-rendered HTML from the backend — the same page a person lands
on, not a crawler-only shim, so what the preview promised is what opens.
"""
import inspect
import re
from pathlib import Path

import pytest

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"


# --- The list ---------------------------------------------------------------


def test_it_lists_open_and_upcoming():
    """Both, not just open — an upcoming brief is one you can still plan for."""
    assert set(server.LIVE_CAMPAIGN_STATUSES) == {"open", "upcoming"}


@pytest.mark.parametrize(
    "name", ["city", "area", "category", "campaign_type", "compensation_type"]
)
def test_every_asked_for_filter_exists(name):
    assert name in inspect.signature(server.list_campaigns).parameters


@pytest.mark.parametrize(
    "name", ["city", "area", "category", "campaign_type", "compensation_type"]
)
def test_no_filter_is_applied_by_default(name):
    """The page opens on everything. A default filter is a slice somebody else
    chose, and the creator cannot tell it is there."""
    assert inspect.signature(server.list_campaigns).parameters[name].default is None


def test_the_list_is_paginated_rather_than_silently_capped():
    """It used to be `.to_list(length=200)` with no count, so a creator on the
    201st brief simply never saw it and nothing said so."""
    params = inspect.signature(server.list_campaigns).parameters
    source = inspect.getsource(server.list_campaigns)

    assert "limit" in params and "offset" in params
    assert "X-Total-Count" in source


def test_an_unknown_campaign_type_is_refused():
    source = inspect.getsource(server.list_campaigns)

    assert "CampaignType.__args__" in source
    assert "422" in source


def test_an_unknown_compensation_type_is_refused():
    source = inspect.getsource(server.list_campaigns)

    assert "CompensationType.__args__" in source


def test_filtering_by_the_default_city_matches_pre_field_campaigns():
    """Campaigns predate `city`. The backfill fills them in, but a filter that
    only works after a migration has run returns nothing on a box that has not
    restarted — the same trap `execution_owner` had."""
    source = inspect.getsource(server.list_campaigns)
    block = source[source.index("if city:"):source.index("if area:")]

    assert '{"city": {"$exists": False}}' in block
    assert "DEFAULT_CAMPAIGN_CITY" in block


def test_filtering_by_fixed_matches_pre_field_campaigns():
    """Same reasoning: a campaign with no compensation_type is fixed."""
    source = inspect.getsource(server.list_campaigns)

    assert '{"compensation_type": {"$exists": False}}' in source


def test_the_keyword_search_does_not_clobber_the_compensation_filter():
    """Both used to want `$or`. A second assignment silently drops the first,
    which would have made "barter" plus a keyword return the keyword matches
    at any compensation."""
    source = inspect.getsource(server.list_campaigns)
    q_block = source[source.index("if q:"):]

    assert 'query["$or"] =' not in q_block
    assert 'query.setdefault("$and", [])' in q_block


# --- The filter options -----------------------------------------------------


@pytest.mark.parametrize(
    "key", ["cities", "areas", "categories", "campaign_types", "compensation_types"]
)
def test_the_options_endpoint_offers_every_filter(key):
    source = inspect.getsource(server.campaign_filters)

    assert f'"{key}"' in source


def test_the_options_are_what_actually_has_briefs():
    """Offering a category with no live brief in it is a filter whose only
    outcome is an empty list."""
    source = inspect.getsource(server.campaign_filters)

    assert "distinct" in source


def test_cities_come_back_in_canonical_order():
    """Bengaluru leads because that is where the work is, not because it sorts
    first — it doesn't."""
    source = inspect.getsource(server.campaign_filters)

    assert "for c in INDIAN_CITIES if c in set(cities)" in source


# --- The campaign's own city ------------------------------------------------


def test_a_campaign_carries_a_city():
    assert "city" in server.PostCampaignPayload.model_fields


def test_it_defaults_to_where_the_operation_is():
    assert server.DEFAULT_CAMPAIGN_CITY == "Bengaluru"
    assert server.PostCampaignPayload.model_fields["city"].default == "Bengaluru"


def test_it_goes_through_the_same_canonicaliser_as_a_creator_s():
    """A filter comparing a campaign's free text against a creator's dropdown
    value matches nothing."""
    for fn in (server.create_brand_campaign, server.update_brand_campaign):
        assert "_canonical_city" in inspect.getsource(fn)


def test_a_campaign_with_no_city_still_reads_as_one():
    """Never null: a filter chip has to print a word."""
    assert '"city": doc.get("city") or DEFAULT_CAMPAIGN_CITY' in Path(
        server.__file__
    ).read_text()


# --- The shareable page -----------------------------------------------------


def test_it_is_served_outside_the_api_prefix():
    """A clean URL somebody can read out loud, not /api/public/…"""
    assert server.SHARE_PATH == "/c"
    assert "/api" not in server.SHARE_PATH


def test_it_needs_no_account():
    """A link that demands a login previews as a login page."""
    params = inspect.signature(server.public_campaign_page).parameters

    assert "user" not in params
    assert "require_roles" not in inspect.getsource(server.public_campaign_page)


def test_it_is_server_rendered_html():
    """The whole reason it is here and not in the SPA: a preview crawler does
    not run JavaScript."""
    source = inspect.getsource(server.public_campaign_page)

    assert "_share_page_html" in source
    assert "text/html" in source


@pytest.mark.parametrize(
    "tag",
    ["og:title", "og:description", "og:url", "og:image", "og:type", "og:site_name",
     "twitter:card", "twitter:title", "twitter:image"],
)
def test_the_preview_tags_are_all_there(tag):
    source = inspect.getsource(server._share_page_html)

    assert tag in source


def test_the_page_carries_the_things_the_brief_asked_for():
    source = inspect.getsource(server._share_page_html)

    for shown in ("brief", "deliverables", "budget_per_creator", "area", "city",
                  "creators_needed", "business_name"):
        assert shown in source, f"the share page does not show {shown}"


def test_barter_is_never_shown_as_a_rupee_figure():
    """A barter brief keeps whatever budget it was posted with, so printing it
    unconditionally is a lie on the one surface strangers see."""
    source = inspect.getsource(server._share_page_html)

    assert "_is_barter(campaign)" in source


def test_it_has_a_way_in():
    source = inspect.getsource(server._share_page_html)

    assert "/signup?role=creator" in source
    assert "/login" in source


def test_everything_typed_is_escaped():
    """A campaign title is brand-supplied text on a public page."""
    source = inspect.getsource(server._share_page_html)

    assert "e = html_escape" in source
    assert "e(campaign.get(\"brief\")" in source or 'e(campaign.get("brief")' in source


def test_only_live_briefs_from_verified_brands_are_public():
    """Same rule as the shop window: an unverified brand can post and be seen
    by verified creators in-app, but is not promoted to the open internet
    under our name."""
    source = inspect.getsource(server.public_campaign_page)

    assert "LIVE_CAMPAIGN_STATUSES" in source
    assert 'brand_profile.get("verified")' in source


def test_a_bad_id_is_a_404_not_a_500():
    source = inspect.getsource(server.public_campaign_page)

    assert "except Exception:" in source
    assert "404" in source


def test_the_share_url_is_configurable_and_not_hardcoded():
    source = inspect.getsource(server._share_base)

    assert "PUBLIC_SHARE_BASE_URL" in source
    assert "CORS_ORIGINS" in source, "it falls back to the frontend's own origin"


# --- The share action -------------------------------------------------------


def _share_button():
    return (FRONTEND / "components" / "ShareButton.jsx").read_text()


def test_it_offers_the_native_sheet_on_mobile():
    source = _share_button()

    assert "navigator.share" in source


def test_it_falls_back_to_copying():
    source = _share_button()

    assert "navigator.clipboard.writeText" in source


def test_dismissing_the_share_sheet_is_not_an_error():
    """Cancelling rejects with AbortError. Toasting that would scold somebody
    for changing their mind."""
    source = _share_button()

    assert "AbortError" in source


def test_sharing_a_card_does_not_also_open_it():
    """The card is a link; the button is inside it."""
    source = _share_button()

    assert "stopPropagation" in source
    assert "preventDefault" in source


def test_the_link_points_at_the_server_rendered_page():
    source = _share_button()

    assert "/c/${campaignId}" in source


def test_the_share_action_is_on_both_the_card_and_the_detail_page():
    for page in ("Campaigns.jsx", "CampaignDetail.jsx"):
        source = (FRONTEND / "pages" / page).read_text()
        assert "ShareButton" in source, f"{page} has no share action"


# --- The list page ----------------------------------------------------------


def _campaigns_page():
    return (FRONTEND / "pages" / "Campaigns.jsx").read_text()


@pytest.mark.parametrize(
    "testid",
    ["filter-city-trigger", "filter-area-trigger", "filter-type-trigger",
     "filter-compensation-trigger"],
)
def test_the_page_has_every_filter(testid):
    assert testid in _campaigns_page()


def test_every_filter_starts_unset():
    source = _campaigns_page()

    for state in ("city", "campaignType", "compensation"):
        assert f"useState(ANY)" in source
        assert f"const [{state}, set" in source


def test_the_new_filters_refetch_when_they_change():
    """A filter left out of the dependency array does nothing — caught by the
    linter once already on the admin campaign list."""
    source = _campaigns_page()
    deps = re.search(r"\}, \[city, area, category, campaignType, compensation,", source)

    assert deps, "the new filters are not in the effect's dependencies"


def test_each_filter_is_removable_on_its_own():
    source = _campaigns_page()

    for key in ('key: "city"', 'key: "campaign_type"', 'key: "compensation"'):
        assert key in source, f"no chip for {key}"
