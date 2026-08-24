"""Three rules about what a brand may reach, and one file it may take away.

- **A brand has no creator directory.** It sees the creators on its own
  briefs — applied, invited, working — and never a browsable roster.
- **Some campaigns are ours to run whatever the brand picks**: a launch,
  because it is one evening with no second attempt, and a brief for more than
  the threshold, because that is that many bookings.
- **The closed campaign is a file the brand keeps**, and that file carries no
  way to reach anybody.

Driven rather than read wherever the rule is about behaviour. A guard that is
present and points at the wrong document keeps the string and loses the
protection, so the enforcement tests call the real handler and read the
database back; only the "this route no longer exists" claims are structural,
because absence is exactly what a structural test is good at.
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timezone
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
        db = AsyncMongoMockClient()["access_and_execution"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return LOOP.run_until_complete(go())


def role_guard(fn):
    """The `require_roles` guard the route actually carries, ready to call.

    **Calling a route function directly skips its `Depends`**, so a test that
    hands a brand user to a handler proves nothing about whether a brand may
    call it. This pulls the real dependency off the signature.
    """
    for p in inspect.signature(fn).parameters.values():
        dep = p.default
        if isinstance(dep, params.Depends) and dep.dependency is not None:
            if getattr(dep.dependency, "__name__", "") == "_guard":
                return dep.dependency
    raise AssertionError(f"{fn.__name__} declares no require_roles guard")


def guard_allows(fn, role):
    guard = role_guard(fn)

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


# --- 1. There is no creator directory a brand can browse -----------------------


class TestTheBrandHasNoRoster:
    def test_the_two_directory_endpoints_are_gone(self):
        """`GET /brand/creators` and `/brand/creators/filters` let a brand page
        through every verified creator on the platform. A brand may see the
        people on its own briefs; the rest are not its business."""
        assert not hasattr(server, "brand_directory")
        assert not hasattr(server, "brand_directory_filters")

    def test_no_route_on_the_brand_router_serves_a_creator_list(self):
        """Structural, and deliberately so: the failure this is aimed at is
        somebody adding the directory back under a different name."""
        paths = [
            r.path
            for r in server.brand_router.routes
            if getattr(r, "path", "").startswith("/creators")
        ]
        assert paths == [], paths

    def test_the_page_and_its_route_are_gone_too(self):
        """A backend flow with no UI is not shipped, and the reverse is worse:
        a screen calling two endpoints that answer 404."""
        assert not (FRONTEND / "pages" / "BrandCreatorDirectory.jsx").exists()
        app = (FRONTEND / "App.js").read_text()
        assert "/brand/creators" not in app
        assert "BrandCreatorDirectory" not in app

    def test_nothing_in_the_frontend_calls_the_directory(self):
        hits = [
            p
            for p in FRONTEND.rglob("*.js*")
            if "/brand/creators" in p.read_text()
        ]
        assert hits == [], [str(p) for p in hits]

    def test_the_brand_navigation_does_not_offer_one(self):
        """The link was in the navbar on every brand screen, which is the
        strongest possible claim that browsing is a thing a brand does."""
        nav = (FRONTEND / "components" / "Navbar.jsx").read_text()
        assert "nav-brand-creators" not in nav
        dash = (FRONTEND / "pages" / "BrandDashboardView.jsx").read_text()
        assert "brand-header-browse-creators-btn" not in dash

    def test_the_curated_replacement_is_still_there_and_still_per_brief(self):
        """This is the half that is *not* being removed. "We surface the right
        creators for your brief" needs a surface, and it is this one — ranked
        against one campaign, with the reasons shipped, and everyone who
        already applied or was invited excluded."""
        assert hasattr(server, "brand_suggested_creators")
        params_ = inspect.signature(server.brand_suggested_creators).parameters
        assert "campaign_id" in params_, "suggestions are per-brief or they are a directory"

    def test_the_suggestions_are_still_a_brand_visible_projection(self):
        # Through the shared builder it delegates to — one implementation, so
        # the panel and the applicant board cannot show different fields.
        src = inspect.getsource(server._suggest_creators_for_campaign)
        assert "_brand_visible_creator" in src

    def test_the_marketing_copy_no_longer_offers_a_roster(self):
        """It said applicants arrive "ranked alongside verified creators who
        fit", which reads as a directory to shop through."""
        copy = (FRONTEND / "pages" / "ForBrands.jsx").read_text()
        code = "\n".join(
            l for l in copy.splitlines() if not l.strip().startswith("//")
        )
        assert "ranked alongside verified creators" not in code
        assert "matched to your brief" in code


# --- 2 & 3. Some campaigns are ours to run ------------------------------------


class TestWhichCampaignsAreOursByRule:
    def test_a_launch_is_ours_whatever_the_headcount(self):
        reason = server._weare_run_reason("launch", 1, 15)
        assert reason and reason[0] == "launch"

    def test_a_big_brief_is_ours_whatever_the_type(self):
        for kind in ("personal_table", "group_event", None, "something_new"):
            reason = server._weare_run_reason(kind, 16, 15)
            assert reason and reason[0] == "large", kind

    def test_the_threshold_is_exclusive(self):
        """"More than 15" is 16, not 15. An off-by-one here quietly moves every
        fifteen-creator brief onto our desk."""
        assert server._weare_run_reason("personal_table", 15, 15) is None
        assert server._weare_run_reason("personal_table", 16, 15)[0] == "large"

    def test_an_ordinary_brief_is_the_brand_s(self):
        assert server._weare_run_reason("personal_table", 4, 15) is None

    def test_the_reason_is_written_as_the_offer(self):
        """A brand is not losing control of a campaign, it is getting a manager
        on the one where it matters. Both sentences say what we do and that
        the brand still approves the work."""
        for reason in (
            server._weare_run_reason("launch", 1, 15),
            server._weare_run_reason("personal_table", 40, 15),
        ):
            assert "our team" in reason[1]
            assert "approve the work" in reason[1]
            assert "cannot" not in reason[1] and "not allowed" not in reason[1]

    def test_a_missing_headcount_is_not_a_large_campaign(self):
        """Absent reads safe: `None` is not "more than fifteen"."""
        for value in (None, "", "not a number", 0):
            assert server._weare_run_reason("personal_table", value, 15) is None

    def test_the_threshold_is_stored_rather_than_hardcoded(self):
        async def body(db):
            assert await server.large_campaign_threshold() == (
                server.LARGE_CAMPAIGN_CREATORS_DEFAULT
            )
            await db.platform_settings.insert_one(
                {"_id": server._LARGE_CAMPAIGN_SETTINGS_ID, "creators": 6}
            )
            assert await server.large_campaign_threshold() == 6

        run(body)

    def test_a_nonsense_stored_value_falls_back_rather_than_breaking_the_form(self):
        async def body(db):
            for stored in ({"creators": 0}, {"creators": "many"}, {"creators": 10**6}, {}):
                await db.platform_settings.delete_many({})
                await db.platform_settings.insert_one(
                    {"_id": server._LARGE_CAMPAIGN_SETTINGS_ID, **stored}
                )
                assert await server.large_campaign_threshold() == (
                    server.LARGE_CAMPAIGN_CREATORS_DEFAULT
                )

        run(body)

    def test_only_an_admin_may_move_the_line(self):
        """A brand that could raise the threshold could opt itself out of the
        rule, which is the rule not existing."""
        for role in ("brand_manager", "brand", "weare_team", "campaign_manager"):
            assert not guard_allows(server.put_large_campaign_threshold, role)
        assert guard_allows(server.put_large_campaign_threshold, "admin")


async def _brand_scene(db, *, verified=True, threshold=None):
    """A verified brand with a manager, ready to post."""
    brand_oid = ObjectId()
    await db.users.insert_one(
        {"_id": brand_oid, "role": "brand_manager", "name": "Ravi",
         "brand_id": brand_oid, "phone": "+919900000001",
         "email": "ravi@example.in"}
    )
    await db.brand_profiles.insert_one(
        {"user_id": brand_oid, "business_name": "Toit", "verified": verified,
         "verified_at": _now(), "verification_state":
             "verified" if verified else "unsubmitted"}
    )
    if threshold is not None:
        await db.platform_settings.insert_one(
            {"_id": server._LARGE_CAMPAIGN_SETTINGS_ID, "creators": threshold}
        )
    user = await db.users.find_one({"_id": brand_oid})
    return {**user, "_id": str(brand_oid)}, brand_oid


def _payload(**over):
    body = {
        "title": "Tasting evening",
        "brief": "Come and shoot the room.",
        "deliverable_items": [{"type": "reel", "quantity": 1}],
        "budget_per_creator": 8000,
        "compensation_type": "fixed",
        "category": "fnb",
        "area": "Indiranagar",
        "creators_needed": 3,
        "campaign_type": "personal_table",
        "start_date": _now(),
        "end_date": _now(),
        "execution_owner": "brand",
    }
    body.update(over)
    return server.PostCampaignPayload(**body)


class TestTheRuleIsEnforcedOnCreation:
    def test_a_launch_is_created_weare_run_however_the_brand_picked(self):
        async def body(db):
            user, _ = await _brand_scene(db)
            out = await server.create_brand_campaign(
                _payload(
                    campaign_type="launch",
                    event_date=_now(),
                    start_date=None,
                    end_date=None,
                    execution_owner="brand",
                ),
                user,
            )
            doc = await db.campaigns.find_one({"_id": ObjectId(out["id"])})
            assert doc["execution_owner"] == "weare"
            assert doc["weare_run_reason"] == "launch"

        run(body)

    def test_a_big_brief_is_created_weare_run(self):
        async def body(db):
            user, _ = await _brand_scene(db, threshold=5)
            out = await server.create_brand_campaign(
                _payload(creators_needed=6, execution_owner="brand"), user
            )
            doc = await db.campaigns.find_one({"_id": ObjectId(out["id"])})
            assert doc["execution_owner"] == "weare"
            assert doc["weare_run_reason"] == "large"

        run(body)

    def test_an_ordinary_brief_still_belongs_to_the_brand(self):
        """The rule must not quietly take everything: posting a brief means
        running it unless you say otherwise."""
        async def body(db):
            user, _ = await _brand_scene(db)
            out = await server.create_brand_campaign(
                _payload(creators_needed=3, execution_owner="brand"), user
            )
            doc = await db.campaigns.find_one({"_id": ObjectId(out["id"])})
            assert doc["execution_owner"] == "brand"
            assert doc.get("weare_run_reason") is None

        run(body)

    def test_a_weare_run_brief_gets_no_campaign_manager_from_the_brand(self):
        """Defaulting the manager to the brand's own person would route every
        application straight back to the brand that just handed it over."""
        async def body(db):
            user, brand_oid = await _brand_scene(db)
            out = await server.create_brand_campaign(
                _payload(campaign_type="launch", event_date=_now(),
                         start_date=None, end_date=None),
                user,
            )
            doc = await db.campaigns.find_one({"_id": ObjectId(out["id"])})
            assert doc.get("manager_id") != brand_oid

        run(body)


class TestTheRuleIsEnforcedOnEdit:
    def test_editing_the_headcount_over_the_line_hands_it_over(self):
        async def body(db):
            user, brand_oid = await _brand_scene(db, threshold=5)
            out = await server.create_brand_campaign(
                _payload(creators_needed=3), user
            )
            cid = out["id"]
            await server.update_brand_campaign(
                cid, server.UpdateCampaignPayload(creators_needed=20), user
            )
            doc = await db.campaigns.find_one({"_id": ObjectId(cid)})
            assert doc["execution_owner"] == "weare"
            assert doc["weare_run_reason"] == "large"

        run(body)

    def test_the_handover_is_audited_and_both_sides_are_told(self):
        """A campaign changing hands without the brand hearing about it is the
        brand finding out from an applicant."""
        async def body(db):
            user, _ = await _brand_scene(db, threshold=5)
            out = await server.create_brand_campaign(_payload(creators_needed=3), user)
            await server.update_brand_campaign(
                out["id"], server.UpdateCampaignPayload(creators_needed=20), user
            )
            actions = await db.audit_log.find(
                {"action": "campaign.execution_handover"}
            ).to_list(length=10)
            assert len(actions) == 1
            notes = await db.notifications.find({}).to_list(length=50)
            assert notes, "nobody was told the campaign changed hands"

        run(body)

    def test_editing_back_under_the_line_returns_it(self):
        """The rule is about the shape of the work. A brief cut back to four
        creators is a four-creator brief again, and holding onto it would be
        us keeping work the rule never said was ours."""
        async def body(db):
            user, _ = await _brand_scene(db, threshold=5)
            out = await server.create_brand_campaign(_payload(creators_needed=3), user)
            cid = out["id"]
            await server.update_brand_campaign(
                cid, server.UpdateCampaignPayload(creators_needed=20), user
            )
            await server.update_brand_campaign(
                cid, server.UpdateCampaignPayload(creators_needed=4), user
            )
            doc = await db.campaigns.find_one({"_id": ObjectId(cid)})
            assert doc.get("weare_run_reason") is None

        run(body)

    def test_a_brand_cannot_take_a_launch_back(self):
        async def body(db):
            user, _ = await _brand_scene(db)
            out = await server.create_brand_campaign(
                _payload(campaign_type="launch", event_date=_now(),
                         start_date=None, end_date=None),
                user,
            )
            cid = out["id"]
            with pytest.raises(HTTPException) as err:
                await server.update_brand_campaign(
                    cid,
                    server.UpdateCampaignPayload(execution_owner="brand"),
                    user,
                )
            # 409, not 422: the payload is well formed, the campaign's shape
            # is what refuses it.
            assert err.value.status_code == 409
            assert err.value.detail["code"] == "weare_run_launch"
            # **Read the row back.** A refusal raised after the write is not a
            # refusal.
            doc = await db.campaigns.find_one({"_id": ObjectId(cid)})
            assert doc["execution_owner"] == "weare"

        run(body)

    def test_a_brand_cannot_take_a_large_brief_back(self):
        async def body(db):
            user, _ = await _brand_scene(db, threshold=5)
            out = await server.create_brand_campaign(_payload(creators_needed=9), user)
            cid = out["id"]
            with pytest.raises(HTTPException) as err:
                await server.update_brand_campaign(
                    cid,
                    server.UpdateCampaignPayload(execution_owner="brand"),
                    user,
                )
            assert err.value.detail["code"] == "weare_run_large"
            doc = await db.campaigns.find_one({"_id": ObjectId(cid)})
            assert doc["execution_owner"] == "weare"

        run(body)

    def test_an_admin_is_not_held_to_it(self):
        """`PATCH /admin/campaigns/{id}` deliberately does not call the guard —
        the same asymmetry `_refuse_brand_barter` has, and for the same reason:
        the rule is a default for brands, not a fact about the database."""
        src = inspect.getsource(server.admin_update_campaign)
        assert "_refuse_late_execution_handover" not in src

    def test_the_form_is_told_the_threshold_rather_than_keeping_a_copy(self):
        """A number the form hardcodes is a form arguing with the route it
        posts to the day an admin changes it."""
        src = inspect.getsource(server._brand_profile_response)
        assert "large_campaign_threshold" in src
        js = (FRONTEND / "lib" / "execution.js").read_text()
        # The reader takes the threshold rather than knowing it. A default
        # spelled here would be a second answer to a question an admin can
        # change.
        assert "export const weareRunReason = ({" in js
        assert "threshold" in js
        assert f"= {server.LARGE_CAMPAIGN_CREATORS_DEFAULT}" not in js

    def test_the_form_replaces_the_picker_rather_than_offering_a_dead_choice(self):
        form = (FRONTEND / "pages" / "PostCampaign.jsx").read_text()
        # The derivation itself, not merely the identifier: `const weareRun =
        # null && weareRunReason(...)` mentions it and answers nothing.
        assert "const weareRun = weareRunReason({" in form
        assert "{weareRun ? (" in form
        assert "EXECUTION.weareRun" in form
        # And it sends the value the server is going to store, or the edit path
        # refuses the whole save over a field the form no longer shows.
        assert 'weareRun ? "weare" : executionOwner' in form


# --- 4. The closed campaign, as a file the brand keeps -------------------------


async def _finished_campaign(db, *, status="closed", contact=True):
    """A closed campaign with two creators on it, one delivered, one cancelled.

    The creator profile is planted with **every** kind of contact detail this
    product holds, so the leak test below has something to find if the
    projection ever stops being an allow-list.
    """
    brand_oid, campaign_oid = ObjectId(), ObjectId()
    delivered_oid, cancelled_oid = ObjectId(), ObjectId()

    await db.users.insert_one(
        {"_id": brand_oid, "role": "brand_manager", "name": "Ravi",
         "brand_id": brand_oid, "phone": "+919900000001"}
    )
    await db.brand_profiles.insert_one(
        {"user_id": brand_oid, "business_name": "Toit", "verified": True,
         "verified_at": _now()}
    )
    await db.campaigns.insert_one(
        {"_id": campaign_oid, "brand_id": brand_oid, "title": "Tasting evening",
         "status": status, "reference": "CMP-0034",
         "compensation_type": "fixed", "budget_per_creator": 12000,
         "deliverables": "1 reel · 3 stories",
         "deliverable_items": [{"type": "reel", "quantity": 1},
                               {"type": "story", "quantity": 3}],
         "usage_rights": "organic_only",
         "start_date": _now(), "end_date": _now()}
    )

    people = []
    for oid, name, state in (
        (delivered_oid, "Asha", "content_approved"),
        (cancelled_oid, "Nikhil", "cancelled"),
    ):
        creator_oid = ObjectId()
        people.append(creator_oid)
        await db.users.insert_one(
            {"_id": creator_oid, "role": "creator", "name": name,
             "phone": PLANTED["phone"], "email": PLANTED["email"]}
        )
        await db.creator_profiles.insert_one(
            {"user_id": creator_oid, "name": name,
             "instagram_handle": f"{name.lower()}.shoots",
             "verification_status": "verified",
             # Everything a brand must never receive, all at once.
             "phone": PLANTED["phone"],
             "whatsapp": PLANTED["phone"],
             "email": PLANTED["email"],
             "full_address": PLANTED["address"],
             "location_lat": PLANTED["lat"],
             "location_lng": PLANTED["lng"],
             "payout_upi": PLANTED["upi"],
             "payout_account_number": PLANTED["account"],
             "payout_ifsc": PLANTED["ifsc"],
             "pan": PLANTED["pan"]}
        )
        await db.collaborations.insert_one(
            {"_id": oid, "campaign_id": campaign_oid, "creator_id": creator_oid,
             "state": state, "agreed_amount": 12000, "agreed_at": _now(),
             "state_since": _now(), "checked_in_at": _now(),
             "content_urls": ["https://instagram.com/p/abc"],
             "delivered_counts": {"reel": 1, "story": 3}}
        )

    campaign = await db.campaigns.find_one({"_id": campaign_oid})
    user = await db.users.find_one({"_id": brand_oid})
    return campaign, {**user, "_id": str(brand_oid)}, str(campaign_oid), people


PLANTED = {
    "phone": "+919876500001",
    "email": "priya.leak@example.in",
    "address": "42 Chinmaya Road, Indiranagar, Bengaluru 560038",
    "lat": 12.9784321,
    "lng": 77.6408123,
    "upi": "priyaleak@okaxis",
    "account": "50100123456789",
    "ifsc": "HDFC0000123",
    "pan": "ABCDE1234F",
}


class TestTheBrandExportCarriesNoWayToReachAnybody:
    def test_not_one_planted_value_survives_into_the_file(self):
        """**Run the builder and search the bytes**, rather than reading the
        source for a column name. Source-reading catches the mistake somebody
        makes on purpose; running it catches the one where a phone number
        arrives through a `**spread` from a document nobody remembered had
        one."""
        async def body(db):
            campaign, _, _, _ = await _finished_campaign(db)
            return await server._build_brand_campaign_export(campaign)

        csv_text = run(body)
        for label, value in PLANTED.items():
            assert str(value) not in csv_text, f"{label} leaked into the export"

    def test_the_forbidden_keys_are_not_column_headers_either(self):
        for key in server.BRAND_FORBIDDEN_CREATOR_FIELDS:
            assert key not in server.BRAND_EXPORT_COLUMNS

    def test_it_builds_its_creators_through_the_allow_list(self):
        """Structural on top of the behavioural one, and worth both: this is
        what makes the exclusion a property of the projection rather than of
        the ten column names somebody happened to choose."""
        src = inspect.getsource(server._build_brand_campaign_export)
        assert "_brand_visible_creator" in src

    def test_the_route_records_that_it_carried_none(self):
        src = inspect.getsource(server.export_brand_campaign)
        assert '"includes_contact_details": False' in src


class TestWhatTheExportSays:
    def _csv(self, **over):
        async def body(db):
            campaign, _, _, _ = await _finished_campaign(db, **over)
            return await server._build_brand_campaign_export(campaign)

        return run(body)

    def test_it_names_the_creators_and_their_handles(self):
        text = self._csv()
        assert "Asha" in text and "@asha.shoots" in text

    def test_it_carries_what_was_asked_for_and_what_arrived(self):
        text = self._csv()
        assert "1 reel · 3 stories" in text
        for column in ("Deliverables agreed", "Deliverables delivered",
                       "Live content", "Attended", "Fee", "Usage rights"):
            assert column in text, column

    def test_it_carries_the_live_links(self):
        assert "https://instagram.com/p/abc" in self._csv()

    def test_it_ends_with_the_campaign_s_totals(self):
        text = self._csv()
        assert "Creators on the campaign" in text
        assert "Creators who delivered" in text
        assert "Total agreed (INR)" in text

    def test_a_date_rather_than_an_instant(self):
        """This goes to a client. An ISO timestamp in a spreadsheet cell is us
        showing our working."""
        text = self._csv()
        assert "T00:" not in text and "+00:00" not in text

    def test_it_lists_who_was_taken_on_rather_than_who_applied(self):
        """A brand forwarding this to its own finance team should not be
        forwarding a list of the creators it turned down."""
        async def body(db):
            campaign, _, campaign_oid, _ = await _finished_campaign(db)
            rejected = ObjectId()
            await db.users.insert_one(
                {"_id": rejected, "role": "creator", "name": "Turned Down"}
            )
            await db.creator_profiles.insert_one(
                {"user_id": rejected, "name": "Turned Down"}
            )
            await db.collaborations.insert_one(
                {"_id": ObjectId(), "campaign_id": ObjectId(campaign_oid),
                 "creator_id": rejected, "state": "declined",
                 "state_since": _now()}
            )
            return await server._build_brand_campaign_export(campaign)

        assert "Turned Down" not in run(body)

    def test_barter_carries_no_total_and_no_zero(self):
        """`0` in a money column reads as a campaign that cost nothing rather
        than one that was never priced."""
        async def body(db):
            campaign, _, _, _ = await _finished_campaign(db)
            await db.campaigns.update_one(
                {"_id": campaign["_id"]},
                {"$set": {"compensation_type": "barter",
                          "barter_description": "Dinner for two"}},
            )
            fresh = await db.campaigns.find_one({"_id": campaign["_id"]})
            return await server._build_brand_campaign_export(fresh)

        text = run(body)
        line = [l for l in text.splitlines() if l.startswith("Total agreed")][0]
        assert line.strip().rstrip(",") == "Total agreed (INR)"


class TestWhoMayExportAndWhen:
    def test_a_brand_and_an_admin_may_a_creator_may_not(self):
        for role in ("brand", "brand_manager", "admin"):
            assert guard_allows(server.export_brand_campaign, role), role
        for role in ("creator", "campaign_manager"):
            assert not guard_allows(server.export_brand_campaign, role), role

    def test_ownership_is_checked_before_verification(self):
        """The other order turns another brand's campaign from a 404 into a
        403, which leaks which ids exist."""
        src = inspect.getsource(server.export_brand_campaign)
        assert "_own_campaign_or_404" in src

    def test_another_brand_s_campaign_is_a_404(self):
        async def body(db):
            campaign, _, campaign_oid, _ = await _finished_campaign(db)
            stranger_oid = ObjectId()
            await db.users.insert_one(
                {"_id": stranger_oid, "role": "brand_manager", "name": "Someone",
                 "brand_id": stranger_oid}
            )
            stranger = await db.users.find_one({"_id": stranger_oid})
            with pytest.raises(HTTPException) as err:
                await server.export_brand_campaign(
                    campaign_oid, {**stranger, "_id": str(stranger_oid)}
                )
            return err.value.status_code

        assert run(body) == 404

    @pytest.mark.parametrize("status", ["open", "in_progress", "paused", "draft"])
    def test_a_running_campaign_is_refused_and_says_why(self, status):
        """The delivery columns are the point of the file and they are still
        being filled in."""
        async def body(db):
            _, user, campaign_oid, _ = await _finished_campaign(db, status=status)
            with pytest.raises(HTTPException) as err:
                await server.export_brand_campaign(campaign_oid, user)
            return err.value

        exc = run(body)
        assert exc.status_code == 409
        assert exc.detail["code"] == "campaign_not_closed"

    @pytest.mark.parametrize("status", ["closed", "completed"])
    def test_a_finished_campaign_downloads(self, status):
        async def body(db):
            _, user, campaign_oid, _ = await _finished_campaign(db, status=status)
            return await server.export_brand_campaign(campaign_oid, user)

        response = run(body)
        assert response.status_code == 200
        assert "text/csv" in response.media_type
        # Not something to leave in a shared browser cache.
        assert response.headers["cache-control"] == "no-store"
        assert "attachment" in response.headers["content-disposition"]

    def test_the_download_is_audited(self):
        """A file of a campaign's whole delivery record leaving the system is
        exactly the event the log exists to record."""
        async def body(db):
            _, user, campaign_oid, _ = await _finished_campaign(db)
            await server.export_brand_campaign(campaign_oid, user)
            return await db.audit_log.find(
                {"action": "campaign.export"}
            ).to_list(length=5)

        lines = run(body)
        assert len(lines) == 1
        assert lines[0].get("campaign_id") is not None

    def test_the_button_is_absent_rather_than_present_and_refusing(self):
        dash = (FRONTEND / "pages" / "BrandDashboardView.jsx").read_text()
        assert "brand-campaign-export-" in dash
        # **The status check has to be the whole condition**, not one arm of
        # it: `{true || [...].includes(c.status)}` contains every string a
        # looser assertion looks for and renders the button on a live
        # campaign. So read the gap between the check and the button it
        # guards, and refuse anything that would let something else through.
        #
        # The opening brace is what carries that: with anything in front of
        # the check the expression no longer *starts* with it. Matching the
        # condition alone passes on the broken version, because the `||` sits
        # on the side a forward slice never reads — which is how this
        # assertion was wrong the first time it was written.
        assert '{["closed", "completed"].includes(' in dash
        gap = dash[
            dash.index('{["closed", "completed"].includes(')
            : dash.index("brand-campaign-export-")
        ]
        assert len(gap) < 600, "the check does not guard the export button"

    def test_the_file_is_fetched_as_an_authenticated_blob(self):
        """The cookie is `SameSite=None`, so a bare `href` at the API rides
        along in production and silently does not on a plain-http laptop —
        the lesson `BrandDocuments` already learned."""
        dash = (FRONTEND / "pages" / "BrandDashboardView.jsx").read_text()
        block = dash[dash.index("const exportCampaign") :]
        block = block[: block.index("const profileMissing")]
        assert 'responseType: "blob"' in block
        assert "API_BASE" not in block
