"""The draft review window: a deadline that resolves itself.

Driven against mongomock and read back from the database, the arrangement
`test_money_paths.py` uses — every assertion here is about a stored row or an
audit line, because a window that answered 200 and approved nothing is the
failure this exists to rule out.

The delivery-type campaign is the default scene on purpose: the draft gate
was unreachable on that type until `_own_collab_for_draft` stopped naming
`attended`, so these tests are also the regression for that.
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId
from fastapi import HTTPException, params
from mongomock_motor import AsyncMongoMockClient

import server

LOOP = None


def run(body):
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()

    async def go():
        db = AsyncMongoMockClient()["review_window"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return LOOP.run_until_complete(go())


def _now():
    return datetime.now(timezone.utc)


def _aware(value):
    return value if value is None or value.tzinfo else value.replace(tzinfo=timezone.utc)


ADMIN = {"_id": str(ObjectId()), "role": "admin", "name": "Admin"}


async def _scene(db, *, state="received", campaign_type="delivery", execution_owner="brand",
                 days=None, **collab_extra):
    brand_oid, creator_oid = ObjectId(), ObjectId()
    campaign_oid, collab_oid = ObjectId(), ObjectId()
    await db.users.insert_many([
        {"_id": brand_oid, "role": "brand_manager", "name": "Toit", "brand_id": brand_oid},
        {"_id": creator_oid, "role": "creator", "name": "Asha"},
    ])
    await db.campaigns.insert_one(
        {"_id": campaign_oid, "brand_id": brand_oid, "title": "Hamper drop",
         "status": "in_progress", "campaign_type": campaign_type,
         "execution_owner": execution_owner, "requires_draft_approval": True,
         "compensation_type": "fixed", "budget_per_creator": 8000,
         **({"draft_review_days": days} if days is not None else {})}
    )
    await db.collaborations.insert_one(
        {"_id": collab_oid, "campaign_id": campaign_oid, "creator_id": creator_oid,
         "state": state, "state_since": _now(), "agreed_amount": 8000, "agreed_at": _now(),
         **collab_extra}
    )
    return {
        "collab_id": str(collab_oid), "collab_oid": collab_oid, "campaign_oid": campaign_oid,
        "brand": {"_id": str(brand_oid), "role": "brand_manager", "name": "Toit",
                  "brand_id": brand_oid},
        "creator": {"_id": str(creator_oid), "role": "creator", "name": "Asha"},
        "brand_oid": brand_oid, "creator_oid": creator_oid,
    }


async def _submit(s):
    return await server.submit_draft_link(
        s["collab_id"], server.DraftLinkPayload(draft_url="https://drive.example.com/cut"),
        s["creator"],
    )


async def _row(db, s):
    return await db.collaborations.find_one({"_id": s["collab_oid"]})


async def _audit(db, action):
    return await db.audit_log.find({"action": action}).to_list(length=50)


async def _elapse(db, s, hours=1):
    """Put the deadline in the past, as if the window had run."""
    await db.collaborations.update_one(
        {"_id": s["collab_oid"]},
        {"$set": {"draft_review_deadline_at": _now() - timedelta(hours=hours)}},
    )


def guard_allows(fn, role):
    for p in inspect.signature(fn).parameters.values():
        dep = p.default
        if isinstance(dep, params.Depends) and getattr(dep.dependency, "__name__", "") == "_guard":
            guard = dep.dependency
            break
    else:
        raise AssertionError(f"{fn.__name__} declares no require_roles guard")

    async def go():
        try:
            await guard({"_id": str(ObjectId()), "role": role})
            return True
        except HTTPException:
            return False

    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()
    return LOOP.run_until_complete(go())


# ---------------------------------------------------------------------------
# The prerequisite: a delivery brief can reach the draft gate at all
# ---------------------------------------------------------------------------


class TestADeliveryBriefReachesTheGate:
    def test_a_draft_is_accepted_from_received(self):
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            return await _row(db, s)

        assert run(body)["state"] == "draft_submitted"

    def test_attended_is_not_a_delivery_state(self):
        """The old gate's state, on a delivery brief, is refused — the gate
        reads the campaign's own ready state, not a hardcoded one."""
        async def body(db):
            s = await _scene(db, state="attended")
            with pytest.raises(HTTPException) as err:
                await _submit(s)
            return err.value

        assert run(body).status_code == 409

    def test_a_send_back_returns_a_delivery_brief_to_received(self):
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            await server.request_draft_changes(
                s["collab_id"], server.DraftDecisionPayload(note="Show the label"), s["brand"]
            )
            row = await _row(db, s)
            # …and the next draft is accepted from there.
            await _submit(s)
            return row, await _row(db, s)

        sent_back, resubmitted = run(body)
        assert sent_back["state"] == "received"
        assert resubmitted["state"] == "draft_submitted"

    def test_a_venue_brief_still_uses_attended(self):
        async def body(db):
            s = await _scene(db, state="attended", campaign_type="personal_table")
            await _submit(s)
            return await _row(db, s)

        assert run(body)["state"] == "draft_submitted"


# ---------------------------------------------------------------------------
# The deadline
# ---------------------------------------------------------------------------


class TestTheDeadline:
    def test_it_is_set_on_submission_from_the_campaigns_days(self):
        async def body(db):
            s = await _scene(db, days=5)
            before = _now()
            await _submit(s)
            return before, await _row(db, s)

        before, row = run(body)
        deadline = _aware(row["draft_review_deadline_at"])
        # BSON keeps milliseconds, so the stored value can trail by one.
        slack = timedelta(milliseconds=1)
        assert before + timedelta(days=5) - slack <= deadline <= _now() + timedelta(days=5)

    def test_absent_days_reads_as_the_default(self):
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            return await _row(db, s)

        row = run(body)
        delta = _aware(row["draft_review_deadline_at"]) - _now()
        assert timedelta(days=server.DEFAULT_DRAFT_REVIEW_DAYS - 1) < delta <= timedelta(
            days=server.DEFAULT_DRAFT_REVIEW_DAYS
        )

    @pytest.mark.parametrize("stored", [None, "x", 0, 15, -2])
    def test_an_unusable_stored_value_reads_as_the_default(self, stored):
        assert server._draft_review_days({"draft_review_days": stored}) == 3

    @pytest.mark.parametrize("value,ok", [(0, False), (1, True), (14, True), (15, False)])
    def test_the_campaign_payloads_hold_one_to_fourteen(self, value, ok):
        for model in (server.UpdateCampaignPayload,):
            if ok:
                assert model(draft_review_days=value).draft_review_days == value
            else:
                with pytest.raises(Exception):
                    model(draft_review_days=value)

    def test_a_revision_request_clears_it(self):
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            await server.request_draft_changes(
                s["collab_id"], server.DraftDecisionPayload(note="Show the label"), s["brand"]
            )
            return await _row(db, s)

        assert run(body)["draft_review_deadline_at"] is None

    def test_a_resubmission_starts_a_fresh_window(self):
        async def body(db):
            s = await _scene(db, days=3)
            await _submit(s)
            # Most of the first window used up…
            stale = _now() + timedelta(hours=2)
            await db.collaborations.update_one(
                {"_id": s["collab_oid"]}, {"$set": {"draft_review_deadline_at": stale}}
            )
            await server.request_draft_changes(
                s["collab_id"], server.DraftDecisionPayload(note="Show the label"), s["brand"]
            )
            await _submit(s)
            return stale, await _row(db, s)

        stale, row = run(body)
        assert _aware(row["draft_review_deadline_at"]) > stale + timedelta(days=2)


# ---------------------------------------------------------------------------
# The sweep
# ---------------------------------------------------------------------------


class TestTheSweep:
    def test_an_elapsed_window_reaches_draft_approved_as_the_system(self):
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            await _elapse(db, s)
            report = await server._settle_due_review_windows()
            return s, report, await _row(db, s), await _audit(db, "collaboration.draft_auto_approved")

        s, report, row, lines = run(body)
        assert report["auto_approved"] == 1 and report["ids"] == [s["collab_id"]]
        assert row["state"] == "draft_approved"
        assert row["draft_auto_approved_at"] is not None
        # Never the brand's id: nobody approved it.
        assert row["draft_approved_by"] == "system_auto"
        assert row["draft_approved_by"] != s["brand_oid"]
        assert row["draft_approved_via"] == "review_window_elapsed"
        [line] = lines
        assert line["actor_role"] == "system_auto" and line["actor_id"] is None
        assert line["note"] == "brand_review_window_elapsed"
        assert line["before"]["state"] == "draft_submitted"
        assert line["after"]["state"] == "draft_approved"

    def test_the_disclosure_check_is_not_fabricated(self):
        """`approve_draft` makes a person confirm the label. Nobody looked
        here, so the record says not-reviewed rather than confirmed."""
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            await _elapse(db, s)
            await server._settle_due_review_windows()
            return await _row(db, s)

        row = run(body)
        assert not row.get("draft_disclosure_check")
        assert server._serialize_disclosure_check(row.get("draft_disclosure_check")) is None

    def test_a_window_still_running_is_left_alone(self):
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            report = await server._settle_due_review_windows()
            return report, await _row(db, s)

        report, row = run(body)
        assert report["auto_approved"] == 0 and row["state"] == "draft_submitted"

    def test_running_it_again_approves_nothing_more(self):
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            await _elapse(db, s)
            first = await server._settle_due_review_windows()
            second = await server._settle_due_review_windows()
            return first, second, await _audit(db, "collaboration.draft_auto_approved")

        first, second, lines = run(body)
        assert first["auto_approved"] == 1 and second["auto_approved"] == 0
        assert len(lines) == 1

    def test_two_passes_that_both_selected_the_row_apply_once(self):
        """**Staged rather than gathered.** mongomock does not interleave
        coroutines, so `asyncio.gather` of two sweeps would be answered by the
        first one's read, which proves nothing. What two overlapping passes
        actually do is both select the row and both attempt the write, so that
        is what this does: the conditional write is the only thing that can
        stop the second, and it is the thing under test."""
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            await _elapse(db, s)
            now = _now()
            a = await server._approve_draft_by_window(s["collab_oid"], now)
            b = await server._approve_draft_by_window(s["collab_oid"], now)
            notes = await db.notifications.count_documents({"event": "draft_auto_approved"})
            return a, b, await _audit(db, "collaboration.draft_auto_approved"), notes

        a, b, lines, _ = run(body)
        assert a is not None and b is None
        assert len(lines) == 1

    def test_a_paused_window_is_skipped(self):
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            await _elapse(db, s)
            await db.collaborations.update_one(
                {"_id": s["collab_oid"]}, {"$set": {"draft_review_paused_at": _now()}}
            )
            report = await server._settle_due_review_windows()
            return report, await _row(db, s)

        report, row = run(body)
        assert report["auto_approved"] == 0 and row["state"] == "draft_submitted"

    def test_a_disputed_collaboration_is_treated_as_paused(self):
        """Read off the dispute the freeze already reads — no second flag."""
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            await _elapse(db, s)
            await db.collaborations.update_one(
                {"_id": s["collab_oid"]},
                {"$set": {"dispute": {"state": "open", "raised_by_role": "creator"}}},
            )
            report = await server._settle_due_review_windows()
            return report, await _row(db, s)

        report, row = run(body)
        assert report["auto_approved"] == 0 and row["state"] == "draft_submitted"
        assert server._review_window(row)["frozen_by_dispute"] is True
        assert server._review_window(row)["running"] is False

    def test_a_resolved_dispute_no_longer_holds_it(self):
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            await _elapse(db, s)
            await db.collaborations.update_one(
                {"_id": s["collab_oid"]},
                {"$set": {"dispute": {"state": "resolved"}}},
            )
            return await server._settle_due_review_windows()

        assert run(body)["auto_approved"] == 1

    def test_the_lifecycle_pass_runs_it(self):
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            await _elapse(db, s)
            server._SLA_CACHE.clear()
            report = await server.run_lifecycle_chasers()
            return report, await _row(db, s)

        report, row = run(body)
        assert report["drafts_auto_approved"] == 1 and row["state"] == "draft_approved"

    def test_both_sides_are_told_it_elapsed_rather_than_that_somebody_approved(self):
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            await _elapse(db, s)
            await server._settle_due_review_windows()
            return s, await db.notifications.find({"event": "draft_auto_approved"}).to_list(10)

        s, notes = run(body)
        recipients = {n["user_id"] for n in notes}
        assert s["creator_oid"] in recipients and s["brand_oid"] in recipients
        for n in notes:
            text = f"{n.get('title')} {n.get('body')}".lower()
            assert "window" in text or "within" in text
            assert "the brand approved" not in text


# ---------------------------------------------------------------------------
# The day-before warning
# ---------------------------------------------------------------------------


class TestTheReminder:
    def test_the_reviewer_hears_once_inside_the_last_day(self):
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            await db.collaborations.update_one(
                {"_id": s["collab_oid"]},
                {"$set": {"draft_review_deadline_at": _now() + timedelta(hours=10)}},
            )
            a = await server._settle_due_review_windows()
            b = await server._settle_due_review_windows()
            notes = await db.notifications.find({"event": "draft_review_due_soon"}).to_list(10)
            return s, a, b, notes

        s, a, b, notes = run(body)
        assert a["reminded"] == 1 and b["reminded"] == 0
        assert [n["user_id"] for n in notes] == [s["brand_oid"]]

    def test_not_before_the_last_day(self):
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            return await server._settle_due_review_windows()

        assert run(body)["reminded"] == 0

    def test_an_extension_earns_a_fresh_warning(self):
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            await db.collaborations.update_one(
                {"_id": s["collab_oid"]},
                {"$set": {"draft_review_deadline_at": _now() + timedelta(hours=10)}},
            )
            first = await server._settle_due_review_windows()
            await db.collaborations.update_one(
                {"_id": s["collab_oid"]},
                {"$set": {"draft_review_deadline_at": _now() + timedelta(hours=20)}},
            )
            second = await server._settle_due_review_windows()
            return first, second

        first, second = run(body)
        assert first["reminded"] == 1 and second["reminded"] == 1


# ---------------------------------------------------------------------------
# The admin controls
# ---------------------------------------------------------------------------


class TestTheAdminControls:
    @pytest.mark.parametrize(
        "fn",
        ["extend_draft_review", "pause_draft_review", "resume_draft_review",
         "force_approve_draft", "run_draft_auto_approvals_job"],
    )
    def test_they_are_admin_only(self, fn):
        handler = getattr(server, fn)
        assert guard_allows(handler, "admin")
        for role in ("weare_team", "brand_manager", "campaign_manager", "creator"):
            assert not guard_allows(handler, role), f"{fn} lets {role} through"

    def test_extending_moves_the_deadline_and_counts(self):
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            before = _aware((await _row(db, s))["draft_review_deadline_at"])
            await server.extend_draft_review(
                s["collab_id"], server.ReviewWindowExtendPayload(days=2, reason="Brand away"), ADMIN
            )
            return before, await _row(db, s), await _audit(db, "collaboration.draft_review_extended")

        before, row, lines = run(body)
        assert _aware(row["draft_review_deadline_at"]) == before + timedelta(days=2)
        assert row["draft_review_extensions"] == 1
        [line] = lines
        assert line["note"] == "Brand away" and line["actor_role"] == "admin"
        assert line["before"]["draft_review_deadline_at"] != line["after"]["draft_review_deadline_at"]

    def test_extending_an_elapsed_window_counts_from_now(self):
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            await _elapse(db, s, hours=48)
            await server.extend_draft_review(
                s["collab_id"], server.ReviewWindowExtendPayload(days=1, reason="Brand away"), ADMIN
            )
            return await _row(db, s)

        assert _aware(run(body)["draft_review_deadline_at"]) > _now() + timedelta(hours=23)

    def test_an_extension_needs_a_reason(self):
        with pytest.raises(Exception):
            server.ReviewWindowExtendPayload(days=2, reason="")

    def test_a_pause_holds_the_sweep_and_a_resume_gives_the_time_back(self):
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            deadline = _aware((await _row(db, s))["draft_review_deadline_at"])
            await server.pause_draft_review(
                s["collab_id"], server.ReasonPayload(reason="Checking with legal"), ADMIN
            )
            # Pretend it was paused two days ago, past the original deadline.
            await db.collaborations.update_one(
                {"_id": s["collab_oid"]},
                {"$set": {"draft_review_paused_at": _now() - timedelta(days=2),
                          "draft_review_deadline_at": _now() - timedelta(hours=1)}},
            )
            held = await server._settle_due_review_windows()
            await server.resume_draft_review(
                s["collab_id"], server.ReasonPayload(reason="Legal is happy"), ADMIN
            )
            row = await _row(db, s)
            after = await server._settle_due_review_windows()
            return deadline, held, row, after, await _audit(db, "collaboration.draft_review_paused")

        _, held, row, after, paused_lines = run(body)
        assert held["auto_approved"] == 0
        assert row["draft_review_paused_at"] is None
        # Two days given back on a deadline one hour gone: still running.
        assert _aware(row["draft_review_deadline_at"]) > _now() + timedelta(hours=40)
        assert after["auto_approved"] == 0
        assert len(paused_lines) == 1

    def test_approve_now_is_recorded_as_the_admin_and_not_the_window(self):
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            await server.force_approve_draft(
                s["collab_id"], server.ReasonPayload(reason="Brand confirmed by phone"), ADMIN
            )
            return await _row(db, s), await _audit(db, "collaboration.draft_force_approved")

        row, lines = run(body)
        assert row["state"] == "draft_approved"
        assert row["draft_approved_via"] == "admin_forced"
        assert str(row["draft_approved_by"]) == ADMIN["_id"]
        assert row.get("draft_auto_approved_at") is None
        [line] = lines
        assert line["note"] == "Brand confirmed by phone"

    def test_approve_now_does_not_reach_around_a_dispute(self):
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            await db.collaborations.update_one(
                {"_id": s["collab_oid"]},
                {"$set": {"dispute": {"state": "open", "raised_by_role": "creator"}}},
            )
            with pytest.raises(HTTPException) as err:
                await server.force_approve_draft(
                    s["collab_id"], server.ReasonPayload(reason="Just do it"), ADMIN
                )
            return err.value, await _row(db, s)

        exc, row = run(body)
        assert exc.status_code == 409 and row["state"] == "draft_submitted"

    def test_the_controls_refuse_a_draft_that_is_not_waiting(self):
        async def body(db):
            s = await _scene(db, state="draft_approved")
            with pytest.raises(HTTPException) as err:
                await server.pause_draft_review(
                    s["collab_id"], server.ReasonPayload(reason="Hold it"), ADMIN
                )
            return err.value

        assert run(body).status_code == 409

    def test_the_job_route_reports_the_ids(self):
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            await _elapse(db, s)
            return s, await server.run_draft_auto_approvals_job(ADMIN)

        s, report = run(body)
        assert report["auto_approved"] == 1 and report["ids"] == [s["collab_id"]]

    def test_the_routes_are_actually_served(self):
        """Declared above `include_router(admin_router)`, or they are dead —
        four routes in this file were, for months."""
        from fastapi.routing import APIRoute

        served = {r.endpoint.__name__ for r in server.app.routes if isinstance(r, APIRoute)}
        for name in ("extend_draft_review", "pause_draft_review", "resume_draft_review",
                     "force_approve_draft", "run_draft_auto_approvals_job"):
            assert name in served


# ---------------------------------------------------------------------------
# Lazy settlement on read
# ---------------------------------------------------------------------------


class TestReadingSettlesIt:
    def test_the_application_screen_never_shows_a_window_that_already_ran_out(self):
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            await _elapse(db, s)
            return await server.get_application(s["collab_id"], ADMIN)

        app = run(body)
        assert app["state"] == "draft_approved"
        assert app["draft"]["review_window"]["approved_via"] == "review_window_elapsed"

    def test_the_admin_sees_the_controls_and_the_brand_does_not(self):
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            admin_view = await server.get_application(s["collab_id"], ADMIN)
            brand_view = await server.get_application(s["collab_id"], s["brand"])
            return admin_view, brand_view

        admin_view, brand_view = run(body)
        assert admin_view["actions"]["can_manage_review_window"] is True
        assert brand_view["actions"]["can_manage_review_window"] is False
        window = brand_view["draft"]["review_window"]
        assert window["running"] is True and window["deadline_at"]

    def test_the_creators_dashboard_settles_their_rows(self):
        async def body(db):
            s = await _scene(db)
            await _submit(s)
            await _elapse(db, s)
            await server.get_creator_dashboard(s["creator"])
            return await _row(db, s)

        assert run(body)["state"] == "draft_approved"
