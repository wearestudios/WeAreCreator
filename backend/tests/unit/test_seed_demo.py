"""The demo data, run for real and then read back.

A fixture nobody checks is a fixture that quietly stops matching the code it is
meant to exercise — a renamed field, a state that left the ladder, a
collaboration pointing at a campaign that was cut. This drives the actual
seeder against a real (mock) database and then asks the questions a person
would ask of the result: does every row join, is every state legal, does the
history the reliability panel reads actually exist, and is anything here
carrying a real phone number.

It also holds the two rules that make the script safe to run at all: it refuses
outside a development environment, and it does not delete anything until
somebody says so.
"""

from __future__ import annotations

import asyncio
import importlib
import os
from datetime import datetime, timezone

import pytest
from mongomock_motor import AsyncMongoMockClient

import server

LOOP = None


def _seed_module():
    """Imported lazily and fresh, because the module stamps `NOW` at import."""
    import seed_demo

    return importlib.reload(seed_demo)


def run(body):
    """One loop per call, kept in a module global — `asyncio.get_event_loop`
    fails inside a pytest-xdist worker thread, and `asyncio.run` closes the loop
    mongomock's cursors were built on."""
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()

    async def go():
        db = AsyncMongoMockClient()["seeded"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return LOOP.run_until_complete(go())


@pytest.fixture(scope="module")
def seeded():
    """The whole dataset, once, read back into plain lists.

    Seeding is not cheap and every assertion below reads the same result, so it
    runs once and the tests interrogate the output rather than re-running it.
    """
    seed = _seed_module()

    async def body(db):
        brands = await seed.seed_brands(seed.NOW)
        creators = await seed.seed_creators(seed.NOW)
        staff = await seed.seed_staff(seed.NOW, brands)
        campaigns = await seed.seed_campaigns(brands, staff)
        work = await seed.seed_work(brands, creators, campaigns, staff)
        await seed.seed_invitations(brands, creators, campaigns, staff)
        await seed.seed_questions(brands, creators, campaigns, staff)
        await seed.seed_lists_and_templates(brands, creators, campaigns, staff)
        await seed.seed_notifications(creators, brands, campaigns, work, staff)
        await seed.seed_audit(brands, creators, campaigns, work, staff)
        await seed.seed_invoice_override(brands)
        await seed.seed_deletion_request(creators)

        async def rows(name):
            return await db[name].find({}).to_list(length=2000)

        return {
            "module": seed,
            "brands": brands,
            "creators": creators,
            "staff": staff,
            "campaigns": campaigns,
            "work": work,
            "users": await rows("users"),
            "creator_profiles": await rows("creator_profiles"),
            "brand_profiles": await rows("brand_profiles"),
            "brand_documents": await rows("brand_documents"),
            "campaign_rows": await rows("campaigns"),
            "collaborations": await rows("collaborations"),
            "payments": await rows("payments"),
            "slots": await rows("campaign_slots"),
            "invitations": await rows("campaign_invitations"),
            "questions": await rows("campaign_questions"),
            "notes": await rows("collaboration_notes"),
            "ratings": await rows("collaboration_ratings"),
            "performance": await rows("content_performance"),
            "lists": await rows("creator_lists"),
            "templates": await rows("campaign_templates"),
            "notifications": await rows("notifications"),
            "audit": await rows("audit_log"),
            "deletions": await rows("deletion_requests"),
        }

    return run(body)


# ---------------------------------------------------------------------------
# It joins up
# ---------------------------------------------------------------------------


class TestEverythingPointsAtSomething:
    """A fixture whose foreign keys are broken is worse than no fixture: the
    screens render, the joins come back empty, and it reads as a bug in the
    product."""

    def test_every_collaboration_has_a_campaign_and_a_creator(self, seeded):
        campaigns = {c["_id"] for c in seeded["campaign_rows"]}
        creators = {p["user_id"] for p in seeded["creator_profiles"]}
        for collab in seeded["collaborations"]:
            assert collab["campaign_id"] in campaigns, collab["reference"]
            assert collab["creator_id"] in creators, collab["reference"]

    def test_every_campaign_has_a_brand(self, seeded):
        brands = {p["user_id"] for p in seeded["brand_profiles"]}
        for c in seeded["campaign_rows"]:
            assert c["brand_id"] in brands, c["title"]

    def test_every_payment_hangs_off_a_collaboration(self, seeded):
        collabs = {c["_id"] for c in seeded["collaborations"]}
        for p in seeded["payments"]:
            assert p["collaboration_id"] in collabs

    def test_every_side_record_points_at_a_real_row(self, seeded):
        collabs = {c["_id"] for c in seeded["collaborations"]}
        campaigns = {c["_id"] for c in seeded["campaign_rows"]}
        for key in ("notes", "ratings", "performance"):
            for row in seeded[key]:
                assert row["collaboration_id"] in collabs, key
        for row in seeded["questions"] + seeded["invitations"] + seeded["slots"]:
            assert row["campaign_id"] in campaigns

    def test_every_list_member_exists(self, seeded):
        creators = {p["user_id"] for p in seeded["creator_profiles"]}
        for row in seeded["lists"]:
            for cid in row["creator_ids"]:
                assert cid in creators


class TestTheStatesAreLegal:
    def test_every_collaboration_state_is_one_the_machine_knows(self, seeded):
        allowed = set(server.COLLAB_STATE_ORDER) | set(server.TERMINAL_COLLAB_STATES)
        for c in seeded["collaborations"]:
            assert c["state"] in allowed, c["state"]

    def test_every_rung_of_the_ladder_has_an_occupant(self, seeded):
        """A state with nothing in it is a transition nobody can try, and a
        screen nobody can see."""
        present = {c["state"] for c in seeded["collaborations"]}
        missing = [s for s in server.COLLAB_STATE_ORDER if s not in present]
        assert not missing, f"no seeded collaboration is at: {missing}"

    def test_every_exit_has_one_too(self, seeded):
        """`declined`, `cancelled`, `withdrawn` and `expired` are four
        different facts about a creator, and the history panel prints them
        differently."""
        present = {c["state"] for c in seeded["collaborations"]}
        missing = [s for s in server.TERMINAL_COLLAB_STATES if s not in present]
        assert not missing, f"no seeded collaboration exited by: {missing}"

    def test_every_campaign_status_is_represented(self, seeded):
        present = {c["status"] for c in seeded["campaign_rows"]}
        for status in ("draft", "pending_review", "open", "in_progress",
                       "paused", "completed", "closed", "rejected"):
            assert status in present, f"no seeded campaign is {status}"

    def test_every_clocked_record_knows_when_it_got_there(self, seeded):
        """Without `state_since` the whole platform reads as having started
        waiting the moment the seeder ran, and nothing is ever overdue — which
        is the one thing the ageing display exists to show."""
        for c in seeded["collaborations"]:
            assert isinstance(c.get("state_since"), datetime), c["reference"]
        for c in seeded["campaign_rows"]:
            assert isinstance(c.get("state_since"), datetime), c["title"]
        for p in seeded["brand_profiles"] + seeded["creator_profiles"]:
            assert isinstance(p.get("state_since"), datetime)

    def test_nothing_is_stamped_in_the_future(self, seeded):
        now = datetime.now(timezone.utc)
        for c in seeded["collaborations"]:
            since = c["state_since"]
            since = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
            assert since <= now, c["reference"]


class TestReferencesAndIdentity:
    def test_every_entity_has_a_readable_reference(self, seeded):
        for p in seeded["creator_profiles"]:
            assert (p.get("reference") or "").startswith("CRT-")
        for p in seeded["brand_profiles"]:
            assert (p.get("reference") or "").startswith("BRD-")
        for c in seeded["campaign_rows"]:
            assert (c.get("reference") or "").startswith("CMP-")
        for c in seeded["collaborations"]:
            assert (c.get("reference") or "").startswith("COL-")

    def test_references_are_unique(self, seeded):
        for key in ("creator_profiles", "brand_profiles", "campaign_rows",
                    "collaborations"):
            refs = [r["reference"] for r in seeded[key]]
            assert len(refs) == len(set(refs)), key

    def test_the_counters_start_from_one(self, seeded):
        """A wipe clears `reference_counters` too, or the first seeded brand
        is BRD-0043 because of a database that no longer exists."""
        firsts = sorted(p["reference"] for p in seeded["brand_profiles"])
        assert firsts[0] == "BRD-0001"

    def test_one_login_per_brand(self, seeded):
        """A database constraint, not a rule to remember — so the fixture must
        not be the thing that violates it."""
        brand_ids = [u["brand_id"] for u in seeded["users"] if u.get("brand_id")]
        assert len(brand_ids) == len(set(brand_ids))

    def test_every_phone_is_in_the_fake_block(self, seeded):
        """`+9199000000` in a production database is a self-announcing bug,
        which only works if the seeder never uses anything else."""
        for u in seeded["users"]:
            assert u["phone"].startswith("+9199000000"), u["phone"]


# ---------------------------------------------------------------------------
# It is worth looking at
# ---------------------------------------------------------------------------


class TestTheScreensHaveSomethingOnThem:
    def test_the_reliability_panel_reads_a_real_history(self, seeded):
        """The numbers on a creator's record have to come from rows somebody
        can open. A hardcoded record is a panel nobody trusts twice."""
        ana = seeded["creators"]["ana"]["user_id"]

        async def body(db):
            await db.collaborations.insert_many(
                [dict(r) for r in seeded["collaborations"]])
            await db.collaboration_ratings.insert_many(
                [dict(r) for r in seeded["ratings"]])
            return await server._reliability_for([ana])

        stats = run(body).get(ana) or {}
        assert stats.get("completed", 0) >= 3, "a strong record needs finished work"
        assert stats.get("on_time_rate") is not None
        assert stats.get("rating_count"), "nobody has rated the finished work"
        assert stats.get("rating_avg") is not None

    def test_the_finished_work_is_mostly_on_time(self, seeded):
        """Counted here in Python rather than read off `_reliability_for`,
        and that is not laziness.

        **mongomock's `$ne` does not treat a missing field as null.** Real
        MongoDB counts a row with no `no_show_reported` as "not a no-show";
        mongomock counts only rows where the field is present and `False`, so
        the aggregation reports `on_time_rate` 0.0 for creators whose seeded
        rows are perfectly clean. Writing the flags explicitly would make the
        fixture stop matching what the app writes — which is the one thing a
        fixture must never do — so the seed stays honest and the assertion
        does the arithmetic itself.
        """
        delivered = server.DELIVERED_COLLAB_STATES
        finished = [c for c in seeded["collaborations"] if c["state"] in delivered]
        assert finished
        on_time = [
            c for c in finished
            if not c.get("no_show_reported") and not c.get("content_overdue")
        ]
        late = [c for c in finished if c.get("content_overdue")]
        assert on_time, "every delivery is marked late, which is not a record"
        assert late, "no delivery is late, so the late-delivery mark is untested"

    def test_somebody_is_at_every_verification_state(self, seeded):
        states = {p["verification_state"] for p in seeded["brand_profiles"]}
        assert {"verified", "pending_verification", "rejected"} <= states
        statuses = {p["verification_status"] for p in seeded["creator_profiles"]}
        assert {"verified", "pending", "rejected"} <= statuses

    def test_a_verification_is_lapsing_and_another_has_lapsed(self, seeded):
        """The warning window and the block both need an occupant, or neither
        prompt is reachable."""
        ageing = [
            server._verification_ageing(p)
            for p in seeded["creator_profiles"]
            if p.get("verified_at")
        ]
        ageing = [a for a in ageing if a]
        assert any(a["expiring_soon"] for a in ageing), "nobody is in the warning window"
        assert any(a["lapsed"] for a in ageing), "nobody has lapsed"

    def test_somebody_is_suspended_and_blocked_by_it(self, seeded):
        by_id = {u["_id"]: u for u in seeded["users"]}
        suspended = [u for u in seeded["users"] if u.get("status") == "suspended"]
        assert suspended, "the suspension gate has nobody to block"
        assert all(u.get("suspension_reason") for u in suspended), (
            "a suspension with no reason is one nobody can explain"
        )
        profile = next(
            p for p in seeded["creator_profiles"]
            if p["user_id"] == suspended[0]["_id"]
        )
        block = server._creator_block(profile, by_id[suspended[0]["_id"]])
        assert block and block["code"] == "suspended"

    def test_the_suspension_prompt_has_somebody_to_prompt_about(self, seeded):
        no_shows = {}
        for c in seeded["collaborations"]:
            if c.get("no_show_reported"):
                no_shows[c["creator_id"]] = no_shows.get(c["creator_id"], 0) + 1
        assert any(n >= server.SUSPENSION_PROMPT_NO_SHOWS for n in no_shows.values())

    def test_there_is_an_open_dispute_and_a_resolved_one(self, seeded):
        states = [
            (c.get("dispute") or {}).get("state")
            for c in seeded["collaborations"] if c.get("dispute")
        ]
        assert "open" in states and "resolved" in states

    def test_the_open_dispute_freezes_its_payment(self, seeded):
        """The freeze is the point. A seeded dispute with the money still
        moving would be a fixture that contradicts the rule it illustrates."""
        frozen_collabs = {
            c["_id"] for c in seeded["collaborations"]
            if (c.get("dispute") or {}).get("state") == "open"
        }
        for p in seeded["payments"]:
            if p["collaboration_id"] in frozen_collabs:
                assert p.get("frozen") is True

    def test_there_is_a_takedown_waiting_and_one_answered(self, seeded):
        states = [
            (c.get("takedown") or {}).get("state")
            for c in seeded["collaborations"] if c.get("takedown")
        ]
        assert "requested" in states and "actioned" in states

    def test_a_brand_is_overdue_on_an_invoice(self, seeded):
        """Without one, the health panel's invoice row and the publish block
        are both unreachable."""

        async def body(db):
            await db.payments.insert_many([dict(p) for p in seeded["payments"]])
            await db.collaborations.insert_many(
                [dict(c) for c in seeded["collaborations"]])
            await db.campaigns.insert_many([dict(c) for c in seeded["campaign_rows"]])
            return await server._brand_overdue_invoices()

        owing = run(body)
        assert owing, "nobody owes us anything, so the block never fires"
        assert any(row["worst_days"] > 0 for row in owing.values())

    def test_the_invitations_include_an_open_one_and_a_lapsed_one(self, seeded):
        opens = [i for i in seeded["invitations"]
                 if not server._invitation_lapsed(i)]
        lapsed = [i for i in seeded["invitations"] if server._invitation_lapsed(i)]
        assert opens and lapsed

    def test_a_question_is_unanswered(self, seeded):
        """The admin action queue's question rows need one, and "unanswered"
        means the thread's last word is the creator's."""
        threads = {}
        for q in sorted(seeded["questions"], key=lambda r: (r["created_at"], r["_id"])):
            threads[(q["campaign_id"], q["creator_id"])] = q["from_creator"]
        assert any(threads.values()), "every thread has been answered"
        assert not all(threads.values()), "no thread has been answered"

    def test_a_slot_is_booked_and_waiting_on_an_answer(self, seeded):
        """`slot_confirmed_at` absent on a `slot_booked` row is what puts the
        manager's SlotAnswer band on screen."""
        booked = [c for c in seeded["collaborations"] if c["state"] == "slot_booked"]
        assert any(not c.get("slot_confirmed_at") for c in booked)
        assert any(c.get("slot_confirmed_at") for c in booked)

    def test_a_seat_is_never_sold_twice(self, seeded):
        by_slot = {}
        for c in seeded["collaborations"]:
            if c.get("slot_id"):
                by_slot[c["slot_id"]] = by_slot.get(c["slot_id"], 0) + 1
        for slot in seeded["slots"]:
            held = by_slot.get(slot["_id"], 0)
            assert held == slot["booked_count"], "booked_count disagrees with the rows"
            assert held <= slot["capacity"], "a slot is oversold"

    def test_performance_leaves_unknowns_unknown(self, seeded):
        """A post with no saves and a post whose saves we could not read are
        different, and the fixture has to contain the second kind or the em
        dash is never rendered."""
        assert any(r.get("saves") is None for r in seeded["performance"])
        assert any(r.get("saves") for r in seeded["performance"])

    def test_both_sides_have_rated_something(self, seeded):
        sides = {r["side"] for r in seeded["ratings"]}
        assert sides == {"runner", "creator"}

    def test_a_payment_records_withholding_and_another_records_none(self, seeded):
        """Three states, not two: `None` is "nobody has said", which the export
        prints differently from "no"."""
        paid = [p for p in seeded["payments"] if p.get("state") == "paid"]
        assert any(p.get("tds_applicable") for p in paid)
        assert any(p.get("tds_applicable") is False for p in paid)

    def test_a_campaign_is_barter_and_it_is_not_a_brands(self, seeded):
        """Barter is admin-only, so a seeded one has to be a brief WeAre
        arranged — the fixture must not model something the API refuses."""
        barter = [c for c in seeded["campaign_rows"]
                  if server._compensation_type(c) == "barter"]
        assert barter, "no barter brief, so the compensation formatter is untested"

    def test_a_brief_is_invite_only(self, seeded):
        vis = {server._campaign_visibility(c) for c in seeded["campaign_rows"]}
        assert vis == {"public", "private"}

    def test_both_execution_owners_are_present(self, seeded):
        owners = {server._execution_owner(c) for c in seeded["campaign_rows"]}
        assert owners == {"brand", "weare"}

    def test_a_draft_has_gone_stale(self, seeded):
        """`DRAFT_STALE_DAYS` needs an occupant or the health check that flags
        them can never be seen firing."""
        assert any(
            c["status"] == "draft" and server._draft_is_stale(c)
            for c in seeded["campaign_rows"]
        )


class TestTheDeliverablesAreStructured:
    def test_every_campaign_carries_counted_items_and_a_sentence(self, seeded):
        """Both, from one resolver — a brief's words and its counted pieces can
        never describe different asks."""
        for c in seeded["campaign_rows"]:
            items = server._deliverable_items(c)
            assert items, c["title"]
            assert c.get("deliverables"), c["title"]
            assert c["deliverables"] == server._deliverables_text(items)

    def test_every_deliverable_type_is_one_the_vocabulary_knows(self, seeded):
        for c in seeded["campaign_rows"]:
            for item in server._deliverable_items(c):
                assert item["type"] in server.DELIVERABLE_TYPES, item


# ---------------------------------------------------------------------------
# It cannot leak, and it cannot run where it must not
# ---------------------------------------------------------------------------


class TestNothingBrandFacingCarriesContact:
    def test_the_brand_projection_drops_every_forbidden_field(self, seeded):
        """The seeded creators carry phone numbers, addresses, PANs and bank
        details on purpose — they are what a real profile has. This is the
        check that a brand still receives none of it.

        Searched for by value, not by key: a number arriving through a
        `**spread` from a document nobody remembered had one is the mistake
        source-reading misses.
        """
        planted = 0
        for p in seeded["creator_profiles"]:
            # Per profile, and excluding any value that is *also* legitimately
            # brand-visible on the same record: a bank account in the name
            # "Cal Mehta" does not make the creator's name a secret, and a
            # cross-profile search would report that as a leak forever.
            visible = {
                str(v) for k, v in p.items()
                if k in server._BRAND_VISIBLE_CREATOR_FIELDS and v
            }
            secrets = {
                str(v) for k, v in p.items()
                if k in server.BRAND_FORBIDDEN_CREATOR_FIELDS and v
            } - visible
            planted += len(secrets)
            rendered = str(server._brand_visible_creator(p))
            for secret in secrets:
                assert secret not in rendered, f"{secret} reached a brand surface"
        assert planted, "the fixture has no contact details, so this proves nothing"

    def test_the_public_brand_page_drops_the_managers_details(self, seeded):
        secrets = []
        for p in seeded["brand_profiles"]:
            secrets += [
                str(v) for k, v in p.items()
                if k in server.PUBLIC_BRAND_FORBIDDEN_FIELDS and v
            ]
        assert secrets
        for p in seeded["brand_profiles"]:
            rendered = str(server._public_brand(p))
            for secret in secrets:
                assert secret not in rendered


class TestItRefusesToRunWhereItShould:
    def test_it_will_not_run_without_simulation(self, monkeypatch):
        """The gate and the usefulness are one fact: without simulation you
        could not read the OTP, so the accounts would be unusable anyway."""
        seed = _seed_module()
        monkeypatch.delenv("ALLOW_OTP_SIMULATION", raising=False)
        monkeypatch.setenv("APP_ENV", "production")
        assert LOOP is not None or True
        loop = asyncio.new_event_loop()
        try:
            assert loop.run_until_complete(seed.main(["--yes"])) == 1
        finally:
            loop.close()

    def test_it_will_not_run_against_something_that_looks_like_production(
        self, monkeypatch
    ):
        """`_simulation_allowed` returns true for an explicit
        ALLOW_OTP_SIMULATION whatever APP_ENV says, so on its own it would let
        `APP_ENV=production ALLOW_OTP_SIMULATION=true` wipe a live database."""
        seed = _seed_module()
        monkeypatch.setenv("ALLOW_OTP_SIMULATION", "true")
        monkeypatch.setenv("APP_ENV", "production")
        loop = asyncio.new_event_loop()
        try:
            assert loop.run_until_complete(seed.main(["--yes"])) == 1
        finally:
            loop.close()

    def test_an_unset_app_env_reads_as_production(self, monkeypatch):
        """The safe direction to guess in, for a script whose first act is a
        delete."""
        seed = _seed_module()
        monkeypatch.setenv("ALLOW_OTP_SIMULATION", "true")
        monkeypatch.delenv("APP_ENV", raising=False)
        monkeypatch.delenv("ENV", raising=False)
        loop = asyncio.new_event_loop()
        try:
            assert loop.run_until_complete(seed.main(["--yes"])) == 1
        finally:
            loop.close()

    def test_it_will_not_wipe_unattended_without_being_told_to(self, monkeypatch):
        """The first two fences are about the environment; this one is about
        the person. A mistyped DB_NAME passes both of the others."""
        seed = _seed_module()
        monkeypatch.setenv("ALLOW_OTP_SIMULATION", "true")
        monkeypatch.setenv("APP_ENV", "test")
        monkeypatch.setenv("DB_NAME", "wearecreators")

        async def body(db):
            await db.users.insert_one({"phone": "+919876543210", "role": "creator"})
            # No tty in a test run, and no --yes: it must refuse rather than
            # fall through to deleting somebody's data.
            code = await seed.main([])
            return code, await db.users.count_documents({})

        code, survivors = run(body)
        assert code == 1
        assert survivors == 1, "it deleted without being told to"

    def test_the_wipe_list_covers_every_collection_the_app_writes_to(self):
        """A collection added to `server.py` and forgotten here shows up as
        data that survives a wipe, which is exactly the confusing half-state
        this script exists to end."""
        import re

        seed = _seed_module()
        used = set(re.findall(r"\bdb\.([a-z_]+)\.", server.__file__ and
                              open(server.__file__).read()))
        # `db.command` and friends are not collections.
        used -= {"client", "name", "command"}
        missing = sorted(used - set(seed.WIPED))
        assert not missing, f"the wipe would leave these behind: {missing}"


class TestTheOldSeederIsGone:
    def test_there_is_one_seeder(self):
        """Two scripts writing the same phone numbers is two definitions of
        the demo data, and the one you did not run is the one you debug."""
        from pathlib import Path

        backend = Path(server.__file__).parent
        assert not (backend / "seed_personas.py").exists(), (
            "seed_personas.py is superseded by seed_demo.py"
        )
        assert (backend / "seed_demo.py").exists()
