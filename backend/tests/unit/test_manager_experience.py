"""The person who actually runs the shoot.

A campaign manager had been given five jobs and a screen for one of them. The
`/manager` router grew endpoints, `notify_campaign_manager` grew events, and
`_question_staff_may_see` grew a `campaign_manager` branch — while the frontend
kept the three tabs it started with. The result was a role that got *paged*
about work it had no way to do:

- the second half of the booking handshake had two routes, a notification and
  no button anywhere, so every booking on a weare-run campaign sat pending
  until an admin answered it from the console;
- the manager is the draft reviewer on their own campaigns, and could not see a
  draft;
- they could read and answer a creator's question thread, and had no thread;
- `POST /manager/collaborations/{id}/performance` had no caller at all, on a
  home screen whose own comment says finished campaigns are kept *because*
  performance gets recorded later;
- and no manager surface rendered the brief or the deliverables, so the person
  standing in the venue could not see what the creators had been asked for.

The first test below is the one that matters: **every route on the manager
router has a caller in the frontend.** It is the "a backend flow with no UI is
not shipped" rule made mechanical, and it fails all five of the above.
"""
import ast
import asyncio
import inspect
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from mongomock_motor import AsyncMongoMockClient

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"


def no_comments(path: Path) -> str:
    src = re.sub(r"\{/\*.*?\*/\}", "", path.read_text(), flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


def frontend_source() -> str:
    """Every source file, comments stripped, as one string."""
    return "\n".join(
        no_comments(p)
        for p in FRONTEND.rglob("*.js*")
        if p.is_file() and "node_modules" not in p.parts
    )


# ---------------------------------------------------------------------------
# Every route has a caller
# ---------------------------------------------------------------------------


def manager_routes():
    """(method, path) for everything on the manager router."""
    src = Path(server.__file__).read_text()
    lines = src.splitlines()
    out = []
    for node in ast.parse(src).body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for d in node.decorator_list:
            text = "\n".join(lines[d.lineno - 1 : d.end_lineno]).replace("\n", " ")
            m = re.search(r'manager_router\.(\w+)\(\s*"([^"]+)"', text)
            if m:
                out.append((m.group(1), m.group(2), node.name))
    return out


def call_pattern(method: str, path: str) -> re.Pattern:
    """The route as it is written at a call site.

    `/collaborations/{collab_id}/no-show` is typed in the client as
    `` api.post(`/manager/collaborations/${id}/no-show`) `` — so every
    `{param}` becomes "some template expression" and everything else matches
    literally.

    **The method is part of it.** Matching the path alone let
    `POST /campaigns/{id}/slots` pass on the *GET* beside it, which is exactly
    the false pass that would let a real gap through.
    """
    parts = [re.escape(seg) for seg in re.split(r"\{[^}]+\}", path)]
    body = r"/manager" + r"\$\{[^}]*\}".join(parts)
    forms = [rf"api\.{method}\(\s*[`\"']{body}"]
    if method == "post":
        # **The second legitimate call form.** A request that has to survive a
        # venue's wifi is declared as data — `{ url, body }` — so the offline
        # queue can put it on disk and replay it, and `enqueue` defaults the
        # method to post. Requiring `api.post(` beside the path would fail
        # exactly the three actions that were written most carefully.
        forms.append(rf"url:\s*[`\"']{body}")
    return re.compile("|".join(forms))


# One documented alias, and the reason it is exempt: `POST /manager/slots` is
# the same operation naming the campaign in the body, it delegates to this
# handler rather than repeating it, and the docstring says it stays "for
# callers already using it". A legacy door with one implementation behind it is
# not the failure this test is looking for.
ALIASES = {("post", "/campaigns/{campaign_id}/slots")}

ROUTES = [r for r in manager_routes() if (r[0], r[1]) not in ALIASES]


def test_the_route_list_is_not_empty():
    """A structural test that matches nothing passes for free."""
    assert len(ROUTES) >= 12


@pytest.mark.parametrize(
    "method,path,name", ROUTES, ids=[f"{m.upper()} {p}" for m, p, _ in ROUTES]
)
def test_every_manager_route_has_a_caller_in_the_frontend(method, path, name):
    """**The rule that would have caught all five gaps at once.**

    A route nobody can reach is not a feature, it is a promise in a route
    table. This is the same rule that was written after four brand
    verification endpoints spent months with no caller anywhere — a brand
    could sign up, draft, and then hit the wall forever with no route to the
    thing that would clear it.
    """
    src = frontend_source()
    assert call_pattern(method, path).search(src), (
        f"{method.upper()} /manager{path} ({name}) has no caller in the frontend — "
        "the manager is told about work they cannot do"
    )


@pytest.mark.parametrize(
    "component,mounted_in",
    [
        ("SlotAnswer", "pages/ManagerCampaign.jsx"),
        ("BriefPanel", "pages/ManagerCampaign.jsx"),
        ("PerformanceSheet", "pages/ManagerCampaign.jsx"),
    ],
)
def test_the_new_panels_are_actually_on_a_screen(component, mounted_in):
    """**A component that exists is not a component anybody sees.**

    Deleting `<SlotAnswer />` from the campaign page left every other test
    here green: the file still held the only `api.post(.../slot/confirm)` in
    the repository, so the route-has-a-caller check was satisfied by a
    component nothing rendered. That is the same class of miss the whole file
    is about, one level up — a caller with no mount is as unreachable as a
    route with no caller.
    """
    assert f"<{component}" in no_comments(FRONTEND / mounted_in), (
        f"{component} exists but nothing renders it"
    )


def test_the_manager_can_open_one_application():
    """`get_application` has always accepted a campaign_manager, and no route
    reached it — so the draft they are meant to review, the question thread
    they are meant to answer and the work notes they are meant to read had no
    address."""
    head = inspect.getsource(server.get_application).split("):", 1)[0]
    assert '"campaign_manager"' in head

    app = no_comments(FRONTEND / "App.js")
    assert 'path="/manager/applications/:id"' in app
    block = app.split('path="/manager/applications/:id"', 1)[1][:600]
    assert 'roles={["campaign_manager", "admin"]}' in block
    assert "<ApplicationDetail" in block


def test_the_shared_screen_is_told_where_to_post_rather_than_asking_who_it_is():
    """`_answer_slot_request` is one implementation behind four routes, but the
    *route* differs by caller. The component takes it as a prop, the way it
    takes `entityLinks` — a role check here would be the second, disagreeing
    answer the whole component exists to prevent."""
    src = no_comments(FRONTEND / "components" / "application" / "ApplicationDetail.jsx")
    assert "slotBase" in src
    assert "${slotBase}/collaborations/${id}/slot/confirm" in src
    assert "${slotBase}/collaborations/${id}/slot/decline" in src
    for smell in ("role ===", "user?.role", "isAdmin"):
        assert smell not in src, f"ApplicationDetail branches on {smell}"

    app = no_comments(FRONTEND / "App.js")
    block = app.split('path="/manager/applications/:id"', 1)[1][:600]
    assert 'slotBase="/manager"' in block


# ---------------------------------------------------------------------------
# Booked, and booked-and-waiting
# ---------------------------------------------------------------------------


class World:
    """One campaign, three bookings: confirmed, waiting, and pre-handshake."""

    async def build(self):
        self.db = AsyncMongoMockClient()["manager"]
        server.db = self.db
        db = self.db
        now = datetime.now(timezone.utc)

        self.brand, self.manager = ObjectId(), ObjectId()
        self.campaign = ObjectId()
        await db.users.insert_many(
            [
                {"_id": self.brand, "role": "brand_manager", "name": "Toit"},
                {"_id": self.manager, "role": "campaign_manager", "name": "Priya"},
            ]
        )
        await db.brand_profiles.insert_one(
            {"user_id": self.brand, "business_name": "Toit", "verified": True}
        )
        await db.campaigns.insert_one(
            {
                "_id": self.campaign,
                "brand_id": self.brand,
                "manager_id": self.manager,
                "title": "Toit tasting",
                "brief": "Shoot the new menu.\nTwo dishes minimum.",
                "deliverables": "1 reel · 3 stories",
                "deliverable_items": [
                    {"type": "reel", "quantity": 1},
                    {"type": "story", "quantity": 3},
                ],
                "status": "open",
                "campaign_type": "personal_table",
                "creators_needed": 3,
                "budget_per_creator": 8000,
                "compensation_type": "fixed",
                "execution_owner": "weare",
                "created_at": now,
            }
        )

        self.slot = ObjectId()
        await db.campaign_slots.insert_one(
            {
                "_id": self.slot,
                "campaign_id": self.campaign,
                "starts_at": now + timedelta(days=2),
                "ends_at": now + timedelta(days=2, hours=1),
                "capacity": 4,
                "booked_count": 3,
            }
        )

        self.confirmed, self.waiting, self.old = ObjectId(), ObjectId(), ObjectId()
        for oid, extra, name in (
            (self.confirmed, {"slot_booked_at": now, "slot_confirmed_at": now}, "Aditi"),
            # Booked since the handshake, nobody has answered.
            (self.waiting, {"slot_booked_at": now}, "Rhea"),
            # Booked before the handshake existed: no marker at all.
            (self.old, {}, "Kabir"),
        ):
            creator = ObjectId()
            await self.db.users.insert_one(
                {"_id": creator, "role": "creator", "name": name, "phone": "+919900000001"}
            )
            await self.db.creator_profiles.insert_one(
                {"user_id": creator, "name": name}
            )
            await db.collaborations.insert_one(
                {
                    "_id": oid,
                    "campaign_id": self.campaign,
                    "creator_id": creator,
                    "state": "slot_booked",
                    "slot_id": self.slot,
                    "created_at": now,
                    **extra,
                }
            )

        self.manager_user = await db.users.find_one({"_id": self.manager})
        return self


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


class TestTheRosterSaysWhatIsWaiting:
    def test_a_held_booking_is_told_apart_from_an_agreed_one(self, world):
        """They looked identical on the one screen built to answer them, so
        the handshake existed in the state machine and nowhere a manager could
        see it."""
        rows = {
            r["collaboration_id"]: r
            for r in run(server._roster_rows(
                run(world.db.campaigns.find_one({"_id": world.campaign}))
            ))
        }
        assert rows[str(world.waiting)]["slot_pending"] is True
        assert rows[str(world.confirmed)]["slot_pending"] is False

    def test_a_booking_made_before_the_handshake_is_not_reopened(self, world):
        """Those were agreed by the only mechanism there was — nobody
        objecting — and putting a decision in front of a manager for a shoot
        that already happened is how a new feature makes work."""
        rows = {
            r["collaboration_id"]: r
            for r in run(server._roster_rows(
                run(world.db.campaigns.find_one({"_id": world.campaign}))
            ))
        }
        assert rows[str(world.old)]["slot_pending"] is False
        assert rows[str(world.old)]["slot_confirmed"] is True

    def test_the_count_on_the_card_matches_the_rows(self, world):
        counts = run(server._pending_slot_counts_for([world.campaign]))
        assert counts.get(world.campaign) == 1

        cards = run(server.list_managed_campaigns(user=world.manager_user))
        assert cards[0]["slots_pending"] == 1

    def test_the_home_card_raises_it_whatever_the_date(self):
        """Every other signal `attentionFor` raises is about the shoot getting
        closer. A creator holding a seat nobody has answered is a problem the
        moment they book, and it is the only one waiting on this manager
        rather than on the world."""
        src = no_comments(FRONTEND / "components" / "manager" / "shared.jsx")
        head = src.split("if (!soon) return out;", 1)[0]
        assert "slots_pending" in head, (
            "the pending count is behind the two-day gate, so a booking made "
            "three weeks out is invisible until the week of the shoot"
        )


class TestTheManagerCanReadTheBrief:
    def test_the_roster_payload_carries_it(self, world):
        out = run(server.campaign_roster(str(world.campaign), world.manager_user))
        assert out["brief"].startswith("Shoot the new menu.")
        assert out["deliverable_items"] == [
            {"type": "reel", "quantity": 1},
            {"type": "story", "quantity": 3},
        ]
        # And the fee with the word for what kind of fee it is beside it.
        assert out["budget_per_creator"] == 8000
        assert out["compensation_type"] == "fixed"

    def test_the_payload_carries_every_field_the_page_reads_off_it(self, world):
        """`ManagerCampaign` builds its whole `campaign` object out of this
        response. Anything the page reads and the endpoint does not send is
        silently `undefined` — which is how the header came to say "Dates not
        set" on a campaign with dates, and how `SlotEditor` came to validate a
        new slot against nothing."""
        run(world.db.campaigns.update_one(
            {"_id": world.campaign},
            {"$set": {
                "start_date": datetime.now(timezone.utc),
                "end_date": datetime.now(timezone.utc) + timedelta(days=20),
            }},
        ))
        out = run(server.campaign_roster(str(world.campaign), world.manager_user))
        page = no_comments(FRONTEND / "pages" / "ManagerCampaign.jsx")
        block = page.split("const campaign = roster", 1)[1].split("        : null;", 1)[0]
        for field in re.findall(r"roster\.(\w+)", block):
            assert field in out, f"the page reads roster.{field} and nothing sends it"
        assert out["start_date"] and out["end_date"]

    def test_a_campaign_with_no_items_still_carries_its_sentence(self, world):
        """`_deliverable_items` reads absent as `[]` — not "asked for nothing"
        — which is what tells every surface to fall back to the sentence a
        pre-field campaign has."""
        run(world.db.campaigns.update_one(
            {"_id": world.campaign}, {"$unset": {"deliverable_items": ""}}
        ))
        out = run(server.campaign_roster(str(world.campaign), world.manager_user))
        assert out["deliverable_items"] == []
        assert out["deliverables"] == "1 reel · 3 stories"

    def test_it_is_rendered_through_the_one_renderer(self):
        """A test already fails any surface printing `campaign.deliverables`
        directly; this is the other half — that the manager's panel uses the
        shared component rather than growing a fourth spelling."""
        src = no_comments(FRONTEND / "components" / "manager" / "BriefPanel.jsx")
        assert "<DeliverableList" in src
        assert "formatCompensation" in src, (
            "a barter shoot would print its vestigial budget as money owed"
        )

    def test_the_campaign_page_offers_it_as_a_tab(self):
        src = no_comments(FRONTEND / "pages" / "ManagerCampaign.jsx")
        assert '{ key: "brief", label: "Brief" }' in src
        assert "<BriefPanel" in src


class TestTheHomePageActuallyRenders:
    """The manager's landing screen was a `ReferenceError` on every render.

    `shared.jsx` called `istStartOfDay(...)` and imported only `IST`, so
    `isToday` threw for every campaign in the list and the whole page fell
    through to the route boundary. It shipped that way and nothing noticed,
    because every test about this file read functions out of it rather than
    rendering the page — a function you import directly still resolves its own
    module scope, and the missing name only bites at call time.
    """

    SHARED = FRONTEND / "components" / "manager" / "shared.jsx"

    def test_every_name_the_file_calls_is_one_it_can_reach(self):
        """Cheap, blunt, and it would have caught this: any bare identifier
        called as a function has to be defined or imported in the file."""
        src = no_comments(self.SHARED)
        imported = set(re.findall(r"[\w]+(?=\s*[,}])|(?<=import )\w+", src))
        for m in re.finditer(r"import\s*\{([^}]*)\}", src):
            for part in m.group(1).split(","):
                imported.add(part.split(" as ")[-1].strip())
        declared = set(re.findall(r"(?:const|let|function)\s+(\w+)", src))
        known = imported | declared

        for name in re.findall(r"\b([a-z][A-Za-z0-9]*)\(", src):
            if name in ("if", "for", "while", "switch", "catch", "return", "typeof"):
                continue
            # Only bare calls — a method call carries a dot before it, and this
            # regex cannot see that, so check the ones we know are module-level.
            if name in ("istStartOfDay", "dayKey", "startOfDay", "attentionFor"):
                assert name in known, f"{name}() is called and never imported"

    def test_the_zone_helper_is_imported_under_the_name_it_is_called_by(self):
        src = no_comments(self.SHARED)
        assert "startOfDay as istStartOfDay" in src
        assert "istStartOfDay(d)" in src

    def test_is_today_answers_for_both_campaign_shapes(self):
        """The regression this crash hid: `isToday` is the function the whole
        home page buckets on, and nothing exercised it end to end."""
        src = no_comments(self.SHARED)
        block = src.split("export function isToday", 1)[1].split("\n}", 1)[0]
        # An event has a day; a personal table has a window that *contains*
        # today, which is as much "on today" as a launch is.
        assert "event_date" in block and "start_date" in block and "end_date" in block


class TestTheVenueNetwork:
    QUEUE = FRONTEND / "lib" / "offlineQueue.js"
    DAY_OF = FRONTEND / "components" / "manager" / "DayOfMode.jsx"

    def test_all_three_day_of_actions_survive_a_dropped_connection(self):
        """Check-in already did. No-show and reschedule are the same manager,
        in the same basement, on the same phone, in the same minute — and a
        reschedule that silently failed is worse than a lost check-in, because
        the creator has been told a time nobody recorded."""
        src = no_comments(self.DAY_OF)
        assert src.count("enqueue(") == 2, (
            "the check-in queue and the shared `run` should each enqueue once"
        )
        # `run` is what no-show and reschedule both go through.
        block = src.split("const run = async", 1)[1].split("};", 1)[0]
        assert "enqueue(" in block
        assert "shouldRetry(e)" in block

    def test_the_two_ends_of_the_queue_share_one_rule(self):
        """A call site decides whether to enqueue and the flusher decides
        whether to keep replaying. Two copies of that rule is a request that
        vanishes while the UI says it is waiting to sync."""
        queue = no_comments(self.QUEUE)
        assert "export function shouldRetry" in queue
        assert 'import { enqueue, shouldRetry } from "@/lib/offlineQueue";' in (
            no_comments(self.DAY_OF)
        )

    def test_a_refusal_is_still_never_queued(self):
        """409 is the server answering about this specific request. On a
        check-in it usually means it already succeeded, and replaying it would
        loop forever on work that landed."""
        queue = no_comments(self.QUEUE)
        block = queue.split("export function shouldRetry", 1)[1].split("\n}", 1)[0]
        assert "status === 408" in block and "status === 429" in block
        assert "status >= 500" in block
        assert "return false" in block


class TestRecordingWhatTheWorkDid:
    def test_the_sheet_omits_a_blank_rather_than_sending_a_zero(self):
        """An unknown metric is `None`, never `0`. A post with no saves and a
        post whose saves nobody could read are different, and averaging the
        second as a zero makes a campaign look worse than it was."""
        src = no_comments(FRONTEND / "components" / "manager" / "PerformanceSheet.jsx")
        assert 'if (raw !== "") body[m.key] = Number(raw);' in src
        assert "engagement_rate" not in src, (
            "it is derived on read so it cannot disagree with its own inputs"
        )

    def test_it_asks_for_the_metrics_the_server_accepts(self):
        src = no_comments(FRONTEND / "components" / "manager" / "PerformanceSheet.jsx")
        for metric in server.PERFORMANCE_METRICS:
            assert f'key: "{metric}"' in src, f"{metric} cannot be typed in"

    def test_the_control_only_appears_once_there_is_a_post(self):
        """Before that the button opens a form that cannot be filled in
        honestly."""
        src = no_comments(FRONTEND / "pages" / "ManagerCampaign.jsx")
        assert "DELIVERED_STATES.has(r.state)" in src
        block = src.split("const DELIVERED_STATES", 1)[1].split("]);", 1)[0]
        for state in ("content_submitted", "content_approved", "in_payment", "closed"):
            assert state in block
        # A draft is not delivered: performance is measured on published work,
        # and a draft has no reach.
        assert "draft_submitted" not in block
