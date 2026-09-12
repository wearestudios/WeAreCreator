"""Managed-only execution, staff-only invites, negotiated rates, refunds.

The same instrument as `test_money_paths.py`: these are money paths and access
paths, so every test builds the rows, calls the **real handler** and reads the
database back. A 409 raised after the write is not a refusal, and a rate that
reports correctly while the stored one says something else is not a rate.

Two rules the file holds itself to:

- **Assert on stored state, not only on the exception.**
- **Run the guard rather than grepping for it.** Calling a route function
  directly skips its `Depends` entirely, so `guard_allows` pulls the real
  `require_roles` dependency off the signature and calls it — which is the
  only way to check that a brand really cannot invite anybody.
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

LOOP = None
FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"


def _loop():
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()
    return LOOP


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


def run(body):
    async def go():
        db = AsyncMongoMockClient()["managed_commission"]
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


async def _brand(db, *, verified=True, commission=None):
    oid = ObjectId()
    await db.users.insert_one(
        {"_id": oid, "role": "brand_manager", "name": "Toit", "brand_id": oid,
         "phone": "+919900000001"}
    )
    await db.brand_profiles.insert_one(
        {"user_id": oid, "business_name": "Toit", "verified": verified,
         "verified_at": _now(),
         **({"commission_percent": commission} if commission is not None else {})}
    )
    account = await db.users.find_one({"_id": oid})
    return {**account, "_id": str(oid)}, oid


def _post(**over):
    body = {
        "title": "Tasting evening",
        "brief": "Come and shoot the new menu.",
        "deliverable_items": [{"type": "reel", "quantity": 1}],
        "budget_per_creator": 12000,
        "category": "fnb",
        "area": "Indiranagar",
        "creators_needed": 4,
        "campaign_type": "personal_table",
        "start_date": _now(),
        "end_date": _now(),
    }
    body.update(over)
    return server.PostCampaignPayload(**body)


async def _campaign(db, brand_oid, **over):
    oid = ObjectId()
    doc = {
        "_id": oid, "brand_id": brand_oid, "title": "Tasting", "status": "open",
        "execution_owner": "weare", "compensation_type": "fixed",
        "budget_per_creator": 12000, "creators_needed": 4, **over,
    }
    await db.campaigns.insert_one(doc)
    return await db.campaigns.find_one({"_id": oid})


async def _collab(db, campaign, *, state="applied", shortlisted=False, amount=12000):
    creator_oid, oid = ObjectId(), ObjectId()
    await db.users.insert_one(
        {"_id": creator_oid, "role": "creator", "name": "Asha",
         "phone": "+919900000002"}
    )
    await db.creator_profiles.insert_one(
        {"user_id": creator_oid, "name": "Asha", "verification_status": "verified",
         "payout_method": "upi", "payout_upi": "asha@okhdfc", "pan": "ABCDE1234F"}
    )
    await db.collaborations.insert_one(
        {"_id": oid, "campaign_id": campaign["_id"], "creator_id": creator_oid,
         "state": state, "quoted_rate": 12000, "created_at": _now(),
         "state_since": _now(),
         # `agreed_at` is the shortlist line — the moment somebody here
         # finished the job. Written exactly as the app writes it: absent
         # rather than None on a pitch nobody has worked.
         **({"agreed_at": _now(), "agreed_amount": amount} if shortlisted else {})}
    )
    return {"id": str(oid), "oid": oid, "creator_oid": creator_oid}


# ---------------------------------------------------------------------------
# 1. Every brand-posted campaign is ours to run
# ---------------------------------------------------------------------------


class TestManagedByDefault:
    def test_a_brand_posting_a_brief_gets_a_weare_run_campaign(self):
        async def body(db):
            user, oid = await _brand(db)
            out = await server.create_brand_campaign(_post(), user)
            doc = await db.campaigns.find_one({"_id": ObjectId(out["id"])})
            assert doc["execution_owner"] == "weare"
            assert doc["weare_run_reason"] == server.MANAGED_BY_DEFAULT_REASON
            assert oid  # the brand exists; silences the unused warning

        run(body)

    def test_a_stale_client_asking_for_brand_execution_is_ignored(self):
        # **Ignored rather than refused**, on this path only. The payload
        # carries a default a cached form would send by accident, and failing
        # a whole post over a field the form no longer shows is the wrong
        # trade — the same reasoning `compensation_type` gets on the way in.
        async def body(db):
            user, _ = await _brand(db)
            out = await server.create_brand_campaign(
                _post(execution_owner="brand"), user
            )
            doc = await db.campaigns.find_one({"_id": ObjectId(out["id"])})
            assert doc["execution_owner"] == "weare"

        run(body)

    def test_the_campaign_gets_no_manager_from_the_brand(self):
        # Stamping the brand's own person would route every application
        # straight back to the brand we are running it for.
        async def body(db):
            user, _ = await _brand(db)
            out = await server.create_brand_campaign(_post(), user)
            doc = await db.campaigns.find_one({"_id": ObjectId(out["id"])})
            assert doc["manager_id"] is None

        run(body)

    def test_the_offer_is_stated_in_the_response(self):
        # The form shows it before the button; this is the same wording after
        # it, from one constant, so the promise cannot drift between screens.
        async def body(db):
            user, _ = await _brand(db)
            out = await server.create_brand_campaign(_post(), user)
            assert out["managed_note"] == server.MANAGED_BY_DEFAULT_SENTENCE
            assert "end to end" in out["managed_note"]
            # And the refund promise, which is the other half of what they are
            # being asked to trust at exactly this moment.
            assert out["refund_terms"] == server.REFUND_POLICY_TERMS

        run(body)

    def test_a_brand_cannot_edit_it_back_and_the_row_does_not_move(self):
        async def body(db):
            user, _ = await _brand(db)
            out = await server.create_brand_campaign(_post(), user)
            with pytest.raises(HTTPException) as err:
                await server.update_brand_campaign(
                    out["id"],
                    server.UpdateCampaignPayload(execution_owner="brand"),
                    user,
                )
            assert err.value.status_code == 409
            assert err.value.detail["code"] == "managed_by_weare"
            doc = await db.campaigns.find_one({"_id": ObjectId(out["id"])})
            assert doc["execution_owner"] == "weare"

        run(body)

    def test_an_admin_is_the_only_one_who_can_hand_it_back(self):
        async def body(db):
            user, brand_oid = await _brand(db)
            out = await server.create_brand_campaign(_post(), user)
            await server.admin_update_campaign(
                out["id"],
                server.UpdateCampaignPayload(execution_owner="brand"),
                ADMIN,
            )
            doc = await db.campaigns.find_one({"_id": ObjectId(out["id"])})
            assert doc["execution_owner"] == "brand"
            assert brand_oid

        run(body)

    def test_resending_the_same_owner_is_not_a_change(self):
        # A form that round-trips every field must not trip the guard, or an
        # edit to the title fails on a value nothing asked to change.
        server._refuse_brand_execution_choice(
            {"execution_owner": "weare"}, {"execution_owner": "weare"}
        )  # does not raise
        server._refuse_brand_execution_choice(
            {"execution_owner": "weare"}, {"title": "New title"}
        )  # does not raise

    def test_a_launch_still_names_its_own_reason(self):
        # Every brand-posted brief is ours; only some have something specific
        # to say about *why*. Collapsing the two would lose the sentence the
        # form shows on a launch, which is a different offer from the general
        # one — "we run launches" rather than "we run everything".
        async def body(db):
            user, _ = await _brand(db)
            out = await server.create_brand_campaign(
                _post(
                    campaign_type="launch",
                    event_date=_now(),
                    start_date=None,
                    end_date=None,
                ),
                user,
            )
            doc = await db.campaigns.find_one({"_id": ObjectId(out["id"])})
            assert doc["weare_run_reason"] == "launch"

        run(body)

    def test_the_readers_default_is_untouched(self):
        # The migration promise. Thousands of campaigns predate the field and
        # an absent value still means the brand ran it — flipping this reader
        # is the one change that would have hurt.
        assert server._execution_owner({}) == "brand"
        assert server.DEFAULT_EXECUTION_OWNER == "brand"
        assert server.NEW_CAMPAIGN_EXECUTION_OWNER == "weare"


# ---------------------------------------------------------------------------
# 2. Inviting creators is ours
# ---------------------------------------------------------------------------


class TestInvitesAreStaffOnly:
    @pytest.mark.parametrize(
        "fn", [server.weare_invite_creators, server.invite_creator_list]
    )
    def test_no_brand_role_reaches_either_route(self, fn):
        # Through the real `require_roles` dependency, not a string match: a
        # guard listing the wrong roles passes a grep and fails here.
        assert guard_allows(fn, "brand_manager") is False
        assert guard_allows(fn, "brand") is False
        assert guard_allows(fn, "creator") is False
        assert guard_allows(fn, "admin") is True
        assert guard_allows(fn, "weare_team") is True

    def test_a_weare_team_member_can_actually_invite(self):
        # **The other half, and the one a role swap alone would have broken.**
        # `_own_campaign_or_404` resolves the *caller's* brand, so leaving it
        # in place would have 404'd every staff invite while the guard looked
        # correct. This drives the handler rather than reading it.
        async def body(db):
            _, brand_oid = await _brand(db)
            campaign = await _campaign(db, brand_oid)
            staff = {"_id": str(ObjectId()), "role": "weare_team", "name": "Ravi",
                     "assigned_brand_ids": [brand_oid]}
            creator_oid = ObjectId()
            await db.users.insert_one(
                {"_id": creator_oid, "role": "creator", "name": "Asha",
                 "phone": "+919900000002"}
            )
            await db.creator_profiles.insert_one(
                {"user_id": creator_oid, "name": "Asha",
                 "verification_status": "verified"}
            )
            out = await server.weare_invite_creators(
                str(campaign["_id"]),
                server.CampaignInvitePayload(creator_ids=[str(creator_oid)]),
                staff,
            )
            assert out
            assert await db.campaign_invitations.count_documents({}) == 1

        run(body)

    def test_a_weare_team_member_cannot_invite_outside_their_scope(self):
        # The console's door applies the scope, and a brand they are not on is
        # a 404 rather than a refusal that confirms the campaign exists.
        async def body(db):
            _, brand_oid = await _brand(db)
            campaign = await _campaign(db, brand_oid)
            staff = {"_id": str(ObjectId()), "role": "weare_team", "name": "Ravi",
                     "assigned_brand_ids": [ObjectId()]}
            with pytest.raises(HTTPException) as err:
                await server.weare_invite_creators(
                    str(campaign["_id"]),
                    server.CampaignInvitePayload(creator_ids=[str(ObjectId())]),
                    staff,
                )
            assert err.value.status_code == 404
            assert await db.campaign_invitations.count_documents({}) == 0

        run(body)

    def test_an_unverified_brand_still_blocks_the_invite(self):
        # The rule survives, pointed at the right party: it is a fact about
        # the brand on the campaign rather than about whoever is asking, so
        # `_brand_scope` on an admin cannot be what decides it.
        async def body(db):
            _, brand_oid = await _brand(db, verified=False)
            campaign = await _campaign(db, brand_oid)
            with pytest.raises(HTTPException) as err:
                await server.weare_invite_creators(
                    str(campaign["_id"]),
                    server.CampaignInvitePayload(creator_ids=[str(ObjectId())]),
                    ADMIN,
                )
            assert err.value.status_code == 409
            assert await db.campaign_invitations.count_documents({}) == 0

        run(body)

    def test_the_frontend_offers_a_brand_no_way_to_invite(self):
        # A backend rule with a button still on screen is a 403 somebody
        # presses. The brand's applicant board is where the invite lived.
        src = (FRONTEND / "pages" / "BrandCampaignApplicants.jsx").read_text()
        assert "/invite" not in src, "the brand board still calls an invite route"


# ---------------------------------------------------------------------------
# 3. The shortlist gate, end to end
# ---------------------------------------------------------------------------


class TestTheShortlistGate:
    def test_the_board_shows_only_shortlisted_creators(self):
        async def body(db):
            user, brand_oid = await _brand(db)
            campaign = await _campaign(db, brand_oid)
            await _collab(db, campaign, state="applied")
            await _collab(db, campaign, state="applied")
            await _collab(db, campaign, state="accepted", shortlisted=True)

            out = await server.list_campaign_applicants(str(campaign["_id"]), user)
            assert len(out["applicants"]) == 1
            assert out["totals"]["all"] == 1

        run(body)

    def test_the_count_on_the_card_agrees_with_the_board(self):
        # **The leak this audit found.** `_applicant_counts_for` ignored the
        # gate, so a brand read "3 applicants" on a card and opened a board
        # with one on it — which is a perfectly good way to tell somebody that
        # two people they may not see applied.
        async def body(db):
            user, brand_oid = await _brand(db)
            campaign = await _campaign(db, brand_oid)
            await _collab(db, campaign, state="applied")
            await _collab(db, campaign, state="applied")
            await _collab(db, campaign, state="accepted", shortlisted=True)

            rows = await server.list_brand_campaigns(None, user)
            assert rows[0]["applicant_count"] == 1

            dash = await server.get_brand_dashboard(user)
            assert dash["campaigns"][0]["applicant_count"] == 1
            assert dash["totals"]["total_applications"] == 1

        run(body)

    def test_a_brand_run_campaign_still_counts_everybody(self):
        # The control. Without it a counter that returned zero always, or one
        # that filtered every campaign, would pass the test above.
        async def body(db):
            user, brand_oid = await _brand(db)
            campaign = await _campaign(db, brand_oid, execution_owner="brand")
            await _collab(db, campaign, state="applied")
            await _collab(db, campaign, state="applied")

            rows = await server.list_brand_campaigns(None, user)
            assert rows[0]["applicant_count"] == 2

        run(body)

    def test_the_door_to_one_application_carries_it_too(self):
        # A board that hides a row while its id opens the pitch is a shield on
        # one of two doors, which is a shield on neither.
        async def body(db):
            user, brand_oid = await _brand(db)
            campaign = await _campaign(db, brand_oid)
            raw = await _collab(db, campaign, state="applied")
            with pytest.raises(HTTPException) as err:
                await server._brand_collab_or_404(raw["id"], user)
            assert err.value.status_code == 404

        run(body)

    def test_the_close_out_export_carries_it(self):
        # `_BRAND_EXPORT_STATES` includes `cancelled`, and a collaboration can
        # be cancelled straight out of `applied` — so the state list alone
        # would put somebody in a brand's CSV whose application it never saw.
        async def body(db):
            _, brand_oid = await _brand(db)
            campaign = await _campaign(db, brand_oid, status="closed")
            await _collab(db, campaign, state="cancelled")
            await _collab(db, campaign, state="closed", shortlisted=True)

            body_text = await server._build_brand_campaign_export(campaign)
            # One creator row under the header, plus the totals block.
            assert body_text.count("Asha") == 1

        run(body)

    def test_a_raw_application_never_notifies_the_brand(self):
        async def body(db):
            _, brand_oid = await _brand(db)
            await db.users.insert_one({"_id": ObjectId(), "role": "admin"})
            campaign = await _campaign(db, brand_oid)
            creator_oid = ObjectId()
            await db.users.insert_one(
                {"_id": creator_oid, "role": "creator", "name": "Asha",
                 "phone": "+919900000002"}
            )
            await db.creator_profiles.insert_one(
                {"user_id": creator_oid, "name": "Asha",
                 "verification_status": "verified", "verified_at": _now()}
            )
            await server.apply_to_campaign(
                str(campaign["_id"]),
                server.ApplyPayload(pitch="I'd love to", quoted_rate=12000),
                {"_id": str(creator_oid), "role": "creator", "name": "Asha"},
            )
            told = await db.notifications.find(
                {"user_id": brand_oid}
            ).to_list(length=10)
            assert told == []

        run(body)


# ---------------------------------------------------------------------------
# 4. The rate: resolution order, and history
# ---------------------------------------------------------------------------


class TestCommissionResolution:
    def test_nothing_set_anywhere_falls_to_the_global_default(self):
        out = server._resolve_commission({}, {})
        assert out["percent"] == server.platform_fee_percent()
        assert out["source"] == "default"

    def test_a_brand_rate_beats_the_default(self):
        out = server._resolve_commission({}, {"commission_percent": 8})
        assert out == {"percent": 8.0, "source": "brand"}

    def test_a_campaign_rate_beats_the_brand(self):
        out = server._resolve_commission(
            {"commission_percent": 20}, {"commission_percent": 8}
        )
        assert out == {"percent": 20.0, "source": "campaign"}

    def test_zero_is_a_rate_and_not_an_absence(self):
        # **The distinction the whole resolver turns on.** A brand we charge
        # nothing is on 0%; one nobody has negotiated with is on whatever the
        # default is today. Collapsing them would either invent a discount or
        # quietly re-price a free account the next time the default moved.
        out = server._resolve_commission({}, {"commission_percent": 0})
        assert out == {"percent": 0.0, "source": "brand"}
        assert server._commission_of({"commission_percent": 0}) == 0.0
        assert server._commission_of({"commission_percent": None}) is None
        assert server._commission_of({}) is None

    def test_an_unreadable_rate_falls_through_rather_than_throwing(self):
        # The safe direction: it is what the brand was paying before somebody
        # wrote something unreadable into the field.
        out = server._resolve_commission({}, {"commission_percent": "eight"})
        assert out["source"] == "default"

    @pytest.mark.parametrize("bad", [-1, 101])
    def test_a_rate_outside_the_range_is_refused(self, bad):
        with pytest.raises(HTTPException) as err:
            server._clean_commission_percent(bad)
        assert err.value.status_code == 422

    def test_the_campaign_reader_walks_to_the_brand(self):
        # **`_commission_for_campaign`'s early return is an optimisation, not
        # a second guard.** It skips loading the brand when the campaign has
        # its own rate; removing it leaves every answer correct, because
        # `_resolve_commission` checks the campaign first either way. Written
        # down rather than papered over with an assertion that would not mean
        # anything — break-testing is what established it.
        async def body(db):
            _, brand_oid = await _brand(db, commission=8)
            campaign = await _campaign(db, brand_oid)
            assert await server._commission_for_campaign(campaign) == {
                "percent": 8.0, "source": "brand"
            }
            priced = await _campaign(db, brand_oid, commission_percent=22)
            assert await server._commission_for_campaign(priced) == {
                "percent": 22.0, "source": "campaign"
            }

        run(body)


class TestSettingTheRate:
    def test_only_an_admin_sets_a_brand_rate(self):
        # What we charge a client is the relationship, not scoped work — the
        # same line the settings that hand out scope already draw.
        assert guard_allows(server.set_brand_commission, "admin") is True
        assert guard_allows(server.set_brand_commission, "weare_team") is False
        assert guard_allows(server.set_brand_commission, "brand_manager") is False

    def test_a_campaign_rate_is_console_work(self):
        # Deliberately wider than the brand's: a launch carrying different
        # terms is exactly what a `weare_team` member is already trusted with.
        assert guard_allows(server.set_campaign_commission, "weare_team") is True
        assert guard_allows(server.set_campaign_commission, "brand_manager") is False

    def test_setting_it_stores_the_rate_and_audits_both_values(self):
        async def body(db):
            _, brand_oid = await _brand(db, commission=15)
            out = await server.set_brand_commission(
                str(brand_oid),
                server.CommissionPayload(
                    commission_percent=8, reason="Agreed at the renewal call."
                ),
                ADMIN,
            )
            assert out["commission_percent"] == 8.0
            profile = await db.brand_profiles.find_one({"user_id": brand_oid})
            assert profile["commission_percent"] == 8.0
            assert profile["commission_set_by_name"] == "Admin"

            line = await db.audit_log.find_one({"action": "brand.commission"})
            # **Both values.** "Set to 8" cannot answer whether that was a
            # discount or a rise, which is the entire content of the question.
            assert line["before"]["commission_percent"] == 15.0
            assert line["after"]["commission_percent"] == 8.0
            assert line["note"] == "Agreed at the renewal call."

        run(body)

    def test_clearing_it_is_a_null_and_still_costs_a_reason(self):
        async def body(db):
            _, brand_oid = await _brand(db, commission=8)
            out = await server.set_brand_commission(
                str(brand_oid),
                server.CommissionPayload(
                    commission_percent=None, reason="Back to standard terms."
                ),
                ADMIN,
            )
            assert out["commission_percent"] is None
            profile = await db.brand_profiles.find_one({"user_id": brand_oid})
            assert profile["commission_percent"] is None
            # And the rate that now applies is the global one again.
            assert out["effective"]["source"] == "default"

        run(body)

    def test_the_reason_is_required(self):
        with pytest.raises(Exception):
            server.CommissionPayload(commission_percent=8)

    def test_a_brand_reads_its_rate_and_has_nowhere_to_write_one(self):
        # It is on every invoice they pay, so hiding it would be coy — but the
        # update payload has no such key, so the generic copy loop has nothing
        # to let through.
        assert "commission_percent" not in server.BrandProfileUpdate.model_fields
        assert (
            "commission_percent"
            in inspect.getsource(server._serialize_brand_profile)
        )


class TestPaymentsKeepTheirRate:
    async def _to_payment(self, db, *, brand_commission=None, campaign_commission=None):
        _, brand_oid = await _brand(db, commission=brand_commission)
        campaign = await _campaign(
            db,
            brand_oid,
            **({"commission_percent": campaign_commission}
               if campaign_commission is not None else {}),
        )
        collab = await _collab(db, campaign, state="content_approved", shortlisted=True)
        await server.advance_collaboration(
            collab["id"],
            server.AdvanceCollabPayload(from_state="content_approved"),
            ADMIN,
        )
        return brand_oid, campaign, collab

    def test_the_resolved_rate_is_frozen_onto_the_payment(self):
        async def body(db):
            brand_oid, _, collab = await self._to_payment(db, brand_commission=8)
            payment = await db.payments.find_one({"collaboration_id": collab["oid"]})
            assert payment["fee_percent"] == 8.0
            assert payment["fee_percent_source"] == "brand"
            # The margin follows the rate, not the default.
            assert payment["platform_fee"] == 960.0
            assert brand_oid

        run(body)

    def test_a_campaign_rate_wins_at_the_moment_of_the_write(self):
        async def body(db):
            _, _, collab = await self._to_payment(
                db, brand_commission=8, campaign_commission=25
            )
            payment = await db.payments.find_one({"collaboration_id": collab["oid"]})
            assert payment["fee_percent"] == 25.0
            assert payment["fee_percent_source"] == "campaign"
            assert payment["platform_fee"] == 3000.0

        run(body)

    def test_editing_the_rate_afterwards_does_not_move_a_payment(self):
        # **The whole reason the resolution is a function rather than a lookup
        # at the point of use.** Renegotiating terms must not restate last
        # month's invoices.
        async def body(db):
            brand_oid, _, collab = await self._to_payment(db, brand_commission=8)
            await server.set_brand_commission(
                str(brand_oid),
                server.CommissionPayload(
                    commission_percent=30, reason="New terms from April."
                ),
                ADMIN,
            )
            payment = await db.payments.find_one({"collaboration_id": collab["oid"]})
            assert payment["fee_percent"] == 8.0
            assert payment["platform_fee"] == 960.0

        run(body)

    def test_a_mediated_partial_release_recomputes_at_the_stored_rate(self):
        # The one place a recomputation happens against an existing payment,
        # and the one that used to reach for the global default.
        async def body(db):
            brand_oid, campaign, collab = await self._to_payment(db, brand_commission=8)
            await server.set_brand_commission(
                str(brand_oid),
                server.CommissionPayload(commission_percent=40, reason="New terms."),
                ADMIN,
            )
            await db.collaborations.update_one(
                {"_id": collab["oid"]},
                {"$set": {"dispute": {"state": "open", "raised_by_role": "creator",
                                      "reason": "Half of it never ran."}}},
            )
            await server.resolve_dispute(
                collab["id"],
                server.DisputeResolutionPayload(
                    resolution="partial_release",
                    amount=6000,
                    note="Half the deliverables arrived.",
                ),
                ADMIN,
            )
            payment = await db.payments.find_one({"collaboration_id": collab["oid"]})
            assert payment["platform_fee"] == 480.0  # 8% of 6000, not 40%
            # **And the creator keeps the whole of what was released.** This
            # line used to deduct the fee from the payout, so a mediation paid
            # out less than the figure the mediator wrote down — found while
            # making the rate historical.
            assert payment["creator_payout"] == 6000.0
            assert payment["brand_invoice_amount"] == 6480.0
            assert campaign

        run(body)

    def test_a_payment_written_before_the_field_reads_the_global_default(self):
        assert server._payment_fee_percent({}) == server.platform_fee_percent()
        assert server._payment_fee_percent(None) == server.platform_fee_percent()
        assert server._payment_fee_percent({"fee_percent": 12}) == 12.0

    def test_the_export_prints_the_stored_rate(self):
        src = inspect.getsource(server._export_payments)
        assert "_payment_fee_percent(d)" in src
        assert "Commission %" in src


# ---------------------------------------------------------------------------
# 5. The campaign fee, and the refund
# ---------------------------------------------------------------------------


class TestRefundEligibility:
    def test_a_filled_campaign_has_no_refund_question(self):
        out = server._refund_reckoning(
            {"campaign_fee": 25000}, targeted=4, finalised=4, shortlisted=4, rejected=0
        )
        assert out["state"] == "none"
        assert out["eligible"] is False

    def test_underfilled_with_no_rejections_is_eligible(self):
        # The sentence the requirement asked for, word for word.
        out = server._refund_reckoning(
            {"campaign_fee": 25000}, targeted=8, finalised=5, shortlisted=5, rejected=0
        )
        assert out["eligible"] is True
        assert out["state"] == "eligible"
        assert out["reason"] == (
            "Underfilled by 3; brand rejected 0 of 5 shortlisted — refund eligible."
        )

    def test_rejecting_every_shortlisted_creator_forfeits_it(self):
        # We delivered the whole brief and it was turned down.
        out = server._refund_reckoning(
            {"campaign_fee": 25000}, targeted=5, finalised=0, shortlisted=5, rejected=5
        )
        assert out["eligible"] is False
        assert out["state"] == "forfeited"
        assert "would have filled at 5 of 5" in out["reason"]

    def test_the_middle_is_answered_by_the_same_question(self):
        # **The case the policy's two examples do not name**, and the reason
        # the rule is "would it have filled had they taken everybody we put
        # forward" rather than a count of rejections. Ten shortlisted on an
        # eight-creator brief: they could have filled it, so the shortfall is
        # theirs even though they took six.
        out = server._refund_reckoning(
            {"campaign_fee": 25000}, targeted=8, finalised=6, shortlisted=10, rejected=4
        )
        assert out["eligible"] is False

    def test_and_the_other_middle_goes_the_brands_way(self):
        # Six shortlisted on an eight-creator brief, one turned down: even
        # taking all six leaves us two short of our own doing.
        out = server._refund_reckoning(
            {"campaign_fee": 25000}, targeted=8, finalised=5, shortlisted=6, rejected=1
        )
        assert out["eligible"] is True

    def test_a_brief_with_no_fee_has_nothing_to_assess(self):
        async def body(db):
            _, brand_oid = await _brand(db)
            campaign = await _campaign(db, brand_oid)
            assert await server._refund_assessment(campaign) is None

        run(body)

    def test_the_counts_come_off_the_collaborations(self):
        # Shortlisted is `agreed_at`, the same line `_brand_sees_collab`
        # draws — so what we counted and what the brand actually saw cannot
        # disagree. Rejected is shortlisted *and* declined: somebody we never
        # put forward is not somebody they turned down.
        async def body(db):
            _, brand_oid = await _brand(db)
            campaign = await _campaign(db, brand_oid, creators_needed=4, campaign_fee=25000)
            await _collab(db, campaign, state="applied")           # never shortlisted
            await _collab(db, campaign, state="declined")          # nor this one
            await _collab(db, campaign, state="declined", shortlisted=True)
            await _collab(db, campaign, state="accepted", shortlisted=True)
            await _collab(db, campaign, state="closed", shortlisted=True)

            counts = await server._refund_counts_for(campaign)
            assert counts["targeted"] == 4
            assert counts["finalised"] == 2
            assert counts["shortlisted"] == 3
            assert counts["rejected"] == 1

        run(body)


class TestTheRefundDecision:
    async def _closed_short(self, db, **over):
        _, brand_oid = await _brand(db)
        campaign = await _campaign(
            db, brand_oid, creators_needed=4, campaign_fee=25000, **over
        )
        await _collab(db, campaign, state="accepted", shortlisted=True)
        return brand_oid, campaign

    def test_the_reasoning_is_on_the_admin_campaign_page(self):
        async def body(db):
            _, campaign = await self._closed_short(db)
            out = await server.read_campaign_refund(str(campaign["_id"]), ADMIN)
            assert out["state"] == "eligible"
            assert "Underfilled by 3" in out["reason"]
            assert out["campaign_fee"] == 25000

        run(body)

    def test_nothing_refunds_automatically(self):
        # The computation says what it thinks; it moves no money and writes no
        # decision. A rule that refunded on its own would be a rule nobody
        # checked.
        async def body(db):
            _, campaign = await self._closed_short(db)
            await server.read_campaign_refund(str(campaign["_id"]), ADMIN)
            row = await db.campaigns.find_one({"_id": campaign["_id"]})
            assert row.get("refund") is None

        run(body)

    def test_confirming_records_the_decision_and_what_the_rule_said(self):
        async def body(db):
            brand_oid, campaign = await self._closed_short(db)
            out = await server.decide_campaign_refund(
                str(campaign["_id"]),
                server.RefundDecisionPayload(
                    state="refunded", reason="Agreed on the call with Priya."
                ),
                ADMIN,
            )
            assert out["decided_state"] == "refunded"
            assert out["overridden"] is False

            row = await db.campaigns.find_one({"_id": campaign["_id"]})
            assert row["refund"]["state"] == "refunded"
            assert row["refund"]["computed_state"] == "eligible"
            assert row["refund"]["amount"] == 25000
            assert row["refund"]["decided_by_name"] == "Admin"

            line = await db.audit_log.find_one({"action": "campaign.refund"})
            assert line["note"] == "Agreed on the call with Priya."
            # The brand is told either way.
            told = await db.notifications.find_one({"user_id": brand_oid})
            assert told["event"] == "campaign_fee_refunded"

        run(body)

    def test_an_override_against_the_computation_is_visible_as_one(self):
        # An admin refunding a forfeited fee is a judgement worth being able
        # to find; one that silently agreed with the panel would be
        # indistinguishable from the panel having acted alone.
        async def body(db):
            _, brand_oid = await _brand(db)
            campaign = await _campaign(
                db, brand_oid, creators_needed=2, campaign_fee=25000
            )
            await _collab(db, campaign, state="declined", shortlisted=True)
            await _collab(db, campaign, state="declined", shortlisted=True)

            before = await server.read_campaign_refund(str(campaign["_id"]), ADMIN)
            assert before["state"] == "forfeited"

            out = await server.decide_campaign_refund(
                str(campaign["_id"]),
                server.RefundDecisionPayload(
                    state="refunded", reason="Our shortlist was weak; goodwill."
                ),
                ADMIN,
            )
            assert out["overridden"] is True
            assert out["decided_state"] == "refunded"

        run(body)

    def test_it_can_only_be_decided_once(self):
        async def body(db):
            _, campaign = await self._closed_short(db)
            await server.decide_campaign_refund(
                str(campaign["_id"]),
                server.RefundDecisionPayload(state="refunded", reason="Agreed."),
                ADMIN,
            )
            with pytest.raises(HTTPException) as err:
                await server.decide_campaign_refund(
                    str(campaign["_id"]),
                    server.RefundDecisionPayload(state="declined", reason="Changed."),
                    ADMIN,
                )
            assert err.value.status_code == 409
            row = await db.campaigns.find_one({"_id": campaign["_id"]})
            assert row["refund"]["state"] == "refunded"

        run(body)

    def test_it_lands_on_the_payment_records(self):
        async def body(db):
            _, brand_oid = await _brand(db)
            campaign = await _campaign(
                db, brand_oid, creators_needed=4, campaign_fee=25000
            )
            collab = await _collab(db, campaign, state="closed", shortlisted=True)
            await db.payments.insert_one(
                {"_id": ObjectId(), "collaboration_id": collab["oid"],
                 "state": "paid", "agreed_amount": 12000, "fee_percent": 15.0}
            )
            await server.decide_campaign_refund(
                str(campaign["_id"]),
                server.RefundDecisionPayload(state="refunded", reason="Agreed."),
                ADMIN,
            )
            payment = await db.payments.find_one({"collaboration_id": collab["oid"]})
            assert payment["campaign_fee_refund_state"] == "refunded"
            assert payment["campaign_fee_refund_amount"] == 25000

        run(body)

    def test_declining_records_no_amount(self):
        # A declined refund is not a refund of zero, and a finance export
        # reading `0` there would look like money that moved.
        async def body(db):
            _, brand_oid = await _brand(db)
            campaign = await _campaign(
                db, brand_oid, creators_needed=2, campaign_fee=25000
            )
            collab = await _collab(db, campaign, state="declined", shortlisted=True)
            await _collab(db, campaign, state="declined", shortlisted=True)
            await db.payments.insert_one(
                {"_id": ObjectId(), "collaboration_id": collab["oid"], "state": "paid"}
            )
            await server.decide_campaign_refund(
                str(campaign["_id"]),
                server.RefundDecisionPayload(
                    state="declined", reason="Both shortlisted creators were turned down."
                ),
                ADMIN,
            )
            payment = await db.payments.find_one({"collaboration_id": collab["oid"]})
            assert payment["campaign_fee_refund_state"] == "declined"
            assert payment["campaign_fee_refund_amount"] is None

        run(body)

    def test_only_an_admin_may_decide_though_staff_may_price(self):
        # Pricing a brief is scoped work; moving money back to a client is not.
        assert guard_allows(server.decide_campaign_refund, "admin") is True
        assert guard_allows(server.decide_campaign_refund, "weare_team") is False
        assert guard_allows(server.set_campaign_fee, "weare_team") is True
        assert guard_allows(server.set_campaign_fee, "brand_manager") is False

    def test_closing_short_raises_the_decision_once(self):
        async def body(db):
            admin_oid = ObjectId()
            await db.users.insert_one({"_id": admin_oid, "role": "admin"})
            user, brand_oid = await _brand(db)
            campaign = await _campaign(
                db, brand_oid, creators_needed=4, campaign_fee=25000
            )
            await _collab(db, campaign, state="accepted", shortlisted=True)

            await server.close_brand_campaign(
                str(campaign["_id"]), server.ReasonPayload(reason="Ran its course."), user
            )
            told = await db.notifications.find(
                {"event": "campaign_fee_decision"}
            ).to_list(length=10)
            assert len(told) == 1
            assert "Underfilled by 3" in told[0]["body"]

            # The claim is the write, so a second pass sends nothing.
            await server._raise_refund_decision(
                await db.campaigns.find_one({"_id": campaign["_id"]})
            )
            assert await db.notifications.count_documents(
                {"event": "campaign_fee_decision"}
            ) == 1

        run(body)

    def test_a_filled_campaign_raises_nothing(self):
        # The control: without it a version that notified unconditionally
        # would pass the test above.
        async def body(db):
            await db.users.insert_one({"_id": ObjectId(), "role": "admin"})
            user, brand_oid = await _brand(db)
            campaign = await _campaign(
                db, brand_oid, creators_needed=1, campaign_fee=25000
            )
            await _collab(db, campaign, state="accepted", shortlisted=True)
            await server.close_brand_campaign(
                str(campaign["_id"]), server.ReasonPayload(reason="Done."), user
            )
            assert await db.notifications.count_documents(
                {"event": "campaign_fee_decision"}
            ) == 0

        run(body)

    def test_the_policy_is_stated_before_it_is_needed(self):
        # A refund policy somebody meets for the first time during an argument
        # is a surprise rather than a policy. Said at creation and frozen into
        # the terms both sides accept.
        terms = server._build_terms({"title": "Tasting"}, {})
        assert terms["refund_terms"] == server.REFUND_POLICY_TERMS
        assert "refundable" in server.REFUND_POLICY_TERMS
        assert "turn down" in server.REFUND_POLICY_TERMS


# ---------------------------------------------------------------------------
# 6. The frontend half — mounted, mirrored, and not deciding for itself
# ---------------------------------------------------------------------------


def _read(*parts):
    return FRONTEND.joinpath(*parts).read_text()


def _strip_comments(src: str) -> str:
    import re

    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(l for l in src.splitlines() if not l.strip().startswith("//"))


class TestTheFrontendHalf:
    def test_the_post_form_offers_no_execution_choice(self):
        # It was two buttons. A picker still on screen would be a choice the
        # server is about to override, which is worse than no choice at all.
        src = _strip_comments(_read("pages", "PostCampaign.jsx"))
        assert "EXECUTION_OPTIONS" not in src
        assert "setExecutionOwner" not in src
        # And the field is not posted: the create path ignores it and the edit
        # path refuses it, so sending one is noise at best.
        assert "execution_owner:" not in src

    def test_the_form_states_the_offer_and_the_refund(self):
        # Rendered, not merely imported — an import with the render deleted
        # is the failure this class of assertion exists to catch. `MANAGED_NOTE`
        # is the fallback in a ternary, because a launch has its own sentence
        # to show instead; `REFUND_TERMS` is unconditional.
        src = _strip_comments(_read("pages", "PostCampaign.jsx"))
        assert ": MANAGED_NOTE}" in src
        assert "{REFUND_TERMS}" in src
        # And the specific sentence still wins where there is one, so a launch
        # is not told the generic thing.
        assert "weareRun ? weareRun.line" in src

    def test_the_two_promises_match_the_server_word_for_word(self):
        # **Mirrored with a drift test**, because the form renders both before
        # a campaign exists — there is nothing to fetch them from at the
        # moment they matter most. The same arrangement `followerTiers.js` and
        # `platformTerms.js` use.
        src = _read("lib", "execution.js")
        for name, expected in (
            ("MANAGED_NOTE", server.MANAGED_BY_DEFAULT_SENTENCE),
            ("REFUND_TERMS", server.REFUND_POLICY_TERMS),
        ):
            start = src.index(f"export const {name} =")
            mirrored = "".join(src[start : src.index(";", start)].split('"')[1::2])
            assert mirrored == expected, name

    def test_the_brand_board_offers_no_way_to_invite(self):
        # A backend rule with a button still on screen is a 403 somebody
        # presses. Both invite surfaces went: the saved lists entirely, and
        # the suggestions panel's button.
        src = _read("pages", "BrandCampaignApplicants.jsx")
        assert "/invite" not in src
        assert "<CreatorLists" not in src
        # The curated panel stays, and is told it cannot invite rather than
        # working it out for itself.
        assert "canInvite={false}" in src

    def test_the_lists_moved_to_the_people_who_now_invite(self):
        # A route with no mount is as unreachable as a route with no caller,
        # and inviting from a saved list is a real job — it is simply ours.
        assert "<CreatorLists" in _read("components", "admin", "CampaignDetailPage.jsx")

    def test_the_commercial_panels_are_mounted(self):
        assert "<CommercialTerms" in _read(
            "components", "admin", "CampaignDetailPage.jsx"
        )
        assert "<CommissionControl" in _read(
            "components", "admin", "BrandDetailPage.jsx"
        )

    def test_the_browser_computes_no_refund_verdict(self):
        # `_refund_reckoning` decides on the server and ships the sentence.
        # A browser working out whether a campaign underfilled would be a
        # second definition of "filled" — the mistake `isStale` made here once.
        src = _strip_comments(_read("components", "admin", "CommercialTerms.jsx"))
        assert "refund.reason" in src
        for probe in ("targeted -", "creators_needed", "shortfall >", "eligible ="):
            assert probe not in src, f"the panel decides for itself: {probe}"
