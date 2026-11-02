"""The admin and `weare_team` console, complete.

Four places the scoped console broke, three settings with an endpoint and no
form, five smaller admin dead ends, and one product decision surfaced rather
than made. Every gated item is driven against its real guard here — calling a
route function directly skips its `Depends`, so a test that hands a team
member to a handler proves nothing about whether they may call it.

And one finding none of the above was looking for: four routes were declared
on a router *after* that router had been included, so `include_router` had
already copied its routes and these were never served — the disputes queue,
its resolution, and both `verification/confirm` routes answered 404 in
production while every unit test, which calls handlers directly, stayed green.
`TestEveryRouteIsServed` drives the app's own route table to hold it.
"""
import asyncio
import inspect
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException, params

import server
from test_access_matrix import World, no_comments

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"
ADMIN = FRONTEND / "components" / "admin"

_LOOP = None


@pytest.fixture
def world():
    global _LOOP
    keep = server.db
    _LOOP = asyncio.new_event_loop()
    try:
        yield _LOOP.run_until_complete(World().build())
    finally:
        _LOOP.close()
        _LOOP = None
        server.db = keep
        server._SLA_CACHE.clear() if hasattr(server, "_SLA_CACHE") else None


def run(coro):
    return _LOOP.run_until_complete(coro)


def route(method, path):
    for r in server.app.routes:
        if getattr(r, "path", None) == "/api" + path and method in getattr(r, "methods", ()):
            return r.endpoint
    raise AssertionError(f"{method} {path} is not served")


def allows(fn, role):
    for p in inspect.signature(fn).parameters.values():
        dep = p.default
        if isinstance(dep, params.Depends) and getattr(dep.dependency, "__name__", "") == "_guard":
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(dep.dependency({"_id": "x", "role": role}))
                return True
            except HTTPException as err:
                assert err.status_code == 403
                return False
            finally:
                loop.close()
    raise AssertionError(f"{fn.__name__} has no role guard")


# ---------------------------------------------------------------------------
# Every route on every router reaches the app
# ---------------------------------------------------------------------------


class TestEveryRouteIsServed:
    def test_every_router_route_is_served(self):
        served = {(m, r.path) for r in server.app.routes for m in getattr(r, "methods", ())}
        missing = []
        for name in dir(server):
            router = getattr(server, name)
            if isinstance(router, server.APIRouter) and router is not server.api_router:
                for r in router.routes:
                    for m in r.methods:
                        if (m, "/api" + r.path) not in served:
                            missing.append(f"{m} {r.path} ({name})")
        assert missing == [], f"declared after their router was mounted: {missing}"

    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/admin/disputes"),
            ("POST", "/admin/disputes/{collab_id}/resolve"),
            ("POST", "/brand/verification/confirm"),
            ("POST", "/creator/verification/confirm"),
        ],
    )
    def test_the_four_that_were_missing(self, method, path):
        assert route(method, path)

    def test_routers_are_mounted_once_at_the_end(self):
        src = Path(server.__file__).read_text()
        mounts = [m.start() for m in re.finditer(r"^api_router\.include_router\(", src, re.M)]
        last_route = max(
            m.start() for m in re.finditer(r"^@\w+_router\.(get|post|put|patch|delete)\(", src, re.M)
        )
        assert mounts and min(mounts) > last_route


# ---------------------------------------------------------------------------
# 1 · The scoped console
# ---------------------------------------------------------------------------


class TestPerformance:
    def test_its_read_is_admin_only_and_the_section_says_so(self):
        assert not allows(route("GET", "/admin/intelligence"), "weare_team")
        src = no_comments(ADMIN / "console" / "Sidebar.jsx")
        chunk = src.split('key: "performance"', 1)[1].split("key: ", 1)[0]
        assert "adminOnly: true" in chunk

    def test_a_failure_is_said_rather_than_blank(self):
        src = no_comments(ADMIN / "Health.jsx")
        block = src.split("export function IntelligencePanel", 1)[1].split("if (!d)", 1)[0]
        assert "return null" not in block
        assert "INTEL_IDS.error" in block


class TestExports:
    def _tiles(self):
        src = no_comments(ADMIN / "Health.jsx")
        block = src.split("export const EXPORTS = [", 1)[1].split("];", 1)[0]
        tiles = {}
        for line in block.splitlines():
            m = re.search(r'key: "(\w+)"', line)
            if m:
                tiles[m.group(1)] = "adminOnly: true" in line
        return tiles

    def test_every_kind_has_a_tile(self):
        """Seven kinds, seven tiles — the survey had a server kind and no tile."""
        assert set(self._tiles()) == set(server.EXPORT_KINDS)

    def test_the_admin_only_tiles_are_the_admin_only_exports(self):
        assert {k for k, a in self._tiles().items() if a} == set(server.ADMIN_ONLY_EXPORTS)

    def test_the_tiles_are_gated_by_role(self):
        src = no_comments(ADMIN / "Health.jsx")
        assert "exportsFor(allAccess).map" in src
        assert "EXPORTS.map" not in src
        routes = no_comments(ADMIN / "routes.jsx")
        assert "<ExportsPanel allAccess={allAccess} />" in routes

    def test_downloads_go_through_download_csv(self):
        """A bare anchor saved a 403 to disk as a `.csv`."""
        src = no_comments(ADMIN / "Health.jsx")
        panel = src.split("export function ExportsPanel", 1)[1]
        assert "downloadCsv(" in panel
        assert "<a" not in panel and "API_BASE" not in src

    def test_a_team_member_is_refused_the_admin_only_kinds(self, world):
        for kind in server.ADMIN_ONLY_EXPORTS:
            with pytest.raises(HTTPException) as e:
                run(server.admin_export(kind=kind, user=world.team))
            assert e.value.status_code in (403, 404)


class TestTheCreatorPage:
    FORBIDDEN = server._TEAM_HIDDEN_CREATOR_FIELDS

    def test_a_team_member_may_call_it(self):
        assert allows(route("GET", "/admin/creators/{user_id}"), "weare_team")
        assert not allows(route("GET", "/admin/creators/{user_id}"), "brand_manager")

    def test_a_creator_on_their_brand_opens_scoped(self, world):
        run(
            world.db.creator_profiles.update_one(
                {"user_id": world.creator_mine},
                {"$set": {
                    "email": "aditi@planted.test", "full_address": "Flat 4, planted",
                    "location_lat": 12.97, "payout_upi": "9900000001@okaxis",
                    "pan": "ABCDE1234F",
                }},
            )
        )
        data = run(server.get_creator_detail(str(world.creator_mine), user=world.team))
        assert data["scope"] == "team"
        creator = data["creator"]
        for key in self.FORBIDDEN:
            assert key not in creator, key
        blob = repr(data)
        for planted in ("aditi@planted.test", "Flat 4, planted", "+919900000001",
                        "okaxis", "ABCDE1234F"):
            assert planted not in blob

    def test_the_work_shown_is_only_on_their_brands(self, world):
        # The same creator also applied to the other brand's brief.
        run(world.db.collaborations.insert_one({
            "campaign_id": world.camp_theirs, "creator_id": world.creator_mine,
            "state": "applied", "created_at": datetime.now(timezone.utc),
        }))
        team = run(server.get_creator_detail(str(world.creator_mine), user=world.team))
        rows = [r for g in team["collaborations"].values() for r in g]
        assert {r["campaign_id"] for r in rows} == {str(world.camp_mine)}
        admin = run(server.get_creator_detail(str(world.creator_mine), user=world.admin))
        rows = [r for g in admin["collaborations"].values() for r in g]
        assert {r["campaign_id"] for r in rows} == {str(world.camp_mine), str(world.camp_theirs)}

    def test_a_creator_outside_the_scope_is_a_404(self, world):
        with pytest.raises(HTTPException) as e:
            run(server.get_creator_detail(str(world.creator_theirs), user=world.team))
        assert e.value.status_code == 404

    def test_an_admin_still_reads_everything(self, world):
        data = run(server.get_creator_detail(str(world.creator_mine), user=world.admin))
        assert data["scope"] == "all"
        assert data["creator"]["phone"] == "+919900000001"

    def test_the_page_leaves_out_admin_decisions_for_the_team(self):
        src = no_comments(ADMIN / "CreatorDetailPage.jsx")
        assert 'data?.scope === "team"' in src
        assert "!team && (" in src  # the aside, the contact block, the audit
        assert "Only admins can open this creator's profile." in src


class TestTheManagerPicker:
    def test_the_list_is_readable_by_the_console(self):
        fn = route("GET", "/admin/managers")
        assert allows(fn, "weare_team") and allows(fn, "admin")
        assert not allows(fn, "brand_manager") and not allows(fn, "campaign_manager")
        assert not allows(route("POST", "/admin/managers"), "weare_team")

    def test_a_team_member_gets_names_and_load_not_contact(self, world):
        run(world.db.users.update_one(
            {"_id": world.manager_id},
            {"$set": {"email": "mgr@weare.test", "phone": "+919900000099"}},
        ))
        team = run(server.list_managers(user=world.team))
        assert team and set(team[0]) == {"id", "name", "active_campaigns"}
        admin = run(server.list_managers(user=world.admin))
        assert admin[0]["email"] == "mgr@weare.test"

    def test_the_picker_reads_the_id_the_list_sends_and_says_a_failure(self):
        src = no_comments(ADMIN / "CampaignDetailPage.jsx")
        assert "value={m.id}" in src and "m.user_id" not in src
        assert "setManagersError(" in src
        assert "/* the picker stays empty and says so */" not in (ADMIN / "CampaignDetailPage.jsx").read_text()


# ---------------------------------------------------------------------------
# 2 · Settings with an endpoint and now a form
# ---------------------------------------------------------------------------


SETTINGS = [
    # (path, field the form posts, a value inside the bounds)
    ("/admin/settings/trusted-brands", "approvals", 5),
    ("/admin/settings/large-campaign", "creators", 20),
    ("/admin/settings/leaderboard", "minimum", 4),
    ("/admin/settings/leaderboard", "size", 10),
]


class TestTheThreeSettings:
    @pytest.mark.parametrize("path,field,value", SETTINGS)
    def test_round_trip(self, world, path, field, value):
        put, get = route("PUT", path), route("GET", path)
        model = [p.annotation for p in inspect.signature(put).parameters.values()
                 if p.name == "payload"][0]
        run(put(payload=model(**{field: value}), user=world.admin))
        for cache in ("_LEADERBOARD_CACHE", "_SETTINGS_CACHE"):
            getattr(server, cache, {}).clear() if isinstance(getattr(server, cache, None), dict) else None
        read = run(get(user=world.admin))
        assert read[field] == value

    @pytest.mark.parametrize("path", sorted({p for p, _, _ in SETTINGS}))
    def test_admin_only(self, path):
        for method in ("GET", "PUT"):
            assert not allows(route(method, path), "weare_team")
            assert allows(route(method, path), "admin")

    @pytest.mark.parametrize("path,field,value", SETTINGS)
    def test_the_form_posts_the_field_the_server_reads(self, path, field, value):
        src = no_comments(ADMIN / "PlatformSettings.jsx")
        m = re.search(
            r'endpoint="' + re.escape(path) + r'"\s+field="(\w+)"', src
        )
        assert m, f"no form for {path}"
        fields = re.findall(r'endpoint="' + re.escape(path) + r'"\s+field="(\w+)"', src)
        assert field in fields

    def test_the_bounds_are_read_off_both_shapes(self):
        """The leaderboard and the brand wall send `defaults` and `maximum`."""
        src = no_comments(ADMIN / "PlatformSettings.jsx")
        assert "data?.maximum" in src and "data.defaults?.[field]" in src


# ---------------------------------------------------------------------------
# 3 · Smaller admin dead ends
# ---------------------------------------------------------------------------


class TestDeliveryCost:
    def test_the_admin_campaign_payload_carries_it(self, world):
        run(world.db.campaigns.update_one({"_id": world.camp_mine}, {"$set": {"delivery_cost": 12000}}))
        data = run(server.get_admin_campaign_detail(str(world.camp_mine), user=world.admin))
        assert data["campaign"]["delivery_cost"] == 12000

    def test_the_brand_never_sees_it(self, world):
        doc = run(world.db.campaigns.find_one({"_id": world.camp_mine}))
        doc["delivery_cost"] = 12000
        out = server._serialize_brand_campaign(doc, 0, 0, 0, None, payout_default=7)
        assert "delivery_cost" not in out

    def test_the_campaign_page_has_the_control(self):
        src = no_comments(ADMIN / "CommercialTerms.jsx")
        assert "/delivery-cost`" in src and "api.put(" in src
        assert "<DeliveryCostPanel" in src
        analytics = no_comments(ADMIN / "Analytics.jsx")
        assert "Commercial terms" in analytics


class TestSurvey:
    def test_the_payload_carries_the_wording(self, world):
        data = run(server.admin_creator_survey(user=world.admin))
        fields = {q["field"] for q in data["questions"]}
        assert {f for f, _ in server.SURVEY_CLOSED_FIELDS} <= fields
        city = next(q for q in data["questions"] if q["field"] == "collabs_3m")
        assert city["options"]["more_than_10"] == "More than 10"

    def test_admin_only(self):
        assert not allows(route("GET", "/admin/survey/creator"), "weare_team")

    def test_the_screen_reads_it_and_offers_the_export(self):
        src = no_comments(ADMIN / "SurveyResults.jsx")
        assert 'api.get("/admin/survey/creator")' in src
        assert 'downloadCsv("/admin/exports/survey"' in src
        assert "open_text_warning" in src


class TestCaseStudies:
    def test_reorder_and_delete_are_wired(self):
        src = no_comments(ADMIN / "CaseStudies.jsx")
        assert 'api.post("/admin/case-studies/order"' in src
        assert "api.delete(`/admin/case-studies/${study.id}`)" in src

    def test_delete_is_confirmed_and_drafts_only(self):
        src = no_comments(ADMIN / "CaseStudies.jsx")
        assert "<AlertDialog open={confirmDelete}" in src
        assert "{!published && (" in src

    def test_the_server_still_refuses_a_published_one(self, world):
        oid = ObjectId()
        run(world.db.case_studies.insert_one({"_id": oid, "status": "published", "slug": "x"}))
        with pytest.raises(HTTPException) as e:
            run(server.delete_case_study(str(oid), user=world.admin))
        assert e.value.status_code == 409

    def test_reorder_writes_the_order(self, world):
        a, b = ObjectId(), ObjectId()
        now = datetime.now(timezone.utc)
        run(world.db.case_studies.insert_many([
            {"_id": a, "status": "draft", "title": "A", "display_order": 0, "created_at": now},
            {"_id": b, "status": "draft", "title": "B", "display_order": 1, "created_at": now},
        ]))
        out = run(server.reorder_case_studies(
            server.CaseStudyOrderPayload(ids=[str(b), str(a)]), user=world.admin
        ))
        assert [r["id"] for r in out["case_studies"]] == [str(b), str(a)]


class TestDuplicate:
    def test_staff_may_duplicate_and_the_page_offers_it(self):
        fn = route("POST", "/admin/campaigns/{campaign_id}/duplicate")
        assert allows(fn, "weare_team") and allows(fn, "admin")
        src = no_comments(ADMIN / "CampaignDetailPage.jsx")
        assert "/duplicate`" in src and 'DIDS.action("duplicate")' in src

    def test_a_team_member_cannot_copy_another_brands_brief(self, world):
        with pytest.raises(HTTPException) as e:
            run(server.admin_duplicate_campaign(str(world.camp_theirs), None, user=world.team))
        assert e.value.status_code == 404

    def test_the_copy_is_a_draft(self, world):
        out = run(server.admin_duplicate_campaign(str(world.camp_mine), None, user=world.team))
        assert out["status"] == "draft"


class TestUnfinishedProfiles:
    def test_the_screen_reads_the_list_and_runs_the_nudge(self):
        src = no_comments(ADMIN / "UnfinishedProfiles.jsx")
        assert 'api.get("/admin/creators/incomplete")' in src
        assert 'api.post("/admin/jobs/creator-nudges")' in src

    def test_admin_only(self):
        assert not allows(route("GET", "/admin/creators/incomplete"), "weare_team")
        assert not allows(route("POST", "/admin/jobs/creator-nudges"), "weare_team")


# ---------------------------------------------------------------------------
# 4 · Surfaced, not decided
# ---------------------------------------------------------------------------


class TestDisputesForTheTeam:
    def test_who_may_resolve_did_not_change(self):
        assert not allows(route("POST", "/admin/disputes/{collab_id}/resolve"), "weare_team")
        assert allows(route("GET", "/admin/disputes"), "weare_team")

    def test_the_section_says_so_to_the_team(self):
        src = no_comments(ADMIN / "DisputeQueue.jsx")
        assert "{!allAccess && (" in src and "an admin decides them" in src
        assert "<DisputeQueue allAccess={allAccess} />" in no_comments(ADMIN / "routes.jsx")
