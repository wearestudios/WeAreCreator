"""What a brand is looking for, and one vocabulary for audience size.

Two problems, one fix.

**There were two vocabularies for the same axis.** The suggestion scorer had
four bands named nano / micro / mid / macro with its own boundaries, while
every screen a person reads described followers in raw numbers and the
directory filter offered "10k+ / 50k+ / 100k+ / 500k+". A brand seeing "micro"
in one place and picking "10k+" in another were talking about different people.
`FOLLOWER_TIERS` is the only vocabulary now, and the budget map returns one of
its keys rather than a fourth name.

**The ranking was guessing at something a brand could have told us.** It read
the expected audience off each brief's fee. `content_types`,
`preferred_follower_tier` and `typical_budget_band` are standing preferences on
the brand profile, and all three feed `score_creator_for_campaign` — a stated
preference beats an inferred one, and an unstated one scores at the midpoint
like every other unknown rather than pushing everybody down.
"""
import asyncio
import inspect
from pathlib import Path

import pytest

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"


def read(*parts):
    return FRONTEND.joinpath(*parts).read_text()


CAMPAIGN = {
    "_id": "c1",
    "title": "Weekend brunch launch",
    "brief": "Brunch reels from Bengaluru creators",
    "deliverables": "1 reel",
    "category": "fnb",
    "area": "Indiranagar",
    "budget_per_creator": 8000,
}


def profile(**over):
    base = {
        "niches": ["brunch"],
        "genres": ["food"],
        "city": "Indiranagar",
        "follower_count": 24000,
        "engagement_rate": 4.2,
        "platforms": ["instagram"],
    }
    base.update(over)
    return base


# --- One vocabulary -----------------------------------------------------------


def test_there_is_no_fourth_tier_name():
    """"nano" was the fourth band. It has no place on a form that offers three
    and no place in a reason line a brand reads beside a filter."""
    assert [t[0] for t in server.FOLLOWER_TIERS] == ["micro", "mid", "macro"]
    assert "nano" not in str(server.FOLLOWER_TIERS)
    assert all(key in server.FOLLOWER_TIER_KEYS for _, key in server.CREATOR_REACH_TIERS)


def test_the_tiers_do_not_overlap_or_leave_a_gap():
    bounds = [(low, high) for _, low, high, _, _ in server.FOLLOWER_TIERS]
    for (_, high), (low, _) in zip(bounds, bounds[1:]):
        assert high == low, "one tier's ceiling is the next one's floor"
    assert bounds[-1][1] is None, "the top tier is open-ended"


@pytest.mark.parametrize(
    "followers,tier",
    [(400, "micro"), (1_000, "micro"), (9_999, "micro"),
     (10_000, "mid"), (99_999, "mid"), (100_000, "macro"), (2_000_000, "macro")],
)
def test_every_audience_lands_in_exactly_one_tier(followers, tier):
    """Below the smallest floor is still the smallest tier: a 400-follower
    account is a very small micro, not an unclassifiable one."""
    assert server._tier_for_followers(followers) == tier


def test_an_unknown_audience_has_no_tier():
    for value in (None, 0, -5, "lots"):
        assert server._tier_for_followers(value) is None


def test_the_budget_map_did_not_quietly_retune_itself():
    """The boundaries moved when the vocabulary did, and they were picked so
    the same fee buys roughly the same audience it did before. Keeping the old
    numbers against the new bands would have made ₹8,000 buy a 1k–10k creator
    where it used to buy 10k–50k — a re-tuning smuggled in under a renaming."""
    assert server._reach_tier(2_000)[2] == "micro"
    assert server._reach_tier(8_000)[2] == "mid"
    assert server._reach_tier(50_000)[2] == "macro"


# --- A stated preference beats a guess ----------------------------------------


def test_the_brand_s_stated_tier_overrides_the_budget_guess():
    """The budget map is a guess about what a fee buys. A brand that answered
    the question has told us, and inferring over the top is ignoring it."""
    low, high, key, stated = server._wanted_reach_tier(
        CAMPAIGN, {"preferred_follower_tier": "macro"}
    )
    assert (key, stated) == ("macro", True)
    assert (low, high) == (100_000, None)


def test_no_stated_tier_falls_back_to_the_fee():
    _, _, key, stated = server._wanted_reach_tier(CAMPAIGN, {})
    assert (key, stated) == ("mid", False)


def test_any_is_a_real_answer_and_does_not_steer_the_ranking():
    """"We don't mind" is not the same as "we didn't reach the question", but
    neither should push the ranking toward a band."""
    _, _, key, stated = server._wanted_reach_tier(CAMPAIGN, {"preferred_follower_tier": "any"})
    assert (key, stated) == ("mid", False)


def test_the_typical_band_stands_in_when_a_brief_has_no_fee():
    """A barter brief, or a draft where the number isn't in yet. Without this
    the reach signal on a barter campaign is read off ₹0."""
    barter = {**CAMPAIGN, "budget_per_creator": None}
    _, _, key, _ = server._wanted_reach_tier(barter, {"typical_budget_band": "over_40k"})

    assert key == "macro"
    assert server._wanted_reach_tier(barter, {})[2] == "micro", "₹0 buys micro"


def test_a_macro_brand_ranks_a_macro_creator_above_a_micro_one():
    """The end-to-end version: the preference has to actually move the order,
    or it is a field nobody can tell is working."""
    brand = {"preferred_follower_tier": "macro"}
    big = server.score_creator_for_campaign(profile(follower_count=400_000), CAMPAIGN, brand=brand)
    small = server.score_creator_for_campaign(profile(follower_count=3_000), CAMPAIGN, brand=brand)

    assert big["score"] > small["score"]
    assert big["wanted_tier"] == "macro" and big["wanted_tier_stated"] is True


def test_without_the_preference_the_same_pair_ranks_the_other_way():
    """₹8,000 reads as mid, so 3k is a closer miss than 400k. The point is
    that the preference is what changed the answer, not the creators."""
    big = server.score_creator_for_campaign(profile(follower_count=400_000), CAMPAIGN)
    small = server.score_creator_for_campaign(profile(follower_count=24_000), CAMPAIGN)

    assert small["score"] > big["score"]


# --- Content types ------------------------------------------------------------


def test_a_creator_who_cannot_post_the_format_scores_lower():
    brand = {"content_types": ["reels", "shorts"]}
    both = server.score_creator_for_campaign(
        profile(platforms=["instagram", "youtube"]), CAMPAIGN, brand=brand
    )
    instagram_only = server.score_creator_for_campaign(
        profile(platforms=["instagram"]), CAMPAIGN, brand=brand
    )

    assert both["components"]["content_fit"] > instagram_only["components"]["content_fit"]
    assert both["components"]["content_fit"] == server.CREATOR_MATCH_WEIGHTS["content_fit"]


def test_the_reason_names_the_gap_and_only_the_gap():
    """"Posts reels" on a brief asking for reels is noise. "No YouTube" on one
    asking for Shorts is the reason to look elsewhere."""
    brand = {"content_types": ["reels", "shorts"]}
    missing = server.score_creator_for_campaign(
        profile(platforms=["instagram"]), CAMPAIGN, brand=brand
    )
    complete = server.score_creator_for_campaign(
        profile(platforms=["instagram", "youtube"]), CAMPAIGN, brand=brand
    )

    assert "no Youtube" in missing["reason"]
    assert "no " not in complete["reason"].lower().replace("no preference", "")


def test_an_unstated_content_preference_is_an_unknown_not_a_zero():
    """A brand that skipped the question must not push every creator down."""
    silent = server.score_creator_for_campaign(profile(), CAMPAIGN, brand={})
    assert silent["components"]["content_fit"] == (
        server.CREATOR_MATCH_WEIGHTS["content_fit"] * server._UNKNOWN_SIGNAL
    )
    assert "content_fit" in silent["unknown_signals"]


def test_a_creator_who_listed_no_platforms_is_also_an_unknown():
    """Not a zero. They have not told us, which is the ordinary state of a
    half-built profile — and burying them would bury everyone new."""
    out = server.score_creator_for_campaign(
        profile(platforms=[]), CAMPAIGN, brand={"content_types": ["reels"]}
    )
    assert "content_fit" in out["unknown_signals"]


def test_the_content_types_are_cleaned_and_ordered():
    assert server._clean_content_types(["shorts", "reels", "nonsense", "reels"]) == [
        "reels",
        "shorts",
    ]
    assert server._clean_content_types(None) == []


# --- The score still adds up --------------------------------------------------


def test_the_weights_still_sum_to_one_hundred():
    assert sum(server.CREATOR_MATCH_WEIGHTS.values()) == 100


def test_content_fit_came_out_of_niche_and_genre():
    """Not out of city or reliability. It measures the same thing they do —
    does this creator's work look like what is being asked for — at a finer
    and more factual grain, so it is right for it to come out of their
    budget."""
    w = server.CREATOR_MATCH_WEIGHTS
    assert w["niche"] + w["genre"] + w["content_fit"] == 45
    assert w["city"] == 20 and w["delivery"] == 10 and w["engagement"] == 10


def test_the_components_are_still_the_whole_score():
    out = server.score_creator_for_campaign(profile(), CAMPAIGN, brand={"content_types": ["reels"]})
    assert round(sum(out["components"].values()), 1) == out["score"]
    assert set(out["components"]) == set(server.CREATOR_MATCH_WEIGHTS)


def test_the_scorer_is_still_pure():
    """No database, no clock — that is what makes the ranking testable and
    arguable. The brand arrives as an argument like everything else."""
    src = inspect.getsource(server.score_creator_for_campaign)
    for forbidden in ("db.", "await ", "datetime.now"):
        assert forbidden not in src


# --- Saving and reading it back -----------------------------------------------


def test_the_preferences_ride_on_the_profile_response():
    src = inspect.getsource(server._serialize_brand_profile)
    for key in ("content_types", "preferred_follower_tier", "typical_budget_band"):
        assert f'"{key}"' in src


def test_the_option_lists_come_from_the_server():
    """A dropdown offering a value the API refuses is a dead control, and a
    tier label that disagrees with the ranking's is the split these tiers
    exist to end."""
    src = inspect.getsource(server._brand_profile_response)
    assert '"preferences"' in src
    assert "FOLLOWER_TIERS" in src and "CONTENT_TYPES" in src and "BUDGET_BANDS" in src


def test_a_junk_budget_band_is_dropped_rather_than_stored():
    src = inspect.getsource(server.update_brand_profile)
    assert "BUDGET_BAND_KEYS" in src


def test_none_of_it_is_required_for_verification():
    """It is what we rank on, not evidence of anything. Demanding it would
    hold up a real business over a marketing question."""
    required = {field for field, _ in server._BRAND_REQUIRED_FIELDS}
    assert required.isdisjoint(
        {"content_types", "preferred_follower_tier", "typical_budget_band"}
    )


def test_the_suggestions_endpoint_loads_the_brand():
    src = inspect.getsource(server._suggest_creators_for_campaign)
    assert "brand=brand" in src
    assert "_wanted_reach_tier(" in src
    assert '"stated"' in src, "the panel has to be able to say which it was"


# --- The frontend mirror ------------------------------------------------------


def test_the_frontend_tiers_match_the_server_s():
    src = read("lib", "followerTiers.js")
    for key, low, high, label, human in server.FOLLOWER_TIERS:
        assert f'value: "{key}", label: "{label}", range: "{human}"' in src
        assert f"min: {low}" in src
        assert (f"max: {high}" if high else "max: null") in src


def test_the_frontend_content_types_and_bands_match_too():
    src = read("lib", "followerTiers.js")
    for key, label, _ in server.CONTENT_TYPES:
        assert f'value: "{key}", label: "{label}"' in src
    for key, _, _, label in server.BUDGET_BANDS:
        assert f'value: "{key}", label: "{label}"' in src


def test_the_directory_filter_uses_the_tiers_not_its_own_buckets():
    """It used to offer 10k+/50k+/100k+/500k+ — a fourth vocabulary for the
    same axis, on the screen right next to the ranking that used a different
    one."""
    src = read("pages", "BrandCreatorDirectory.jsx")
    assert "FOLLOWER_TIERS.map" in src
    assert '"500k+ followers"' not in src


def test_the_directory_filter_sends_a_ceiling_as_well_as_a_floor():
    """A tier has both. Sending only the floor made "Micro" return every macro
    creator too, which is the opposite of what the filter is for."""
    src = read("pages", "BrandCreatorDirectory.jsx")
    assert "params.max_followers = bucket.max" in src


def test_the_suggestions_filter_picks_a_tier_rather_than_typing_numbers():
    """It was two raw number boxes — a fourth vocabulary for the same axis, on
    the very panel whose band above it reads micro / mid / macro. A brand that
    told us "micro" in onboarding had to work out which numbers meant that."""
    src = read("components", "brand", "SuggestedCreators.jsx")

    assert "FOLLOWER_TIERS.map" in src
    assert "Followers from" not in src and "Followers to" not in src
    # The API still filters on a range; the tier is how a person says it.
    assert "tierByValue(v)?.min" in src and "tierByValue(v)?.max" in src


def test_the_suggestions_panel_says_whether_the_brand_told_us():
    src = read("components", "brand", "SuggestedCreators.jsx")
    assert "tier.stated" in src
    # Comment lines stripped: the comment above the change explains that
    # "nano" is gone, and searching the whole file finds the explanation
    # rather than the thing.
    code = "\n".join(l for l in src.splitlines() if not l.strip().startswith("//"))
    assert "nano" not in code


def test_the_onboarding_step_re_seeds_rather_than_defaults():
    """A brand editing its address must not silently reset the preferences the
    ranking has been using."""
    src = read("pages", "BrandOnboarding.jsx")
    assert "setContentTypes(data.content_types || [])" in src
    assert 'setFollowerTier(data.preferred_follower_tier || "")' in src
    assert 'setBudgetBand(data.typical_budget_band || "")' in src


def test_the_onboarding_step_prefers_the_server_s_option_lists():
    src = read("pages", "BrandOnboarding.jsx")
    assert "prefOptions?.content_types" in src
    assert "prefOptions?.follower_tiers" in src
    assert "prefOptions?.budget_bands" in src
