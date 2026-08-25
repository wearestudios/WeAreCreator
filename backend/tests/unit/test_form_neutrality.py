"""The forms address every category, and name one city only where it is true.

Two habits this codebase picked up from its first customers, both found by
somebody signing up as a creator and reading the screens:

- **Food-and-drink language in fields everybody fills in.** The niches box
  suggested "cafe, brunch", the tagline example was a coffee roastery, the
  scheduling note talked about "the kitchen, the floor or the light". Accurate
  for a café, faintly baffling to a gym, a showroom or a games studio — on a
  platform whose taxonomy is fifteen groups precisely because it takes every
  category.
- **A hardcoded city on screens that know the real one.** The hero eyebrow said
  Bengaluru on every marketing page while signup is open to anyone, and the
  creator's own dashboard said "Creator · Bengaluru" to creators who had told
  us in the profile form that they are somewhere else.

These are greps, deliberately: the failure is a *new* placeholder written in
the old voice, and only a sweep catches that. What they cannot check is whether
the replacement reads well, so the wording is reviewed by a person and pinned
here only where a specific claim matters.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"


def no_comments(path: Path) -> str:
    """Source with comments stripped, so a note *about* the old copy does not
    read as the old copy. Every file below explains what it used to say."""
    src = re.sub(r"\{/\*.*?\*/\}", "", path.read_text(), flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


# Forms and controls a person of any category fills in. Not the whole app: a
# campaign *titled* "Weekend brunch reel" in seed data is a real campaign, and
# an F&B brand's own copy is theirs to write.
SHARED_FORMS = [
    "pages/PostCampaign.jsx",
    "pages/CreatorOnboarding.jsx",
    "pages/BrandOnboarding.jsx",
    "components/campaign/ShootPreferences.jsx",
    "components/campaign/ShootWindowNote.jsx",
    "components/application/ApplicationDetail.jsx",
    "components/brand/CampaignTemplates.jsx",
]

# Words that assume the reader runs a restaurant. "venue" survives on purpose:
# it is the generic word for the place a shoot happens and reads correctly for
# a showroom, a gym and a studio.
FOOD_ONLY = (
    "kitchen",
    "brunch",
    "tasting",
    "menu launch",
    "café",
    "cafes",
    "diner",
    "chef",
)


@pytest.mark.parametrize("rel", SHARED_FORMS)
def test_no_shared_form_assumes_food_and_drink(rel):
    path = FRONTEND / rel
    if not path.exists():
        pytest.skip(f"{rel} no longer exists")
    body = no_comments(path).lower()
    found = [w for w in FOOD_ONLY if w in body]
    assert not found, (
        f"{rel} still speaks to a restaurant: {', '.join(found)}. "
        "Every category signs up here."
    )


def _placeholders(path: Path) -> list:
    """Every `placeholder="…"` in a file.

    **Placeholders rather than the whole file**, because a city *list* is not
    the same thing as a city *assumption*: `INDIAN_CITIES` legitimately
    contains "Bengaluru", and a fallback array of area options is data. What
    tells a creator in Pune the form is not for them is the greyed-out example
    inside the box they are about to type in.
    """
    return re.findall(r'placeholder=(?:\{)?"([^"]+)"', path.read_text())


@pytest.mark.parametrize("rel", SHARED_FORMS)
def test_no_placeholder_hardcodes_a_city(rel):
    path = FRONTEND / rel
    if not path.exists():
        pytest.skip(f"{rel} no longer exists")
    named = [p for p in _placeholders(path) if "Bengaluru" in p]
    assert not named, (
        f"{rel} names a city in an example: {named}. The city field is a "
        "canonical dropdown for exactly this reason."
    )


@pytest.mark.parametrize("rel", SHARED_FORMS)
def test_no_placeholder_assumes_food_and_drink(rel):
    """The same sweep at placeholder grain, which is where the examples live
    and where the old voice is most likely to come back."""
    path = FRONTEND / rel
    if not path.exists():
        pytest.skip(f"{rel} no longer exists")
    bad = [
        p
        for p in _placeholders(path)
        if any(w in p.lower() for w in FOOD_ONLY + ("cafe",))
    ]
    assert not bad, f"{rel} gives a food-only example: {bad}"


# ---------------------------------------------------------------------------
# The eyebrow
# ---------------------------------------------------------------------------


class TestTheHeroEyebrow:
    def test_it_is_one_constant_and_not_a_string_per_page(self):
        """It read "Vol. 01 · Bengaluru · Influencer studio", inlined
        separately on the home page and the brief feed — two strings that had
        to be edited together and were not."""
        nav = (FRONTEND / "lib" / "siteNav.js").read_text()
        assert "export const HERO_EYEBROW" in nav
        for rel in ("pages/Landing.jsx", "pages/Campaigns.jsx"):
            body = no_comments(FRONTEND / rel)
            assert "HERO_EYEBROW" in body, rel

    def test_it_carries_no_volume_number(self):
        """Magazine furniture. It implies a second volume that does not exist
        and tells a first-time visitor nothing."""
        nav = (FRONTEND / "lib" / "siteNav.js").read_text()
        value = re.search(r'HERO_EYEBROW = "([^"]*)"', nav).group(1)
        assert not re.search(r"vol\.?\s*\d", value, re.I), value

    def test_it_makes_no_geographic_claim_in_either_direction(self):
        """Not a city, because signup is open and an eyebrow on every page
        naming one tells everybody else they are in the wrong place. And not
        "nationwide" either — that is in `_FORBIDDEN_MARKETING_PHRASES`,
        because the network really is deepest in Bengaluru and a claim the
        operation cannot back is worse than the city it replaces."""
        nav = (FRONTEND / "lib" / "siteNav.js").read_text()
        value = re.search(r'HERO_EYEBROW = "([^"]*)"', nav).group(1).lower()
        assert "bengaluru" not in value
        for banned in server._FORBIDDEN_MARKETING_PHRASES:
            assert banned not in value, banned

    def test_the_pages_do_not_still_hold_the_old_line(self):
        for rel in ("pages/Landing.jsx", "pages/Campaigns.jsx"):
            body = no_comments(FRONTEND / rel)
            assert "Influencer studio" not in body, rel


class TestASurfaceThatKnowsTheCityUsesIt:
    """The creator's own header said "Creator · Bengaluru" to every creator on
    the platform, including the ones who had just told us otherwise in the
    profile form — a hardcoded city on the one screen that knows the answer."""

    @pytest.mark.parametrize(
        "rel,reader",
        [
            ("components/creator/Hero.jsx", "profile?.city"),
            ("pages/BrandDashboardView.jsx", "data?.profile?.city"),
        ],
    )
    def test_it_reads_the_record_rather_than_naming_one(self, rel, reader):
        body = no_comments(FRONTEND / rel)
        assert reader in body, f"{rel} does not read the record's own city"
        assert "· Bengaluru" not in body, f"{rel} still hardcodes a city"


# ---------------------------------------------------------------------------
# The form agrees with the server about which fields exist
# ---------------------------------------------------------------------------


class TestThePostFormAsksOnlyWhatTheTypeHas:
    """A backend rule with a form that ignores it is a 422 the brand meets
    after filling the page in. These check the form gates the same three
    shapes `_SCHEDULING_BY_TYPE` declares."""

    def test_days_and_hours_render_only_for_a_personal_table(self):
        body = no_comments(FRONTEND / "pages" / "PostCampaign.jsx")
        assert 'campaignType === "personal_table" && (' in body
        # And the control itself is inside that branch rather than beside it.
        before = body.split("<ShootPreferences")[0]
        assert 'campaignType === "personal_table" && (' in before.rsplit(
            "\n", 12
        )[-1] or 'campaignType === "personal_table"' in before[-400:]

    def test_a_launch_asks_for_a_start_time(self):
        body = no_comments(FRONTEND / "pages" / "PostCampaign.jsx")
        assert "pc-event-time-input" in body
        assert "pc-duration-input" in body

    def test_a_group_event_asks_for_its_sittings(self):
        body = no_comments(FRONTEND / "pages" / "PostCampaign.jsx")
        assert "pc-sittings" in body
        assert "pc-sitting-add" in body

    def test_the_payload_sends_only_the_fields_the_type_allows(self):
        """Sending a field the server refuses is a 422 with a filled-in form
        behind it."""
        body = no_comments(FRONTEND / "pages" / "PostCampaign.jsx")
        assert 'campaignType === "personal_table"\n' in body or (
            "restricted_days: restrictedDays," in body
            and body.index("restricted_days: restrictedDays,")
            > body.index('...(campaignType === "personal_table"')
        )

    def test_the_edit_round_trip_re_seeds_the_new_fields(self):
        """The trap the venue fields already fell into: `buildPayload` sends
        these, so a form that loads without them saves a launch back with no
        start time."""
        body = no_comments(FRONTEND / "pages" / "PostCampaign.jsx")
        assert "setEventTime(" in body
        assert "setDurationMinutes(" in body
        assert "data.sittings" in body

    def test_the_time_of_day_is_read_in_ist(self):
        """A launch at 19:00 in Bengaluru is 13:30 UTC. Reading it back any
        other way moves the brief by five and a half hours every time somebody
        opens the edit form — the same trap `dayKey` exists to close."""
        time_js = (FRONTEND / "lib" / "time.js").read_text()
        assert "export function timeKey" in time_js
        block = time_js.split("export function timeKey", 1)[1][:600]
        assert "timeZone: IST" in block
        body = no_comments(FRONTEND / "pages" / "PostCampaign.jsx")
        assert "timeKey(" in body
