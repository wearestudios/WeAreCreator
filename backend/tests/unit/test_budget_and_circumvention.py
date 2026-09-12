"""The campaign budget cap, and off-platform enforcement — both driven.

Same instrument as `test_money_paths.py` and for the same reason: these are
money paths and account paths, and a guard that is present but pointed at the
wrong document keeps the string and loses the protection. So every test here
builds the rows, calls the **real handler**, and reads the database back.

Two rules the file holds itself to:

- **Assert on stored state, not only on the exception.** A 409 raised after
  the write is not a refusal, and a release that reports the right number
  while the row still counts is not a release.
- **Run the guard rather than grepping for it.** Calling a route function
  directly skips its `Depends` entirely, so `guard_allows` pulls the real
  `require_roles` dependency off the signature and calls it.

The release half deserves a note on why it is barely tested as a *write*:
committed is **derived** from collaboration state, so cancelling somebody
releases their amount by virtue of the state no longer being in
`_COMMITTED_COLLAB_STATES` — there is no decrement to get wrong. What the
tests here check is that the derivation is what the handlers actually read,
which is the claim that would break if somebody cached the figure.
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timezone

import pytest
from bson import ObjectId
from fastapi import HTTPException, params
from mongomock_motor import AsyncMongoMockClient

import server

LOOP = None


def role_guard(fn):
    for p in inspect.signature(fn).parameters.values():
        dep = p.default
        if isinstance(dep, params.Depends) and dep.dependency is not None:
            if getattr(dep.dependency, "__name__", "") == "_guard":
                return dep.dependency
    raise AssertionError(f"{fn.__name__} declares no require_roles guard")


def guard_allows(fn, role):
    """Would FastAPI let this role through to the handler?"""
    guard = role_guard(fn)

    async def go():
        try:
            await guard({"_id": str(ObjectId()), "role": role})
            return True
        except HTTPException as err:
            assert err.status_code == 403
            return False

    return _loop().run_until_complete(go())


def _loop():
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()
    return LOOP


def run(body):
    """One loop per call, kept in a module global — see test_money_paths."""

    async def go():
        db = AsyncMongoMockClient()["budget_circumvention"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return _loop().run_until_complete(go())


def _now():
    return datetime.now(timezone.utc)


ADMIN = {"_id": str(ObjectId()), "role": "admin", "name": "Admin"}


async def _scene(
    db,
    *,
    total_budget=None,
    compensation_type="negotiated",
    budget_per_creator=12000,
    execution_owner="brand",
    creators_needed=10,
):
    """A brand, a campaign with (or without) a cap, and nobody on it yet.

    Written the way the app writes these rows — no `total_budget` key at all
    when there is no cap, rather than an explicit `None` — so a test cannot
    pass against a fixture the product would never produce.
    """
    brand_oid, campaign_oid = ObjectId(), ObjectId()
    await db.users.insert_one(
        {"_id": brand_oid, "role": "brand_manager", "name": "Toit",
         "brand_id": brand_oid, "phone": "+919900000001"}
    )
    await db.brand_profiles.insert_one(
        {"user_id": brand_oid, "business_name": "Toit", "verified": True,
         "verified_at": _now()}
    )
    await db.campaigns.insert_one(
        {"_id": campaign_oid, "brand_id": brand_oid, "title": "Tasting",
         "status": "open", "execution_owner": execution_owner,
         "compensation_type": compensation_type,
         "budget_per_creator": budget_per_creator,
         "creators_needed": creators_needed,
         **({"total_budget": total_budget} if total_budget is not None else {})}
    )
    brand_user = await db.users.find_one({"_id": brand_oid})
    return {
        "brand": {**brand_user, "_id": str(brand_oid)},
        "brand_oid": brand_oid,
        "campaign_oid": campaign_oid,
    }


async def _applicant(db, scene, *, state="verified", amount=None, quoted=12000):
    """One creator on the campaign, at whatever rung the test needs."""
    creator_oid, collab_oid = ObjectId(), ObjectId()
    await db.users.insert_one(
        {"_id": creator_oid, "role": "creator", "name": f"Asha {collab_oid}",
         "phone": "+919900000002"}
    )
    await db.creator_profiles.insert_one(
        {"user_id": creator_oid, "name": "Asha", "verification_status": "verified",
         "verified_at": _now()}
    )
    await db.collaborations.insert_one(
        {"_id": collab_oid, "campaign_id": scene["campaign_oid"],
         "creator_id": creator_oid, "state": state, "quoted_rate": quoted,
         "state_since": _now(), "created_at": _now(),
         **({"agreed_amount": amount, "agreed_at": _now()} if amount is not None else {})}
    )
    return {"collab_id": str(collab_oid), "collab_oid": collab_oid,
            "creator_oid": creator_oid}


# ---------------------------------------------------------------------------
# 1. Draw-down: what "committed" counts, and what it does not
# ---------------------------------------------------------------------------


class TestDrawDown:
    def test_a_brief_with_no_cap_has_no_budget_block_at_all(self):
        # Absent reads as unlimited, never as zero. Campaigns predate the
        # field, so the other reading would hard-block the whole platform on
        # the morning this deployed.
        #
        # **Both readers are asked**, because there are two: the pure
        # `_budget_of` and the async `_campaign_budget` that wraps it.
        # `_budget_of` is the one that decides — break it and everything here
        # fails. `_campaign_budget`'s matching early return is an optimisation
        # rather than a second guard (it skips an aggregation nobody needs),
        # so removing it leaves every answer correct and this test green.
        # That is the honest state of it and is written down rather than
        # papered over with an assertion that would not mean anything.
        async def body(db):
            scene = await _scene(db)
            campaign = await db.campaigns.find_one({"_id": scene["campaign_oid"]})
            assert await server._campaign_budget(campaign) is None
            assert server._budget_of(campaign, 0, 0) is None
            assert server._budget_of(campaign, 99999, 3) is None

        run(body)

    def test_an_agreed_fee_draws_down_and_the_remainder_is_what_is_left(self):
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            await _applicant(db, scene, state="commercial_agreed", amount=12000)
            campaign = await db.campaigns.find_one({"_id": scene["campaign_oid"]})
            budget = await server._campaign_budget(campaign)
            assert budget["total"] == 50000
            assert budget["committed"] == 12000
            assert budget["remaining"] == 38000
            assert budget["collaborations_counted"] == 1

        run(body)

    def test_acceptance_commits_it_not_only_commercial_agreed(self):
        # **The line the requirement got wrong.** `brand_accept_applicant`
        # records the fee in the same write as `accepted`, so a cap that only
        # counted `commercial_agreed` would let ten acceptances through
        # against a budget nothing had drawn down.
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            await _applicant(db, scene, state="accepted", amount=20000)
            campaign = await db.campaigns.find_one({"_id": scene["campaign_oid"]})
            assert (await server._campaign_budget(campaign))["committed"] == 20000

        run(body)

    @pytest.mark.parametrize("state", ["applied", "verified"])
    def test_a_quoted_rate_is_an_ask_and_commits_nothing(self, state):
        # A quoted rate is what a creator would like, not what anybody agreed.
        # Counting it would refuse an acceptance on the strength of
        # applications the brand is about to decline.
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            await _applicant(db, scene, state=state, quoted=40000)
            campaign = await db.campaigns.find_one({"_id": scene["campaign_oid"]})
            assert (await server._campaign_budget(campaign))["committed"] == 0

        run(body)

    @pytest.mark.parametrize("state", ["applied", "verified"])
    def test_the_state_list_is_what_excludes_a_pitch_not_the_missing_amount(
        self, state
    ):
        # **The fixture here is deliberately one the app never writes**, and
        # that is the point. The product's own `applied` and `verified` rows
        # carry no `agreed_amount`, so the test above passes whatever
        # `_COMMITTED_COLLAB_STATES` says — break-testing found it green with
        # the state list widened to the whole ladder.
        #
        # Planting an amount on a pre-acceptance row is the only way to ask
        # whether the state boundary is load-bearing at all. It is: the two
        # guards are belt and braces, and this is the belt.
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            await db.collaborations.insert_one(
                {"_id": ObjectId(), "campaign_id": scene["campaign_oid"],
                 "creator_id": ObjectId(), "state": state,
                 "agreed_amount": 40000, "state_since": _now()}
            )
            campaign = await db.campaigns.find_one({"_id": scene["campaign_oid"]})
            budget = await server._campaign_budget(campaign)
            assert budget["committed"] == 0
            assert budget["collaborations_counted"] == 0

        run(body)

    @pytest.mark.parametrize(
        "state", ["declined", "cancelled", "withdrawn", "expired"]
    )
    def test_every_exit_releases_what_it_had_committed(self, state):
        # Derived rather than stored, so the release needs no decrement and
        # cannot be forgotten at one of the four exits.
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            await _applicant(db, scene, state=state, amount=30000)
            campaign = await db.campaigns.find_one({"_id": scene["campaign_oid"]})
            budget = await server._campaign_budget(campaign)
            assert budget["committed"] == 0
            assert budget["remaining"] == 50000

        run(body)

    def test_a_closed_collaboration_still_counts(self):
        # Money that has been paid is money the budget spent. Releasing it at
        # `closed` would make a finished campaign look like it had its whole
        # budget left.
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            await _applicant(db, scene, state="closed", amount=30000)
            campaign = await db.campaigns.find_one({"_id": scene["campaign_oid"]})
            assert (await server._campaign_budget(campaign))["committed"] == 30000

        run(body)

    def test_cancelling_through_the_real_handler_frees_the_money(self):
        # The derivation is the release, but only if the handlers read it
        # rather than a cached figure. This drives `cancel_collaboration` and
        # then asks the budget again.
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            app = await _applicant(db, scene, state="commercial_agreed", amount=30000)
            campaign = await db.campaigns.find_one({"_id": scene["campaign_oid"]})
            assert (await server._campaign_budget(campaign))["remaining"] == 20000

            await server.cancel_collaboration(
                app["collab_id"],
                server.CancelCollabPayload(
                    reason="Venue pulled out", cancellation_type="brand_cancelled"
                ),
                ADMIN,
            )

            row = await db.collaborations.find_one({"_id": app["collab_oid"]})
            assert row["state"] == "cancelled"
            budget = await server._campaign_budget(campaign)
            assert budget["committed"] == 0
            assert budget["remaining"] == 50000

        run(body)


# ---------------------------------------------------------------------------
# 2. Barter is excluded, not counted as zero
# ---------------------------------------------------------------------------


class TestBarterIsExcluded:
    def test_a_barter_collaboration_is_not_in_the_committed_count(self):
        # Not "counted at zero" — **absent**, which is the difference the
        # requirement named. `collaborations_counted` is the assertion that
        # tells the two apart: a zero-valued row would still be counted.
        async def body(db):
            scene = await _scene(db, total_budget=50000, compensation_type="barter")
            # A barter collaboration carries no `agreed_amount` at all —
            # `_resolve_agreed_amount` returns None on purpose.
            creator_oid, collab_oid = ObjectId(), ObjectId()
            await db.collaborations.insert_one(
                {"_id": collab_oid, "campaign_id": scene["campaign_oid"],
                 "creator_id": creator_oid, "state": "commercial_agreed",
                 "agreed_at": _now(), "state_since": _now()}
            )
            campaign = await db.campaigns.find_one({"_id": scene["campaign_oid"]})
            budget = await server._campaign_budget(campaign)
            assert budget["committed"] == 0
            assert budget["collaborations_counted"] == 0

        run(body)

    def test_a_zero_amount_would_have_been_counted_which_is_the_point(self):
        # The control for the test above: if a barter row *did* carry `0`, the
        # aggregation would count it — so the exclusion is doing real work
        # rather than being an accident of the number being zero.
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            await db.collaborations.insert_one(
                {"_id": ObjectId(), "campaign_id": scene["campaign_oid"],
                 "creator_id": ObjectId(), "state": "commercial_agreed",
                 "agreed_amount": 0, "agreed_at": _now(), "state_since": _now()}
            )
            campaign = await db.campaigns.find_one({"_id": scene["campaign_oid"]})
            assert (await server._campaign_budget(campaign))["collaborations_counted"] == 1

        run(body)

    def test_a_paid_row_beside_a_barter_row_counts_only_the_paid_one(self):
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            await _applicant(db, scene, state="commercial_agreed", amount=12000)
            await db.collaborations.insert_one(
                {"_id": ObjectId(), "campaign_id": scene["campaign_oid"],
                 "creator_id": ObjectId(), "state": "commercial_agreed",
                 "agreed_at": _now(), "state_since": _now()}
            )
            campaign = await db.campaigns.find_one({"_id": scene["campaign_oid"]})
            budget = await server._campaign_budget(campaign)
            assert budget["committed"] == 12000
            assert budget["collaborations_counted"] == 1

        run(body)


# ---------------------------------------------------------------------------
# 3. The 80% warning
# ---------------------------------------------------------------------------


class TestTheWarning:
    @pytest.mark.parametrize(
        "committed,warning",
        [(39000, False), (40000, True), (45000, True)],
    )
    def test_the_flag_turns_on_at_four_fifths_exactly(self, committed, warning):
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            await _applicant(db, scene, state="commercial_agreed", amount=committed)
            campaign = await db.campaigns.find_one({"_id": scene["campaign_oid"]})
            assert (await server._campaign_budget(campaign))["warning"] is warning

        run(body)

    def test_a_fully_committed_brief_reads_exhausted_and_not_warning(self):
        # Two flags rather than one number so a panel and a route cannot
        # disagree, and they are mutually exclusive: "nearly spent" is not
        # true of a brief that is spent.
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            await _applicant(db, scene, state="commercial_agreed", amount=50000)
            campaign = await db.campaigns.find_one({"_id": scene["campaign_oid"]})
            budget = await server._campaign_budget(campaign)
            assert budget["exhausted"] is True
            assert budget["warning"] is False
            assert budget["remaining"] == 0

        run(body)

    def test_crossing_the_line_notifies_the_brand_and_stamps_the_campaign(self):
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            app = await _applicant(db, scene, state="accepted", amount=42000)
            campaign = await db.campaigns.find_one({"_id": scene["campaign_oid"]})

            await server._warn_if_budget_tight(campaign)

            stamped = await db.campaigns.find_one({"_id": scene["campaign_oid"]})
            assert stamped.get("budget_warning_sent_at") is not None
            sent = await db.notifications.find(
                {"event": "campaign_budget_warning"}
            ).to_list(length=10)
            assert len(sent) == 1
            assert sent[0]["user_id"] == scene["brand_oid"]
            # The numbers travel with it. "Your budget is nearly gone" with
            # nothing beside it is not something anybody can act on.
            assert "8,000" in sent[0]["body"]
            assert app  # the applicant exists; silences the unused warning

        run(body)

    def test_it_is_sent_once_and_not_again(self):
        # The claim is the write, under a filter that only matches while the
        # stamp is absent — so two acceptances landing together send one
        # message rather than two.
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            await _applicant(db, scene, state="accepted", amount=42000)
            campaign = await db.campaigns.find_one({"_id": scene["campaign_oid"]})

            await server._warn_if_budget_tight(campaign)
            await server._warn_if_budget_tight(campaign)
            await server._warn_if_budget_tight(campaign)

            assert await db.notifications.count_documents(
                {"event": "campaign_budget_warning"}
            ) == 1

        run(body)

    def test_a_comfortable_brief_is_not_warned_about(self):
        # The control. Without it, a version of `_warn_if_budget_tight` that
        # notified unconditionally would pass every test above.
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            await _applicant(db, scene, state="accepted", amount=10000)
            campaign = await db.campaigns.find_one({"_id": scene["campaign_oid"]})
            await server._warn_if_budget_tight(campaign)
            assert await db.notifications.count_documents(
                {"event": "campaign_budget_warning"}
            ) == 0
            assert (
                await db.campaigns.find_one({"_id": scene["campaign_oid"]})
            ).get("budget_warning_sent_at") is None

        run(body)

    def test_a_brief_with_no_cap_is_never_warned_about(self):
        async def body(db):
            scene = await _scene(db)
            await _applicant(db, scene, state="accepted", amount=999999)
            campaign = await db.campaigns.find_one({"_id": scene["campaign_oid"]})
            await server._warn_if_budget_tight(campaign)
            assert await db.notifications.count_documents(
                {"event": "campaign_budget_warning"}
            ) == 0

        run(body)

    def test_a_weare_run_brief_tells_our_team_as_well(self):
        # Routed exactly the way a new application is: the runner hears, and
        # the brand hears too because it is the brand's money.
        async def body(db):
            admin_oid = ObjectId()
            await db.users.insert_one(
                {"_id": admin_oid, "role": "admin", "name": "Admin"}
            )
            scene = await _scene(db, total_budget=50000, execution_owner="weare")
            await _applicant(db, scene, state="accepted", amount=45000)
            campaign = await db.campaigns.find_one({"_id": scene["campaign_oid"]})

            await server._warn_if_budget_tight(campaign)

            told = {
                n["user_id"]
                for n in await db.notifications.find(
                    {"event": "campaign_budget_warning"}
                ).to_list(length=10)
            }
            assert admin_oid in told
            assert scene["brand_oid"] in told

        run(body)


# ---------------------------------------------------------------------------
# 4. The hard block at 100%, and the admin override
# ---------------------------------------------------------------------------


class TestTheBlock:
    def test_an_acceptance_that_would_go_over_is_refused_and_writes_nothing(self):
        # **Stored state, not only the exception.** A 409 raised after the
        # write is not a refusal.
        async def body(db):
            scene = await _scene(db, total_budget=50000, compensation_type="fixed",
                                 budget_per_creator=30000)
            await _applicant(db, scene, state="accepted", amount=30000)
            app = await _applicant(db, scene, state="verified", quoted=30000)

            with pytest.raises(HTTPException) as err:
                await server.brand_accept_applicant(
                    app["collab_id"],
                    server.BrandAcceptPayload(agreed_amount=30000),
                    scene["brand"],
                )
            assert err.value.status_code == 409
            assert err.value.detail["code"] == "over_budget"

            row = await db.collaborations.find_one({"_id": app["collab_oid"]})
            assert row["state"] == "verified"
            assert row.get("agreed_amount") is None

        run(body)

    def test_the_refusal_names_the_shortfall_and_the_three_figures(self):
        # "Over budget" is not something anybody can act on; "₹10,000 over,
        # with ₹20,000 left of ₹50,000" is the difference between topping up
        # and agreeing a lower number.
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            await _applicant(db, scene, state="commercial_agreed", amount=30000)
            app = await _applicant(db, scene, state="accepted")

            with pytest.raises(HTTPException) as err:
                await server.brand_record_agreed_amount(
                    app["collab_id"],
                    server.AgreedAmountPayload(agreed_amount=30000),
                    scene["brand"],
                )
            detail = err.value.detail
            assert detail["shortfall"] == 10000
            assert detail["total"] == 50000
            assert detail["committed"] == 30000
            assert detail["remaining"] == 20000
            assert "10,000" in detail["message"]

        run(body)

    def test_an_amount_that_exactly_fills_the_budget_is_allowed(self):
        # The boundary. `>` not `>=`, or a brief could never spend its last
        # rupee and every cap would be off by whatever the final fee was.
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            await _applicant(db, scene, state="commercial_agreed", amount=30000)
            app = await _applicant(db, scene, state="accepted")

            await server.brand_record_agreed_amount(
                app["collab_id"],
                server.AgreedAmountPayload(agreed_amount=20000),
                scene["brand"],
            )
            row = await db.collaborations.find_one({"_id": app["collab_oid"]})
            assert row["state"] == "commercial_agreed"
            assert row["agreed_amount"] == 20000

        run(body)

    def test_a_brand_cannot_override_its_own_cap(self):
        # A cap the party it constrains can lift is not a cap. The reason is
        # accepted by the model and ignored by the guard.
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            await _applicant(db, scene, state="commercial_agreed", amount=45000)
            app = await _applicant(db, scene, state="accepted")

            with pytest.raises(HTTPException) as err:
                await server.brand_record_agreed_amount(
                    app["collab_id"],
                    server.AgreedAmountPayload(
                        agreed_amount=30000,
                        budget_override_reason="We'll top the campaign up later",
                    ),
                    scene["brand"],
                )
            assert err.value.status_code == 409
            assert err.value.detail["override_available"] is False
            row = await db.collaborations.find_one({"_id": app["collab_oid"]})
            assert row["state"] == "accepted"

        run(body)

    def test_an_admin_can_override_with_a_reason_and_it_is_audited(self):
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            await _applicant(db, scene, state="commercial_agreed", amount=45000)
            app = await _applicant(db, scene, state="accepted")

            await server.brand_record_agreed_amount(
                app["collab_id"],
                server.AgreedAmountPayload(
                    agreed_amount=30000,
                    budget_override_reason="Brand confirmed a top-up on the call",
                ),
                ADMIN,
            )

            row = await db.collaborations.find_one({"_id": app["collab_oid"]})
            assert row["state"] == "commercial_agreed"
            assert row["agreed_amount"] == 30000

            line = await db.audit_log.find_one({"action": "campaign.budget_override"})
            assert line is not None
            assert line["note"] == "Brand confirmed a top-up on the call"
            # The figures at the moment of the decision, so somebody reading
            # this later knows what was overridden rather than what it says
            # now.
            assert line["before"]["remaining"] == 5000
            assert line["after"]["amount"] == 30000
            assert line["campaign_id"] == scene["campaign_oid"]

        run(body)

    def test_an_admin_without_a_reason_is_refused_like_anybody_else(self):
        # The override costs a reason. Without one it is not an override, it
        # is a cap that stops nobody with the right role.
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            await _applicant(db, scene, state="commercial_agreed", amount=45000)
            app = await _applicant(db, scene, state="accepted")

            with pytest.raises(HTTPException) as err:
                await server.brand_record_agreed_amount(
                    app["collab_id"],
                    server.AgreedAmountPayload(agreed_amount=30000),
                    ADMIN,
                )
            assert err.value.status_code == 409
            assert err.value.detail["override_available"] is True
            assert await db.audit_log.count_documents(
                {"action": "campaign.budget_override"}
            ) == 0

        run(body)

    def test_re_recording_a_fee_is_checked_against_what_it_would_become(self):
        # `exclude` is this collaboration, so correcting ₹30,000 down to
        # ₹20,000 on a brief with nothing left is allowed. Without it a
        # correction that *lowers* a fee would be refused for being over.
        async def body(db):
            scene = await _scene(db, total_budget=30000)
            app = await _applicant(db, scene, state="commercial_agreed", amount=30000)

            await server.brand_record_agreed_amount(
                app["collab_id"],
                server.AgreedAmountPayload(agreed_amount=20000),
                scene["brand"],
            )
            row = await db.collaborations.find_one({"_id": app["collab_oid"]})
            assert row["agreed_amount"] == 20000

        run(body)

    def test_the_admin_advance_path_is_capped_too(self):
        # Three doors agree a fee, and a cap on two of them is a cap on none.
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            await _applicant(db, scene, state="commercial_agreed", amount=45000)
            app = await _applicant(db, scene, state="accepted")

            with pytest.raises(HTTPException) as err:
                await server.advance_collaboration(
                    app["collab_id"],
                    server.AdvanceCollabPayload(
                        from_state="accepted", agreed_amount=30000
                    ),
                    ADMIN,
                )
            assert err.value.status_code == 409
            assert err.value.detail["code"] == "over_budget"
            row = await db.collaborations.find_one({"_id": app["collab_oid"]})
            assert row["state"] == "accepted"

        run(body)

    def test_a_barter_brief_is_never_blocked_by_a_cap(self):
        # It draws down nothing, so it cannot exceed anything. A brief that
        # was switched to barter keeps whatever total it was posted with.
        async def body(db):
            scene = await _scene(
                db, total_budget=1, compensation_type="barter", budget_per_creator=12000
            )
            app = await _applicant(db, scene, state="accepted")

            await server.brand_record_agreed_amount(
                app["collab_id"],
                server.AgreedAmountPayload(),
                scene["brand"],
            )
            row = await db.collaborations.find_one({"_id": app["collab_oid"]})
            assert row["state"] == "commercial_agreed"
            assert row.get("agreed_amount") is None

        run(body)

    def test_a_brief_with_no_cap_refuses_nothing(self):
        async def body(db):
            scene = await _scene(db)
            app = await _applicant(db, scene, state="accepted")
            await server.brand_record_agreed_amount(
                app["collab_id"],
                server.AgreedAmountPayload(agreed_amount=999999),
                scene["brand"],
            )
            row = await db.collaborations.find_one({"_id": app["collab_oid"]})
            assert row["agreed_amount"] == 999999

        run(body)

    def test_released_budget_lets_the_next_creator_through(self):
        # The end-to-end claim: full brief, cancel one, and the next
        # acceptance goes through against the money that came back.
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            first = await _applicant(db, scene, state="commercial_agreed", amount=50000)
            app = await _applicant(db, scene, state="accepted")

            with pytest.raises(HTTPException):
                await server.brand_record_agreed_amount(
                    app["collab_id"],
                    server.AgreedAmountPayload(agreed_amount=20000),
                    scene["brand"],
                )

            await server.cancel_collaboration(
                first["collab_id"],
                server.CancelCollabPayload(
                    reason="Creator pulled out", cancellation_type="brand_cancelled"
                ),
                ADMIN,
            )

            await server.brand_record_agreed_amount(
                app["collab_id"],
                server.AgreedAmountPayload(agreed_amount=20000),
                scene["brand"],
            )
            row = await db.collaborations.find_one({"_id": app["collab_oid"]})
            assert row["state"] == "commercial_agreed"
            assert row["agreed_amount"] == 20000

        run(body)


# ---------------------------------------------------------------------------
# 5. The budget on the screens that need it
# ---------------------------------------------------------------------------


class TestItReachesTheScreens:
    def test_the_applicant_board_carries_it(self):
        # The board with the Accept button on it. A backend flow with no UI is
        # not shipped, and a flag with no caller is the same thing — this is
        # the check that the payload the board reads actually has it.
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            await _applicant(db, scene, state="commercial_agreed", amount=20000)
            payload = await server.list_campaign_applicants(
                str(scene["campaign_oid"]), scene["brand"]
            )
            assert payload["campaign"]["budget"]["remaining"] == 30000

        run(body)

    def test_the_serializer_ships_the_total_and_the_block_apart(self):
        # `total_budget` is what the edit form reads back; `budget` is what a
        # panel draws. A round trip that dropped the first would clear a
        # brand's cap every time somebody fixed a typo in the title.
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            campaign = await db.campaigns.find_one({"_id": scene["campaign_oid"]})
            row = server._serialize_brand_campaign(
                campaign, 0, 0, 0, await server._campaign_budget(campaign)
            )
            assert row["total_budget"] == 50000
            assert row["budget"]["remaining"] == 50000

        run(body)

    def test_a_caller_that_did_not_look_ships_none_rather_than_zeroes(self):
        # "No cap" and "we did not look" are the same answer for a screen —
        # draw nothing — and keeping them one value is why no panel has to
        # decide which it is looking at.
        async def body(db):
            scene = await _scene(db, total_budget=50000)
            campaign = await db.campaigns.find_one({"_id": scene["campaign_oid"]})
            assert server._serialize_brand_campaign(campaign, 0)["budget"] is None

        run(body)


# ---------------------------------------------------------------------------
# 6. The circumvention clause, where it is read
# ---------------------------------------------------------------------------


class TestTheClause:
    def test_it_is_frozen_into_the_terms_at_acceptance(self):
        # The moment the introduction actually happens — the creator now has a
        # brand's name and a date — so it is the moment the rule stops being
        # abstract.
        async def body(db):
            scene = await _scene(db, compensation_type="fixed", budget_per_creator=12000)
            app = await _applicant(db, scene, state="verified", quoted=12000)

            await server.brand_accept_applicant(
                app["collab_id"],
                server.BrandAcceptPayload(agreed_amount=12000),
                scene["brand"],
            )

            row = await db.collaborations.find_one({"_id": app["collab_oid"]})
            assert row["terms"]["platform_terms"] == server.CIRCUMVENTION_TERMS

        run(body)

    def test_a_frozen_snapshot_is_not_rewritten_when_the_clause_changes(self):
        # Frozen means frozen. A later rewording must not be applied backwards
        # to somebody who agreed to different words.
        async def body(db):
            scene = await _scene(db, compensation_type="fixed", budget_per_creator=12000)
            app = await _applicant(db, scene, state="verified", quoted=12000)
            await db.collaborations.update_one(
                {"_id": app["collab_oid"]},
                {"$set": {"terms": {"platform_terms": "the old wording",
                                    "issued_at": _now(), "accepted_at": None}}},
            )
            await server.brand_accept_applicant(
                app["collab_id"],
                server.BrandAcceptPayload(agreed_amount=12000),
                scene["brand"],
            )
            row = await db.collaborations.find_one({"_id": app["collab_oid"]})
            assert row["terms"]["platform_terms"] == "the old wording"

        run(body)

    def test_the_clause_names_the_consequence_in_plain_words(self):
        # A rule somebody only meets when it is applied to them is a rule they
        # can fairly say they never agreed to, so the sentence has to be
        # readable rather than referenced. Checked as content, because that is
        # the requirement: plain language, not buried.
        text = server.CIRCUMVENTION_TERMS.lower()
        assert "off-platform" in text or "outside the platform" in text
        assert "losing your account" in text or "lose your account" in text
        # And what they lose by it, which is the half that actually retains
        # anybody — a threat with no alternative beside it is just a threat.
        assert "payment protection" in text
        assert "dispute cover" in text

    def test_what_the_platform_provides_reaches_the_creator_dashboard(self):
        # The other half of the same fact, on the screen where somebody is
        # weighing up a brand's DM. Shipped as data so the wording and the
        # terms it mirrors stay in one file.
        async def body(db):
            creator_oid = ObjectId()
            await db.users.insert_one(
                {"_id": creator_oid, "role": "creator", "name": "Asha",
                 "phone": "+919900000002"}
            )
            await db.creator_profiles.insert_one(
                {"user_id": creator_oid, "name": "Asha",
                 "verification_status": "verified"}
            )
            payload = await server.get_creator_dashboard(
                {"_id": str(creator_oid), "role": "creator", "name": "Asha"}
            )
            keys = {p["key"] for p in payload["platform_protections"]}
            assert {"payment_protection", "dispute_cover", "reliability_record"} <= keys
            # Positively framed: this is retention, not a warning. Nothing in
            # it mentions removal or the rule.
            blob = " ".join(
                p["title"] + " " + p["detail"] for p in payload["platform_protections"]
            ).lower()
            for word in ("suspend", "remove", "off-platform", "ban", "lose your"):
                assert word not in blob, f"the protections panel threatens: {word}"

        run(body)


# ---------------------------------------------------------------------------
# 7. Reporting, reviewing, and what a confirmation does
# ---------------------------------------------------------------------------


async def _reported(db, scene, app, *, reason="direct_payment"):
    return await server.report_circumvention(
        app["collab_id"],
        server.CircumventionReportPayload(
            reason=reason,
            evidence="They asked me to pay by UPI directly on the 4th.",
        ),
        scene["brand"],
    )


class TestReporting:
    def test_a_report_creates_a_review_item_and_penalises_nobody(self):
        # The whole design. The people who notice this are also people who
        # might be annoyed about something else, so a flag that suspended an
        # account on its own would make a bad week into the end of somebody's
        # livelihood.
        async def body(db):
            admin_oid = ObjectId()
            await db.users.insert_one({"_id": admin_oid, "role": "admin"})
            scene = await _scene(db)
            app = await _applicant(db, scene, state="content_approved", amount=12000)

            out = await _reported(db, scene, app)
            assert out["state"] == "open"

            creator = await db.users.find_one({"_id": app["creator_oid"]})
            assert creator.get("status") != "suspended"
            collab = await db.collaborations.find_one({"_id": app["collab_oid"]})
            assert collab["state"] == "content_approved"

            assert await db.audit_log.count_documents(
                {"action": "collaboration.circumvention_report"}
            ) == 1
            # Every admin, because it is a decision about an account rather
            # than about a campaign.
            told = await db.notifications.find(
                {"event": "circumvention_reported"}
            ).to_list(length=10)
            assert [n["user_id"] for n in told] == [admin_oid]

        run(body)

    def test_a_second_open_report_on_the_same_row_is_refused(self):
        async def body(db):
            scene = await _scene(db)
            app = await _applicant(db, scene, state="content_approved", amount=12000)
            await _reported(db, scene, app)
            with pytest.raises(HTTPException) as err:
                await _reported(db, scene, app)
            assert err.value.status_code == 409
            assert await db.circumvention_reports.count_documents({}) == 1

        run(body)

    def test_the_creator_is_not_on_the_route_at_all(self):
        # Reporting yourself is not a flow, and reading the report about you
        # before anybody has looked at it is not one either. Through the real
        # guard, not a string match.
        assert guard_allows(server.report_circumvention, "creator") is False
        assert guard_allows(server.report_circumvention, "brand_manager") is True
        assert guard_allows(server.report_circumvention, "campaign_manager") is True
        assert guard_allows(server.report_circumvention, "admin") is True

    def test_the_queue_and_both_decisions_are_admin_only(self):
        # A creator works across every brand, so deciding whether one keeps
        # their account is not scoped work — the same line ADMIN_ONLY_EXPORTS
        # draws. `weare_team` must not reach it.
        for fn in (
            server.list_circumvention_reports,
            server.confirm_circumvention,
            server.dismiss_circumvention,
        ):
            assert guard_allows(fn, "admin") is True, fn.__name__
            assert guard_allows(fn, "weare_team") is False, fn.__name__
            assert guard_allows(fn, "campaign_manager") is False, fn.__name__
            assert guard_allows(fn, "brand_manager") is False, fn.__name__

    def test_evidence_shorter_than_a_sentence_is_refused_by_the_model(self):
        # A reason code on its own is not something anybody can weigh, and the
        # admin reading it has to decide whether somebody loses their account.
        with pytest.raises(Exception):
            server.CircumventionReportPayload(reason="other", evidence="yeah")


class TestConfirming:
    def test_confirming_suspends_through_the_existing_flow(self):
        # **Through `_suspend_creator_account`, not a write of its own.**
        # `_creator_block` reads `status`, so anything that does not come
        # through that function blocks nobody.
        async def body(db):
            await db.users.insert_one({"_id": ObjectId(), "role": "admin"})
            scene = await _scene(db)
            app = await _applicant(db, scene, state="content_approved", amount=12000)
            report = await _reported(db, scene, app)

            out = await server.confirm_circumvention(
                report["id"],
                server.CircumventionDecisionPayload(
                    note="Confirmed with the brand — the shoot was paid in cash."
                ),
                ADMIN,
            )
            assert out["suspended"] is True

            creator = await db.users.find_one({"_id": app["creator_oid"]})
            assert creator["status"] == "suspended"
            assert "off the" in creator["suspension_reason"]
            # And the suspension is the one the gates read.
            profile = await db.creator_profiles.find_one(
                {"user_id": app["creator_oid"]}
            )
            assert server._creator_block(profile, creator)["code"] == "suspended"

        run(body)

    def test_it_never_touches_the_verification_decision(self):
        # Rejecting a verified creator to remove them would erase the record
        # that they were ever approved — the reason suspension is separate.
        async def body(db):
            await db.users.insert_one({"_id": ObjectId(), "role": "admin"})
            scene = await _scene(db)
            app = await _applicant(db, scene, state="content_approved", amount=12000)
            report = await _reported(db, scene, app)

            await server.confirm_circumvention(
                report["id"],
                server.CircumventionDecisionPayload(note="Upheld after review."),
                ADMIN,
            )
            profile = await db.creator_profiles.find_one(
                {"user_id": app["creator_oid"]}
            )
            assert profile["verification_status"] == "verified"

        run(body)

    def test_history_is_preserved_and_nothing_is_deleted(self):
        async def body(db):
            await db.users.insert_one({"_id": ObjectId(), "role": "admin"})
            scene = await _scene(db)
            app = await _applicant(db, scene, state="content_approved", amount=12000)
            await db.collaboration_ratings.insert_one(
                {"collaboration_id": app["collab_oid"],
                 "creator_id": app["creator_oid"], "side": "runner", "score": 4}
            )
            report = await _reported(db, scene, app)

            await server.confirm_circumvention(
                report["id"],
                server.CircumventionDecisionPayload(note="Upheld after review."),
                ADMIN,
            )

            assert await db.collaborations.count_documents(
                {"_id": app["collab_oid"]}
            ) == 1
            assert await db.collaboration_ratings.count_documents({}) == 1
            assert await db.creator_profiles.count_documents(
                {"user_id": app["creator_oid"]}
            ) == 1

        run(body)

    def test_both_decisions_are_audited_with_the_note(self):
        async def body(db):
            await db.users.insert_one({"_id": ObjectId(), "role": "admin"})
            scene = await _scene(db)
            one = await _applicant(db, scene, state="content_approved", amount=12000)
            two = await _applicant(db, scene, state="content_approved", amount=12000)
            r1 = await _reported(db, scene, one)
            r2 = await _reported(db, scene, two)

            await server.confirm_circumvention(
                r1["id"],
                server.CircumventionDecisionPayload(note="Brand confirmed it."),
                ADMIN,
            )
            await server.dismiss_circumvention(
                r2["id"],
                server.CircumventionDecisionPayload(
                    note="Misread the thread — the booking is on the platform."
                ),
                ADMIN,
            )

            up = await db.audit_log.find_one(
                {"action": "creator.circumvention_confirmed"}
            )
            down = await db.audit_log.find_one(
                {"action": "creator.circumvention_dismissed"}
            )
            assert up["note"] == "Brand confirmed it."
            assert down["note"].startswith("Misread")

        run(body)

    def test_dismissing_does_nothing_to_the_creator(self):
        async def body(db):
            await db.users.insert_one({"_id": ObjectId(), "role": "admin"})
            scene = await _scene(db)
            app = await _applicant(db, scene, state="content_approved", amount=12000)
            report = await _reported(db, scene, app)

            await server.dismiss_circumvention(
                report["id"],
                server.CircumventionDecisionPayload(note="Nothing in it."),
                ADMIN,
            )
            creator = await db.users.find_one({"_id": app["creator_oid"]})
            assert creator.get("status") != "suspended"
            profile = await db.creator_profiles.find_one(
                {"user_id": app["creator_oid"]}
            )
            assert profile.get("circumvention_confirmed_at") is None

        run(body)

    def test_a_report_can_only_be_answered_once(self):
        async def body(db):
            await db.users.insert_one({"_id": ObjectId(), "role": "admin"})
            scene = await _scene(db)
            app = await _applicant(db, scene, state="content_approved", amount=12000)
            report = await _reported(db, scene, app)

            await server.dismiss_circumvention(
                report["id"],
                server.CircumventionDecisionPayload(note="Nothing in it."),
                ADMIN,
            )
            with pytest.raises(HTTPException) as err:
                await server.confirm_circumvention(
                    report["id"],
                    server.CircumventionDecisionPayload(note="Changed my mind."),
                    ADMIN,
                )
            assert err.value.status_code == 409
            # **The refusal names what actually happened**, which is the half
            # a 409 alone does not pin. There are two guards here — the read
            # check and the `find_one_and_update` precondition — and dropping
            # the first still refuses, just with "this just moved", which
            # sends somebody to reload a page that is already right.
            assert "dismissed" in err.value.detail
            creator = await db.users.find_one({"_id": app["creator_oid"]})
            assert creator.get("status") != "suspended"

        run(body)


# ---------------------------------------------------------------------------
# 8. What a confirmed circumvention costs, afterwards
# ---------------------------------------------------------------------------


class TestAfterwards:
    def test_a_suspended_creator_cannot_apply(self):
        async def body(db):
            await db.users.insert_one({"_id": ObjectId(), "role": "admin"})
            scene = await _scene(db)
            app = await _applicant(db, scene, state="content_approved", amount=12000)
            report = await _reported(db, scene, app)
            await server.confirm_circumvention(
                report["id"],
                server.CircumventionDecisionPayload(note="Upheld."),
                ADMIN,
            )

            other = ObjectId()
            await db.campaigns.insert_one(
                {"_id": other, "brand_id": scene["brand_oid"], "title": "Another",
                 "status": "open", "creators_needed": 4,
                 "compensation_type": "fixed", "budget_per_creator": 9000}
            )
            with pytest.raises(HTTPException) as err:
                await server.apply_to_campaign(
                    str(other),
                    server.ApplyPayload(pitch="I'd love to", quoted_rate=9000),
                    {"_id": str(app["creator_oid"]), "role": "creator", "name": "Asha"},
                )
            assert err.value.status_code == 403
            assert await db.collaborations.count_documents({"campaign_id": other}) == 0

        run(body)

    def test_they_are_off_the_leaderboard_and_stay_off_after_reinstatement(self):
        # **Permanent, and read off the profile rather than the account
        # status.** A suspension can be lifted — sometimes it should be — and
        # the leaderboard is a claim this platform makes about people in
        # public.
        async def body(db):
            await db.users.insert_one({"_id": ObjectId(), "role": "admin"})
            scene = await _scene(db)
            app = await _applicant(db, scene, state="content_approved", amount=12000)
            await db.creator_profiles.update_one(
                {"user_id": app["creator_oid"]}, {"$set": {"homepage_opt_in": True}}
            )

            profile = await db.creator_profiles.find_one(
                {"user_id": app["creator_oid"]}
            )
            account = await db.users.find_one({"_id": app["creator_oid"]})
            assert server._leaderboard_eligible(profile, account) is True

            report = await _reported(db, scene, app)
            await server.confirm_circumvention(
                report["id"],
                server.CircumventionDecisionPayload(note="Upheld."),
                ADMIN,
            )

            await server.reinstate_creator(
                str(app["creator_oid"]),
                server.ReasonPayload(reason="Second chance after a conversation."),
                ADMIN,
            )
            account = await db.users.find_one({"_id": app["creator_oid"]})
            assert account["status"] == "active"

            profile = await db.creator_profiles.find_one(
                {"user_id": app["creator_oid"]}
            )
            # The account works again; the homepage claim does not come back.
            assert server._creator_block(profile, account) is None
            assert server._leaderboard_eligible(profile, account) is False

        run(body)

    def test_it_lands_on_the_reliability_record(self):
        # A suspension can be lifted and then there is nothing left saying it
        # happened. Counted rather than flagged, because a second confirmed
        # report is a different fact from a first.
        async def body(db):
            await db.users.insert_one({"_id": ObjectId(), "role": "admin"})
            scene = await _scene(db)
            app = await _applicant(db, scene, state="content_approved", amount=12000)

            before = (await server._reliability_for([app["creator_oid"]]))[
                app["creator_oid"]
            ]
            assert before["circumvention_confirmed"] == 0

            report = await _reported(db, scene, app)
            await server.confirm_circumvention(
                report["id"],
                server.CircumventionDecisionPayload(note="Upheld."),
                ADMIN,
            )

            after = (await server._reliability_for([app["creator_oid"]]))[
                app["creator_oid"]
            ]
            assert after["circumvention_confirmed"] == 1

        run(body)

    def test_a_brand_never_sees_the_count(self):
        # Brands get a band and never a number — the existing rule, which this
        # new signal has to stay inside. `_brand_visible_creator` runs the
        # block through `_reliability_band`, which carries no counts.
        async def body(db):
            await db.users.insert_one({"_id": ObjectId(), "role": "admin"})
            scene = await _scene(db)
            app = await _applicant(db, scene, state="content_approved", amount=12000)
            report = await _reported(db, scene, app)
            await server.confirm_circumvention(
                report["id"],
                server.CircumventionDecisionPayload(note="Upheld."),
                ADMIN,
            )

            stats = (await server._reliability_for([app["creator_oid"]]))[
                app["creator_oid"]
            ]
            profile = await db.creator_profiles.find_one(
                {"user_id": app["creator_oid"]}
            )
            account = await db.users.find_one({"_id": app["creator_oid"]})
            shown = server._brand_visible_creator(profile, account, reliability=stats)
            assert "circumvention_confirmed" not in str(shown)

        run(body)

    def test_a_dismissed_report_leaves_no_mark(self):
        # The control. Without it, a version that stamped the profile on every
        # decision would pass everything above.
        async def body(db):
            await db.users.insert_one({"_id": ObjectId(), "role": "admin"})
            scene = await _scene(db)
            app = await _applicant(db, scene, state="content_approved", amount=12000)
            await db.creator_profiles.update_one(
                {"user_id": app["creator_oid"]}, {"$set": {"homepage_opt_in": True}}
            )
            report = await _reported(db, scene, app)
            await server.dismiss_circumvention(
                report["id"],
                server.CircumventionDecisionPayload(note="Nothing in it."),
                ADMIN,
            )

            profile = await db.creator_profiles.find_one(
                {"user_id": app["creator_oid"]}
            )
            account = await db.users.find_one({"_id": app["creator_oid"]})
            assert server._leaderboard_eligible(profile, account) is True
            stats = (await server._reliability_for([app["creator_oid"]]))[
                app["creator_oid"]
            ]
            assert stats["circumvention_confirmed"] == 0

        run(body)


# ---------------------------------------------------------------------------
# 9. What was deliberately not built
# ---------------------------------------------------------------------------


class TestTheScopeWeWereGiven:
    def test_nothing_scans_message_content(self):
        # Explicitly out of scope, and worth pinning: an automatic detector is
        # the obvious next feature and it is the one that would be wrong often,
        # about somebody's income. The reports collection is the only input.
        src = inspect.getsource(server.report_circumvention)
        src += inspect.getsource(server.confirm_circumvention)
        for word in ("collaboration_notes", "campaign_questions", "regex", "re.search"):
            assert word not in src, f"the flow reads message content: {word}"

    def test_there_is_no_brand_side_penalty(self):
        # A brand that leaves loses little, and policing it would damage trust
        # with the paying side. Confirming a report touches the creator's
        # account and nothing on the brand.
        src = inspect.getsource(server.confirm_circumvention)
        assert "brand_profiles" not in src
        assert "verified" not in src


# ---------------------------------------------------------------------------
# 10. The frontend half — mirrored, mounted, and not deciding for itself
# ---------------------------------------------------------------------------
#
# "If a backend flow has no UI it is not shipped, whatever the tests say", and
# "a caller with no mount is as unreachable as a route with no caller". Both
# halves are checked here, because both have bitten this codebase before.

from pathlib import Path  # noqa: E402  (grouped with its own section)

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"


def read(*parts):
    return FRONTEND.joinpath(*parts).read_text()


def _strip_comments(src: str) -> str:
    """Drop `//` lines and `/* */` blocks, so prose about a rule is not
    mistaken for the rule."""
    import re

    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(l for l in src.splitlines() if not l.strip().startswith("//"))


class TestTheFrontendMirror:
    def test_the_clause_is_word_for_word_the_server_s(self):
        # **It cannot be served.** The signup screen renders before an account
        # exists to fetch a profile for, so this is a mirror with a drift test
        # — the arrangement `followerTiers.js` and `shootWindows.js` use. Two
        # copies with nothing holding them together is how a rule ends up
        # worded one way in the thing somebody agreed to and another way in
        # the thing they are held to.
        src = read("lib", "platformTerms.js")
        start = src.index("export const CIRCUMVENTION_TERMS")
        end = src.index(";", start)
        mirrored = "".join(
            part for part in src[start:end].split('"')[1::2]
        )
        assert mirrored == server.CIRCUMVENTION_TERMS

    def test_the_reason_codes_match(self):
        src = _strip_comments(read("lib", "platformTerms.js"))
        for value, label in server.CIRCUMVENTION_REASON_LABELS.items():
            assert f'value: "{value}"' in src, value
            assert label in src, label
        # And nothing extra: a reason the server refuses would be a dropdown
        # option that 422s.
        import re

        offered = set(re.findall(r'value: "([a-z_]+)"', src))
        assert offered == set(server.CIRCUMVENTION_REASONS)

    def test_the_protections_fallback_matches_the_server(self):
        # The dashboard receives these, so the mirror is a fallback only — but
        # a fallback that says something different is worse than none.
        src = _strip_comments(read("lib", "platformTerms.js"))
        for row in server.PLATFORM_PROTECTIONS:
            assert f'key: "{row["key"]}"' in src, row["key"]
            assert row["title"] in src, row["title"]

    def test_the_browser_holds_no_second_definition_of_nearly_spent(self):
        # The console already learned this once with `isStale`, a flat 48
        # hours that was wrong in both directions against nine real targets.
        # `BUDGET_WARNING_RATIO` lives on the server and travels in the block.
        src = _strip_comments(read("lib", "budget.js"))
        assert "0.8" not in src
        assert "BUDGET_WARNING_RATIO" not in src
        # The tone is read off the flags, not derived from the numbers.
        assert "block.warning" in src and "block.exhausted" in src


class TestItIsActuallyReachable:
    def test_every_new_route_has_a_caller(self):
        # The rule `test_manager_experience.py` holds for the manager router:
        # four endpoints shipped with no caller anywhere, so the role was
        # paged about work it had no way to do.
        js = "\n".join(
            p.read_text() for p in FRONTEND.rglob("*.js*") if p.is_file()
        )
        #
        # Both decision routes are spelled out in full rather than
        # interpolated, and that is the point: a path built as `/${action}` is
        # one no grep can find, so it would pass this check while being
        # unreachable. Writing this test is what caught the queue doing that.
        for path in (
            "/circumvention-report",
            "/admin/circumvention-reports",
            "circumvention-reports/${id}/confirm",
            "circumvention-reports/${id}/dismiss",
        ):
            assert path in js, f"no caller for {path}"

    def test_every_new_component_is_mounted(self):
        # **And the second half, which matters as much.** Deleting a panel
        # from its page leaves the route-has-a-caller check green, because the
        # component file still holds the only call in the repository.
        mounts = {
            "BudgetMeter": (
                ("pages", "BrandCampaignApplicants.jsx"),
                ("components", "admin", "CampaignDetailPage.jsx"),
                ("components", "manager", "BriefPanel.jsx"),
                ("components", "application", "ApplicationDetail.jsx"),
            ),
            "CircumventionReport": (
                ("components", "application", "ApplicationDetail.jsx"),
            ),
            "PlatformProtections": (("pages", "CreatorHome.jsx"),),
            "CircumventionQueue": (("components", "admin", "routes.jsx"),),
        }
        for component, pages in mounts.items():
            for page in pages:
                src = read(*page)
                assert f"<{component}" in src, f"{component} is not mounted in {page[-1]}"

    def test_the_console_section_routes_somewhere(self):
        # `ADMIN_SECTIONS` is both the navigation and the route table, and a
        # section that routes nowhere is a sidebar entry that 404s.
        assert 'to: "circumvention"' in read("components", "admin", "console", "Sidebar.jsx")
        assert 'path="circumvention"' in read("..", "src", "App.js")
        assert "CircumventionRoute" in read("components", "admin", "routes.jsx")

    def test_the_clause_is_read_where_somebody_agrees_to_something(self):
        # Signup (before an account exists), the frozen terms card (at
        # acceptance) and the terms page. "Plain language, not buried" is the
        # requirement, and a link to /terms is buried.
        #
        # **Asserting it is rendered, not that it is imported.** Break-testing
        # found all three of these green with the render deleted and the
        # import left behind, which is the exact failure this whole class of
        # test exists to catch.
        assert "{CIRCUMVENTION_TERMS}" in read("pages", "Signup.jsx")
        assert "{CIRCUMVENTION_TERMS}" in read("pages", "Legal.jsx")
        assert "{terms.platform_terms}" in read(
            "components", "campaign", "CampaignTerms.jsx"
        )

    def test_the_total_budget_field_survives_an_edit_round_trip(self):
        # The trap every field on this form has hit: a round trip that drops
        # the value blanks it the next time somebody fixes a typo. So the
        # assertion is on the *re-seed reading the server's value*, not on the
        # setter existing — the setter is also used by the onChange handler,
        # and a test that matched it passed with the re-seed deleted.
        post = read("pages", "PostCampaign.jsx")
        assert "setTotalBudget(\n" in post and "data.total_budget" in post
        # And clearing it has to travel as an explicit null, or a cap set by
        # mistake could only ever be lowered. The whole expression, because
        # `: null` on its own appears all over a form this size.
        assert 'String(totalBudget).trim() === "" ? null :' in post

    def test_the_report_component_never_asks_what_role_is_looking(self):
        # The rule the shared application screen holds, and this panel is on
        # it: every action is decided server-side.
        src = _strip_comments(read("components", "application", "CircumventionReport.jsx"))
        for probe in ('role === "admin"', 'role === "brand', "isAdmin", "user?.role"):
            assert probe not in src, f"the panel asks the role: {probe}"
        assert "can_report_circumvention" in src
