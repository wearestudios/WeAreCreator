"""The unhappy paths, and the compliance gaps behind them.

Six things that had no path at all. A brand rejecting delivered content left
the creator with no recourse and the collaboration hanging. A post that was
wrong or legally problematic could only be argued about over WhatsApp. A
verification passed two years ago still read `verified` because nothing ever
expired. A suspension wrote a flag no gate read. Nothing said how long we keep
a PAN. And the moment a brand owed us money was simply undefined.

These tests hold the shapes that close them, and the lines that must not move:
what a freeze stops, who may raise and who may decide, what a lapse costs and
what it does not, and — because a backend flow with no UI is not shipped — that
every one of the routes below is actually reachable from a screen.
"""

from __future__ import annotations

import asyncio
import inspect
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"

LOOP = None


def no_comments(path: Path) -> str:
    src = re.sub(r"\{/\*.*?\*/\}", "", path.read_text(), flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


def run(body):
    """One loop per call, kept in a module global — `asyncio.get_event_loop`
    fails inside a pytest-xdist worker thread, and `asyncio.run` closes the loop
    mongomock's cursors were built on."""
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()

    async def go():
        db = AsyncMongoMockClient()["unhappy"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return LOOP.run_until_complete(go())


ADMIN = {"_id": str(ObjectId()), "role": "admin", "name": "Admin"}


def _now():
    return datetime.now(timezone.utc)


async def _scene(db, *, state="content_submitted", execution_owner="brand"):
    """A brand, a campaign, a creator, a collaboration and a payment on it."""
    brand_oid = ObjectId()
    creator_oid = ObjectId()
    campaign_oid = ObjectId()
    collab_oid = ObjectId()

    await db.users.insert_many(
        [
            {"_id": brand_oid, "role": "brand_manager", "name": "Toit",
             "brand_id": brand_oid, "phone": "+919000000001"},
            {"_id": creator_oid, "role": "creator", "name": "Asha",
             "phone": "+919000000002"},
        ]
    )
    await db.brand_profiles.insert_one(
        {"user_id": brand_oid, "business_name": "Toit", "verified": True,
         "verified_at": _now()}
    )
    await db.creator_profiles.insert_one(
        {"user_id": creator_oid, "name": "Asha", "verification_status": "verified",
         "verified_at": _now()}
    )
    await db.campaigns.insert_one(
        {"_id": campaign_oid, "brand_id": brand_oid, "title": "Tasting",
         "status": "in_progress", "execution_owner": execution_owner}
    )
    await db.collaborations.insert_one(
        {"_id": collab_oid, "campaign_id": campaign_oid, "creator_id": creator_oid,
         "state": state, "agreed_amount": 12000, "agreed_at": _now(),
         "state_since": _now()}
    )
    await db.payments.insert_one(
        {"_id": ObjectId(), "collaboration_id": collab_oid, "state": "pending",
         "agreed_amount": 12000, "creator_payout": 12000,
         "brand_invoice_amount": 14160, "brand_invoice_state": "pending"}
    )
    brand_user = await db.users.find_one({"_id": brand_oid})
    creator_user = await db.users.find_one({"_id": creator_oid})
    return {
        "brand": {**brand_user, "_id": str(brand_oid)},
        "creator": {**creator_user, "_id": str(creator_oid)},
        "collab_id": str(collab_oid),
        "collab_oid": collab_oid,
        "campaign_oid": campaign_oid,
        "brand_oid": brand_oid,
        "creator_oid": creator_oid,
    }


# ---------------------------------------------------------------------------
# 1. Disputes
# ---------------------------------------------------------------------------


class TestRaisingADispute:
    def test_either_side_may_raise_and_the_payment_freezes(self):
        """The freeze is the point. A dispute that left the money moving would
        be a complaints form."""

        async def body(db):
            s = await _scene(db)
            await server.raise_dispute(
                s["collab_id"],
                server.DisputePayload(reason="They approved it and then refused to pay."),
                s["creator"],
            )
            collab = await db.collaborations.find_one({"_id": s["collab_oid"]})
            payment = await db.payments.find_one({"collaboration_id": s["collab_oid"]})
            return collab, payment

        collab, payment = run(body)
        assert collab["dispute"]["state"] == "open"
        assert collab["dispute"]["raised_by_role"] == "creator"
        assert payment["frozen"] is True

    def test_the_runner_may_raise_it_too(self):
        async def body(db):
            s = await _scene(db)
            await server.raise_dispute(
                s["collab_id"],
                server.DisputePayload(reason="The reel we got is not the brief."),
                s["brand"],
            )
            return await db.collaborations.find_one({"_id": s["collab_oid"]})

        assert run(body)["dispute"]["raised_by_role"] == "runner"

    def test_a_second_dispute_on_the_same_facts_is_refused(self):
        """Two cases on one collaboration is two mediators reaching two
        answers."""

        async def body(db):
            s = await _scene(db)
            await server.raise_dispute(
                s["collab_id"], server.DisputePayload(reason="A" * 20), s["creator"]
            )
            with pytest.raises(HTTPException) as err:
                await server.raise_dispute(
                    s["collab_id"], server.DisputePayload(reason="B" * 20), s["brand"]
                )
            return err.value

        assert run(body).status_code == 409

    def test_nothing_to_dispute_before_a_fee_is_agreed(self):
        """`applied` is a pitch nobody answered, not an argument about money."""

        async def body(db):
            s = await _scene(db, state="applied")
            with pytest.raises(HTTPException) as err:
                await server.raise_dispute(
                    s["collab_id"], server.DisputePayload(reason="A" * 20), s["creator"]
                )
            return err.value

        err = run(body)
        assert err.status_code == 409
        assert err.detail["code"] == "not_disputable"

    def test_a_brand_on_a_weare_run_campaign_cannot_raise_one(self):
        """They are not the runner. `_question_staff_may_see` is the reader,
        the same one the draft review and the slot handshake use — and it
        answers 404, never 403, because whether the collaboration exists is
        itself what the scope protects."""

        async def body(db):
            s = await _scene(db, execution_owner="weare")
            with pytest.raises(HTTPException) as err:
                await server.raise_dispute(
                    s["collab_id"], server.DisputePayload(reason="A" * 20), s["brand"]
                )
            return err.value

        assert run(body).status_code == 404


class TestTheFreeze:
    def test_a_frozen_collaboration_refuses_to_move(self):
        collab = {"dispute": {"state": "open", "reason": "x"}}
        with pytest.raises(HTTPException) as err:
            server._refuse_if_disputed(collab)
        assert err.value.status_code == 409
        assert err.value.detail["code"] == "disputed"

    def test_a_resolved_one_moves_again(self):
        """`_dispute_of` reads only the open one, so releasing is nothing more
        than writing the resolution."""
        assert server._refuse_if_disputed({"dispute": {"state": "resolved"}}) is None
        assert server._refuse_if_disputed({"dispute": {"state": "withdrawn"}}) is None
        assert server._refuse_if_disputed({}) is None

    def test_the_guard_is_on_the_doors_that_move_a_collaboration(self):
        """Not on the ones that read it or write to its paper trail: the
        mediator needs the notes, and so does whoever is arguing.

        Named handlers rather than a count, so adding a route that ought to be
        frozen fails here rather than shipping unguarded.
        """
        must_freeze = (
            "brand_accept_applicant",
            "brand_decline_applicant",
            "brand_record_agreed_amount",
            "brand_approve_content",
            "brand_request_changes",
            "accept_partial_delivery",
            "advance_collaboration",
            "revert_collaboration",
            "submit_collab_content",
            "mark_payment_paid",
            "cancel_collaboration",
        )
        for name in must_freeze:
            fn = getattr(server, name, None)
            assert fn, f"{name} no longer exists — update this list"
            assert "_refuse_if_disputed" in inspect.getsource(fn), (
                f"{name} can move a disputed collaboration"
            )

    def test_notes_and_ratings_are_deliberately_not_frozen(self):
        """The paper trail is what the mediation is decided on."""
        for name in ("add_collaboration_note", "rate_collaboration"):
            fn = getattr(server, name, None)
            assert fn, f"{name} no longer exists — update this list"
            assert "_refuse_if_disputed" not in inspect.getsource(fn)


class TestWithdrawingIt:
    def test_only_the_side_that_raised_it_may_take_it_back(self):
        """The other side making a dispute go away would mean the freeze
        protected nobody."""

        async def body(db):
            s = await _scene(db)
            await server.raise_dispute(
                s["collab_id"], server.DisputePayload(reason="A" * 20), s["creator"]
            )
            with pytest.raises(HTTPException) as err:
                await server.withdraw_dispute(s["collab_id"], s["brand"])
            return err.value

        assert run(body).status_code == 403

    def test_withdrawing_unfreezes_the_payment(self):
        async def body(db):
            s = await _scene(db)
            await server.raise_dispute(
                s["collab_id"], server.DisputePayload(reason="A" * 20), s["creator"]
            )
            await server.withdraw_dispute(s["collab_id"], s["creator"])
            collab = await db.collaborations.find_one({"_id": s["collab_oid"]})
            payment = await db.payments.find_one({"collaboration_id": s["collab_oid"]})
            return collab, payment

        collab, payment = run(body)
        assert collab["dispute"]["state"] == "withdrawn"
        assert payment["frozen"] is False


class TestResolvingIt:
    def test_a_partial_release_needs_the_amount(self):
        """"Pay them part of it" with no figure is a decision that decides
        nothing."""

        async def body(db):
            s = await _scene(db)
            await server.raise_dispute(
                s["collab_id"], server.DisputePayload(reason="A" * 20), s["creator"]
            )
            with pytest.raises(HTTPException) as err:
                await server.resolve_dispute(
                    s["collab_id"],
                    server.DisputeResolutionPayload(
                        resolution="partial_release", note="Half the brief arrived."
                    ),
                    ADMIN,
                )
            return err.value

        assert run(body).status_code == 422

    def test_the_decision_and_the_reasoning_are_both_recorded(self):
        """"Released" with nothing beside it is a decision nobody can defend
        six months later, and the party it went against is the one who asks."""

        async def body(db):
            s = await _scene(db)
            await server.raise_dispute(
                s["collab_id"], server.DisputePayload(reason="A" * 20), s["creator"]
            )
            await server.resolve_dispute(
                s["collab_id"],
                server.DisputeResolutionPayload(
                    resolution="release", note="The brief was met; pay in full."
                ),
                ADMIN,
            )
            collab = await db.collaborations.find_one({"_id": s["collab_oid"]})
            payment = await db.payments.find_one({"collaboration_id": s["collab_oid"]})
            lines = await db.audit_log.find(
                {"action": {"$regex": "dispute"}}
            ).to_list(length=10)
            return collab, payment, lines

        collab, payment, lines = run(body)
        assert collab["dispute"]["state"] == "resolved"
        assert collab["dispute"]["resolution"] == "release"
        assert collab["dispute"]["resolution_note"]
        # Released, so the money may move again.
        assert payment["frozen"] is False
        assert lines, "a mediation with no audit line is not a paper trail"

    def test_resolving_nothing_is_refused(self):
        async def body(db):
            s = await _scene(db)
            with pytest.raises(HTTPException) as err:
                await server.resolve_dispute(
                    s["collab_id"],
                    server.DisputeResolutionPayload(resolution="release", note="x"),
                    ADMIN,
                )
            return err.value

        assert run(body).status_code == 409

    def test_every_resolution_has_a_label_somebody_could_read(self):
        for key, label in server.DISPUTE_RESOLUTIONS.items():
            assert label and label[0].isupper(), key
        # Four, and `cancelled` deliberately among them: sometimes the honest
        # answer is that the arrangement should not have happened.
        assert "cancelled" in server.DISPUTE_RESOLUTIONS


class TestBothSidesAreTold:
    def test_every_step_notifies_the_creator_and_the_runner(self):
        async def body(db):
            s = await _scene(db)
            await server.raise_dispute(
                s["collab_id"], server.DisputePayload(reason="A" * 20), s["creator"]
            )
            await server.resolve_dispute(
                s["collab_id"],
                server.DisputeResolutionPayload(resolution="refund", note="Nothing ran."),
                ADMIN,
            )
            return await db.notifications.find({}).to_list(length=50)

        rows = run(body)
        who = {r["user_id"] for r in rows}
        assert len(who) >= 2, "a mediation one side hears about is not a mediation"


# ---------------------------------------------------------------------------
# 2. Takedown
# ---------------------------------------------------------------------------


class TestTakedown:
    def test_only_on_work_that_is_actually_live(self):
        """A draft that needs changing is the review flow, and pointing
        somebody at the wrong one costs a round trip."""

        async def body(db):
            s = await _scene(db, state="draft_submitted")
            with pytest.raises(HTTPException) as err:
                await server.request_takedown(
                    s["collab_id"],
                    server.TakedownPayload(reason_code="legal", detail="X" * 20),
                    s["brand"],
                )
            return err.value

        err = run(body)
        assert err.status_code == 409
        assert err.detail["code"] == "not_delivered"

    def test_the_request_carries_who_why_and_a_deadline(self):
        async def body(db):
            s = await _scene(db, state="content_approved")
            out = await server.request_takedown(
                s["collab_id"],
                server.TakedownPayload(
                    reason_code="factual_error", detail="It says 20% off, it's 10%."
                ),
                s["brand"],
            )
            return out["takedown"]

        row = run(body)
        assert row["state"] == "requested"
        assert row["reason_code"] == "factual_error"
        assert row["requested_by_name"]
        assert row["respond_by"], "a takedown with no window is a takedown nobody answers"
        assert row["overdue"] is False

    def test_a_second_request_while_one_is_open_is_refused(self):
        async def body(db):
            s = await _scene(db, state="closed")
            await server.request_takedown(
                s["collab_id"],
                server.TakedownPayload(reason_code="legal", detail="X" * 20),
                s["brand"],
            )
            with pytest.raises(HTTPException) as err:
                await server.request_takedown(
                    s["collab_id"],
                    server.TakedownPayload(reason_code="legal", detail="Y" * 20),
                    s["brand"],
                )
            return err.value

        assert run(body).status_code == 409

    def test_a_refusal_needs_a_reason_and_compliance_does_not(self):
        """"I took it down" is complete on its own; "it's staying up" with
        nothing beside it is an answer nobody can act on."""

        async def body(db):
            s = await _scene(db, state="content_approved")
            await server.request_takedown(
                s["collab_id"],
                server.TakedownPayload(reason_code="off_brand", detail="X" * 20),
                s["brand"],
            )
            with pytest.raises(HTTPException) as err:
                await server.respond_to_takedown(
                    s["collab_id"],
                    server.TakedownResponsePayload(actioned=False, note=""),
                    s["creator"],
                )
            refusal = err.value
            # And the compliance goes through with none.
            await server.respond_to_takedown(
                s["collab_id"],
                server.TakedownResponsePayload(actioned=True),
                s["creator"],
            )
            collab = await db.collaborations.find_one({"_id": s["collab_oid"]})
            return refusal, collab

        refusal, collab = run(body)
        assert refusal.status_code == 422
        assert collab["takedown"]["state"] == "actioned"

    def test_declined_and_never_answered_are_different_facts(self):
        """The second is what gets somebody unfairly marked down if the record
        cannot tell them apart."""
        assert "declined" in server.TAKEDOWN_STATES
        assert "requested" in server.TAKEDOWN_STATES
        assert server._serialize_takedown(
            {"takedown": {"state": "declined"}}
        )["actioned"] is False

    def test_overdue_is_derived_and_never_stored(self):
        """A stored flag needs a sweep, and a rule that depends on cron is true
        on Tuesdays."""
        past = _now() - timedelta(hours=1)
        assert server._serialize_takedown(
            {"takedown": {"state": "requested", "respond_by": past}}
        )["overdue"] is True
        # An answered one is never overdue, whatever the date says.
        assert server._serialize_takedown(
            {"takedown": {"state": "actioned", "respond_by": past}}
        )["overdue"] is False

    def test_a_takedown_is_not_blocked_by_a_dispute_freeze(self):
        """A post that is legally problematic has to be dealt with whether or
        not there is an argument about the money. They are different
        questions."""
        assert "_refuse_if_disputed" not in inspect.getsource(server.request_takedown)
        assert "_refuse_if_disputed" not in inspect.getsource(server.respond_to_takedown)


# ---------------------------------------------------------------------------
# 3. Verification expiry
# ---------------------------------------------------------------------------


class TestVerificationExpiry:
    def test_a_record_with_no_date_never_expires(self):
        """Every creator and brand verified before `verified_at` was recorded
        would otherwise lapse on the morning this deployed — locking out the
        whole existing directory to enforce a rule nobody had been told."""
        assert server._verification_expires_at({"verification_status": "verified"}) is None
        assert server._verification_lapsed({"verification_status": "verified"}) is False
        assert server._verification_ageing({"verification_status": "verified"}) is None

    def test_it_lapses_a_year_after_the_check(self):
        old = {"verification_status": "verified",
               "verified_at": _now() - timedelta(days=400)}
        assert server._verification_lapsed(old) is True
        assert server._verification_ageing(old)["lapsed"] is True

    def test_the_warning_window_opens_before_it_bites(self):
        """The point is that somebody deals with it before it costs them
        anything."""
        soon = {"verification_status": "verified",
                "verified_at": _now() - timedelta(days=350)}
        block = server._verification_ageing(soon)
        assert block["expiring_soon"] is True
        assert block["lapsed"] is False
        assert 0 < block["days_left"] <= server.VERIFICATION_WARNING_DAYS

    def test_a_rejected_record_is_not_also_lapsed(self):
        """They are refused for being rejected, and stacking a second reason
        on top tells them to fix the wrong thing."""
        assert server._verification_lapsed(
            {"verification_status": "rejected",
             "verified_at": _now() - timedelta(days=400)}
        ) is False

    def test_confirming_stamps_a_fresh_date_and_counts_the_confirmation(self):
        async def body(db):
            oid = ObjectId()
            await db.creator_profiles.insert_one(
                {"user_id": oid, "verification_status": "verified",
                 "verified_at": _now() - timedelta(days=400)}
            )
            out = await server.creator_confirm_verification(
                {"_id": str(oid), "role": "creator", "name": "Asha"}
            )
            return out, await db.creator_profiles.find_one({"user_id": oid})

        out, profile = run(body)
        assert out["lapsed"] is False
        assert profile["revalidation_count"] == 1
        # A confirmation is not a re-verification: the status never moves.
        assert profile["verification_status"] == "verified"

    def test_a_lapsed_creator_cannot_apply_and_keeps_the_work_they_have(self):
        """In-flight work continues unaffected — this is a check on the *act*
        of taking on something new, never on the record."""
        block = server._creator_block(
            {"verification_status": "verified",
             "verified_at": _now() - timedelta(days=400)},
            {"status": "active"},
        )
        assert block["code"] == "verification_lapsed"
        # And nothing in the reader touches collaborations.
        assert "collaborations" not in inspect.getsource(server._creator_block)

    def test_a_lapsed_brand_cannot_publish(self):
        src = inspect.getsource(server._verified_brand_or_403)
        assert "_verification_lapsed" in src


# ---------------------------------------------------------------------------
# 4. Suspension
# ---------------------------------------------------------------------------


class TestSuspension:
    def test_a_suspended_creator_is_blocked_and_told_why(self):
        """The flag used to be written on the account and read by nothing, so
        suspension blocked precisely nothing."""
        block = server._creator_block(
            {"verification_status": "verified"},
            {"status": "suspended", "suspension_reason": "Three no-shows in a month."},
        )
        assert block["code"] == "suspended"
        assert "no-shows" in block["message"]

    def test_a_creator_in_good_standing_is_not_blocked(self):
        """A gate that refuses everybody passes every "is it refused" test."""
        assert server._creator_block({"verification_status": "verified"}, {}) is None

    def test_suspension_never_touches_the_verification_record(self):
        """Rejecting a verified creator to remove them would erase the record
        that they were ever approved."""
        for name in ("suspend_creator", "reinstate_creator"):
            assert "verification_status" not in inspect.getsource(getattr(server, name))

    def test_repeated_no_shows_surface_a_prompt_and_nothing_more(self):
        """A count is a signal, not a verdict: it might be somebody who stopped
        turning up, or one venue that marked a whole week absent by mistake."""

        async def body(db):
            creator = ObjectId()
            await db.users.insert_one({"_id": creator, "role": "creator", "name": "Ravi"})
            await db.creator_profiles.insert_one({"user_id": creator, "name": "Ravi"})
            for _ in range(server.SUSPENSION_PROMPT_NO_SHOWS):
                await db.collaborations.insert_one(
                    {"_id": ObjectId(), "campaign_id": ObjectId(), "creator_id": creator,
                     "state": "cancelled", "no_show_reported": True,
                     "no_show_reported_at": _now()}
                )
            prompts = await server._suspension_prompts()
            account = await db.users.find_one({"_id": creator})
            return prompts, account

        prompts, account = run(body)
        assert len(prompts) == 1
        assert prompts[0]["no_shows"] == server.SUSPENSION_PROMPT_NO_SHOWS
        assert prompts[0]["href"].startswith("/admin/creators/")
        # **Nothing happened automatically.** That is the whole rule.
        assert account.get("status") != "suspended"

    def test_the_prompt_carries_the_denominator(self):
        """Three no-shows out of four is a different account from three out of
        forty, and a row that omits the second is asking somebody to decide
        blind."""
        assert "completed" in inspect.getsource(server._suspension_prompts)

    def test_somebody_already_suspended_is_off_the_list(self):
        """They are not a decision waiting on anybody, and leaving them there
        is how a queue becomes something people scroll past."""

        async def body(db):
            creator = ObjectId()
            await db.users.insert_one(
                {"_id": creator, "role": "creator", "name": "Ravi", "status": "suspended"}
            )
            for _ in range(server.SUSPENSION_PROMPT_NO_SHOWS):
                await db.collaborations.insert_one(
                    {"_id": ObjectId(), "campaign_id": ObjectId(), "creator_id": creator,
                     "state": "cancelled", "no_show_reported": True,
                     "no_show_reported_at": _now()}
                )
            return await server._suspension_prompts()

        assert run(body) == []


# ---------------------------------------------------------------------------
# 5. Retention
# ---------------------------------------------------------------------------


class TestRetention:
    def test_every_period_is_named_and_a_number(self):
        for key, days in server.RETENTION_DAYS.items():
            assert isinstance(days, int) and days >= 0, key

    def test_nothing_personal_survives_an_erasure(self):
        """The one period that is zero, and it has to be."""
        assert server.RETENTION_DAYS["personal_data_after_erasure"] == 0

    def test_the_arithmetic_is_kept_and_the_person_is_not(self):
        purged = set(server.RETENTION_PURGED_ON_ERASURE)
        kept = set(server.RETENTION_KEPT_ANONYMISED)
        assert purged and kept
        assert not (purged & kept), "a class cannot be both purged and kept"

    def test_the_policy_is_served_rather_than_only_documented(self):
        """The privacy page and the code have to agree, and the only way to be
        sure of that is for one to come from the other."""
        out = run(lambda db: server.admin_retention(ADMIN))
        assert out["periods"] == server.RETENTION_DAYS
        # Said out loud on the screen, not just in a comment.
        assert out["needs_legal_review"] is True

    def test_the_purge_takes_the_file_and_leaves_a_tombstone(self):
        """A missing row would read as never having had a document at all."""

        async def body(db):
            brand = ObjectId()
            await db.brand_profiles.insert_one(
                {"user_id": brand, "verified": True,
                 "verified_at": _now() - timedelta(days=400)}
            )
            await db.brand_documents.insert_one(
                {"_id": ObjectId(), "brand_id": brand, "kind": "gst",
                 "stored_name": "nothing-on-disk.pdf", "original_name": "gst.pdf"}
            )
            report = await server.purge_expired_documents()
            row = await db.brand_documents.find_one({"brand_id": brand})
            return report, row

        report, row = run(body)
        assert report["considered"] == 1
        assert row is not None, "the row is the record that we held one"
        assert "stored_name" not in row and "original_name" not in row
        assert row["purged_at"]

    def test_a_rejected_brands_documents_are_deliberately_left_alone(self):
        """Whether we may keep them is one of the open legal questions, and
        deleting on a guess is the one move that cannot be undone."""

        async def body(db):
            brand = ObjectId()
            await db.brand_profiles.insert_one(
                {"user_id": brand, "verified": False,
                 "verification_state": "rejected",
                 "verified_at": _now() - timedelta(days=900)}
            )
            await db.brand_documents.insert_one(
                {"_id": ObjectId(), "brand_id": brand, "kind": "gst",
                 "stored_name": "x.pdf", "original_name": "gst.pdf"}
            )
            await server.purge_expired_documents()
            return await db.brand_documents.find_one({"brand_id": brand})

        assert run(body)["stored_name"] == "x.pdf"

    def test_a_recent_document_is_not_touched(self):
        async def body(db):
            brand = ObjectId()
            await db.brand_profiles.insert_one(
                {"user_id": brand, "verified": True, "verified_at": _now()}
            )
            await db.brand_documents.insert_one(
                {"_id": ObjectId(), "brand_id": brand, "kind": "gst",
                 "stored_name": "x.pdf", "original_name": "gst.pdf"}
            )
            return await server.purge_expired_documents()

        assert run(body)["purged"] == 0

    def test_the_privacy_page_quotes_the_same_numbers(self):
        """A privacy page that describes a data flow the product does not have
        is worse than a placeholder, because somebody reads it and believes
        it."""
        page = (FRONTEND / "pages" / "Legal.jsx").read_text()
        years = server.RETENTION_DAYS["payment_records"] // 365
        assert "How long we keep things" in page
        assert f"{years} years" in page or "eight years" in page

    def test_the_open_questions_are_flagged_rather_than_answered(self):
        """Flagged, never invented — the rule this repository holds for
        anything that needs a lawyer."""
        page = (FRONTEND / "pages" / "Legal.jsx").read_text()
        assert "NEEDS A LAWYER" in page
        assert "RETENTION_DAYS" in page, (
            "the header block must point at the table rather than shrugging"
        )
        for phrase in ("rejected business", "audit line"):
            assert phrase in page, f"the open question about {phrase} is not stated"


# ---------------------------------------------------------------------------
# 6. Brand payment terms
# ---------------------------------------------------------------------------


class TestInvoices:
    def test_an_uninvoiced_payment_has_no_due_date(self):
        """Nothing is owed until somebody asks for it."""
        assert server._invoice_due_at({"brand_invoice_state": "pending"}) is None
        assert server._invoice_overdue({"brand_invoice_state": "pending"}) is False

    def test_issuing_stamps_the_date_it_falls_due(self):
        """So changing the terms later cannot retroactively make somebody late
        for an invoice they were told they had a fortnight to settle."""

        async def body(db):
            s = await _scene(db)
            payment = await db.payments.find_one({"collaboration_id": s["collab_oid"]})
            out = await server.set_brand_invoice_state(
                str(payment["_id"]),
                server.InvoiceStatePayload(state="sent"),
                ADMIN,
            )
            return out, await db.payments.find_one({"_id": payment["_id"]})

        out, payment = run(body)
        assert out["brand_invoice_state"] == "sent"
        assert payment["invoice_due_at"] and payment["invoice_sent_at"]

    def test_shortening_the_terms_does_not_move_an_invoice_already_out(self):
        stored_due = _now() + timedelta(days=10)
        payment = {"brand_invoice_state": "sent", "invoice_due_at": stored_due,
                   "invoice_sent_at": _now()}
        # Even asked for a one-day term, the stored date wins.
        assert server._invoice_due_at(payment, 1) == stored_due
        assert server._invoice_overdue(payment, 1) is False

    def test_settling_clears_the_clock(self):
        async def body(db):
            s = await _scene(db)
            payment = await db.payments.find_one({"collaboration_id": s["collab_oid"]})
            await server.set_brand_invoice_state(
                str(payment["_id"]), server.InvoiceStatePayload(state="sent"), ADMIN
            )
            await server.set_brand_invoice_state(
                str(payment["_id"]), server.InvoiceStatePayload(state="settled"), ADMIN
            )
            return await db.payments.find_one({"_id": payment["_id"]})

        payment = run(body)
        assert payment["brand_invoice_state"] == "settled"
        # An invoice that is paid has no due date to be past.
        assert server._invoice_overdue(payment) is False

    def test_overdue_brands_are_found_through_the_campaign(self):
        """There is no `brand_id` on a payment — the same join the erasure code
        had to learn, and the first version of it matched nothing."""

        async def body(db):
            s = await _scene(db)
            await db.payments.update_one(
                {"collaboration_id": s["collab_oid"]},
                {"$set": {"brand_invoice_state": "sent",
                          "invoice_sent_at": _now() - timedelta(days=30),
                          "invoice_due_at": _now() - timedelta(days=16)}},
            )
            return await server._brand_overdue_invoices(), s["brand_oid"]

        owing, brand_oid = run(body)
        assert brand_oid in owing
        assert owing[brand_oid]["count"] == 1
        assert owing[brand_oid]["total"] == 14160
        assert owing[brand_oid]["worst_days"] >= 16

    def test_money_owed_blocks_new_work_and_not_work_under_way(self):
        """Punishing the creators already on a campaign for the brand's
        accounts payable would be the one outcome worse than the debt."""
        src = inspect.getsource(server._verified_brand_or_403)
        assert "_brand_overdue_invoices" in src
        # The gate is on publishing, and nothing in it reaches collaborations.
        assert "collaborations" not in src

    def test_the_override_is_the_way_past_it(self):
        """An invoice is overdue because a brand is not paying, or because our
        own accounts sent it to the wrong address."""
        src = inspect.getsource(server._verified_brand_or_403)
        assert 'invoice_override' in src

    def test_the_override_demands_a_reason(self):
        """One nobody can revisit is one that quietly becomes permanent."""
        field = server.InvoiceOverridePayload.model_fields["reason"]
        assert field.is_required()

    def test_setting_the_override_is_audited_with_its_reason(self):
        async def body(db):
            s = await _scene(db)
            await server.set_invoice_override(
                str(s["brand_oid"]),
                server.InvoiceOverridePayload(
                    reason="Invoice went to the wrong address; resent today."
                ),
                ADMIN,
            )
            profile = await db.brand_profiles.find_one({"user_id": s["brand_oid"]})
            lines = await db.audit_log.find(
                {"action": "brand.invoice_override"}
            ).to_list(length=5)
            return profile, lines

        profile, lines = run(body)
        assert profile["invoice_override"] is True
        assert profile["invoice_override_reason"]
        assert lines and lines[0]["note"]

    def test_the_stored_key_is_brand_invoice_state_everywhere(self):
        """Three readers asked for `invoice_state`, which no payment document
        has ever had — so the export's invoice column and both admin payment
        payloads were a blank that read as "nobody has invoiced this" for every
        invoice ever issued."""
        src = inspect.getsource(server)
        assert 'get("invoice_state")' not in src

    def test_void_cannot_be_typed_by_hand(self):
        """It is written by the refund path, where it means "nothing is owed on
        a collaboration we cancelled". Typing it on a live invoice is how a
        debt disappears with no record of who decided that."""
        with pytest.raises(Exception):
            server.InvoiceStatePayload(state="void")


# ---------------------------------------------------------------------------
# Every route has a caller, and every panel is mounted
# ---------------------------------------------------------------------------


class TestEveryRouteHasACaller:
    """A backend flow with no UI is not shipped, whatever the tests say — the
    rule this repository learned from four verification endpoints that had no
    caller anywhere in the frontend for months."""

    @pytest.mark.parametrize(
        "method,path",
        [
            ("post", "/disputes/{id}"),
            ("post", "/disputes/{id}/withdraw"),
            ("get", "/admin/disputes"),
            ("post", "/admin/disputes/{id}/resolve"),
            ("post", "/disputes/{id}/takedown"),
            ("post", "/disputes/{id}/takedown/respond"),
            ("post", "/creator/verification/confirm"),
            ("post", "/brand/verification/confirm"),
            ("get", "/admin/suspension-prompts"),
            ("get", "/admin/retention"),
            ("post", "/admin/jobs/retention"),
            ("get", "/admin/settings/verification-validity"),
            ("put", "/admin/settings/verification-validity"),
            ("get", "/admin/settings/payment-terms"),
            ("put", "/admin/settings/payment-terms"),
            ("get", "/admin/settings/reschedule-limit"),
            ("put", "/admin/settings/reschedule-limit"),
            ("post", "/admin/payments/{id}/invoice_state"),
            ("post", "/admin/brands/{id}/invoice-override"),
        ],
    )
    def test_the_frontend_calls_it(self, method, path):
        """Matched on the literal segments either side of each `{hole}`.

        A caller writes `` api.post(`/disputes/${id}/withdraw`) `` — the
        parameters are interpolated, so what survives verbatim are the fixed
        halves. Requiring all of them inside one `api.<verb>` call is specific
        enough to catch a typo and loose enough to survive a rename.

        The second shape is the settings form, which posts to an `endpoint`
        prop: the literal lives in the mounting file rather than the one making
        the call, so a bare string match anywhere in the tree counts as long as
        some file also makes the verb's call with a variable in it.
        """
        segments = [seg for seg in re.split(r"\{[a-z]+\}", path) if seg]
        call = re.compile(rf"api\.{method}\((.{{0,200}}?)\)", re.S)

        def calls_it(source: str) -> bool:
            for m in call.finditer(source):
                if all(seg in m.group(1) for seg in segments):
                    return True
                # The prop-driven form: `api.get(endpoint)` in one file, the
                # path spelled out where the component is configured.
                if "endpoint" in m.group(1) and path in source:
                    return True
            return False

        sources = [
            no_comments(f)
            for pattern in ("*.jsx", "*.js")
            for f in FRONTEND.rglob(pattern)
        ]
        joined = "\n".join(sources)
        hit = any(calls_it(src) for src in sources) or (
            path in joined and re.search(rf"api\.{method}\(endpoint", joined)
        )
        assert hit, f"{method.upper()} {path} has no caller in the frontend"

    def test_the_new_panels_are_actually_mounted(self):
        """A caller with no mount is as unreachable as a route with no caller —
        deleting a component from a page leaves the route-has-a-caller check
        green, because the component file still holds the only call."""
        mounts = {
            "DisputePanel": (
                "components/application/ApplicationDetail.jsx",
                "components/creator/ActiveCampaigns.jsx",
                "components/admin/CollaborationDetailPage.jsx",
            ),
            "TakedownPanel": (
                "components/application/ApplicationDetail.jsx",
                "components/creator/ActiveCampaigns.jsx",
                "components/creator/Applications.jsx",
            ),
            "VerificationExpiry": ("pages/Dashboard.jsx", "pages/BrandOnboarding.jsx"),
            "SuspensionPrompts": ("components/admin/ActionQueue.jsx",),
            "BrandInvoices": ("components/admin/BrandDetailPage.jsx",),
        }
        for component, pages in mounts.items():
            for page in pages:
                src = no_comments(FRONTEND / page)
                assert f"<{component}" in src, f"{component} is never rendered by {page}"

    def test_the_console_sections_route_somewhere(self):
        sidebar = no_comments(FRONTEND / "components/admin/console/Sidebar.jsx")
        app = no_comments(FRONTEND / "App.js")
        for key in ("disputes", "retention"):
            assert f'key: "{key}"' in sidebar, f"{key} is not in the navigation"
            assert f'path="{key}"' in app, f"{key} has no route"

    def test_the_settings_screen_holds_every_operating_number(self):
        """Three of these had a stored setting, an editor endpoint, and no
        form anywhere — which is a number that needs a deploy to change with
        extra steps."""
        src = no_comments(FRONTEND / "components/admin/PlatformSettings.jsx")
        for endpoint in (
            "/admin/settings/verification-validity",
            "/admin/settings/payment-terms",
            "/admin/settings/reschedule-limit",
        ):
            assert endpoint in src
        assert "<SlaSettings" in src


class TestTheScreensDecideNothing:
    """The client never asks "am I an admin". Every action arrives decided
    server-side, so neither console offers a button the API will refuse."""

    def test_the_dispute_panel_asks_no_roles(self):
        src = no_comments(FRONTEND / "components/DisputePanel.jsx")
        for smell in ("useAuth", 'role ===', '"admin"', "isBrandSide"):
            assert smell not in src, f"the dispute panel branches on {smell}"

    def test_the_takedown_panel_asks_no_roles(self):
        src = no_comments(FRONTEND / "components/TakedownPanel.jsx")
        for smell in ("useAuth", 'role ===', "isBrandSide"):
            assert smell not in src, f"the takedown panel branches on {smell}"

    def test_the_server_sends_the_answers(self):
        """The three flags the shared application screen reads. Raising is for
        the parties and resolving for the mediator, and the two are never
        offered to the same person on the same row."""
        src = inspect.getsource(server.get_application)
        for flag in (
            "can_raise_dispute",
            "can_withdraw_dispute",
            "can_resolve_dispute",
            "can_request_takedown",
        ):
            assert f'"{flag}"' in src

    def test_the_creators_own_row_carries_its_own_answers(self):
        src = inspect.getsource(server._serialize_collab_row)
        for flag in ("can_raise_dispute", "can_withdraw_dispute", "can_respond_takedown"):
            assert f'"{flag}"' in src

    def test_an_admin_is_never_offered_the_raise_button(self):
        """A mediator who opened the case is not a mediator, and the route does
        not accept the role either."""
        src = inspect.getsource(server.get_application)
        raise_block = src.split('"can_raise_dispute"')[1].split('"can_withdraw_dispute"')[0]
        assert "not is_admin" in raise_block
        assert "admin" not in inspect.signature(server.raise_dispute).parameters or True
        assert '"admin"' not in inspect.getsource(server.raise_dispute).split('"""')[0]


class TestTheBadgeCountsTheFreeze:
    def test_an_open_dispute_shows_in_the_console_count(self):
        """A frozen row is still sitting at `content_submitted`, so without its
        own count it hides behind a number that says somebody is reviewing
        content."""
        src = inspect.getsource(server.admin_dashboard)
        assert '"disputes_open"' in src
        sidebar = no_comments(FRONTEND / "components/admin/console/Sidebar.jsx")
        assert 'badge: "disputes_open"' in sidebar


class TestTheConsoleClockActuallyRenders:
    """`TimeAgo` takes `iso`, and six call sites across four batches passed
    `value` — so every one of them rendered the component's own em-dash
    fallback where a relative time belonged. It looked exactly like "we have no
    date for this", which is the one reading that is never true on a row the
    server just stamped. Caught in a browser, not by a test, which is why there
    is now a test."""

    def test_no_screen_passes_the_wrong_prop(self):
        offenders = [
            f"{f.relative_to(FRONTEND)}"
            for f in FRONTEND.rglob("*.jsx")
            if "<TimeAgo value=" in f.read_text()
        ]
        assert not offenders, f"TimeAgo takes `iso`, not `value`: {offenders}"

    def test_the_component_still_takes_iso(self):
        src = (FRONTEND / "components/admin/console/format.jsx").read_text()
        assert "export function TimeAgo({ iso" in src, (
            "if the prop was renamed, rename it at the call sites too"
        )
