"""The homepage leaderboard: consent, what it ranks on, and what it will not say.

Three claims this file exists to hold, in the order they matter:

1. **Nobody appears without opting in**, and turning it off removes them
   immediately rather than on the next nightly pass.
2. **Nothing about money or contact reaches the payload**, ever.
3. **The section is absent below the floor**, not short.

Driven rather than read wherever the claim is about behaviour: the eligibility
tests build the rows, call the real refresh and the real reader, and assert on
what comes back. The "never earnings" rule is the one place source-reading is
the right instrument, because the failure is a signal somebody adds later and
the test has to fail on the day they add it.
"""

from __future__ import annotations

import asyncio
import inspect
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException, params
from mongomock_motor import AsyncMongoMockClient

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"
SOURCE = Path(server.__file__).read_text()

LOOP = None


def run(body):
    """One loop per call, kept in a module global.

    `asyncio.get_event_loop` fails inside a pytest-xdist worker thread, and
    `asyncio.run` closes the loop mongomock's cursors were built on.
    """
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()

    async def go():
        db = AsyncMongoMockClient()["leaderboard"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return LOOP.run_until_complete(go())


def guard_allows(fn, role):
    """Would FastAPI let this role through? Calling a handler directly skips
    its `Depends` entirely, so the guard has to be pulled off the signature and
    run by hand."""
    guard = None
    for p in inspect.signature(fn).parameters.values():
        dep = p.default
        if isinstance(dep, params.Depends) and dep.dependency is not None:
            if getattr(dep.dependency, "__name__", "") == "_guard":
                guard = dep.dependency
    assert guard is not None, f"{fn.__name__} declares no require_roles guard"

    async def go():
        try:
            await guard({"_id": str(ObjectId()), "role": role})
            return True
        except HTTPException as err:
            assert err.status_code == 403
            return False

    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()
    return LOOP.run_until_complete(go())


def _now():
    return datetime.now(timezone.utc)


def code_of(*parts):
    """A JSX file with its comments removed.

    Both kinds: `//` lines and the `{/* ... */}` blocks JSX uses. Without the
    second, a test searching for a smell finds the comment that explains why
    the smell is absent — which is the shape of a test that passes for the
    wrong reason and then fails for one.
    """
    src = (FRONTEND.joinpath(*parts)).read_text()
    src = re.sub(r"\{/\*.*?\*/\}", "", src, flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(l for l in src.splitlines() if not l.strip().startswith("//"))


# Values planted in the input so a leak has something recognisable to be.
PLANTED = {
    "phone": "+919876500042",
    "email": "featured.leak@example.in",
    "address": "9 Wood Street, Ashok Nagar, Bengaluru 560025",
    "lat": 12.9611159,
    "lng": 77.6012278,
    "upi": "featuredleak@okicici",
    "account": "50100987654321",
    "ifsc": "ICIC0000456",
    "pan": "ZYXWV9876Z",
    "base_rate": 47500,
    "follower_count": 123456,
}


async def _creator(
    db,
    *,
    name="Asha",
    opted_in=True,
    status="verified",
    completed=4,
    on_time=4,
    days_since_active=5,
    suspended=False,
    verified_days_ago=30,
    rating=None,
    reach=None,
    engagements=None,
):
    """One creator with a real collaboration history behind their numbers.

    Written the way the app writes these rows — `no_show_reported` absent
    rather than `False` — so a test cannot pass against a fixture the product
    would never produce.
    """
    creator_oid, brand_oid, campaign_oid = ObjectId(), ObjectId(), ObjectId()
    await db.users.insert_one(
        {
            "_id": creator_oid,
            "role": "creator",
            "name": name,
            "phone": PLANTED["phone"],
            "email": PLANTED["email"],
            **({"status": "suspended", "suspension_reason": "under review"} if suspended else {}),
        }
    )
    await db.creator_profiles.insert_one(
        {
            "user_id": creator_oid,
            "name": name,
            "instagram_handle": f"{name.lower()}.shoots",
            "profile_image_url": None,
            "city": "Bengaluru",
            "niches": ["fnb", "lifestyle", "travel"],
            "verification_status": status,
            "verified_at": _now() - timedelta(days=verified_days_ago),
            "homepage_opt_in": opted_in,
            # Everything a public card must never carry, all at once.
            "phone": PLANTED["phone"],
            "whatsapp": PLANTED["phone"],
            "email": PLANTED["email"],
            "full_address": PLANTED["address"],
            "location_lat": PLANTED["lat"],
            "location_lng": PLANTED["lng"],
            "payout_upi": PLANTED["upi"],
            "payout_account_number": PLANTED["account"],
            "payout_ifsc": PLANTED["ifsc"],
            "pan": PLANTED["pan"],
            "base_rate": PLANTED["base_rate"],
            "follower_count": PLANTED["follower_count"],
        }
    )
    await db.campaigns.insert_one(
        {"_id": campaign_oid, "brand_id": brand_oid, "title": "Tasting", "status": "closed"}
    )
    moved = _now() - timedelta(days=days_since_active)
    for i in range(completed):
        collab_oid = ObjectId()
        await db.collaborations.insert_one(
            {
                "_id": collab_oid,
                "campaign_id": campaign_oid,
                "creator_id": creator_oid,
                "state": "closed",
                "updated_at": moved,
                "state_since": moved,
                # Late deliveries are how a row stops counting as on time.
                **({"content_overdue": True} if i >= on_time else {}),
            }
        )
        if reach:
            await db.content_performance.insert_one(
                {
                    "_id": ObjectId(),
                    "collaboration_id": collab_oid,
                    "campaign_id": campaign_oid,
                    "reach": reach,
                    "likes": engagements,
                    "captured_at": moved,
                }
            )
        if rating is not None:
            await db.collaboration_ratings.insert_one(
                {
                    "_id": ObjectId(),
                    "collaboration_id": collab_oid,
                    "creator_id": creator_oid,
                    "side": "runner",
                    "score": rating,
                }
            )
    return creator_oid


async def _row(db, **over):
    """A full pass: seed, refresh, read the public payload back."""
    await _creator(db, **over)
    await server.refresh_creator_leaderboard()
    return await server._public_leaderboard()


async def _floor(db, value=1):
    await db.platform_settings.update_one(
        {"_id": server._LEADERBOARD_SETTINGS_ID},
        {"$set": {"minimum": value}},
        upsert=True,
    )


# --- 1. Consent -------------------------------------------------------------


class TestNobodyIsFeaturedWithoutSayingSo:
    def test_the_field_defaults_to_off_on_a_profile_that_never_answered(self):
        """Absent is **not** consent. Every profile written before this field
        existed is one nobody has asked yet."""
        assert (
            server._serialize_creator_profile(
                {"_id": ObjectId(), "user_id": ObjectId()}
            )["homepage_opt_in"]
            is False
        )

    def test_a_creator_who_did_not_opt_in_never_appears(self):
        async def body(db):
            await _floor(db)
            return await _row(db, opted_in=False)

        assert run(body) == {}

    def test_the_refresh_does_not_even_score_them(self):
        """Ranking everybody and filtering at the end would mean holding a
        ranking of people who never consented — the thing this declines to
        build. So they are absent from the cache, not merely hidden."""
        async def body(db):
            await _creator(db, opted_in=False)
            await server.refresh_creator_leaderboard()
            return await db.leaderboard_cache.find_one({"_id": "current"})

        assert (run(body) or {}).get("ranked") == []

    def test_they_are_never_even_loaded(self):
        """The stronger half, and the one a behavioural test cannot see: with
        the filter dropped, `_leaderboard_eligible` still excludes them at the
        end of the loop and the cache still comes back empty — so the *output*
        is identical and the property that changed is which people were read
        at all. Asserting on the query is the only way to hold that."""
        src = inspect.getsource(server.refresh_creator_leaderboard)
        find = src[src.index("db.creator_profiles.find(") :]
        assert '"homepage_opt_in": True' in find[: find.index(")")]

    def test_turning_it_off_removes_them_immediately(self):
        """**The whole point of re-reading opt-in on the read path.** The
        cache still has them; the payload must not."""
        async def body(db):
            await _floor(db)
            creator_oid = await _creator(db)
            await server.refresh_creator_leaderboard()
            before = await server._public_leaderboard()

            await db.creator_profiles.update_one(
                {"user_id": creator_oid}, {"$set": {"homepage_opt_in": False}}
            )
            # Deliberately no second refresh — this is the "immediately" claim.
            after = await server._public_leaderboard()
            cached = await db.leaderboard_cache.find_one({"_id": "current"})
            return before, after, cached

        before, after, cached = run(body)
        assert len(before["creators"]) == 1
        assert after == {}
        assert len(cached["ranked"]) == 1, "the cache was not what changed"

    def test_erasing_an_account_takes_the_consent_with_it(self):
        """An erased row that kept `homepage_opt_in: True` would be a name we
        removed and a permission we kept."""
        assert "homepage_opt_in" in server._ERASE_CREATOR_PROFILE

    def test_the_toggle_is_offered_in_both_places_and_says_the_same_thing(self):
        """A consent control somebody can only find once is one they cannot
        withdraw."""
        sentence = "Show my profile on the WeAre Creators homepage."
        for page in ("CreatorOnboarding.jsx", "CreatorProfile.jsx"):
            src = (FRONTEND / "pages" / page).read_text()
            assert sentence in src, page
            assert "homepage_opt_in" in src, page
        # **Defined is not mounted.** A component sitting in a file nothing
        # renders is as unreachable as a route with no caller, and it is the
        # trap this codebase has already been caught by once.
        profile = code_of("pages", "CreatorProfile.jsx")
        assert "<FeaturingToggle" in profile
        onboarding = code_of("pages", "CreatorOnboarding.jsx")
        assert "<Switch" in onboarding and "IDS.homepageOptIn" in onboarding

    def test_the_builder_defaults_it_off(self):
        src = (FRONTEND / "pages" / "CreatorOnboarding.jsx").read_text()
        assert "homepage_opt_in: false," in src


# --- 2. Who else is excluded ------------------------------------------------


class TestTheOtherGates:
    @pytest.mark.parametrize(
        "over",
        [
            pytest.param({"status": "pending"}, id="not verified"),
            pytest.param({"status": "rejected"}, id="rejected"),
            pytest.param({"suspended": True}, id="suspended"),
            pytest.param({"days_since_active": 400}, id="gone quiet"),
            pytest.param({"completed": 1, "on_time": 1}, id="too little history"),
        ],
    )
    def test_they_do_not_appear(self, over):
        async def body(db):
            await _floor(db)
            return await _row(db, **over)

        assert run(body) == {}

    def test_a_verified_active_creator_does(self):
        """The control: without this, every case above could be passing for the
        wrong reason."""
        async def body(db):
            await _floor(db)
            return await _row(db)

        out = run(body)
        assert len(out["creators"]) == 1
        assert out["creators"][0]["name"] == "Asha"

    def test_losing_verification_after_the_refresh_removes_them_too(self):
        """The refresh query already filters on verified, so seeding somebody
        unverified proves nothing about the live re-check. This changes the
        status *after* the ranking is cached — the case that would otherwise
        leave a rejected creator on a public page until the nightly pass."""
        async def body(db):
            await _floor(db)
            creator_oid = await _creator(db)
            await server.refresh_creator_leaderboard()
            before = await server._public_leaderboard()
            await db.creator_profiles.update_one(
                {"user_id": creator_oid}, {"$set": {"verification_status": "rejected"}}
            )
            return before, await server._public_leaderboard()

        before, after = run(body)
        assert len(before["creators"]) == 1
        assert after == {}

    def test_suspending_an_account_after_the_refresh_removes_them_too(self):
        async def body(db):
            await _floor(db)
            creator_oid = await _creator(db)
            await server.refresh_creator_leaderboard()
            await db.users.update_one(
                {"_id": creator_oid},
                {"$set": {"status": "suspended", "suspension_reason": "under review"}},
            )
            return await server._public_leaderboard()

        assert run(body) == {}

    def test_a_lapsed_verification_is_not_featured(self):
        """Not a rejection — what ran out is our confidence that the check is
        current, and featuring somebody on that basis is making the claim
        anyway."""
        async def body(db):
            await _floor(db)
            await db.platform_settings.update_one(
                {"_id": "verification_validity"}, {"$set": {"days": 30}}, upsert=True
            )
            return await _row(db, verified_days_ago=400)

        assert run(body) == {}

    def test_the_activity_window_reads_absent_as_inactive(self):
        """The opposite of the usual absent-is-safe rule, deliberately: the
        claim being made is that these are people currently doing the work."""
        assert server._recently_active(None) is False
        assert server._recently_active({}) is False
        assert server._recently_active({"last_active_at": "not a date"}) is False


# --- 3. What the payload may carry ------------------------------------------


class TestTheCardCarriesNoMoneyAndNoWayToReachAnybody:
    def test_not_one_planted_value_survives_into_the_payload(self):
        """**Run it and search the output.** Source-reading catches the mistake
        somebody makes on purpose; running it catches the one where a value
        arrives through a `**spread` from a document nobody remembered had
        one."""
        async def body(db):
            await _floor(db)
            return await _row(db)

        rendered = repr(run(body))
        for label, value in PLANTED.items():
            assert str(value) not in rendered, f"{label} leaked onto a public card"

    def test_the_forbidden_keys_are_not_keys_either(self):
        async def body(db):
            await _floor(db)
            return await _row(db)

        card = run(body)["creators"][0]
        for key in server.PUBLIC_CREATOR_CARD_FORBIDDEN:
            assert key not in card, key

    def test_it_is_a_narrower_allow_list_than_the_brand_one(self):
        """Reusing `_brand_visible_creator` would have been the obvious move
        and would have shipped a follower count, an engagement rate and a base
        rate onto a public page."""
        for key in ("follower_count", "engagement_rate", "base_rate"):
            assert key in server._BRAND_VISIBLE_CREATOR_FIELDS
            assert key in server.PUBLIC_CREATOR_CARD_FORBIDDEN

    def test_no_position_or_score_travels(self):
        """A visible ordinal is a public statement that somebody is eighth, and
        the person it is worst for is whoever is last."""
        async def body(db):
            await _floor(db)
            return await _row(db)

        card = run(body)["creators"][0]
        for key in ("rank", "position", "score", "components"):
            assert key not in card

    def test_what_it_does_carry(self):
        async def body(db):
            await _floor(db)
            return await _row(db)

        card = run(body)["creators"][0]
        assert card["instagram_handle"] == "asha.shoots"
        assert card["city"] == "Bengaluru"
        assert card["campaigns_completed"] == 4
        assert card["reliability"]["band"]
        # Two niches, not the three on the profile.
        assert len(card["niches"]) == server.PUBLIC_CARD_NICHES

    def test_the_component_cannot_render_a_rank(self):
        code = code_of("components", "marketing", "CreatorLeaderboard.jsx")
        # The ways a position could actually get drawn. Not the bare word
        # "rank" — the section's own copy says the creators are ranked on how
        # they work, which is the claim being made rather than a number being
        # printed.
        for smell in ("i + 1", "index + 1", "creator.score", "creator.rank",
                      "creator.position", "#{i", "No. "):
            assert smell not in code, smell


# --- 4. What it ranks on ----------------------------------------------------


class TestTheScoreIsProfessionalismNeverMoney:
    def test_the_scorer_reads_no_money_field_at_all(self):
        """**The one place source-reading is the right instrument**: the
        failure this guards against is a money signal somebody adds later, and
        the test has to fail on the day they add it rather than the day
        somebody notices the ordering looks like a price list."""
        src = inspect.getsource(server.score_creator_standing)
        for money in (
            "agreed_amount", "base_rate", "budget", "creator_payout",
            "lifetime_earned", "earnings", "payout", "fee", "amount", "spend",
            "invoice", "rupee", "price",
        ):
            assert money not in src, f"the standing score reads {money}"

    def test_the_weights_sum_to_a_hundred(self):
        assert sum(server.CREATOR_STANDING_WEIGHTS.values()) == 100

    def test_the_signals_are_the_four_that_were_asked_for(self):
        assert set(server.CREATOR_STANDING_WEIGHTS) == {
            "delivered", "on_time", "performance", "standing",
        }

    def test_it_is_pure(self):
        """No database, so the whole rule can be read in one place and a
        ranking is reproducible from its inputs."""
        src = inspect.getsource(server.score_creator_standing)
        assert "db." not in src and "await" not in src

    def test_every_component_ships_with_the_result(self):
        out = server.score_creator_standing({"completed": 4, "on_time_rate": 1.0})
        assert set(out["components"]) == set(server.CREATOR_STANDING_WEIGHTS)
        assert 0 <= out["score"] <= 100

    def test_an_unmeasured_signal_scores_at_the_midpoint_never_zero(self):
        """A creator whose posts nobody recorded a reading for has an unknown
        performance, not a bad one — the same rule
        `score_creator_for_campaign` holds."""
        out = server.score_creator_standing({"completed": 4, "on_time_rate": 1.0})
        assert "performance" in out["unknown_signals"]
        assert out["components"]["performance"] == pytest.approx(
            server.CREATOR_STANDING_WEIGHTS["performance"] * 0.5
        )

    def test_a_perfect_record_outranks_a_patchy_one(self):
        good = server.score_creator_standing({"completed": 8, "on_time_rate": 1.0})
        patchy = server.score_creator_standing(
            {"completed": 8, "on_time_rate": 0.5, "no_shows": 2}
        )
        assert good["score"] > patchy["score"]

    def test_volume_saturates_so_the_board_is_not_a_seniority_list(self):
        """A creator on their eighth campaign can outrank one on their
        fortieth by doing the work better — the whole point of ranking on
        professionalism."""
        veteran = server.score_creator_standing({"completed": 40, "on_time_rate": 1.0})
        newer = server.score_creator_standing(
            {"completed": server.STANDING_VOLUME_SATURATION, "on_time_rate": 1.0}
        )
        # Asserted as the equality rather than as an ordering: a comparison
        # between a good record and a patchy one passes without saturation
        # existing at all, which is how this test first missed its own break.
        assert veteran["score"] == newer["score"]
        fewer = server.score_creator_standing({"completed": 2, "on_time_rate": 1.0})
        assert fewer["score"] < newer["score"]

    def test_doing_the_work_better_beats_doing_more_of_it(self):
        veteran = server.score_creator_standing({"completed": 40, "on_time_rate": 0.7})
        newer = server.score_creator_standing({"completed": 8, "on_time_rate": 1.0})
        assert newer["score"] > veteran["score"]

    def test_engagement_rate_is_a_percentage_like_everywhere_else(self):
        """A fraction here would be a second meaning for one key name, wrong by
        a factor of a hundred and reading perfectly."""
        full = server.score_creator_standing(
            {"completed": 4, "on_time_rate": 1.0},
            {"engagement_rate": server.STANDING_TARGET_ENGAGEMENT},
        )
        assert full["components"]["performance"] == pytest.approx(
            server.CREATOR_STANDING_WEIGHTS["performance"]
        )
        assert server.STANDING_TARGET_ENGAGEMENT > 1, "a percentage, not a fraction"

    def test_reach_alone_does_not_lift_anybody(self):
        """Otherwise it is a follower-count leaderboard wearing another name:
        a post that reached a hundred thousand and moved none of them must not
        outrank one that reached five thousand and moved them all."""
        async def body(db):
            await _floor(db)
            huge = await _creator(db, name="Huge", reach=100000, engagements=200)
            small = await _creator(db, name="Small", reach=5000, engagements=400)
            await server.refresh_creator_leaderboard()
            cached = await db.leaderboard_cache.find_one({"_id": "current"})
            by_id = {r["user_id"]: r["score"] for r in cached["ranked"]}
            return by_id[huge], by_id[small]

        huge_score, small_score = run(body)
        assert small_score > huge_score

    def test_the_average_is_over_reach_not_the_mean_of_the_rates(self):
        """The mean lets one tiny post with a freak rate move the number — the
        same arithmetic `_rollup_performance` uses."""
        async def body(db):
            creator_oid = await _creator(db, completed=2, reach=1000, engagements=50)
            return await server._creator_performance_for([creator_oid])

        out = run(body)
        assert list(out.values())[0]["engagement_rate"] == pytest.approx(5.0)

    def test_a_reading_with_no_engagements_is_skipped_rather_than_zeroed(self):
        """`_engagements` returns `None` rather than `0` for exactly this
        reason; averaging it in as a zero makes a creator look worse than they
        were."""
        async def body(db):
            creator_oid = await _creator(db, completed=2, reach=1000, engagements=None)
            return await server._creator_performance_for([creator_oid])

        assert run(body) == {}


# --- 5. The honesty floor ---------------------------------------------------


class TestTheSectionHidesRatherThanLookingThin:
    def test_below_the_floor_nothing_comes_back_at_all(self):
        """Not a short row: four faces under a heading about top creators
        advertises a platform with four creators on it."""
        async def body(db):
            await _floor(db, 6)
            for i in range(4):
                await _creator(db, name=f"Creator{i}")
            await server.refresh_creator_leaderboard()
            return await server._public_leaderboard()

        assert run(body) == {}

    def test_at_the_floor_it_renders(self):
        async def body(db):
            await _floor(db, 6)
            for i in range(6):
                await _creator(db, name=f"Creator{i}")
            await server.refresh_creator_leaderboard()
            return await server._public_leaderboard()

        assert len(run(body)["creators"]) == 6

    def test_one_withdrawal_can_take_the_whole_section_down(self):
        """And that is correct rather than unfortunate: the floor is about
        whether the claim is worth making, and it stops being worth making the
        moment there are too few people behind it."""
        async def body(db):
            await _floor(db, 6)
            ids = [await _creator(db, name=f"Creator{i}") for i in range(6)]
            await server.refresh_creator_leaderboard()
            before = await server._public_leaderboard()
            await db.creator_profiles.update_one(
                {"user_id": ids[0]}, {"$set": {"homepage_opt_in": False}}
            )
            return before, await server._public_leaderboard()

        before, after = run(body)
        assert len(before["creators"]) == 6
        assert after == {}

    def test_the_row_is_capped_at_the_configured_size(self):
        async def body(db):
            await db.platform_settings.update_one(
                {"_id": server._LEADERBOARD_SETTINGS_ID},
                {"$set": {"minimum": 2, "size": 3}},
                upsert=True,
            )
            for i in range(8):
                await _creator(db, name=f"Creator{i}")
            await server.refresh_creator_leaderboard()
            return await server._public_leaderboard()

        assert len(run(body)["creators"]) == 3

    def test_the_floor_is_stored_and_falls_back_rather_than_breaking(self):
        async def body(db):
            assert await server.leaderboard_settings() == {
                "minimum": server.LEADERBOARD_MIN_DEFAULT,
                "size": server.LEADERBOARD_SIZE_DEFAULT,
            }
            for stored in ({"minimum": 0}, {"minimum": "six"}, {"minimum": 10**6}):
                await db.platform_settings.delete_many({})
                await db.platform_settings.insert_one(
                    {"_id": server._LEADERBOARD_SETTINGS_ID, **stored}
                )
                out = await server.leaderboard_settings()
                assert out["minimum"] == server.LEADERBOARD_MIN_DEFAULT, stored

        run(body)

    def test_only_an_admin_may_move_the_floor(self):
        """Lowering it is a decision about what the platform is willing to say
        about itself in public, not scoped work."""
        for role in ("weare_team", "brand_manager", "campaign_manager", "creator"):
            assert not guard_allows(server.set_leaderboard_settings, role), role
        assert guard_allows(server.set_leaderboard_settings, "admin")

    def test_the_client_holds_no_second_copy_of_the_floor(self):
        """A client with its own number is a client that disagrees the day an
        admin moves the server's."""
        code = code_of("components", "marketing", "CreatorLeaderboard.jsx")
        assert "length <" not in code and "length >=" not in code
        assert "creators.length === 0" in code


# --- 6. Fast, and cached ----------------------------------------------------


class TestTheHomepageNeverComputesIt:
    def test_the_public_reader_touches_no_collaboration(self):
        """This is the front door on mobile data. The ranking is an
        aggregation over every collaboration on the platform — fine once a
        day, absurd once a visit."""
        src = inspect.getsource(server._public_leaderboard)
        assert "db.collaborations" not in src
        assert "db.content_performance" not in src
        assert "_reliability_for" not in src
        assert "db.leaderboard_cache" in src

    def test_the_cache_is_not_the_settings_collection(self):
        """A nightly job rewriting a document in `platform_settings` is one bad
        `_id` away from overwriting an operator's SLA targets."""
        # The code, not the docstring — which names `platform_settings` in
        # order to explain why it is not used.
        src = inspect.getsource(server._store_leaderboard)
        code = src[src.rindex('"""') + 3 :]
        assert "platform_settings" not in code
        assert "leaderboard_cache" in code

    def test_an_empty_cache_is_an_absent_section_rather_than_an_error(self):
        """A fresh box before the first pass, and a failed job — both render
        nothing rather than a broken band."""
        async def body(db):
            return await server._public_leaderboard()

        assert run(body) == {}

    def test_the_endpoint_is_unauthenticated_and_declared_before_the_include(self):
        """`include_router` copies the routes it can see: one written below it
        registers nothing and 404s with no error anywhere."""
        assert not any(
            isinstance(p.default, params.Depends)
            for p in inspect.signature(server.public_leaderboard).parameters.values()
        )
        source = SOURCE
        assert source.index('@public_router.get("/leaderboard")') < source.index(
            "api_router.include_router(public_router)"
        )

    def test_the_route_is_registered(self):
        paths = [getattr(r, "path", "") for r in server.public_router.routes]
        assert "/public/leaderboard" in paths

    def test_the_refresh_has_a_loop_and_a_manual_door(self):
        """Zero disables the loop, for a deployment driving the job from its
        own scheduler — the same shape the nudge and lifecycle jobs use."""
        assert server._leaderboard_interval_seconds() > 0
        assert hasattr(server, "run_leaderboard_job")
        assert guard_allows(server.run_leaderboard_job, "admin")
        assert not guard_allows(server.run_leaderboard_job, "weare_team")

    def test_the_section_does_not_fetch_until_it_is_near_the_viewport(self):
        """Lazy below the fold: a visitor who never scrolls never pays for
        this at all."""
        code = code_of("components", "marketing", "CreatorLeaderboard.jsx")
        assert "new IntersectionObserver(" in code
        assert "rootMargin" in code
        # And the fetch is gated on that, not fired on mount.
        assert "if (!near) return undefined;" in code


# --- 7. How it looks --------------------------------------------------------


class TestTheVisualTreatment:
    def test_it_takes_the_shadow_exception_rather_than_writing_a_second_one(self):
        """The design foundations reserve `box-shadow` for what genuinely
        floats and the exception is written down where it is taken — which
        only stays true while there is one place to read it."""
        code = code_of("components", "marketing", "CreatorLeaderboard.jsx")
        assert "${CARD_SHADOW}" in code
        assert "shadow-[" not in code, "a second literal is a second exception"

    def test_the_cards_tilt_and_take_the_quiet_hover(self):
        # **Applied, not merely imported.** `CARD_HOVER` at the top of the
        # file says nothing about whether any element wears it.
        code = code_of("components", "marketing", "CreatorLeaderboard.jsx")
        assert "rotate(${tilt}deg)" in code
        assert "${CARD_HOVER}" in code

    def test_there_is_a_monogram_where_there_is_no_photograph(self):
        # Defined *and* rendered — a fallback nothing mounts is a broken
        # image frame on a page about people.
        code = code_of("components", "marketing", "CreatorLeaderboard.jsx")
        assert "function Monogram" in code
        assert "<Monogram" in code
        assert "profile_image_url ? (" in code

    def test_the_image_is_lazy_and_the_ratio_is_on_the_container(self):
        """The design foundations' rule: a photograph that never arrives still
        occupies the space it claimed."""
        src = (FRONTEND / "components" / "marketing" / "CreatorLeaderboard.jsx").read_text()
        assert 'loading="lazy"' in src
        frame = src[src.index("aspect-[4/5]") : src.index("</div>", src.index("aspect-[4/5]"))]
        assert "aspect-" not in frame[frame.index("<img") :] if "<img" in frame else True

    def test_a_card_is_not_a_link_to_a_login_wall(self):
        """The rule is to link through to a public creator page where one
        exists and to leave the card inert otherwise. This product has no
        public creator page — `/profile` is the creator's own, behind auth and
        behind the creator role — so linking there would put every visitor on
        a sign-in screen from a section written for strangers."""
        code = code_of("components", "marketing", "CreatorLeaderboard.jsx")
        assert "<Link" not in code and "<a " not in code
        assert "href" not in code
        assert "<article" in code

    def test_it_is_mounted_on_the_homepage(self):
        """A component with no mount is as unreachable as a route with no
        caller."""
        landing = (FRONTEND / "pages" / "Landing.jsx").read_text()
        assert "<CreatorLeaderboard />" in landing
