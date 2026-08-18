"""The creator profile: what we ask for, and what we let people say.

Three things this holds.

**The suggestions span every category we accept.** They were food and nothing
but food — cafe, brunch, bakery, brewery, home chef — which is a list that
tells a fashion or gaming creator the platform is not for them before they
have typed anything. Food is now one group of fifteen rather than the whole
taxonomy.

**City is a closed list.** Free text cannot be reconciled: "Bangalore",
"bangalore", "Bengaluru " and "BLR" are four rows in a filter and one city in
reality, and a brand filtering the directory found a fraction of the people in
it each time.

**The pin is not brand-visible.** A coordinate on somebody's front door is
their home address to five decimal places — the same disclosure the postal
address already is, and a sharper one.
"""
import inspect
import re
from pathlib import Path

import pytest
from fastapi import HTTPException

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"


# --- The taxonomy -----------------------------------------------------------


def test_it_spans_the_categories_we_actually_accept():
    groups = {name for name, _ in server.CREATOR_TAXONOMY}
    for expected in (
        "Food & Drink", "Fashion", "Beauty", "Travel", "Fitness & Wellness",
        "Tech", "Gaming", "Home & Interiors", "Parenting", "Finance",
        "Art & Design", "Music", "Comedy", "Automotive", "Pets",
    ):
        assert expected in groups, f"{expected} is missing from the suggestions"


def test_food_is_one_group_not_the_whole_list():
    """The bug in one assertion: the food terms are still there, but they are
    a fraction of the list rather than all of it."""
    food = dict(server.CREATOR_TAXONOMY)["Food & Drink"]

    assert "cafe" in food and "brunch" in food, "the food terms are still offered"
    assert len(food) < len(server.CREATOR_TAXONOMY_TERMS) / 4, (
        "food is still most of the taxonomy"
    )


def test_no_term_is_offered_twice():
    """A term in two groups is a chip that vanishes from one when picked in
    the other, which reads as a bug."""
    terms = list(server.CREATOR_TAXONOMY_TERMS)

    assert len(terms) == len(set(terms)), "a term appears in more than one group"


def test_every_term_is_lowercase_free_text():
    """`niches` and `genres` are stored lowercased; a suggestion that does not
    round-trip through that would be added twice."""
    for term in server.CREATOR_TAXONOMY_TERMS:
        assert term == term.lower().strip()


def test_no_group_is_empty():
    for name, terms in server.CREATOR_TAXONOMY:
        assert terms, f"{name} has no terms"


# --- Cities -----------------------------------------------------------------


def test_bengaluru_leads_because_the_product_does():
    assert server.INDIAN_CITIES[0] == "Bengaluru"


@pytest.mark.parametrize("raw", ["Bengaluru", "bengaluru", "  BENGALURU  ", "Bangalore", "blr"])
def test_the_spellings_of_one_city_all_land_on_one_value(raw):
    """This is the whole point: four spellings, one row in a filter."""
    assert server._canonical_city(raw) == "Bengaluru"


@pytest.mark.parametrize(
    "raw,expected",
    [("bombay", "Mumbai"), ("new delhi", "Delhi NCR"), ("gurgaon", "Delhi NCR"),
     ("madras", "Chennai"), ("calcutta", "Kolkata")],
)
def test_the_old_names_are_understood(raw, expected):
    assert server._canonical_city(raw) == expected


def test_an_unknown_city_is_refused_with_the_list():
    with pytest.raises(HTTPException) as err:
        server._canonical_city("Atlantis")

    assert err.value.status_code == 422
    assert "Bengaluru" in str(err.value.detail), "the refusal has to say what is allowed"


def test_clearing_the_city_is_allowed():
    """The profile is built over sittings — an empty city is unfinished, not
    invalid, and refusing it would block every partial save."""
    assert server._canonical_city(None) is None
    assert server._canonical_city("") is None
    assert server._canonical_city("   ") is None


def test_the_update_handler_canonicalises_rather_than_trusting_the_form():
    """A dropdown is what stops most of this, but the form is not the only way
    in."""
    source = inspect.getsource(server.update_creator_profile)

    assert "_canonical_city(payload.city)" in source


# --- The new fields ---------------------------------------------------------


@pytest.mark.parametrize(
    "field", ["facebook_url", "about", "location_lat", "location_lng", "location_place_id"]
)
def test_the_new_fields_exist_and_are_optional(field):
    """Optional matters: a required field here would drop every existing
    creator below 100% and quietly un-submit them."""
    assert field in server.CreatorProfileUpdate.model_fields
    assert server.CreatorProfileUpdate.model_fields[field].default is None


@pytest.mark.parametrize(
    "field", ["facebook_url", "about", "location_lat", "location_lng", "location_place_id"]
)
def test_none_of_them_are_required_for_completeness(field):
    required = {f for f, _ in server._PROFILE_COMPLETENESS_FIELDS}

    assert field not in required


def test_a_coordinate_outside_the_planet_is_refused():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        server.CreatorProfileUpdate(location_lat=91)
    with pytest.raises(ValidationError):
        server.CreatorProfileUpdate(location_lng=181)


def test_the_update_handler_writes_all_three_pin_fields():
    source = inspect.getsource(server.update_creator_profile)

    for field in ("location_lat", "location_lng", "location_place_id"):
        assert field in source


# --- Already true, and must stay so -----------------------------------------


def test_youtube_is_only_asked_for_when_they_post_there():
    """An Instagram-only creator reaches 100% with no YouTube link. This was
    already the case; pinning it so it stays."""
    instagram_only = {
        "genres": ["food"], "platforms": ["instagram"], "city": "Bengaluru",
        "full_address": "x", "email": "a@b.in", "niches": ["cafe"],
        "base_rate": 1, "profile_image_url": "u",
        "instagram_handle": "h", "instagram_profile_url": "u",
    }

    assert server._profile_completeness(instagram_only)["percent"] == 100


def test_the_neighbourhood_is_optional():
    """`address` is the neighbourhood. Also already true, also worth pinning —
    it is the field the brief asked to make optional."""
    required = {f for f, _ in server._PROFILE_COMPLETENESS_FIELDS}

    assert "address" not in required


def test_facebook_is_not_a_platform():
    """Adding it to CREATOR_PLATFORMS would make it a completeness question for
    anyone who ticked it, which is the opposite of optional."""
    assert "facebook" not in server.CREATOR_PLATFORMS


# --- Privacy ----------------------------------------------------------------


@pytest.mark.parametrize("field", ["location_lat", "location_lng", "location_place_id"])
def test_the_pin_is_forbidden_to_brands(field):
    assert field in server.BRAND_FORBIDDEN_CREATOR_FIELDS


@pytest.mark.parametrize("field", ["location_lat", "location_lng", "location_place_id"])
def test_the_pin_is_not_on_the_brand_allow_list(field):
    """The allow-list is the mechanism; the forbidden list is what the leak
    test walks. Both, because either alone has been wrong before."""
    assert field not in server._BRAND_VISIBLE_CREATOR_FIELDS


def test_a_brand_may_read_the_about_text():
    """They wrote it for a brand to read — it is the one long-form field that
    belongs on that surface."""
    assert "about" in server._BRAND_VISIBLE_CREATOR_FIELDS


def test_the_pin_does_not_survive_the_brand_projection():
    """Run it, don't read it: a planted coordinate must not come back."""
    projected = server._brand_visible_creator(
        {
            "name": "Asha", "about": "I shoot food",
            "location_lat": 12.97, "location_lng": 77.59,
            "location_place_id": "ChIJsecret", "full_address": "12 MG Road",
        },
        {"_id": "u1", "name": "Asha"},
    )

    blob = repr(projected)
    assert "12.97" not in blob and "77.59" not in blob
    assert "ChIJsecret" not in blob
    assert "MG Road" not in blob
    assert projected.get("about") == "I shoot food"


def test_an_admin_does_see_the_pin():
    """It is collected so somebody can find the door. Staff-side only."""
    source = inspect.getsource(server._serialize_admin_creator)

    for field in ("location_lat", "location_lng", "location_place_id", "about"):
        assert field in source


# --- The frontend agrees ----------------------------------------------------


def _taxonomy_js():
    return (FRONTEND / "lib" / "taxonomy.js").read_text()


def test_the_frontend_taxonomy_matches_the_backend():
    source = _taxonomy_js()
    terms = set(re.findall(r'"([a-z][a-z &]*)"', source))

    for term in server.CREATOR_TAXONOMY_TERMS:
        assert term in terms, f"{term!r} is in the backend taxonomy but not the frontend"


def test_the_frontend_city_list_matches_the_backend():
    source = _taxonomy_js()
    cities = re.search(r"INDIAN_CITIES = \[(.*?)\];", source, re.S).group(1)

    for city in server.INDIAN_CITIES:
        assert f'"{city}"' in cities, f"{city} missing from the frontend list"


def test_no_screen_keeps_its_own_food_only_list():
    """The list appeared in three files. Any one left behind is a screen that
    still tells a fashion creator this is a food platform."""
    for page in (
        FRONTEND / "pages" / "CreatorOnboarding.jsx",
        FRONTEND / "components" / "admin" / "AdminCreators.jsx",
    ):
        source = page.read_text()
        code = re.sub(r"//.*", "", source)
        # The import, not just the identifier: a bare reference with no import
        # compiles fine and throws at runtime, which is how this was missed
        # once already.
        assert re.search(r'import \{[^}]*CREATOR_TAXONOMY[^}]*\} from "@/lib/taxonomy"', source), (
            f"{page.name} references the taxonomy without importing it"
        )
        assert '"brewery"' not in code, f"{page.name} still has a hand-kept food list"
        assert '"home chef"' not in code, f"{page.name} still has a hand-kept food list"


def test_the_city_field_is_a_dropdown_not_free_text():
    source = (FRONTEND / "pages" / "CreatorOnboarding.jsx").read_text()

    assert "INDIAN_CITIES.map" in source
    assert "city-suggestions" not in source, "the free-text datalist is gone"


def test_the_form_offers_facebook_and_about():
    source = (FRONTEND / "pages" / "CreatorOnboarding.jsx").read_text()

    assert "facebook_url" in source
    assert "about" in source


def test_the_address_field_degrades_without_a_key():
    """The point of the whole fallback: nothing breaks before the key is
    configured, and nothing breaks if it is taken away."""
    source = (FRONTEND / "components" / "creator" / "AddressPicker.jsx").read_text()

    assert "mapsConfigured()" in source
    assert '"off"' in source, "there is a no-key state"
    # The textarea is rendered unconditionally, not inside a maps branch.
    body = source[source.index("return ("):]
    assert body.index("<Textarea") < body.index("showMap &&")


def test_the_key_is_never_hardcoded():
    """It comes from the environment or it does not exist."""
    source = (FRONTEND / "lib" / "googleMaps.js").read_text()

    assert "process.env.REACT_APP_GOOGLE_MAPS_API_KEY" in source
    # An AIza-prefixed literal is what a leaked Google key looks like.
    assert not re.search(r'"AIza[0-9A-Za-z_\-]{10,}"', source)


def test_no_google_key_is_hardcoded_anywhere_in_the_frontend():
    for path in FRONTEND.rglob("*.js*"):
        assert not re.search(r"AIza[0-9A-Za-z_\-]{30,}", path.read_text()), (
            f"a Google API key literal is in {path}"
        )


def test_dragging_the_pin_does_not_rewrite_the_typed_address():
    """They wrote "2nd floor, above the pharmacy". Reverse-geocoding the drag
    would replace that with a street name, which is worse for a courier."""
    source = (FRONTEND / "components" / "creator" / "AddressPicker.jsx").read_text()
    dragend = source[source.index('addListener("dragend"') :][:400]

    assert "address" not in dragend.split("setPin(")[1][:120]


def test_the_review_queue_is_no_longer_called_vetting():
    source = (FRONTEND / "components" / "admin" / "Reviews.jsx").read_text()

    assert "waiting to be vetted" not in source
    assert "Pending creator approvals" in source
