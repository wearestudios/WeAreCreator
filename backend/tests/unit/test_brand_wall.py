"""The brand wall — logos of businesses that have actually run campaigns here.

Mirrored on `test_leaderboard.py`, because the feature is mirrored on
`_public_leaderboard`: a cached ordering, eligibility re-read on every request,
an allow-list built by naming keys, and absence below a floor rather than a
thin row.

**Two layers, the split the money paths make.** Several tests here drive the
real handlers against a database and read the result back, because that is the
only thing that catches a guard which is present and does nothing. The
source-reading tests are aimed at a different failure — a new field added to
`brand_profiles` and copied onto a public card by a `**spread` — and they say
so where they are.

The claim this whole file exists to protect: **a wall of logos says "these
businesses are our customers", and the cheap version of that is a wall of
everybody who ever signed up.** Every exclusion test below is one way that
could happen.
"""

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
        db = AsyncMongoMockClient()["brand_wall"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return LOOP.run_until_complete(go())


def guard_allows(fn, role):
    """Would FastAPI let this role through?

    Calling a handler directly skips its `Depends` entirely — the trap
    `bulk_review` re-checks by hand — so the guard is pulled off the signature
    and run. A string match on `require_roles("admin")` would pass for a guard
    listing the wrong roles.
    """
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


def read(*parts):
    return (FRONTEND.joinpath(*parts)).read_text()


# **A sweep over source has to read the code, not the prose about it.**
#
# The convention in this codebase is to explain a decision where it was made,
# and an explanation of a removal necessarily quotes the thing removed — so a
# comment saying "`object-contain`, never `object-cover`" fails a sweep for
# `object-cover`, and a docstring saying "its own collection, not
# `platform_settings`" fails a sweep for `platform_settings`. Three tests in
# this file failed on their own documentation the first time it was run.
#
# Rewording around it is the wrong fix twice over: it makes the comment worse,
# and it leaves the next sweep with the same trap. Stripping comments is the
# fix, and it is the one `test_marketing_pages.py` already uses.
def js_code(*parts):
    """Frontend source with `//` lines and `/* */` blocks removed.

    Whole lines whose first non-space characters are `//`, rather than
    everything from `//` onward — the latter also truncates at the `//` in a
    `https://` inside a real string, which is how a sweep stops seeing the
    code it is for.
    """
    src = read(*parts)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


def py_code(fn):
    """A handler's source with its docstring and `#` comments removed."""
    src = inspect.getsource(fn)
    src = re.sub(r'"""(?:[^"\\]|\\.|"(?!""))*"""', "", src, flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("#")
    )


# Values planted on the brand profile and on everything that joins to it, so
# the leak test can search the real rendered output for them rather than
# reading the source for key names.
PLANTED = {
    "manager_phone": "+919876500077",
    "manager_email": "wall.leak@example.in",
    "manager_name": "Priya Manager",
    "registered_address": "4 Castle Street, Ashok Nagar, Bengaluru 560025",
    "gst_number": "29ABCDE1234F1Z5",
    "verification_reason": "the entity name did not match",
    "legal_entity_name": "Wall Leak Hospitality Private Limited",
    "campaign_fee": 48500,
    "commission_percent": 17.5,
    "total_budget": 275000,
    "budget_per_creator": 9100,
    "typical_budget_band": "band_10k_25k",
}


async def _brand(
    db,
    *,
    name="Toit",
    opted_in=True,
    approved=True,
    verified=True,
    revoked=False,
    logo="/uploads/toit.png",
    finished=1,
    planted=False,
):
    """One brand profile, plus however many finished campaigns it needs."""
    oid = ObjectId()
    doc = {
        "user_id": oid,
        "business_name": name,
        "verified": verified,
        "city": "Bengaluru",
        "category": "fnb",
        "logo_url": logo,
        "homepage_logo_opt_in": opted_in,
        "homepage_logo_approved_at": datetime.now(timezone.utc) if approved else None,
    }
    if revoked:
        doc["trust_revoked"] = True
    if planted:
        doc.update(
            {
                "manager_phone": PLANTED["manager_phone"],
                "contact_phone": PLANTED["manager_phone"],
                "contact_email": PLANTED["manager_email"],
                "contact_person_name": PLANTED["manager_name"],
                "registered_address": PLANTED["registered_address"],
                "gst_number": PLANTED["gst_number"],
                "verification_reason": PLANTED["verification_reason"],
                "legal_entity_name": PLANTED["legal_entity_name"],
                "commission_percent": PLANTED["commission_percent"],
                "typical_budget_band": PLANTED["typical_budget_band"],
            }
        )
    await db.brand_profiles.insert_one(doc)
    for _ in range(finished):
        campaign = {"brand_id": oid, "status": "closed"}
        if planted:
            campaign.update(
                {
                    "campaign_fee": PLANTED["campaign_fee"],
                    "total_budget": PLANTED["total_budget"],
                    "budget_per_creator": PLANTED["budget_per_creator"],
                }
            )
        await db.campaigns.insert_one(campaign)
    return oid


async def _floor(db, *, n=6, **kw):
    """Enough eligible brands to clear the default floor of six.

    Every exclusion test needs this: without it a card going missing is
    indistinguishable from the floor withholding the whole row, which is the
    shape of a test that cannot tell "the rule works" from "nothing ever
    renders".
    """
    return [await _brand(db, name=f"Filler {i:02d}", **kw) for i in range(n)]


async def _wall(db):
    await server.refresh_brand_wall()
    return await server._public_brand_wall()


# --- 1. What the wall is a claim about ---------------------------------------


class TestOnlyBrandsThatHaveActuallyRunACampaign:
    def test_a_signup_that_never_posted_is_not_a_customer(self):
        """**The claim this feature must not get wrong.** A brand that
        registered, consented and was approved is still not evidence of
        anything — and a wall saying otherwise is exactly the thing a
        sceptical reader is checking."""

        async def body(db):
            await _floor(db)
            never = await _brand(db, name="Never Posted", finished=0)
            wall = await _wall(db)
            return [c["name"] for c in wall["brands"]], never

        names, _ = run(body)
        assert "Never Posted" not in names
        assert len(names) == 6

    def test_a_brief_still_running_is_not_a_finished_campaign(self):
        """`_CLOSED_CAMPAIGN_STATUSES` is the line, not "has a campaign". A
        live brief is not evidence that anything was delivered."""

        async def body(db):
            await _floor(db)
            oid = await _brand(db, name="Still Running", finished=0)
            await db.campaigns.insert_one({"brand_id": oid, "status": "open"})
            return [c["name"] for c in (await _wall(db))["brands"]]

        assert "Still Running" not in run(body)

    @pytest.mark.parametrize("status", list(server._CLOSED_CAMPAIGN_STATUSES))
    def test_every_closed_status_counts(self, status):
        """Parametrised over the real tuple, so a status added to it is
        covered by having been added rather than by somebody remembering."""

        async def body(db):
            await _floor(db)
            oid = await _brand(db, name="Finished", finished=0)
            await db.campaigns.insert_one({"brand_id": oid, "status": status})
            return [c["name"] for c in (await _wall(db))["brands"]]

        assert "Finished" in run(body), status

    def test_the_count_is_derived_on_read_not_cached(self):
        """**The count is the whole claim, so it is the last thing that may go
        stale.** A brand whose only campaign is reopened after the nightly
        pass must come off the wall on the next page load, not the next pass.
        """

        async def body(db):
            await _floor(db)
            oid = await _brand(db, name="Reopened", finished=1)
            before = [c["name"] for c in (await _wall(db))["brands"]]
            # The cache is deliberately *not* refreshed after this.
            await db.campaigns.update_one(
                {"brand_id": oid}, {"$set": {"status": "open"}}
            )
            after = [c["name"] for c in (await server._public_brand_wall())["brands"]]
            return before, after

        before, after = run(body)
        assert "Reopened" in before
        assert "Reopened" not in after

    def test_the_count_travels_with_the_card(self):
        async def body(db):
            await _floor(db)
            await _brand(db, name="Busy", finished=4)
            wall = await _wall(db)
            return {c["name"]: c["campaigns_run"] for c in wall["brands"]}

        counts = run(body)
        assert counts["Busy"] == 4
        assert counts["Filler 00"] == 1


# --- 2. Consent, approval, and withdrawal ------------------------------------


class TestBothHalvesOfThePermissionAreRequired:
    def test_a_brand_that_never_consented_is_absent(self):
        """Default off, absent reads off. The only honest default for a
        permission is "not given"."""

        async def body(db):
            await _floor(db)
            await _brand(db, name="No Consent", opted_in=False)
            return [c["name"] for c in (await _wall(db))["brands"]]

        assert "No Consent" not in run(body)

    def test_absent_rather_than_false_also_reads_off(self):
        """Brands predate the field, so the overwhelmingly common state is the
        key simply not being there — and a truthiness check on a missing key
        is the one that has to be right."""

        async def body(db):
            await _floor(db)
            oid = ObjectId()
            await db.brand_profiles.insert_one(
                {
                    "user_id": oid,
                    "business_name": "Predates The Field",
                    "verified": True,
                    "logo_url": "/l.png",
                    "homepage_logo_approved_at": datetime.now(timezone.utc),
                }
            )
            await db.campaigns.insert_one({"brand_id": oid, "status": "closed"})
            return [c["name"] for c in (await _wall(db))["brands"]]

        assert "Predates The Field" not in run(body)

    def test_consent_without_our_approval_is_absent(self):
        """**Two different questions.** Theirs is whether we may use the mark;
        ours is whether we are willing to make the claim. Publishing on
        consent alone means the wall vouches for whoever ticks a box."""

        async def body(db):
            await _floor(db)
            await _brand(db, name="Unapproved", approved=False)
            return [c["name"] for c in (await _wall(db))["brands"]]

        assert "Unapproved" not in run(body)

    def test_withdrawal_takes_effect_without_the_cache_being_rebuilt(self):
        """**The property the whole re-read exists for.** The ordering is a
        day old; consent is not. "You can withdraw at any time with immediate
        effect" is a sentence in the consent text, so it has to be a fact
        about the mechanism rather than a promise on top of it."""

        async def body(db):
            ids = await _floor(db, n=7)
            before = len((await _wall(db))["brands"])
            await db.brand_profiles.update_one(
                {"user_id": ids[0]}, {"$set": {"homepage_logo_opt_in": False}}
            )
            # No refresh. This is the point.
            after = len((await server._public_brand_wall())["brands"])
            return before, after

        before, after = run(body)
        assert (before, after) == (7, 6)

    def test_an_unverified_brand_is_absent(self):
        async def body(db):
            await _floor(db)
            await _brand(db, name="Unverified", verified=False)
            return [c["name"] for c in (await _wall(db))["brands"]]

        assert "Unverified" not in run(body)

    def test_a_trust_revoked_brand_is_absent(self):
        """Revocation is a decision somebody made on purpose about this
        brand. Holding its logo up as an endorsement afterwards would be the
        platform disagreeing with its own record."""

        async def body(db):
            await _floor(db)
            await _brand(db, name="Revoked", revoked=True)
            return [c["name"] for c in (await _wall(db))["brands"]]

        assert "Revoked" not in run(body)

    def test_no_logo_means_no_card(self):
        """The logo is the card — there is nothing to draw without one."""

        async def body(db):
            await _floor(db)
            await _brand(db, name="No Logo", logo="")
            await _brand(db, name="Null Logo", logo=None)
            return [c["name"] for c in (await _wall(db))["brands"]]

        names = run(body)
        assert "No Logo" not in names and "Null Logo" not in names


class TestTheConsentRecordIsFrozen:
    def test_granting_freezes_the_text_and_the_moment(self):
        """**The same arrangement `platform_terms` uses.** A logo is a
        trademark, so what matters in a year is not what the constant says
        then — it is what it said when the box was ticked."""

        async def body(db):
            oid = await _brand(db, name="Consenting", opted_in=False)
            await db.users.insert_one(
                {"_id": oid, "role": "brand_manager", "name": "Consenting"}
            )
            await server.update_brand_profile(
                server.BrandProfileUpdate(homepage_logo_opt_in=True),
                {"_id": oid, "role": "brand_manager", "name": "Consenting"},
            )
            return await db.brand_profiles.find_one({"user_id": oid})

        profile = run(body)
        consent = profile["homepage_logo_consent"]
        assert profile["homepage_logo_opt_in"] is True
        assert consent["terms"] == server.BRAND_LOGO_CONSENT_TERMS
        assert consent["accepted_at"] is not None
        assert consent["accepted_by"] is not None

    def test_saving_again_does_not_move_the_timestamp(self):
        """Re-saving the profile with the box still ticked must not rewrite
        when permission was given, or the record of consent becomes a record
        of the last time somebody pressed Save."""

        async def body(db):
            oid = await _brand(db, name="Consenting", opted_in=False)
            actor = {"_id": oid, "role": "brand_manager", "name": "Consenting"}
            await server.update_brand_profile(
                server.BrandProfileUpdate(homepage_logo_opt_in=True), actor
            )
            first = (await db.brand_profiles.find_one({"user_id": oid}))[
                "homepage_logo_consent"
            ]["accepted_at"]
            await server.update_brand_profile(
                server.BrandProfileUpdate(homepage_logo_opt_in=True), actor
            )
            second = (await db.brand_profiles.find_one({"user_id": oid}))[
                "homepage_logo_consent"
            ]["accepted_at"]
            return first, second

        first, second = run(body)
        assert first == second

    def test_withdrawing_keeps_the_record_and_stamps_it(self):
        """The history is the point: it is what says the logo was published
        with permission at the time."""

        async def body(db):
            oid = await _brand(db, name="Leaving", opted_in=False)
            actor = {"_id": oid, "role": "brand_manager", "name": "Leaving"}
            await server.update_brand_profile(
                server.BrandProfileUpdate(homepage_logo_opt_in=True), actor
            )
            await server.update_brand_profile(
                server.BrandProfileUpdate(homepage_logo_opt_in=False), actor
            )
            return (await db.brand_profiles.find_one({"user_id": oid}))[
                "homepage_logo_consent"
            ]

        consent = run(body)
        assert consent["accepted_at"] is not None
        assert consent["withdrawn_at"] is not None
        assert consent["terms"] == server.BRAND_LOGO_CONSENT_TERMS

    def test_withdrawing_does_not_clear_our_approval(self):
        """Withdrawal is the brand's decision about its own mark, not a
        reversal of ours — so re-ticking the box should not need a second trip
        through the queue."""

        async def body(db):
            oid = await _brand(db, name="Back Again", opted_in=False)
            actor = {"_id": oid, "role": "brand_manager", "name": "Back Again"}
            await server.update_brand_profile(
                server.BrandProfileUpdate(homepage_logo_opt_in=False), actor
            )
            return await db.brand_profiles.find_one({"user_id": oid})

        assert run(body)["homepage_logo_approved_at"] is not None

    def test_the_consent_text_says_both_things_it_has_to(self):
        """What appears where, and that it can be taken back immediately.
        Pinned as ideas rather than as the sentence, because the wording is a
        copy decision and the two commitments are not."""
        terms = server.BRAND_LOGO_CONSENT_TERMS.lower()
        assert "logo" in terms and "name" in terms
        assert "public" in terms
        assert "withdraw" in terms
        assert "immediate" in terms

    def test_an_admin_cannot_tick_the_brands_box_for_it(self):
        """There is no route that grants consent on a brand's behalf, the same
        reason there is no endpoint that mints a second brand manager. The
        approve route writes only our half."""
        src = py_code(server.approve_brand_homepage_logo)
        assert "homepage_logo_opt_in" not in src
        assert "homepage_logo_approved_at" in src


# --- 3. The floor, and the size ---------------------------------------------


class TestAbsentBelowTheFloorRatherThanShort:
    @pytest.mark.parametrize(
        "eligible,expected",
        [(0, None), (5, None), (6, 6), (7, 7), (13, 12)],
    )
    def test_the_boundaries_exactly(self, eligible, expected):
        """Off-by-one at a floor is the classic version of this bug, so both
        sides of it are named. 13 eligible against a size of 12 checks the
        other end."""

        async def body(db):
            await _floor(db, n=eligible)
            return await _wall(db)

        wall = run(body)
        if expected is None:
            assert wall == {}
        else:
            assert len(wall["brands"]) == expected

    def test_one_withdrawal_can_take_the_whole_row_down(self):
        """**And that is correct, not a bug to tune around.** The floor is
        about whether the claim is worth making at all, so a row of five is
        worse than no row."""

        async def body(db):
            ids = await _floor(db, n=6)
            before = len((await _wall(db))["brands"])
            await db.brand_profiles.update_one(
                {"user_id": ids[0]}, {"$set": {"homepage_logo_opt_in": False}}
            )
            return before, await server._public_brand_wall()

        before, after = run(body)
        assert before == 6
        assert after == {}

    def test_the_settings_are_stored_and_clamped(self):
        async def body(db):
            await db.platform_settings.update_one(
                {"_id": server._BRAND_WALL_SETTINGS_ID},
                {"$set": {"minimum": 2, "size": 3}},
                upsert=True,
            )
            stored = await server.brand_wall_settings()
            # Out of range in both directions falls back to the default
            # rather than being honoured — the shape `leaderboard_settings`
            # holds, so a typo cannot empty or flood the section.
            await db.platform_settings.update_one(
                {"_id": server._BRAND_WALL_SETTINGS_ID},
                {"$set": {"minimum": 0, "size": 9999}},
                upsert=True,
            )
            silly = await server.brand_wall_settings()
            return stored, silly

        stored, silly = run(body)
        assert stored == {"minimum": 2, "size": 3}
        assert silly == {
            "minimum": server.BRAND_WALL_MIN_DEFAULT,
            "size": server.BRAND_WALL_SIZE_DEFAULT,
        }

    def test_a_stored_floor_is_honoured(self):
        """Not just read — applied. A settings function nothing consults is
        the shape of a setting that looks editable and governs nothing."""

        async def body(db):
            await db.platform_settings.update_one(
                {"_id": server._BRAND_WALL_SETTINGS_ID},
                {"$set": {"minimum": 3}},
                upsert=True,
            )
            await _floor(db, n=4)
            return await _wall(db)

        assert len(run(body)["brands"]) == 4

    def test_the_cache_is_its_own_collection(self):
        """Not `platform_settings`, which holds what an operator typed. A
        nightly job writing there is one bad `_id` away from overwriting it —
        the separation `leaderboard_cache` makes."""
        src = py_code(server.refresh_brand_wall)
        assert "brand_wall_cache" in src
        assert "platform_settings" not in src


# --- 4. What the card may carry ---------------------------------------------


class TestTheCardCarriesNoContactDetailAndNoMoney:
    def test_not_one_planted_value_survives_into_the_payload(self):
        """**Run it and search the output.** Source-reading catches the
        mistake somebody makes on purpose; running it catches the one where a
        value arrives through a `**spread` from a document nobody remembered
        had one. Values are planted on the brand profile *and* on its
        campaigns, the arrangement `test_exports.py` uses."""

        async def body(db):
            await _floor(db, planted=True)
            return await _wall(db)

        rendered = repr(run(body))
        for label, value in PLANTED.items():
            assert str(value) not in rendered, f"{label} leaked onto a public card"

    def test_the_forbidden_keys_are_not_keys_either(self):
        async def body(db):
            await _floor(db, planted=True)
            return await _wall(db)

        card = run(body)["brands"][0]
        for key in server.PUBLIC_BRAND_CARD_FORBIDDEN:
            assert key not in card, key

    def test_it_is_a_narrower_allow_list_than_the_public_brand_page(self):
        """**Reusing `_public_brand` was the obvious move and would have
        shipped four things onto the home page.** That page is *about* one
        brand, which somebody arrived at on purpose; a wall card is a mark in
        a grid of twelve."""

        async def body(db):
            await _floor(db)
            return await _wall(db)

        card = run(body)["brands"][0]
        for key in ("outlets", "tagline", "about", "instagram_handle"):
            assert key in server._PUBLIC_BRAND_FIELDS or key == "outlets", key
            assert key not in card, key

    def test_the_card_is_exactly_the_keys_it_names(self):
        """An allow-list built by naming keys, so a column added to
        `brand_profiles` next month cannot reach a public page because nobody
        remembered to exclude it."""

        async def body(db):
            await _floor(db)
            return await _wall(db)

        assert set(run(body)["brands"][0]) == {
            "id",
            "name",
            "logo_url",
            "city",
            "category",
            "campaigns_run",
            "public_page",
        }

    def test_a_field_planted_on_the_stored_row_does_not_reach_the_card(self):
        """The break this is aimed at: a projection that copies a document and
        deletes from it. A test that only checks known keys passes for one."""

        async def body(db):
            ids = await _floor(db)
            await db.brand_profiles.update_one(
                {"user_id": ids[0]},
                {"$set": {"some_field_invented_next_month": "SENTINEL-9931"}},
            )
            return await _wall(db)

        assert "SENTINEL-9931" not in repr(run(body))


class TestWhetherTheCardIsALink:
    def test_a_verified_brand_links_to_its_public_page(self):
        async def body(db):
            await _floor(db)
            return await _wall(db)

        card = run(body)["brands"][0]
        assert card["public_page"] == f"/brands/{card['id']}"

    def test_the_component_only_links_where_the_server_said_to(self):
        """The leaderboard's rule: link through where a public page exists and
        leave the card inert otherwise. Decided server-side, so the component
        never works out for itself whether `/brands/{id}` would 404."""
        src = js_code("components", "marketing", "BrandWall.jsx")
        assert "brand.public_page ?" in src
        # And it does not reconstruct the URL itself.
        assert '"/brands/' not in src and "`/brands/" not in src


# --- 5. Who may decide ------------------------------------------------------


class TestAdminOnlyNotConsoleRoles:
    @pytest.mark.parametrize(
        "handler",
        [
            "approve_brand_homepage_logo",
            "revoke_brand_homepage_logo",
            "get_brand_wall_settings",
            "set_brand_wall_settings",
            "run_brand_wall_job",
        ],
    )
    def test_weare_team_cannot_reach_it(self, handler):
        """**The split case studies make, for the same reason.** A logo on the
        home page is a claim this operation puts on the open internet under
        its own name. `weare_team` is scoped to assigned brands, and a scoped
        role that could put a brand on the national home page is not a scope.

        The guard is pulled off the signature and run rather than grepped
        for: a handler listing the wrong roles would pass a string match.
        """
        fn = getattr(server, handler)
        assert guard_allows(fn, "admin") is True
        assert guard_allows(fn, "weare_team") is False
        assert guard_allows(fn, "brand_manager") is False
        assert guard_allows(fn, "creator") is False

    def test_revoking_demands_a_reason(self):
        """"We took them off" is the decision somebody asks about later,
        because nothing visible happens as a result of it. Approving needs
        none: it is complete on its own."""

        async def body(db):
            oid = await _brand(db, name="Going")
            actor = {"_id": ObjectId(), "role": "admin", "name": "An Admin"}
            try:
                await server.revoke_brand_homepage_logo(
                    str(oid), server.ReasonPayload(reason="   "), actor
                )
            except HTTPException as err:
                stored = await db.brand_profiles.find_one({"user_id": oid})
                return err.status_code, stored
            return None, None

        status, stored = run(body)
        assert status == 422
        # **Asserted on stored state, not only on the exception.** A refusal
        # raised after the write is not a refusal.
        assert stored["homepage_logo_approved_at"] is not None

    def test_approving_then_revoking_moves_the_brand_off_the_wall(self):
        async def body(db):
            ids = await _floor(db, n=7)
            actor = {"_id": ObjectId(), "role": "admin", "name": "An Admin"}
            before = len((await _wall(db))["brands"])
            await server.revoke_brand_homepage_logo(
                str(ids[0]),
                server.ReasonPayload(reason="they asked us to over email"),
                actor,
            )
            after = len((await server._public_brand_wall())["brands"])
            stored = await db.brand_profiles.find_one({"user_id": ids[0]})
            return before, after, stored

        before, after, stored = run(body)
        assert (before, after) == (7, 6)
        assert stored["homepage_logo_revoked_reason"] == (
            "they asked us to over email"
        )
        assert stored["homepage_logo_approved_at"] is None

    def test_an_unknown_brand_is_a_404(self):
        async def body(db):
            actor = {"_id": ObjectId(), "role": "admin", "name": "An Admin"}
            try:
                await server.approve_brand_homepage_logo(str(ObjectId()), actor)
            except HTTPException as err:
                return err.status_code
            return None

        assert run(body) == 404

    def test_a_malformed_id_is_a_404_not_a_500(self):
        async def body(db):
            actor = {"_id": ObjectId(), "role": "admin", "name": "An Admin"}
            try:
                await server.approve_brand_homepage_logo("not-an-id", actor)
            except HTTPException as err:
                return err.status_code
            return None

        assert run(body) == 404

    def test_both_decisions_audit(self):
        """Every action that changes what the public site says about a
        business lands in the log."""

        async def body(db):
            oid = await _brand(db, name="Audited")
            actor = {"_id": ObjectId(), "role": "admin", "name": "An Admin"}
            await server.approve_brand_homepage_logo(str(oid), actor)
            await server.revoke_brand_homepage_logo(
                str(oid), server.ReasonPayload(reason="a reason"), actor
            )
            return await db.audit_log.find({}).to_list(length=20)

        actions = {row["action"] for row in run(body)}
        assert "brand.homepage_logo_approve" in actions
        assert "brand.homepage_logo_revoke" in actions

    def test_the_brands_own_consent_audits_too(self):
        """It is a permission about a trademark, so who changed it and when is
        part of the record rather than only a field on a row."""

        async def body(db):
            oid = await _brand(db, name="Consenting", opted_in=False)
            actor = {"_id": oid, "role": "brand_manager", "name": "Consenting"}
            await server.update_brand_profile(
                server.BrandProfileUpdate(homepage_logo_opt_in=True), actor
            )
            return await db.audit_log.find({}).to_list(length=20)

        rows = run(body)
        assert any(r["action"] == "brand.homepage_logo_consent" for r in rows)


# --- 6. The surfaces -------------------------------------------------------
#
# **A caller with no mount is as unreachable as a route with no caller**, the
# rule `test_manager_experience.py` holds. Each of these three endpoints is
# reachable from a screen somebody can actually open.


class TestEveryEndpointHasACallerAndEveryCallerHasAMount:
    def test_the_public_read_is_called_by_the_wall(self):
        assert '"/public/brand-wall"' in read(
            "components", "marketing", "BrandWall.jsx"
        )

    def test_the_wall_is_unmounted_pending_a_decision(self):
        """**Unmounted by the public-site rebuild, deliberately, and pinned that
        way so it cannot happen by accident in either direction.** The rebuilt
        home is the brief's eight sections and the wall is not one of them; the
        component and its endpoint are kept intact for the product decision
        the PR names — remount it, or retire the feature. Until then this
        asserts the component still exists and that no page mounts a second,
        unreviewed copy of it."""
        home = read("pages", "Home.jsx")
        assert "BrandWall" not in home
        assert (FRONTEND / "components" / "marketing" / "BrandWall.jsx").exists()
        assert "/public/brand-wall" in read("components", "marketing", "BrandWall.jsx")

    def test_if_remounted_it_sits_between_the_proof_and_the_case_studies(self):
        """**The order was the argument, and it is recorded for the remount.**
        The figures say there is an operation, the logos say businesses like
        theirs use it, and the write-ups say it works. None of the three is on
        the rebuilt home, so this holds the order where it would be rebuilt:
        nothing mounts the wall anywhere without the other two above and below
        it."""
        for page in (FRONTEND / "pages").glob("*.jsx"):
            src = page.read_text()
            if "<BrandWall" in src:
                assert src.index("<ProofStrip") < src.index("<BrandWall") < src.index("<CaseStudyStrip"), page.name

    def test_the_admin_decisions_have_a_caller(self):
        panel = read("components", "admin", "BrandHomepageLogo.jsx")
        assert "homepage-logo/${action}" in panel
        assert "approve" in panel and "revoke" in panel

    def test_the_admin_panel_is_mounted_on_the_brand_page(self):
        page = read("components", "admin", "BrandDetailPage.jsx")
        assert "import BrandHomepageLogo" in page
        assert "<BrandHomepageLogo" in page

    def test_the_settings_endpoint_has_a_caller(self):
        """`GET`/`PUT /admin/settings/leaderboard` shipped with no caller
        anywhere, which is the failure this project's own rule names: if a
        backend flow has no UI it is not shipped, whatever the tests say. The
        brand wall's does not repeat it."""
        settings = read("components", "admin", "PlatformSettings.jsx")
        assert '"/admin/settings/brand-wall"' in settings
        assert "minimum" in settings and "size" in settings

    def test_the_brand_can_reach_its_own_consent(self):
        onboarding = read("pages", "BrandOnboarding.jsx")
        assert "import HomepageLogoConsent" in onboarding
        assert "<HomepageLogoConsent" in onboarding
        assert "homepage_logo_opt_in: logoOptIn" in onboarding

    def test_the_consent_control_renders_the_servers_terms(self):
        """Not its own copy of the sentence. The text that gets frozen into
        the record is the text that has to be on screen, or we store one
        sentence and show another."""
        src = js_code("components", "brand", "HomepageLogoConsent.jsx")
        assert "terms" in src
        # No hardcoded consent prose of its own.
        assert "withdraw this permission" not in src

    def test_the_control_decides_nothing_for_itself(self):
        """`eligible`, `approved` and `campaigns_run` all arrive from the
        server. A checkbox working out its own eligibility would be a second
        copy of `_brand_wall_eligible`."""
        src = js_code("components", "brand", "HomepageLogoConsent.jsx")
        assert "eligible" in src
        for invented in ("verified", "trust_revoked", "_CLOSED"):
            assert invented not in src, invented


# --- 7. How it behaves on the page -----------------------------------------


class TestTheSectionBehavesLikeTheLeaderboard:
    def test_it_is_fetched_only_when_it_is_nearly_on_screen(self):
        """The same 600px margin, so the two server-fed sections on home
        behave identically. A visitor who never scrolls never pays."""
        src = read("components", "marketing", "BrandWall.jsx")
        assert "IntersectionObserver" in src
        assert 'rootMargin: "600px"' in src

    def test_a_missing_observer_fetches_rather_than_never_rendering(self):
        """Degrading to "the section is missing" would hide real content over
        a progressive enhancement."""
        src = read("components", "marketing", "BrandWall.jsx")
        assert 'typeof IntersectionObserver === "undefined"' in src

    def test_the_shape_is_held_from_first_paint_and_not_gated_on_the_observer(
        self,
    ):
        """**The opposite of what the leaderboard does, and measured.**

        The leaderboard draws nothing until its observer fires, because it is
        at the bottom of the page and reserving earlier leaves a permanent
        block of grey boxes for a visitor who never scrolls that far. This
        section sits directly under the proof strip, which at 390px is right
        at the fold — so the observer fires on load whatever it is told, and
        gating the shape on it bought nothing while costing a 0-to-full growth
        that pushed the whole page down.

        Gated on `near` this measured **0.0823 CLS at 390px against a control
        of 0.0000**, and 0.1644 when the server withheld the row — the section
        appearing and then collapsing, counted twice. Held from first paint it
        is 0.0001.

        So the assertion is that the empty branch is reached *only* by the
        server withholding the row, never by the observer not having fired.
        """
        src = js_code("components", "marketing", "BrandWall.jsx")
        assert "if (brands && brands.length === 0)" in src
        # The render branch must not consult `near`. Specifically `!near ||`,
        # which is the old gate — a blunter sweep for `!near` would match the
        # *fetch* guard below and so could never fail.
        assert "!near ||" not in src
        # The fetch is still deferred — that half is the leaderboard's, and is
        # what keeps a visitor who never scrolls from paying for it.
        assert "if (!near) return undefined;" in src

    def test_the_skeleton_has_its_own_testid(self):
        """**A different id from the real section on purpose.** A test
        asserting the section is absent below the floor must not be satisfied
        by the shape standing in for it before anybody knows."""
        src = read("components", "marketing", "BrandWall.jsx")
        assert "IDS.brandWallSkeleton" in src and "IDS.brandWall" in src
        ids = read("constants", "testIds", "marketing.js")
        assert "brandWall:" in ids and "brandWallSkeleton:" in ids

    def test_the_ratio_is_on_the_container_never_the_image(self):
        """So a logo that never arrives still occupies the space it claimed —
        the rule every media frame in this product holds."""
        src = read("components", "marketing", "BrandWall.jsx")
        # The frame carries it...
        assert 'className="flex aspect-[3/2] w-full' in src
        # ...and the <img> does not.
        img = src[src.index("<img"): src.index("/>", src.index("<img"))]
        assert "aspect-" not in img

    def test_a_logo_is_contained_rather_than_cropped(self):
        """Cropping a mark to fill a box cuts it in half — the rule
        `BrandAvatar` already holds."""
        src = js_code("components", "marketing", "BrandWall.jsx")
        assert "object-contain" in src
        assert "object-cover" not in src

    def test_logos_are_lazy_and_greyscale_at_rest(self):
        src = read("components", "marketing", "BrandWall.jsx")
        assert 'loading="lazy"' in src
        assert "grayscale" in src
        assert "group-hover:grayscale-0" in src

    def test_the_section_carries_no_shadow_at_all(self):
        """A hairline and `bg-card`, which is what elevation is on a light
        band.

        **This required `CARD_SHADOW` to be imported here**, and was right
        while the wall sat on navy: the marketing site has exactly one
        `box-shadow` exception and reusing it beat spelling a second one. The
        wall is a light band now — `data-surface="light"` on home — and a soft
        black shadow on a pale ground reads as dirt rather than as lift, so
        the rule that applies is the other one the design foundations state:
        in a light band, elevation is a hairline plus a card tint.

        The half that has not changed is that no file may spell a shadow of
        its own, so `shadow-[` is still banned here; what changed is that this
        section no longer takes the exception at all.
        """
        src = js_code("components", "marketing", "BrandWall.jsx")
        assert "shadow-[" not in src, "a second box-shadow literal"
        assert "CARD_SHADOW" not in src, "a shadow on a light band"
        assert "border-border" in src and "bg-card" in src, (
            "the hairline and the card tint are what carry elevation here"
        )

    def test_the_name_is_available_to_a_screen_reader(self):
        """A wall of logos a screen reader reads as twelve images is a wall of
        nothing, and `alt` alone does not survive a logo that fails to
        load."""
        src = read("components", "marketing", "BrandWall.jsx")
        assert "sr-only" in src


# --- 8. The job and the loop ------------------------------------------------


class TestTheOrderingIsComputedOffThePage:
    def test_the_public_read_touches_no_campaign_aggregation_it_cannot_afford(
        self,
    ):
        """It reads the cache for the ordering and one aggregation for the
        counts, over a handful of ids rather than every campaign on the
        platform. The ranking is the expensive half and it is not here."""
        src = py_code(server._public_brand_wall)
        assert "brand_wall_cache" in src
        assert "_campaigns_run_by_brand" in src
        # Not the full candidate scan, which is `refresh_brand_wall`'s job.
        assert "find(" not in src.split("brand_wall_cache")[0]

    def test_an_empty_cache_is_an_absent_section_not_an_error(self):
        """A fresh deployment has not run the job yet. The homepage must not
        500 over that."""

        async def body(db):
            return await server._public_brand_wall()

        assert run(body) == {}

    def test_a_brand_erased_between_the_pass_and_the_read_is_skipped(self):
        """A tombstone is not somebody to feature."""

        async def body(db):
            ids = await _floor(db, n=7)
            await server.refresh_brand_wall()
            await db.brand_profiles.delete_one({"user_id": ids[0]})
            return await server._public_brand_wall()

        assert len(run(body)["brands"]) == 6

    def test_the_ordering_puts_the_most_finished_campaigns_first(self):
        async def body(db):
            await _floor(db, n=6)
            await _brand(db, name="Most", finished=9)
            return [c["name"] for c in (await _wall(db))["brands"]]

        assert run(body)[0] == "Most"

    def test_the_refresh_rides_the_leaderboard_loop(self):
        """Same cadence, same kind of work, same kind of claim — two cached
        orderings behind two public sections. A second timer would be a
        second interval constant to keep in step for no gain, and each
        failure is caught separately so one cannot take the other down."""
        src = inspect.getsource(server._leaderboard_loop)
        assert "refresh_brand_wall" in src
        assert src.count("except Exception") >= 2

    def test_approving_refreshes_so_the_page_agrees(self):
        """Approval is the one half that is *not* re-read live — a brand
        nobody has approved was never in the cache to be re-checked — so the
        route rebuilds it rather than leaving an operator to wait a day."""
        src = inspect.getsource(server.approve_brand_homepage_logo)
        assert "refresh_brand_wall" in src
