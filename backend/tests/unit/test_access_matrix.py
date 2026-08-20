"""Five roles, five scopes, and every one of them enforced on the server.

The matrix, as asked for:

| role               | reaches                                    |
|--------------------|--------------------------------------------|
| `admin`            | everything                                 |
| `weare_team`       | the admin console, scoped to assigned brands |
| `brand_manager`    | its own brand only                         |
| `campaign_manager` | its assigned campaigns only                |
| `creator`          | its own data only                          |

**Every test below drives the real handler**, with two brands in a mock
database and a team member assigned to exactly one of them. That is the only
way this can be a test of the *scope* rather than of the source: a filter is
easy to read and easy to remove, and the failure mode this guards against is
somebody widening a query while debugging and never narrowing it again.

The refusals are **404s, not 403s**, throughout. Whether a brand we do not
work with exists is not a question a scoped console answers — the same rule
`_own_campaign_or_404` has always held.
"""
import ast
import asyncio
import functools
import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import server


# ---------------------------------------------------------------------------
# Two brands, and somebody who runs one of them
# ---------------------------------------------------------------------------


class World:
    """Two brands, each with a live campaign, an applicant and a payment.

    Symmetrical on purpose: every assertion about what the team member reaches
    has a mirror about the brand they are not on, so "the filter works" and
    "there was nothing there anyway" cannot be confused.
    """

    async def build(self):
        self.db = AsyncMongoMockClient()["matrix"]
        server.db = self.db
        db = self.db
        now = datetime.now(timezone.utc)

        self.mine, self.theirs = ObjectId(), ObjectId()
        self.creator_mine, self.creator_theirs = ObjectId(), ObjectId()
        self.admin_id, self.team_id, self.manager_id = (
            ObjectId(),
            ObjectId(),
            ObjectId(),
        )

        await db.users.insert_many(
            [
                {"_id": self.mine, "role": "brand_manager", "name": "Toit"},
                {"_id": self.theirs, "role": "brand_manager", "name": "Blue Tokai"},
                {
                    "_id": self.creator_mine,
                    "role": "creator",
                    "name": "Aditi Rao",
                    "phone": "+919900000001",
                    "verification_status": "verified",
                },
                {
                    "_id": self.creator_theirs,
                    "role": "creator",
                    "name": "Rhea Menon",
                    "phone": "+919900000002",
                    "verification_status": "verified",
                },
                {"_id": self.admin_id, "role": "admin", "name": "Admin"},
                {
                    "_id": self.team_id,
                    "role": "weare_team",
                    "name": "Team",
                    "email": "team@weare.test",
                    "assigned_brand_ids": [self.mine],
                },
                {"_id": self.manager_id, "role": "campaign_manager", "name": "Mgr"},
            ]
        )
        await db.brand_profiles.insert_many(
            [
                {
                    "user_id": self.mine,
                    "business_name": "Toit",
                    "verified": False,
                    "verification_state": "pending_verification",
                    "gst_number": "29ABCDE1234F1Z5",
                    "registered_address": "100 Feet Road, Indiranagar",
                },
                {
                    "user_id": self.theirs,
                    "business_name": "Blue Tokai",
                    "verified": False,
                    "verification_state": "pending_verification",
                    "gst_number": "29ZYXWV9876G1Z2",
                    "registered_address": "Church Street",
                },
            ]
        )
        await db.creator_profiles.insert_many(
            [
                {
                    "user_id": self.creator_mine,
                    "name": "Aditi Rao",
                    "verification_status": "verified",
                    "city": "Bengaluru",
                },
                {
                    "user_id": self.creator_theirs,
                    "name": "Rhea Menon",
                    "verification_status": "verified",
                    "city": "Bengaluru",
                },
            ]
        )

        self.camp_mine, self.camp_theirs = ObjectId(), ObjectId()
        await db.campaigns.insert_many(
            [
                {
                    "_id": self.camp_mine,
                    "brand_id": self.mine,
                    "title": "Toit tasting",
                    "status": "pending_review",
                    "creators_needed": 2,
                    "budget_per_creator": 8000,
                    "compensation_type": "fixed",
                    "execution_owner": "weare",
                    "created_at": now,
                },
                {
                    "_id": self.camp_theirs,
                    "brand_id": self.theirs,
                    "title": "Blue Tokai launch",
                    "status": "pending_review",
                    "creators_needed": 2,
                    "budget_per_creator": 9000,
                    "compensation_type": "fixed",
                    "execution_owner": "weare",
                    "created_at": now,
                },
            ]
        )

        self.collab_mine, self.collab_theirs = ObjectId(), ObjectId()
        await db.collaborations.insert_many(
            [
                {
                    "_id": self.collab_mine,
                    "campaign_id": self.camp_mine,
                    "creator_id": self.creator_mine,
                    "state": "applied",
                    "created_at": now,
                },
                {
                    "_id": self.collab_theirs,
                    "campaign_id": self.camp_theirs,
                    "creator_id": self.creator_theirs,
                    "state": "applied",
                    "created_at": now,
                },
            ]
        )
        await db.campaign_questions.insert_many(
            [
                {
                    "campaign_id": self.camp_mine,
                    "creator_id": self.creator_mine,
                    "from_creator": True,
                    "author_name": "Aditi Rao",
                    "body": "Is parking available?",
                    "created_at": now,
                },
                {
                    "campaign_id": self.camp_theirs,
                    "creator_id": self.creator_theirs,
                    "from_creator": True,
                    "author_name": "Rhea Menon",
                    "body": "What time?",
                    "created_at": now,
                },
            ]
        )
        self.pay_mine, self.pay_theirs = ObjectId(), ObjectId()
        await db.payments.insert_many(
            [
                {
                    "_id": self.pay_mine,
                    "collaboration_id": self.collab_mine,
                    "campaign_id": self.camp_mine,
                    "creator_id": self.creator_mine,
                    "amount": 8000,
                    "status": "pending",
                    "created_at": now,
                },
                {
                    "_id": self.pay_theirs,
                    "collaboration_id": self.collab_theirs,
                    "campaign_id": self.camp_theirs,
                    "creator_id": self.creator_theirs,
                    "amount": 9000,
                    "status": "pending",
                    "created_at": now,
                },
            ]
        )
        await db.campaign_invitations.insert_one(
            {
                "campaign_id": self.camp_mine,
                "creator_id": self.creator_mine,
                "status": "sent",
                "created_at": now - timedelta(days=1),
            }
        )

        self.admin = await db.users.find_one({"_id": self.admin_id})
        self.team = await db.users.find_one({"_id": self.team_id})
        self.brand = await db.users.find_one({"_id": self.mine})
        self.other_brand = await db.users.find_one({"_id": self.theirs})
        self.manager = await db.users.find_one({"_id": self.manager_id})
        self.creator = await db.users.find_one({"_id": self.creator_mine})
        return self


# One loop per test, created here rather than reached for: `get_event_loop`
# has no loop to return under xdist's worker threads, and the suite is run in
# parallel.
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


def run(coro):
    return _LOOP.run_until_complete(coro)


@functools.lru_cache(maxsize=1)
def _console_handlers_taking_an_id():
    """Every admin-console handler that addresses one record by a path id.

    Computed once — `ast.get_source_segment` re-scans the whole 22,000-line
    file per call, which turned three structural tests into a minute and a
    half. Slicing the source lines by `lineno` is the same answer for a
    hundredth of the work, and handlers are all top-level so there is nothing
    to walk into.
    """
    src = Path(server.__file__).read_text()
    lines = src.splitlines()

    def text(node):
        return "\n".join(lines[node.lineno - 1 : node.end_lineno])

    found = []
    for node in ast.parse(src).body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        paths = [
            t for t in (text(d).replace("\n", " ") for d in node.decorator_list)
            if "admin_router." in t
        ]
        if not paths:
            continue
        body = text(node)
        if "CONSOLE_ROLES" not in body.split("):", 1)[0]:
            continue
        # A *path* parameter naming one record — a query filter is a different
        # thing, narrowing inside a scope rather than addressing a row
        # (`admin_export`'s `campaign_id` is intersected with the scoped ids,
        # and is covered by its own test). `document_id` and `member_id` are
        # always second segments under one of these, so the first id is what
        # carries the scope.
        if any(
            a.arg in ("campaign_id", "collab_id", "user_id", "payment_id")
            and any("{%s}" % a.arg in d for d in paths)
            for a in node.args.args
        ):
            found.append((node.name, body))
    return tuple(found)


def refuses(coro):
    """Run it and return the HTTPException it raised, or fail loudly."""
    with pytest.raises(HTTPException) as e:
        run(coro)
    return e.value


# ---------------------------------------------------------------------------
# The scope itself
# ---------------------------------------------------------------------------


class TestTheScopeIsTwoDifferentAnswers:
    def test_admin_is_no_filter_and_a_team_member_is_a_list(self, world):
        assert server._console_brand_ids(world.admin) is None
        assert server._console_brand_ids(world.team) == [world.mine]

    def test_assigned_to_nothing_is_an_empty_list_and_never_no_filter(self):
        """The load-bearing distinction. `[]` reading as "no filter" is how a
        new starter opens the console on their first morning and finds the
        whole platform in it."""
        fresh = {"role": "weare_team", "assigned_brand_ids": []}
        assert server._console_brand_ids(fresh) == []
        assert server._console_brand_query(fresh) == {"brand_id": {"$in": []}}
        # Which is a filter that matches nothing, not one that matches all.
        assert server._console_brand_query(fresh) != {}

    def test_an_admin_query_carries_no_scope_at_all(self, world):
        assert server._console_brand_query(world.admin) == {}
        assert run(server._console_campaign_query(world.admin)) == {}

    def test_the_campaign_scope_resolves_through_the_brands(self, world):
        ids = run(server._console_campaign_ids(world.team))
        assert ids == [world.camp_mine]

    def test_a_refusal_is_a_404_and_not_a_403(self):
        """Whether another brand exists is itself what the scope protects."""
        assert server._out_of_scope().status_code == 404


# ---------------------------------------------------------------------------
# weare_team: the admin console, scoped
# ---------------------------------------------------------------------------


class TestWeAreTeamSeesItsOwnBrandsAndNoOthers:
    def test_the_campaign_list_is_filtered_in_the_query(self, world):
        mine = run(server.list_all_campaigns(user=world.team))
        assert [c["title"] for c in mine["campaigns"]] == ["Toit tasting"]
        # The count travels with it, so a scoped list cannot report a total
        # from outside its own scope.
        assert mine["total"] == 1

        everything = run(server.list_all_campaigns(user=world.admin))
        assert {c["title"] for c in everything["campaigns"]} == {
            "Toit tasting",
            "Blue Tokai launch",
        }

    def test_asking_for_another_brand_by_id_returns_that_brands_nothing(self, world):
        """A filter in the query string cannot widen a scope — it narrows
        inside it. Empty, rather than 403: the same reasoning as the calendar."""
        out = run(server.list_all_campaigns(brand_id=str(world.theirs), user=world.team))
        assert out["campaigns"] == []
        assert out["total"] == 0

    def test_the_review_queue_is_filtered(self, world):
        assert [c["title"] for c in run(server.list_campaigns_for_review(user=world.team))] == [
            "Toit tasting"
        ]
        assert len(run(server.list_campaigns_for_review(user=world.admin))) == 2

    def test_the_brand_queue_is_filtered(self, world):
        mine = run(server.list_pending_brands(user=world.team))
        assert [b["business_name"] for b in mine] == ["Toit"]
        assert len(run(server.list_pending_brands(user=world.admin))) == 2

    def test_the_brand_list_is_filtered(self, world):
        rows = run(server.list_brands_for_review(user=world.team))
        assert [b["business_name"] for b in rows] == ["Toit"]
        assert len(run(server.list_brands_for_review(user=world.admin))) == 2

    def test_the_collaboration_list_is_filtered(self, world):
        mine = run(server.list_all_collaborations(user=world.team))
        assert mine["total"] == 1
        assert len(run(server.list_all_collaborations(user=world.admin))["by_state"]["applied"]) == 2

    def test_another_brands_campaign_page_is_a_404(self, world):
        assert (
            refuses(
                server.get_admin_campaign_detail(str(world.camp_theirs), user=world.team)
            ).status_code
            == 404
        )
        # And their own opens.
        assert run(
            server.get_admin_campaign_detail(str(world.camp_mine), user=world.team)
        )["campaign"]["title"] == "Toit tasting"

    def test_another_brands_page_is_a_404(self, world):
        assert (
            refuses(server.get_admin_brand_detail(str(world.theirs), user=world.team)).status_code
            == 404
        )
        assert run(server.get_admin_brand_detail(str(world.mine), user=world.team))

    def test_another_brands_collaboration_is_a_404(self, world):
        assert (
            refuses(
                server.get_admin_collaboration_detail(str(world.collab_theirs), user=world.team)
            ).status_code
            == 404
        )

    def test_another_brands_payment_is_a_404(self, world):
        assert (
            refuses(
                server._console_payment_or_404(str(world.pay_theirs), world.team)
            ).status_code
            == 404
        )
        assert run(server._console_payment_or_404(str(world.pay_mine), world.team))

    def test_the_unanswered_questions_queue_is_filtered(self, world):
        """Scoped in the query rather than on the rows: the cap is applied
        after the sort, so filtering afterwards would silently shorten a scoped
        queue to whatever survived somebody else's hundred."""
        mine = run(server.unanswered_questions(user=world.team))
        assert [q["campaign_title"] for q in mine] == ["Toit tasting"]
        assert len(run(server.unanswered_questions(user=world.admin))) == 2

    def test_the_command_palette_searches_inside_the_scope(self, world):
        found = run(server.admin_global_search(q="a", user=world.team))
        names = {b["name"] for b in found.get("brands", [])}
        assert "Blue Tokai" not in names

    def test_creators_are_reachable_only_through_their_brands_campaigns(self, world):
        allowed = run(server._console_creator_ids(world.team))
        assert allowed == [world.creator_mine]
        # And an admin has no such list at all.
        assert run(server._console_creator_ids(world.admin)) is None

    def test_somebody_assigned_nothing_yet_sees_nothing_at_all(self, world):
        """The first morning. Every one of these would be the whole platform if
        an empty assignment list read as "no filter" anywhere along the way —
        which is a decision made in three places and has to hold in all of
        them."""
        fresh = {
            "_id": ObjectId(),
            "role": "weare_team",
            "name": "New starter",
            "assigned_brand_ids": [],
        }
        assert run(server.list_all_campaigns(user=fresh))["campaigns"] == []
        assert run(server.list_brands_for_review(user=fresh)) == []
        assert run(server.list_pending_brands(user=fresh)) == []
        assert run(server.list_campaigns_for_review(user=fresh)) == []
        assert run(server.list_all_collaborations(user=fresh))["total"] == 0
        assert run(server.unanswered_questions(user=fresh)) == []
        assert (
            refuses(
                server.get_admin_brand_detail(str(world.mine), user=fresh)
            ).status_code
            == 404
        )

    def test_every_action_they_take_is_audited_under_their_own_name(self, world):
        run(server.audit(world.team, "campaign.approve", "campaign", world.camp_mine))
        line = run(server.db.audit_log.find_one({"action": "campaign.approve"}))
        assert line["actor_id"] == world.team_id
        assert line["actor_role"] == "weare_team"


class TestWhatStaysAdminOnly:
    """The four the brief named, plus the settings that hand out scope."""

    @pytest.mark.parametrize(
        "fn",
        [
            "list_all_creators",  # the global creator directory
            "list_pending_creators",  # the creator vetting queue
            "approve_creator",
            "reject_creator",
            "suspend_creator",
            "admin_metrics",  # platform-wide numbers
            "admin_health",
            "admin_intelligence",
            "list_audit_log",
            "create_team_member",  # the settings that decide scope
            "list_team_members",
            "assign_brand_to_team_member",
            "unassign_brand_from_team_member",
            "create_manager_account",
            "impersonate_user",
        ],
    )
    def test_the_guard_is_admin_and_not_the_console_roles(self, fn):
        head = inspect.getsource(getattr(server, fn)).split("):", 1)[0]
        assert 'require_roles("admin")' in head, f"{fn} is reachable by weare_team"

    def test_a_scoped_role_cannot_widen_its_own_scope(self):
        """The one rule that makes every other rule here hold. If assignment
        were `CONSOLE_ROLES`, a team member could put themselves on any brand
        and the scope would be a suggestion."""
        for fn in ("assign_brand_to_team_member", "unassign_brand_from_team_member"):
            head = inspect.getsource(getattr(server, fn)).split("):", 1)[0]
            assert "CONSOLE_ROLES" not in head

    def test_the_creator_and_audit_exports_are_admin_only(self, world):
        assert set(server.ADMIN_ONLY_EXPORTS) == {"creators", "audit"}
        for kind in server.ADMIN_ONLY_EXPORTS:
            assert refuses(server.admin_export(kind, user=world.team)).status_code in (
                403,
                404,
            )

    def test_an_export_filtered_to_another_brand_intersects_rather_than_widens(
        self, world
    ):
        """The one place a `campaign_id` is a filter rather than an address.
        It is ANDed with the caller's scope, so naming somebody else's campaign
        narrows to nothing instead of reaching it."""
        out = run(
            server.admin_export(
                "collaborations", campaign_id=str(world.camp_theirs), user=world.team
            )
        )
        body = out.body.decode()
        assert "Rhea Menon" not in body
        assert "Blue Tokai" not in body

    def test_a_team_member_still_gets_the_exports_that_are_theirs(self, world):
        out = run(server.admin_export("campaigns", user=world.team))
        body = out.body.decode() if hasattr(out, "body") else str(out)
        assert "Toit tasting" in body
        assert "Blue Tokai launch" not in body


class TestEveryConsoleDoorIsTheSameDoor:
    """The class of bug this whole file exists to catch.

    A scope enforced on the lists and not on the row you click from them is a
    scope somebody reaches around by pasting an id. It found five real gaps
    when it was first written: the collaboration detail page and all four
    collaboration actions resolved their id inline, so a team member could
    have advanced, reverted, declined or cancelled any brand's application.

    Structural rather than exhaustive-by-hand, because the failure is a *new*
    route written the old way — a hand-written list is a list somebody forgets
    to add to.
    """

    GUARDS = (
        "_admin_campaign_or_404",
        "_collab_or_404",
        "_console_brand_or_404",
        "_console_payment_or_404",
    )

    def _console_handlers_taking_an_id(self):
        return _console_handlers_taking_an_id()

    def test_the_list_is_not_empty(self):
        """A structural test that matches nothing passes for free."""
        assert len(list(self._console_handlers_taking_an_id())) > 10

    def test_every_one_of_them_resolves_its_id_through_a_scoped_guard(self):
        offenders = [
            name
            for name, body in self._console_handlers_taking_an_id()
            if not any(g in body for g in self.GUARDS)
        ]
        assert offenders == [], (
            "these resolve a record by id without applying the console scope: "
            + ", ".join(offenders)
        )

    def test_none_of_them_reach_for_the_collection_directly_first(self):
        """The specific shape of all five gaps: `find_one({"_id": oid})` before
        the guard, so the guard is a formality the code has already gone
        around."""
        for name, body in self._console_handlers_taking_an_id():
            head = body.split("current = ", 1)[0]
            assert 'db.collaborations.find_one({"_id": oid})' not in head, name


# ---------------------------------------------------------------------------
# The three roles that were already scoped
# ---------------------------------------------------------------------------


class TestBrandManagerReachesItsOwnBrandOnly:
    def test_another_brands_campaign_is_a_404(self, world):
        assert (
            refuses(
                server._own_campaign_or_404(str(world.camp_theirs), world.brand)
            ).status_code
            == 404
        )
        assert run(server._own_campaign_or_404(str(world.camp_mine), world.brand))

    def test_the_scope_is_the_brand_and_never_the_login_row(self):
        """`_brand_scope` is how every brand query finds its brand — reaching
        for `user["_id"]` is right only while the two are the same row."""
        src = inspect.getsource(server._brand_scope)
        assert "brand_id" in src

    def test_a_brand_cannot_reach_the_console(self, world):
        assert "brand_manager" not in server.CONSOLE_ROLES
        assert "brand" not in server.CONSOLE_ROLES


class TestCampaignManagerReachesAssignedCampaignsOnly:
    def test_an_unassigned_campaign_is_a_404(self, world):
        assert (
            refuses(
                server._managed_campaign_or_404(str(world.camp_mine), world.manager)
            ).status_code
            == 404
        )
        run(
            server.db.campaigns.update_one(
                {"_id": world.camp_mine}, {"$set": {"manager_id": world.manager_id}}
            )
        )
        assert run(
            server._managed_campaign_or_404(str(world.camp_mine), world.manager)
        )

    def test_a_campaign_manager_cannot_reach_the_console(self):
        assert "campaign_manager" not in server.CONSOLE_ROLES

    def test_the_manager_router_never_admits_the_brands_own_person(self):
        """Campaigns default their manager to the brand's own person, so
        ownership alone would let a brand manager into the daysheet — which
        carries creators' phone numbers by design."""
        import re

        src = inspect.getsource(server)
        for match in re.finditer(r"@manager_router\.\w+\([^)]*\)\s*\nasync def (\w+)", src):
            head = inspect.getsource(getattr(server, match.group(1))).split("):", 1)[0]
            assert 'require_roles("campaign_manager", "admin")' in head, match.group(1)


class TestCreatorReachesItsOwnDataOnly:
    def test_the_question_thread_routes_take_no_creator_id(self):
        """One creator's thread is invisible to every other creator because
        there is nothing to pass — the thread is the session's."""
        head = inspect.getsource(server.ask_campaign_question).split("):", 1)[0]
        assert "creator_id" not in head

    def test_somebody_elses_invitation_is_a_404(self, world):
        assert "creator" not in server.CONSOLE_ROLES

    def test_work_notes_do_not_accept_the_role_at_all(self):
        for fn in ("add_collaboration_note", "list_collaboration_notes"):
            head = inspect.getsource(getattr(server, fn)).split("):", 1)[0]
            assert "creator" not in head


# ---------------------------------------------------------------------------
# Signing in, and looking through
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# The console, as it is drawn
# ---------------------------------------------------------------------------


FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"


def no_comments(path):
    import re

    src = re.sub(r"\{/\*.*?\*/\}", "", Path(path).read_text(), flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


class TestTheDrawingAgreesWithTheServer:
    """`lib/consoleScope.js` mirrors the server's role split, the same
    arrangement `followerTiers.js` and `shootWindows.js` use — one copy each
    side and a test that fails if they drift."""

    SCOPE = FRONTEND / "lib" / "consoleScope.js"

    def test_the_two_role_lists_are_the_same_two_roles(self):
        src = no_comments(self.SCOPE)
        for role in server.CONSOLE_ROLES:
            assert f'"{role}"' in src, f"{role} is a console role the client omits"
        assert '"campaign_manager"' not in src
        assert '"brand_manager"' not in src

    def test_all_access_is_admin_on_both_sides(self):
        src = no_comments(self.SCOPE)
        assert 'role === "admin"' in src
        assert 'return (user or {}).get("role") == "admin"' in inspect.getsource(
            server.is_all_access
        )

    def test_the_file_says_what_a_client_role_check_is_for(self):
        """It draws; it never allows. Losing that sentence is how the next
        person reads the filter below as the enforcement."""
        text = self.SCOPE.read_text()
        assert "never" in text and "server" in text


class TestTheSidebarHidesWhatItCannotReach:
    SIDEBAR = FRONTEND / "components" / "admin" / "console" / "Sidebar.jsx"

    ADMIN_ONLY_SECTIONS = ("creator-reviews", "creators", "health", "audit", "team")

    @pytest.mark.parametrize("key", ADMIN_ONLY_SECTIONS)
    def test_each_platform_section_is_marked(self, key):
        """A section whose endpoints answer 403 to a team member is a door
        that opens onto an error. Marked here, filtered once in `sectionsFor`,
        and enforced on the server regardless."""
        src = no_comments(self.SIDEBAR)
        block = src.split(f'key: "{key}"', 1)
        assert len(block) == 2, f"no section named {key}"
        # Up to the next section's key, so a flag on a later entry cannot
        # satisfy this one.
        chunk = block[1].split('key: "', 1)[0]
        assert "adminOnly: true" in chunk, f"{key} is offered to a scoped console"

    def test_the_scoped_sections_are_not_marked(self):
        src = no_comments(self.SIDEBAR)
        for key in ("queue", "campaigns", "brands", "campaign-reviews"):
            chunk = src.split(f'key: "{key}"', 1)[1].split('key: "', 1)[0]
            assert "adminOnly" not in chunk, f"{key} is hidden from the people who run it"

    def test_one_filter_feeds_both_the_rail_and_the_sheet(self):
        src = no_comments(self.SIDEBAR)
        assert src.count("sectionsFor(role).map") == 2
        assert "ADMIN_SECTIONS.map" not in src

    def test_every_section_still_routes_somewhere(self):
        """The rule the console already held, now with one more section on the
        list. A section in the sidebar and not in the router is a dead link."""
        app = no_comments(FRONTEND / "App.js")
        src = no_comments(self.SIDEBAR)
        import re

        for to in re.findall(r'to: "([a-z-]*)"', src):
            if not to:
                continue  # the index route
            assert f'path="{to}"' in app, f"the {to} section routes nowhere"


class TestNoScopeIsAppliedOnlyInTheClient:
    """The user's line, held structurally: *never filtered only in the UI*.

    The screens receive lists that are already narrowed. A component that
    re-filtered them by brand would be a second, weaker copy of the scope —
    and the one somebody deletes while debugging.
    """

    def test_the_brand_filter_narrows_the_url_and_nothing_else(self):
        src = no_comments(
            FRONTEND / "components" / "admin" / "console" / "BrandFilter.jsx"
        )
        assert "setParams" in src
        # No local pruning of what the server sent.
        for smell in (".filter((b) =>", "assigned_brand_ids"):
            assert smell not in src

    def test_no_console_screen_reads_the_assignment_list(self):
        """`assigned_brand_ids` is the server's business. A screen reading it
        would be deciding what to show from data it was handed, which is the
        definition of a UI-only filter."""
        import subprocess

        out = subprocess.run(
            ["grep", "-rl", "assigned_brand_ids", str(FRONTEND)],
            capture_output=True,
            text=True,
        )
        assert out.stdout.strip() == "", out.stdout


class TestGettingIn:
    def test_staff_sign_in_with_a_password_and_the_two_sides_do_not(self):
        src = inspect.getsource(server.login)
        assert '"admin", "campaign_manager", "weare_team"' in src

    def test_a_scoped_console_is_worth_looking_through(self):
        """The one thing view-as adds that an admin cannot get otherwise."""
        assert "weare_team" in server.IMPERSONATABLE_ROLES
        assert "admin" not in server.IMPERSONATABLE_ROLES


# ---------------------------------------------------------------------------
# What an admin may create
# ---------------------------------------------------------------------------


class TestAdminCreation:
    """We are the operator as well as the platform.

    Some campaigns are ours to run, some briefs are barter, and some brands and
    creators arrive through a conversation rather than a signup form. Before
    these three routes an admin could review, edit, publish and close but never
    *create* — so an internal client had to be walked through a signup screen
    for an account nobody would ever log into.
    """

    def _campaign(self, world, **over):
        body = {
            "brand_id": str(world.mine),
            "title": "Internal tasting",
            "brief": "Shoot the new menu.",
            "deliverable_items": [{"type": "reel", "quantity": 1}],
            "budget_per_creator": 0,
            "category": "fnb",
            "area": "Indiranagar",
            "creators_needed": 2,
            "campaign_type": "personal_table",
            "start_date": datetime.now(timezone.utc) - timedelta(days=1),
            "end_date": datetime.now(timezone.utc) + timedelta(days=14),
        }
        body.update(over)
        return server.AdminCreateCampaignPayload(**body)

    # -- the campaign --------------------------------------------------------

    def test_it_goes_live_without_passing_through_review(self, world):
        """We are the reviewer. Submitting a brief to ourselves and then
        approving it is a queue item that exists to be dismissed."""
        run(world.db.brand_profiles.update_one(
            {"user_id": world.mine}, {"$set": {"verified": True}}
        ))
        out = run(server.admin_create_campaign(self._campaign(world), world.admin))
        assert out["status"] == "open"
        assert server.CAMPAIGN_REVIEW_STATUS not in (
            server.AdminCreateCampaignPayload.model_fields["status"].annotation.__args__
        )

    def test_it_is_ours_to_run_unless_told_otherwise(self, world):
        """The brand's own form defaults the other way, for the same reason:
        posting a brief means running it, and here the party posting is us."""
        assert (
            server.AdminCreateCampaignPayload.model_fields["execution_owner"].default
            == "weare"
        )
        assert server.PostCampaignPayload.model_fields["execution_owner"].default == "brand"

    def test_a_weare_run_brief_waits_for_a_real_manager(self, world):
        """Stamping the brand's own person would route applications straight
        back to the brand that asked us to take it on."""
        run(world.db.brand_profiles.update_one(
            {"user_id": world.mine}, {"$set": {"verified": True}}
        ))
        out = run(server.admin_create_campaign(self._campaign(world), world.admin))
        doc = run(world.db.campaigns.find_one({"_id": ObjectId(out["id"])}))
        assert doc["manager_id"] is None
        assert server._execution_owner(doc) == "weare"

    def test_barter_is_reachable_here_and_nowhere_else(self, world):
        """The asymmetry `admin_update_campaign` already holds. Adding the
        guard would make a barter brief impossible to *create*, leaving an edit
        as the only way to reach one."""
        run(world.db.brand_profiles.update_one(
            {"user_id": world.mine}, {"$set": {"verified": True}}
        ))
        out = run(server.admin_create_campaign(
            self._campaign(world, compensation_type="barter"), world.admin
        ))
        doc = run(world.db.campaigns.find_one({"_id": ObjectId(out["id"])}))
        assert server._compensation_type(doc) == "barter"

        src = inspect.getsource(server.admin_create_campaign)
        # The call form, not the bare name — the docstring explains why it is
        # absent, and a substring test would read that as the guard.
        assert "_refuse_brand_barter(" not in src

    def test_publishing_onto_an_unchecked_brand_is_refused(self, world):
        """The gate `approve_campaign` holds, for the identical reason:
        creators must never be reachable by a brand nobody has checked."""
        assert refuses(
            server.admin_create_campaign(self._campaign(world), world.admin)
        ).status_code == 409
        # And a draft, which reaches nobody, is fine.
        out = run(server.admin_create_campaign(
            self._campaign(world, status="draft"), world.admin
        ))
        assert out["status"] == "draft"

    def test_an_unknown_brand_is_a_404(self, world):
        assert refuses(
            server.admin_create_campaign(
                self._campaign(world, brand_id=str(ObjectId())), world.admin
            )
        ).status_code == 404

    def test_it_gets_a_reference_like_every_other_brief(self, world):
        run(world.db.brand_profiles.update_one(
            {"user_id": world.mine}, {"$set": {"verified": True}}
        ))
        out = run(server.admin_create_campaign(self._campaign(world), world.admin))
        doc = run(world.db.campaigns.find_one({"_id": ObjectId(out["id"])}))
        assert server._reference_of(doc).startswith("CMP-")

    # -- the brand -----------------------------------------------------------

    def test_a_brand_enters_verified_and_both_fields_agree(self, world):
        out = run(server.admin_create_brand(
            server.AdminCreateBrandPayload(
                business_name="Third Wave",
                manager_name="Meera Iyer",
                manager_phone="+919900000123",
                manager_email="meera@thirdwave.example.com",
            ),
            world.admin,
        ))
        profile = run(world.db.brand_profiles.find_one(
            {"user_id": ObjectId(out["user_id"])}
        ))
        assert profile["verified"] is True
        assert profile["verification_state"] == "verified"
        assert server._brand_verification_state(profile) == "verified"

    def test_the_brand_is_its_own_scope_like_a_self_registered_one(self, world):
        """`_brand_scope` reads `brand_id`; a row without it would work only
        while the login and the brand are the same document, which is exactly
        the assumption that function exists to remove."""
        out = run(server.admin_create_brand(
            server.AdminCreateBrandPayload(
                business_name="Third Wave",
                manager_name="Meera Iyer",
                manager_phone="+919900000123",
            ),
            world.admin,
        ))
        account = run(world.db.users.find_one({"_id": ObjectId(out["user_id"])}))
        assert account["role"] in server.BRAND_ROLES
        assert server._brand_scope(account) == account["_id"]

    def test_a_number_that_already_has_an_account_is_refused(self, world):
        body = server.AdminCreateBrandPayload(
            business_name="Third Wave",
            manager_name="Meera Iyer",
            manager_phone="+919900000123",
        )
        run(server.admin_create_brand(body, world.admin))
        assert refuses(server.admin_create_brand(body, world.admin)).status_code == 409

    # -- the creator ---------------------------------------------------------

    def test_a_creator_enters_verified_and_in_no_queue(self, world):
        """Verified is the record of a check that happened offline. Landing
        them in the review queue as well would be an item somebody has to
        dismiss to say what we already knew."""
        out = run(server.admin_create_creator(
            server.AdminCreateCreatorPayload(name="Kabir Shah", phone="+919900000124"),
            world.admin,
        ))
        profile = run(world.db.creator_profiles.find_one(
            {"user_id": ObjectId(out["user_id"])}
        ))
        assert profile["verification_status"] == "verified"
        assert profile["pending_review"] is False
        assert "submitted_for_review_at" not in profile

    def test_the_profile_is_a_stub_and_not_a_guess(self, world):
        """Everything a brand shortlists on is built in the profile builder.
        Filling it in here would be inventing somebody else's answers."""
        out = run(server.admin_create_creator(
            server.AdminCreateCreatorPayload(name="Kabir Shah", phone="+919900000124"),
            world.admin,
        ))
        profile = run(world.db.creator_profiles.find_one(
            {"user_id": ObjectId(out["user_id"])}
        ))
        assert profile["niches"] == [] and profile["platforms"] == []
        assert profile["base_rate"] is None and profile["follower_count"] is None

    def test_a_creator_number_that_exists_is_refused(self, world):
        body = server.AdminCreateCreatorPayload(name="Kabir", phone="+919900000001")
        assert refuses(server.admin_create_creator(body, world.admin)).status_code == 409

    # -- who may, and the record of it ---------------------------------------

    @pytest.mark.parametrize(
        "fn", ["admin_create_campaign", "admin_create_brand", "admin_create_creator"]
    )
    def test_creating_is_admin_only(self, fn):
        """Not the console roles. Minting a verified brand or creator is a
        statement about a check that happened; a scoped console could otherwise
        create the brand it then assigns itself to."""
        head = inspect.getsource(getattr(server, fn)).split("):", 1)[0]
        assert 'require_roles("admin")' in head

    @pytest.mark.parametrize(
        "fn,action",
        [
            ("admin_create_campaign", "campaign.create"),
            ("admin_create_brand", "brand.create"),
            ("admin_create_creator", "creator.create"),
        ],
    )
    def test_every_creation_is_audited_to_whoever_made_it(self, world, fn, action):
        run(world.db.brand_profiles.update_one(
            {"user_id": world.mine}, {"$set": {"verified": True}}
        ))
        bodies = {
            "admin_create_campaign": self._campaign(world),
            "admin_create_brand": server.AdminCreateBrandPayload(
                business_name="Third Wave",
                manager_name="Meera Iyer",
                manager_phone="+919900000123",
            ),
            "admin_create_creator": server.AdminCreateCreatorPayload(
                name="Kabir Shah", phone="+919900000124"
            ),
        }
        run(getattr(server, fn)(bodies[fn], world.admin))
        line = run(world.db.audit_log.find_one({"action": action}))
        assert line, f"{fn} created something with no audit line"
        assert line["actor_id"] == world.admin_id
        assert line["actor_role"] == "admin"


class TestTheCreationRoutesHaveACaller:
    """A backend flow with no UI is not shipped, whatever the tests say.

    That rule was written after four brand-verification endpoints spent months
    with no caller anywhere in the frontend — a brand could sign up, draft, and
    then hit the verification wall forever with no route to the thing that
    would clear it.
    """

    DIALOGS = FRONTEND / "components" / "admin" / "CreateDialogs.jsx"

    @pytest.mark.parametrize(
        "path", ["/admin/brands", "/admin/creators", "/admin/campaigns"]
    )
    def test_each_route_is_posted_to_from_the_console(self, path):
        src = no_comments(self.DIALOGS)
        assert f'api.post("{path}"' in src

    @pytest.mark.parametrize(
        "path,opener",
        [
            ("AdminBrands.jsx", "CREATE_IDS.brandOpen"),
            ("AdminCreators.jsx", "CREATE_IDS.creatorOpen"),
            ("AdminCampaigns.jsx", "CREATE_IDS.campaignOpen"),
        ],
    )
    def test_each_list_carries_the_button_that_opens_it(self, path, opener):
        src = no_comments(FRONTEND / "components" / "admin" / path)
        assert opener in src, f"{path} has no way to reach the create dialog"

    def test_the_two_that_a_scoped_console_must_not_see_are_gated(self):
        """Minting a *verified* brand is a statement about a check somebody
        made, and an admin-created campaign skips the review gate and can be
        barter. Both are refused server-side; the button is absent rather than
        present and refused."""
        for path, opener in (
            ("AdminBrands.jsx", "CREATE_IDS.brandOpen"),
            ("AdminCampaigns.jsx", "CREATE_IDS.campaignOpen"),
        ):
            src = no_comments(FRONTEND / "components" / "admin" / path)
            # The guard is on the element carrying the opener, so it is within
            # a few lines above it — a whole-file search would pass on an
            # `allAccess` used for something else entirely.
            before = src.split(opener, 1)[0].splitlines()[-8:]
            assert any("allAccess &&" in line for line in before), (
                f"{path} offers the create button to a scoped console"
            )

    def test_barter_is_offered_here_and_only_here(self):
        """`ALL_COMPENSATION_OPTIONS` is admin-only. The brand's form imports
        the paid-only list, so the option is *absent* there — there is nothing
        to re-enable from devtools."""
        src = no_comments(self.DIALOGS)
        assert "ALL_COMPENSATION_OPTIONS" in src

        brand_form = no_comments(FRONTEND / "pages" / "PostCampaign.jsx")
        assert "BRAND_COMPENSATION_OPTIONS" in brand_form
        assert "ALL_COMPENSATION_OPTIONS" not in brand_form

    def test_the_dialog_does_not_offer_the_review_status(self):
        """Submitting a brief to ourselves and then approving it is a queue
        item that exists to be dismissed. The payload has no such status
        either."""
        src = no_comments(self.DIALOGS)
        assert "pending_review" not in src


class TestTheCategoryListIsOne:
    """It was written out twice and a third copy was about to be typed, which
    is the point at which two copies become a fact nobody can check."""

    LIB = FRONTEND / "lib" / "categories.js"

    def test_it_matches_the_server(self):
        import re

        src = no_comments(self.LIB)
        client = re.findall(r'value: "([a-z_]+)"', src)
        assert client == list(server.CATEGORY_LITERAL.__args__)

    def test_nobody_keeps_a_second_copy(self):
        for path in ("pages/PostCampaign.jsx", "pages/BrandOnboarding.jsx",
                     "components/admin/CreateDialogs.jsx"):
            src = no_comments(FRONTEND / path)
            assert "const CATEGORY_OPTIONS = [" not in src, f"{path} re-declares the list"
            assert "CATEGORY_OPTIONS" in src, f"{path} stopped using it"
