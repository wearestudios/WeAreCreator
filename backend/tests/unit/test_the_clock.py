"""The clock: state ageing, SLA targets, escalation, chasing and expiry.

Nothing in this system had a clock. Every state waited indefinitely for a
human, which is fine — these *are* decisions people make — but with nothing
measuring the wait, a record that had stalled looked exactly like a record that
was fine, and the first person to notice was whoever eventually rang up.

These tests hold the four things that stop that being true again: every state
change stamps when it happened, every target is one table, every overdue record
reaches a surface, and every chaser stops on its own.
"""

from __future__ import annotations

import ast
import asyncio
import functools
import inspect
import pathlib
from datetime import datetime, timedelta, timezone

import pytest
from mongomock_motor import AsyncMongoMockClient

import server


# ---------------------------------------------------------------------------
# Structural: every state change stamps the clock
# ---------------------------------------------------------------------------

BACKEND = pathlib.Path(server.__file__).resolve().parent
SERVER_PY = BACKEND / "server.py"


@functools.lru_cache(maxsize=1)
def _source() -> str:
    return SERVER_PY.read_text()


@functools.lru_cache(maxsize=1)
def _tree() -> ast.Module:
    return ast.parse(_source())


@functools.lru_cache(maxsize=1)
def _lines() -> tuple:
    return tuple(_source().splitlines())


def _collection_and_method(func: ast.AST):
    """`db.<collection>.<method>` or nothing."""
    if not isinstance(func, ast.Attribute):
        return None, None
    inner = func.value
    if (
        isinstance(inner, ast.Attribute)
        and isinstance(inner.value, ast.Name)
        and inner.value.id == "db"
    ):
        return inner.attr, func.attr
    return None, None


def _is_clock_exempt(lineno: int) -> bool:
    """A migration marked in the source as not-a-transition.

    **By marker, not by line number.** A test that names line 23273 is a test
    that breaks the next time somebody adds an import, and the person fixing it
    has no idea what the exemption was for. The marker sits at the call and
    says why.
    """
    window = _lines()[max(0, lineno - 12) : lineno + 4]
    return any("clock-exempt:" in line for line in window)


def _unstamped_state_writes() -> list:
    """Writes that set a clocked record's state without stamping when."""
    offenders = []
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue
        collection, method = _collection_and_method(node.func)
        if collection not in server.STATE_CLOCK_FIELDS:
            continue
        if method not in ("update_one", "update_many", "find_one_and_update"):
            continue
        field = server.STATE_CLOCK_FIELDS[collection]
        for arg in node.args:
            if not isinstance(arg, ast.Dict):
                continue
            for key, value in zip(arg.keys, arg.values):
                if not (isinstance(key, ast.Constant) and key.value == "$set"):
                    continue
                if not isinstance(value, ast.Dict):
                    continue
                names = [
                    k.value for k in value.keys if isinstance(k, ast.Constant)
                ]
                if field in names and "state_since" not in names:
                    if not _is_clock_exempt(node.lineno):
                        offenders.append((node.lineno, collection, field))
    return offenders


class TestEveryStateChangeStampsTheClock:
    """**The rule the whole feature rests on.**

    There is no single transition function in `server.py` — states are written
    at more than thirty call sites, each with its own `from_state` write
    precondition — so the stamp cannot be applied centrally. It travels with
    the state instead, and this is what stops the thirty-first site from
    quietly shipping without it.
    """

    def test_no_state_write_forgets_state_since(self):
        offenders = _unstamped_state_writes()
        assert offenders == [], (
            "these writes set a state without stamping when it changed — "
            "spread `**_state_stamp(value, now)` into the $set: "
            + ", ".join(f"{c}.{f} at line {ln}" for ln, c, f in offenders)
        )

    def test_the_rule_covers_all_four_clocked_records(self):
        """A collaboration, a campaign, a brand and a creator — the four the
        product asks "how long has this been waiting" about."""
        assert set(server.STATE_CLOCK_FIELDS) == {
            "collaborations",
            "campaigns",
            "brand_profiles",
            "creator_profiles",
        }

    def test_the_stamp_writes_the_column_each_record_actually_uses(self):
        """They do not agree on the name, and renaming three of them to match
        would be a migration across the whole file for a cosmetic win."""
        for collection, field in server.STATE_CLOCK_FIELDS.items():
            stamped = server._state_stamp("x", field=field)
            assert stamped[field] == "x", collection
            assert "state_since" in stamped and "updated_at" in stamped

    def test_migrations_are_exempt_and_say_why(self):
        """**A rename is not a transition.** The startup migrations move
        `vetted` to `verified` and derive `verification_state` from a boolean;
        stamping either would date every historical record to the deploy and
        make the whole platform read as "waiting since this morning".
        """
        source = _source()
        assert source.count("clock-exempt:") >= 3
        for marker in ("a rename is not a transition", "did not move this morning"):
            assert marker in source


# ---------------------------------------------------------------------------
# The reader
# ---------------------------------------------------------------------------


def _at(hours_ago: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours_ago)


class TestStateSince:
    def test_it_prefers_the_clock_over_the_modification_time(self):
        """`updated_at` moves when anybody writes anything — a note, a rate, a
        cover image. A collaboration nobody has advanced in a fortnight would
        otherwise read as touched five minutes ago."""
        doc = {"state_since": _at(72), "updated_at": _at(0.1), "created_at": _at(200)}
        assert server._state_since(doc) == doc["state_since"]

    def test_absent_falls_back_to_updated_at_then_created_at(self):
        assert server._state_since({"updated_at": _at(5)}) is not None
        assert server._state_since({"created_at": _at(5)}) is not None
        assert server._state_since({}) is None
        assert server._state_since(None) is None

    def test_the_fallback_understates_the_age_rather_than_overstating_it(self):
        """**The safe direction, and it is a deliberate choice.** A record
        written before this field existed does not know when it last moved.
        `updated_at` is at or after the real transition, so the age it yields
        is a lower bound — an escalation that fires late is a nuisance, one
        that fires on a record that is fine teaches everybody to ignore it.
        """
        real_transition = _at(200)
        touched_since = _at(2)
        legacy = {"created_at": real_transition, "updated_at": touched_since}
        ageing = server._ageing(legacy, "application_response", targets={"application_response": 72})
        assert ageing["hours"] < 3
        assert ageing["overdue"] is False


class TestAgeing:
    TARGETS = {"application_response": 72, "draft_review": 48}

    def test_no_timestamp_is_none_not_zero(self):
        """A record whose age we cannot compute is not a fresh one, and
        drawing it as "waiting 0 minutes" is a claim we cannot make."""
        assert server._ageing({}, "draft_review", targets=self.TARGETS) is None

    def test_an_age_with_no_target_still_reports_the_age(self):
        """Half the places this appears — a closed collaboration, a live
        campaign — have no target by design, and "how long has this been like
        this" is still worth saying."""
        block = server._ageing({"state_since": _at(30)}, None, targets=self.TARGETS)
        assert block["sla_hours"] is None
        assert block["overdue"] is False
        assert "waiting" in block["label"]

    @pytest.mark.parametrize(
        "hours,tone",
        [(1, "calm"), (30, "calm"), (40, "due"), (80, "overdue"), (200, "critical")],
    )
    def test_four_bands_not_two(self, hours, tone):
        """"Fine" and "on fire" leaves nothing to say about the record that is
        about to become a problem — which is the one somebody can still act on.
        """
        block = server._ageing(
            {"state_since": _at(hours)}, "application_response", targets=self.TARGETS
        )
        assert block["tone"] == tone

    def test_every_tone_is_one_of_the_declared_four(self):
        for hours in (0, 1, 12, 36, 48, 73, 145, 1000):
            block = server._ageing(
                {"state_since": _at(hours)}, "application_response", targets=self.TARGETS
            )
            assert block["tone"] in server.SLA_TONES

    def test_overdue_carries_how_far_over(self):
        """Sorting by "how far overdue" is the whole point of the escalation
        list, so the number has to be on the row rather than recomputed by
        whoever is drawing it."""
        block = server._ageing(
            {"state_since": _at(100)}, "application_response", targets=self.TARGETS
        )
        assert block["overdue"] is True
        assert 27 < block["overdue_hours"] < 29

    def test_the_label_says_hours_below_two_days(self):
        """"waiting 0 days" is what a two-hour-old record would otherwise read
        as, and that is the record nobody needs to look at."""
        assert "hr" in server._ageing({"state_since": _at(5)}, None)["label"]
        assert "day" in server._ageing({"state_since": _at(100)}, None)["label"]

    def test_a_future_timestamp_reads_as_no_age_rather_than_negative(self):
        """Clock skew between an app server and the database is real, and
        "waiting -3 hours" is a number nobody can act on."""
        block = server._ageing({"state_since": _at(-5)}, None)
        assert block["seconds"] == 0


class TestSlaTable:
    def test_every_target_the_product_promised_is_there(self):
        """The nine states somebody is waiting on, with the numbers the
        operation agreed to."""
        assert server.SLA_DEFAULT_HOURS == {
            "creator_verification": 48,
            "brand_verification": 48,
            "campaign_review": 24,
            "application_response": 72,
            "commercial_agreement": 72,
            "slot_booking": 48,
            "draft_review": 48,
            "content_submission": 72,
            "payment": 168,
        }

    def test_every_target_has_a_label_and_a_sentence(self):
        """Half of these measure our delay and half somebody else's, and an
        operator reading the settings list has to be able to tell which."""
        assert set(server.SLA_LABELS) == set(server.SLA_DEFAULT_HOURS)
        for key, (label, blurb) in server.SLA_LABELS.items():
            assert label and blurb.endswith("."), key

    def test_every_collaboration_state_maps_to_a_target_or_deliberately_none(self):
        """A state that is nobody's delay is absent on purpose: `slot_booked`
        waits on a date in the future rather than on a person, and the terminal
        states are finished. Absent means "no clock", never "zero"."""
        clocked = set(server._SLA_BY_COLLAB_STATE)
        assert clocked <= set(server.COLLAB_STATE_ORDER)
        assert "slot_booked" not in clocked
        for terminal in server.TERMINAL_COLLAB_STATES:
            assert terminal not in clocked
        assert all(v in server.SLA_DEFAULT_HOURS for v in server._SLA_BY_COLLAB_STATE.values())


class TestSlaOverrides:
    def test_unknown_keys_and_unusable_values_are_dropped(self):
        """A stored setting is data somebody typed, and it outlives them."""
        cleaned = server._clean_sla_overrides(
            {"draft_review": 12, "not_a_target": 5, "payment": "soon", "campaign_review": None}
        )
        assert cleaned == {"draft_review": 12}

    def test_zero_is_refused(self):
        """It would mean "overdue the instant it arrives", which is not a
        policy anybody wants and is what an empty number field posts."""
        assert server._clean_sla_overrides({"payment": 0}) == {}
        assert server._clean_sla_overrides({"payment": -4}) == {}

    def test_an_absurd_number_is_refused(self):
        assert server._clean_sla_overrides({"payment": 24 * 365}) == {}

    def test_overrides_are_partial_and_lay_over_the_defaults(self):
        """Adding a tenth target to the table must ship with a sensible number
        rather than being silently unset on every install that ever saved this
        form."""
        merged = {**server.SLA_DEFAULT_HOURS, **server._clean_sla_overrides({"payment": 24})}
        assert merged["payment"] == 24
        assert merged["draft_review"] == server.SLA_DEFAULT_HOURS["draft_review"]
        assert set(merged) == set(server.SLA_DEFAULT_HOURS)


# ---------------------------------------------------------------------------
# Chasing, escalation and expiry, driven against a real database
# ---------------------------------------------------------------------------

LOOP = None


def _run(body):
    """One loop per call, kept in a module global.

    `asyncio.get_event_loop()` fails inside a pytest-xdist worker thread, and
    `asyncio.run` closes the loop mongomock's cursors were built on.
    """
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()

    async def go():
        db = AsyncMongoMockClient()["clock"]
        original = server.db
        server.db = db
        # The targets are cached for thirty seconds, which across a test run is
        # thirty seconds of one test's database answering another's question.
        server._SLA_CACHE["at"] = None
        try:
            return await body(db)
        finally:
            server.db = original
            server._SLA_CACHE["at"] = None

    return LOOP.run_until_complete(go())


def _collab(db, **over):
    from bson import ObjectId

    doc = {
        "campaign_id": over.pop("campaign_id", ObjectId()),
        "creator_id": over.pop("creator_id", ObjectId()),
        "state": "commercial_agreed",
        "state_since": datetime.now(timezone.utc) - timedelta(days=9),
        "created_at": datetime.now(timezone.utc) - timedelta(days=20),
    }
    doc.update(over)
    return doc


class TestTheChaserStopsOnItsOwn:
    """**Two, and then never again.** Chasing somebody a third time about the
    same row is how a WhatsApp channel stops being read, and this operation
    runs entirely on that channel."""

    def test_it_sends_twice_and_then_stops(self):
        async def body(db):
            from bson import ObjectId

            campaign_id = (
                await db.campaigns.insert_one(
                    {"brand_id": ObjectId(), "title": "Toit tasting", "status": "open"}
                )
            ).inserted_id
            await db.collaborations.insert_one(_collab(db, campaign_id=campaign_id))
            sent = []
            for _ in range(4):
                report = await server.run_lifecycle_chasers()
                sent.append(report["book_slot"])
                # Wind the spacing back so the next pass is due, which is what
                # a day passing does in the real world.
                await db.collaborations.update_many(
                    {},
                    {
                        "$set": {
                            "reminders.book_slot.last_at": datetime.now(timezone.utc)
                            - timedelta(days=3)
                        }
                    },
                )
            return sent

        assert _run(body) == [1, 1, 0, 0]

    def test_a_second_pass_straight_away_sends_nothing(self):
        """**Spacing, not just a cap.** Two reminders inside a minute is one
        reminder and one bug, and the loop can legitimately run more than once
        an hour."""

        async def body(db):
            from bson import ObjectId

            campaign_id = (
                await db.campaigns.insert_one(
                    {"brand_id": ObjectId(), "title": "Toit", "status": "open"}
                )
            ).inserted_id
            await db.collaborations.insert_one(_collab(db, campaign_id=campaign_id))
            first = await server.run_lifecycle_chasers()
            second = await server.run_lifecycle_chasers()
            return first["book_slot"], second["book_slot"]

        assert _run(body) == (1, 0)

    def test_advancing_the_state_stops_it_with_no_branch_that_has_to_notice(self):
        """The claim carries the state as a precondition, so a collaboration
        that moved is simply not matched. "Stops once the state advances" is
        structural rather than remembered."""

        async def body(db):
            from bson import ObjectId

            campaign_id = (
                await db.campaigns.insert_one(
                    {"brand_id": ObjectId(), "title": "Toit", "status": "open"}
                )
            ).inserted_id
            row = await db.collaborations.insert_one(
                _collab(db, campaign_id=campaign_id)
            )
            await db.collaborations.update_one(
                {"_id": row.inserted_id},
                {"$set": server._state_stamp("slot_booked")},
            )
            return await server.run_lifecycle_chasers()

        assert _run(body)["book_slot"] == 0

    def test_nothing_is_chased_before_its_target(self):
        async def body(db):
            from bson import ObjectId

            campaign_id = (
                await db.campaigns.insert_one(
                    {"brand_id": ObjectId(), "title": "Toit", "status": "open"}
                )
            ).inserted_id
            await db.collaborations.insert_one(
                _collab(
                    db,
                    campaign_id=campaign_id,
                    state_since=datetime.now(timezone.utc) - timedelta(hours=2),
                )
            )
            return await server.run_lifecycle_chasers()

        assert _run(body)["book_slot"] == 0

    def test_the_claim_itself_refuses_a_state_that_moved(self):
        """**The race guard, tested where the race is.**

        The test above passes even with the precondition removed, because the
        *query* already excludes a collaboration that moved — which is exactly
        why that test is not enough. The window this closes is between the
        query and the claim: a brand accepting in that instant would otherwise
        get a reminder about a state the row is no longer in. Found by deleting
        the precondition and watching the suite stay green.
        """

        async def body(db):
            row = await db.collaborations.insert_one(
                _collab(db, state="slot_booked")
            )
            return await server._claim_reminder(
                row.inserted_id,
                "book_slot",
                "commercial_agreed",
                datetime.now(timezone.utc),
            )

        assert _run(body) is False

    def test_the_claim_is_the_write_so_two_workers_send_once(self):
        """Two passes overlapping is a real thing on a restart. The counter is
        incremented inside the same operation that checks it."""

        async def body(db):
            row = await db.collaborations.insert_one(_collab(db))
            now = datetime.now(timezone.utc)
            first = await server._claim_reminder(
                row.inserted_id, "book_slot", "commercial_agreed", now
            )
            second = await server._claim_reminder(
                row.inserted_id, "book_slot", "commercial_agreed", now
            )
            return first, second

        assert _run(body) == (True, False)

    def test_a_never_reminded_row_is_matched(self):
        """`$lt` skips a missing field. The claim uses `$not: {$gte: n}` for
        exactly this reason, and without it the *first* reminder never sends —
        which is the failure mode that looks like the feature not existing."""
        assert '"$not": {"$gte": MAX_REMINDERS}' in _source()

    def test_the_five_reminders_the_product_promised_all_exist(self):
        assert set(server._reminder_kinds()) == {
            "book_slot",
            "shoot_tomorrow",
            "content_due",
            "draft_review",
            "applications_waiting",
        }

    def test_every_reminder_has_a_notification_event(self):
        """A reminder with no event cannot reach a phone, and this product's
        entire operating channel is WhatsApp."""
        for kind in server._reminder_kinds():
            assert f"reminder_{kind}" in server.NOTIFY_EVENTS, kind


class TestLateDelivery:
    def test_the_grace_is_on_top_of_the_target_not_instead_of_it(self):
        """**Two events, two consequences.** Passing the target means we chase
        — somebody is waiting and a nudge is proportionate. Passing the target
        *and* the grace is what gets written down against the creator, and a
        mark on somebody's record should not be the same event as a reminder.
        """

        async def body(db):
            from bson import ObjectId

            campaign_id = (
                await db.campaigns.insert_one(
                    {"brand_id": ObjectId(), "title": "Toit", "status": "open"}
                )
            ).inserted_id
            # Past the 72h target, inside the 24h grace.
            await db.collaborations.insert_one(
                _collab(
                    db,
                    campaign_id=campaign_id,
                    state="attended",
                    state_since=datetime.now(timezone.utc) - timedelta(hours=80),
                )
            )
            chased = await server.run_lifecycle_chasers()
            row = await db.collaborations.find_one({})
            return chased, row.get("content_overdue")

        report, overdue = _run(body)
        assert report["content_due"] == 1, "they should have been reminded"
        assert overdue is None, "and not yet marked late"

    def test_past_the_grace_it_is_written_down(self):
        async def body(db):
            from bson import ObjectId

            campaign_id = (
                await db.campaigns.insert_one(
                    {"brand_id": ObjectId(), "title": "Toit", "status": "open"}
                )
            ).inserted_id
            await db.collaborations.insert_one(
                _collab(
                    db,
                    campaign_id=campaign_id,
                    state="attended",
                    state_since=datetime.now(timezone.utc) - timedelta(hours=200),
                )
            )
            report = await server.run_lifecycle_chasers()
            row = await db.collaborations.find_one({})
            audited = await db.audit_log.find_one({"action": "collaboration.content_overdue"})
            return report, row.get("content_overdue"), audited

        report, overdue, audited = _run(body)
        assert report["content_flagged_overdue"] == 1
        assert overdue is True
        assert audited, "a mark against a creator with no audit line is a mark nobody can explain"
        assert audited["actor_role"] == "system"

    def test_it_is_flagged_once_however_many_passes_run(self):
        async def body(db):
            from bson import ObjectId

            campaign_id = (
                await db.campaigns.insert_one(
                    {"brand_id": ObjectId(), "title": "Toit", "status": "open"}
                )
            ).inserted_id
            await db.collaborations.insert_one(
                _collab(
                    db,
                    campaign_id=campaign_id,
                    state="attended",
                    state_since=datetime.now(timezone.utc) - timedelta(hours=200),
                )
            )
            for _ in range(3):
                await server.run_lifecycle_chasers()
            return await db.audit_log.count_documents(
                {"action": "collaboration.content_overdue"}
            )

        assert _run(body) == 1

    def test_lateness_counts_against_on_time_delivery(self):
        """The only signal a brand has about whether somebody turns work in.
        Delivering eventually does not make a delivery not have been late."""
        source = inspect.getsource(server._delivery_history)
        assert '{"$ne": ["$content_overdue", True]}' in source


class TestExpiry:
    def test_an_invitation_lapses_on_read_not_only_on_a_sweep(self):
        """**The sweep is a tidy-up, not the enforcement.** The alternative is
        an Accept button whose availability depends on whether cron ran."""
        sent = datetime.now(timezone.utc) - timedelta(days=30)
        assert server._invitation_lapsed({"state": "sent", "created_at": sent}) is True
        fresh = datetime.now(timezone.utc) - timedelta(days=1)
        assert server._invitation_lapsed({"state": "sent", "created_at": fresh}) is False

    def test_a_lapsed_invitation_is_not_open(self):
        """**`open` is what every surface reads**, and it is what decides
        whether an Accept button is drawn. A deadline the serializer does not
        honour is a button that 404s — found by deleting the check from `open`
        and watching the whole suite stay green.
        """
        old = datetime.now(timezone.utc) - timedelta(days=30)
        campaign = {"status": "open", "title": "Toit"}
        row = server._serialize_invitation(
            {"_id": "x", "campaign_id": "y", "state": "sent", "created_at": old},
            campaign,
        )
        assert row["lapsed"] is True
        assert row["open"] is False
        assert row["respond_by"], "the row has to say when it ran out"

    def test_a_live_invitation_inside_its_window_is_open(self):
        fresh = datetime.now(timezone.utc) - timedelta(days=1)
        row = server._serialize_invitation(
            {"_id": "x", "campaign_id": "y", "state": "sent", "created_at": fresh},
            {"status": "open", "title": "Toit"},
        )
        assert row["open"] is True and row["lapsed"] is False

    def test_a_lapsed_invitation_cannot_be_answered(self):
        """The serializer hiding the button is a courtesy; this is the rule."""
        old = datetime.now(timezone.utc) - timedelta(days=30)
        with pytest.raises(Exception) as caught:
            server._refuse_unanswerable_invitation(
                {"state": "sent", "created_at": old}
            )
        assert caught.value.status_code == 409
        assert caught.value.detail["code"] == "invitation_lapsed"

    def test_an_answered_invitation_never_lapses(self):
        """It was answered. Nothing about a deadline changes that."""
        old = datetime.now(timezone.utc) - timedelta(days=90)
        assert server._invitation_lapsed({"state": "accepted", "created_at": old}) is False

    def test_a_row_written_before_the_field_derives_its_deadline(self):
        """The usual absent-reads-safe rule. An invitation from last year
        lapsing the moment this deploys is correct — it lapsed long ago, we
        simply had no way to say so."""
        sent = datetime.now(timezone.utc) - timedelta(days=3)
        deadline = server._invitation_deadline({"created_at": sent})
        assert deadline == sent + timedelta(days=server.INVITATION_RESPONSE_DAYS)

    def test_a_stored_deadline_wins_over_the_derived_one(self):
        """So moving INVITATION_RESPONSE_DAYS later cannot retroactively
        shorten an offer somebody is already holding."""
        sent = datetime.now(timezone.utc) - timedelta(days=3)
        stored = sent + timedelta(days=60)
        assert server._invitation_deadline({"created_at": sent, "respond_by": stored}) == stored

    def test_both_answers_go_through_one_guard(self):
        """Accept and decline must agree about what "still open" means, or an
        invitation is declinable a fortnight after it lapsed but not
        acceptable — a rule nobody wrote down."""
        for fn in (server.accept_invitation, server.decline_invitation):
            assert "_refuse_unanswerable_invitation(invite)" in inspect.getsource(fn)

    def test_the_two_refusals_read_differently(self):
        """"You already answered" and "the offer ran out" are different facts,
        and answering both with one sentence tells somebody they replied when
        they did not."""
        source = inspect.getsource(server._refuse_unanswerable_invitation)
        assert "already answered" in source
        assert "invitation_lapsed" in source

    def test_an_unanswered_application_expires_when_the_campaign_starts(self):
        async def body(db):
            from bson import ObjectId

            campaign_id = (
                await db.campaigns.insert_one(
                    {
                        "brand_id": ObjectId(),
                        "title": "Toit tasting",
                        "status": "open",
                        "event_date": datetime.now(timezone.utc) - timedelta(days=1),
                    }
                )
            ).inserted_id
            await db.collaborations.insert_one(
                _collab(db, campaign_id=campaign_id, state="applied")
            )
            report = await server.run_lifecycle_chasers()
            row = await db.collaborations.find_one({})
            told = await db.notifications.find_one({"event": "application_expired"})
            return report["applications_expired"], row["state"], told

        count, state, told = _run(body)
        assert count == 1
        assert state == "expired"
        assert told, "a state change they discover months later is barely better than silence"

    def test_expired_is_its_own_exit_and_not_a_rejection(self):
        """Nobody decided. "Declined" and "nobody ever answered" are very
        different facts about a creator, and on their own history the
        difference is the whole point."""
        assert "expired" in server.TERMINAL_COLLAB_STATES
        assert "expired" in server.COLLAB_GROUP_ENDED
        assert "expired" in server._PROCESS_BANNERS
        assert "expired" in server._NEXT_ACTION

    def test_the_creator_is_told_it_was_not_about_them(self):
        banner = server._PROCESS_BANNERS["expired"]
        assert "Nothing you did" in banner[2]

    def test_a_live_campaign_expires_nothing(self):
        """A brief that is merely old is still one somebody might answer
        tomorrow."""

        async def body(db):
            from bson import ObjectId

            campaign_id = (
                await db.campaigns.insert_one(
                    {
                        "brand_id": ObjectId(),
                        "title": "Toit",
                        "status": "open",
                        "event_date": datetime.now(timezone.utc) + timedelta(days=30),
                    }
                )
            ).inserted_id
            await db.collaborations.insert_one(
                _collab(db, campaign_id=campaign_id, state="applied")
            )
            report = await server.run_lifecycle_chasers()
            return report["applications_expired"]

        assert _run(body) == 0

    def test_a_stale_draft_is_flagged_and_never_tidied_away(self):
        """It is the brand's own unpublished work. A platform that deletes
        somebody's draft is one they stop trusting with a draft."""
        old = {"status": "draft", "updated_at": datetime.now(timezone.utc) - timedelta(days=45)}
        assert server._draft_is_stale(old) is True
        assert server._draft_is_stale({"status": "draft", "updated_at": datetime.now(timezone.utc)}) is False
        # Flagged and nothing else: the check reads campaigns and builds
        # rows, and touches no writing method at all.
        health = inspect.getsource(server.admin_health)
        block = health[health.index("stale_drafts = [") : health.index('"key": "stale_drafts"')]
        for write in ("update_one", "update_many", "delete_one", "delete_many"):
            assert write not in block


class TestEscalation:
    def test_the_overdue_list_is_sorted_by_how_far_over_not_by_age(self):
        """A creator verification two days past a 48-hour target is a worse
        failure than a payment two days past a seven-day one — the second is
        nearly on time. Sorting by age puts them the other way round."""

        async def body(db):
            from bson import ObjectId

            brand_id = ObjectId()
            campaign_id = (
                await db.campaigns.insert_one(
                    {"brand_id": brand_id, "title": "Toit", "status": "open"}
                )
            ).inserted_id
            # Older in absolute terms, barely over its seven-day target.
            await db.collaborations.insert_one(
                _collab(
                    db,
                    campaign_id=campaign_id,
                    state="content_approved",
                    state_since=datetime.now(timezone.utc) - timedelta(days=8),
                )
            )
            # Younger, but four days past a 24-hour target.
            await db.campaigns.insert_one(
                {
                    "brand_id": brand_id,
                    "title": "Waiting on us",
                    "status": server.CAMPAIGN_REVIEW_STATUS,
                    "submitted_for_review_at": datetime.now(timezone.utc)
                    - timedelta(days=5),
                }
            )
            targets = await server.sla_targets()
            return await server._overdue_check(targets, datetime.now(timezone.utc))

        check = _run(body)
        assert [i["sla_key"] for i in check["items"]] == ["campaign_review", "payment"]

    def test_the_generic_sort_does_not_undo_it(self):
        """The health panel re-sorts every check by severity then oldest-first,
        which is right for the other eight and actively wrong for this one."""
        assert '"presorted": True' in inspect.getsource(server._overdue_check)
        assert 'if not c.get("presorted"):' in inspect.getsource(server.admin_health)

    def test_every_kind_of_record_can_appear_in_it(self):
        """A record can be missing from all eight other checks and still be
        four days over. "Never let an overdue record be invisible" is the
        promise this one keeps."""
        source = inspect.getsource(server._overdue_check)
        for reader in (
            "_collab_ageing",
            "_campaign_review_ageing",
            "_brand_review_ageing",
            "_creator_review_ageing",
        ):
            assert reader in source

    def test_escalation_follows_execution_owner(self):
        """The same routing a new application takes. A brand that handed us a
        campaign is not the party to chase about it."""
        source = inspect.getsource(server._escalate_to_whoever_runs_it)
        assert "_execution_owner(campaign)" in source
        assert "notify_weare_team" in source
        assert "notify_brand_manager" in source

    def test_a_brand_run_escalation_copies_admin(self):
        """An overdue record is an operational fact about the platform as well
        as a job for the brand — and the brand going quiet is exactly the case
        somebody here needs to know about."""

        async def body(db):
            from bson import ObjectId

            admin_id = (
                await db.users.insert_one({"role": "admin", "name": "Admin"})
            ).inserted_id
            brand_id = ObjectId()
            campaign = {
                "_id": ObjectId(),
                "brand_id": brand_id,
                "title": "Toit",
                "execution_owner": "brand",
            }
            await server._escalate_to_whoever_runs_it(
                campaign, "content_overdue", title="t", body="b"
            )
            return await db.notifications.count_documents({"user_id": admin_id})

        assert _run(body) == 1

    def test_a_weare_run_escalation_does_not_go_to_the_brand(self):
        """They handed it over. Being chased about work they asked us to run is
        the thing handing it over was meant to stop."""

        async def body(db):
            from bson import ObjectId

            brand_user = (
                await db.users.insert_one(
                    {"role": "brand_manager", "name": "Toit", "brand_id": ObjectId()}
                )
            ).inserted_id
            manager_id = (
                await db.users.insert_one({"role": "campaign_manager", "name": "Riya"})
            ).inserted_id
            campaign = {
                "_id": ObjectId(),
                "brand_id": (await db.users.find_one({"_id": brand_user}))["brand_id"],
                "title": "Toit",
                "execution_owner": "weare",
                "manager_id": manager_id,
            }
            await server._escalate_to_whoever_runs_it(
                campaign, "content_overdue", title="t", body="b"
            )
            return (
                await db.notifications.count_documents({"user_id": brand_user}),
                await db.notifications.count_documents({"user_id": manager_id}),
            )

        assert _run(body) == (0, 1)


# ---------------------------------------------------------------------------
# The screens
# ---------------------------------------------------------------------------

FRONTEND = pathlib.Path(server.__file__).resolve().parents[1] / "frontend" / "src"


def _no_comments(path: pathlib.Path) -> str:
    import re

    src = re.sub(r"\{/\*.*?\*/\}", "", path.read_text(), flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


class TestTheBrowserHoldsNoSecondPolicy:
    """**The bug this class exists to stop coming back.**

    The console carried its own `isStale` with a flat 48 hours — a second
    definition of "too long", written when there was only one kind of queue
    row. Against nine real targets it was simply wrong in both directions: it
    called a payment overdue on day three of seven, and a campaign review fine
    on day two of one. The server decides now and sends the verdict.
    """

    def test_no_threshold_constant_survives_in_the_console(self):
        offenders = []
        for path in (FRONTEND / "components").rglob("*.jsx"):
            source = _no_comments(path)
            for smell in ("STALE_AFTER_HOURS", "isStale(", "OVERDUE_AFTER"):
                if smell in source:
                    offenders.append(f"{path.name}: {smell}")
        assert offenders == [], (
            "these carry their own idea of how long is too long: " + ", ".join(offenders)
        )

    def test_the_badge_draws_the_server_block_and_computes_nothing(self):
        source = _no_comments(FRONTEND / "components" / "AgeBadge.jsx")
        assert "ageing.tone" in source
        assert "ageing.label" in source
        # No arithmetic on time anywhere in it.
        for smell in ("Date.now()", "3600 * 1000", "new Date(", "getTime()"):
            assert smell not in source, f"the badge recomputes {smell}"

    def test_it_renders_nothing_without_a_block(self):
        """Half the places it appears have no clock by design — a closed
        collaboration, a verified creator, a slot waiting on a date rather than
        on a person. "Waiting 0 minutes" about one of those is an alarm about a
        field nobody filled in."""
        source = _no_comments(FRONTEND / "components" / "AgeBadge.jsx")
        assert "if (!ageing" in source and "return null" in source

    def test_every_tone_the_server_can_send_is_drawn(self):
        """An unrecognised tone would fall through to a default and quietly
        draw a critical record as calm."""
        source = _no_comments(FRONTEND / "components" / "AgeBadge.jsx")
        for tone in server.SLA_TONES:
            assert f"{tone}: {{" in source, tone

    def test_the_queue_sorts_on_the_fraction_of_the_allowance_used(self):
        """Same idea as the server's overdue list: the raw age puts a
        nearly-on-time payment above a badly late review.

        **And it is one scale, not two.** The first version returned
        `1e12 + overdueHours` for overdue rows and a millisecond timestamp for
        the rest — and a current timestamp is about 1.76e12, so every
        un-overdue row outranked every overdue one. Caught in a browser, not by
        a test, which is why this one now names the arithmetic.
        """
        source = _no_comments(FRONTEND / "components" / "admin" / "ActionQueue.jsx")
        assert "a.hours / a.sla_hours" in source
        assert "1e12" not in source, "two incomparable scales in one sort key"

    def test_a_row_with_no_target_sorts_below_every_row_that_has_one(self):
        """It cannot be measured against one, and inventing a position for it
        is what put the bug above on screen."""
        source = _no_comments(FRONTEND / "components" / "admin" / "ActionQueue.jsx")
        block = source.split("value: (i) => {")[1].split("},")[0]
        assert "-1 / (hours + 1)" in block, (
            "un-targeted rows need a key that is always below the targeted ones"
        )

    def test_the_state_labels_cover_every_exit(self):
        """A state with no label renders as its wire value, and "expired" in a
        table cell reads as a bug rather than as a fact."""
        source = _no_comments(FRONTEND / "components" / "admin" / "shared.jsx")
        for state in server.TERMINAL_COLLAB_STATES:
            assert f"{state}: {{ label:" in source, state

    def test_neither_new_exit_is_drawn_as_a_rejection(self):
        """A withdrawal is the creator's own decision before anybody was
        committed; an expiry is a decision nobody made. Red belongs to
        neither."""
        source = _no_comments(FRONTEND / "components" / "admin" / "console" / "tokens.js")
        for state in ("withdrawn", "expired"):
            assert f'{state}: "idle"' in source, state


class TestTheSettingsScreenExists:
    """A backend flow with no UI is not shipped, whatever the tests say — the
    rule this repository learned from four verification endpoints that had no
    caller anywhere in the frontend for months."""

    def test_the_editor_calls_both_ends_of_the_route(self):
        source = _no_comments(FRONTEND / "components" / "admin" / "SlaSettings.jsx")
        assert 'api.get("/admin/settings/sla")' in source
        assert 'api.put("/admin/settings/sla"' in source

    def test_it_is_reachable_from_the_navigation(self):
        sidebar = _no_comments(
            FRONTEND / "components" / "admin" / "console" / "Sidebar.jsx"
        )
        assert 'key: "settings"' in sidebar
        assert "adminOnly: true" in sidebar.split('key: "settings"')[1][:300], (
            "an SLA is the standard a scoped queue is measured against — "
            "somebody being measured must not be able to move the line"
        )
        app = _no_comments(FRONTEND / "src" / "App.js") if (FRONTEND / "src").exists() else _no_comments(FRONTEND / "App.js")
        assert 'path="settings"' in app

    def test_it_offers_a_way_back_to_the_default(self):
        """A settings screen that cannot tell you what it started as is one
        nobody dares touch."""
        source = _no_comments(FRONTEND / "components" / "admin" / "SlaSettings.jsx")
        assert "defaults" in source and "IDS.reset" in source

    def test_it_saves_only_what_changed(self):
        """Sending the whole map would write nine overrides the moment somebody
        changes one, and then "back to default" has nothing left to mean."""
        source = _no_comments(FRONTEND / "components" / "admin" / "SlaSettings.jsx")
        assert "const changed = Object.keys(form).filter(" in source


class TestTheHealthRowsOfferAWayOut:
    def test_underfilling_rows_carry_the_three_actions(self):
        source = _source()
        block = source[
            source.index('"key": "underfilling"') - 3000 : source.index('"key": "underfilling"')
        ]
        for action in ("Invite creators", "Extend the dates", "Ask for fewer"):
            assert action in block, action

    def test_the_panel_draws_them(self):
        source = _no_comments(FRONTEND / "components" / "admin" / "Health.jsx")
        assert "item.actions" in source
        assert "item.slots_short" in source

    def test_a_row_with_actions_does_not_nest_an_anchor_in_an_anchor(self):
        """**Invalid markup, which browsers resolve by dropping one of the
        links** — and the one they drop is not the one you would choose. Same
        stretched-link arrangement the campaign card uses.
        """
        source = _no_comments(FRONTEND / "components" / "admin" / "Health.jsx")
        assert "after:absolute after:inset-0" in source
        assert "relative z-10" in source
