"""The three survey-driven changes, driven rather than read.

Companion to the structural suites, and written to the rule
`test_money_paths.py` states: build the row, call the **real handler**, and
read the database back. A guard that is present and does nothing passes a
source sweep and fails here.

What each section is for:

  * **The payout window.** Two settings govern two opposite directions and
    the whole risk in this feature is conflating them — so the first test is
    that `payment_terms_days` and `creator_payout_days` do not share a stored
    id, a default, or a value. The rest is the absent-reads-safe rule, the
    freeze into the terms snapshot, and the health check.
  * **Barter.** A reversal, so the tests assert both halves: what a brand may
    now do, and what it still may not. The mitigations are driven through the
    real write paths, because a required field that is only required in the
    payload model is not required on the edit that changes something else.
  * **The address.** The purpose line, and the one promise in it that is
    checkable — a brand never sees the address, at any stage.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import server

FRONTEND = Path(__file__).resolve().parents[3] / "frontend" / "src"
LOOP = None
ADMIN = {"_id": str(ObjectId()), "role": "admin", "name": "Admin"}


def run(body):
    """One loop per call, kept in a module global — the arrangement
    `test_money_paths.py` uses, and for its reasons: `get_event_loop` fails in
    an xdist worker and `asyncio.run` closes the loop mongomock built on."""
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()

    async def go():
        db = AsyncMongoMockClient()["survey_changes"]
        original = server.db
        server.db = db
        # The window is cached for 30s in a module global, so a test that
        # stores one and immediately reads it would get whatever the previous
        # test left behind — across a fresh mock database, which looks
        # exactly like the write being dropped. Same trap `sla_targets`
        # documents, same fix.
        server._CREATOR_PAYOUT_CACHE["at"] = None
        server._CREATOR_PAYOUT_CACHE["value"] = None
        try:
            return await body(db)
        finally:
            server.db = original
            server._CREATOR_PAYOUT_CACHE["at"] = None
            server._CREATOR_PAYOUT_CACHE["value"] = None

    return LOOP.run_until_complete(go())


async def refuses(coro):
    """The HTTPException a call raises, or an assertion if it did not.

    Awaited from inside a `run` body rather than driving its own loop — the
    loop is already running there, and starting a second one on it is the
    error this shape exists to avoid.
    """
    try:
        await coro
    except HTTPException as err:
        return err
    raise AssertionError("expected a refusal")


def no_comments(path: Path) -> str:
    """Source with `//` lines and `/* */` blocks removed.

    The convention here is to explain a change where it happened, so a sweep
    that reads prose fails on its own documentation.
    """
    src = path.read_text(encoding="utf-8")
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


# ---------------------------------------------------------------------------
# 1. The payout window
# ---------------------------------------------------------------------------


class TestTheTwoWindowsAreNotTheSameWindow:
    """**The whole risk in this feature, first.** `payment_terms_days` is how
    long a brand has to settle an invoice to us. `creator_payout_days` is how
    long we take to pay a creator. Reusing the first for the second would tie
    a promise we make to creators to a commercial term we negotiate with
    brands, so that giving one client a longer rope silently lengthened the
    wait for everybody who did the work."""

    def test_they_do_not_share_a_stored_id(self):
        assert server._PAYMENT_TERMS_SETTINGS_ID != server._CREATOR_PAYOUT_SETTINGS_ID
        assert server._CREATOR_PAYOUT_SETTINGS_ID == "creator_payout_days"

    def test_they_do_not_share_a_default(self):
        assert server.PAYMENT_TERMS_DAYS == 14
        assert server.CREATOR_PAYOUT_DAYS == 7

    def test_changing_one_does_not_move_the_other(self):
        """Driven, because two constants being different proves nothing about
        two *readers* being different."""

        async def body(db):
            await server.put_payment_terms(
                server.PaymentTermsPayload(days=30), ADMIN
            )
            assert await server.payment_terms_days() == 30
            # Unmoved.
            assert await server.creator_payout_days() == server.CREATOR_PAYOUT_DAYS

            await server.put_creator_payout_window(
                server.CreatorPayoutPayload(days=2), ADMIN
            )
            assert await server.creator_payout_days() == 2
            assert await server.payment_terms_days() == 30

        run(body)

    def test_each_setting_names_its_direction_in_a_comment(self):
        """A reader arriving at either one has to be able to tell which leg it
        governs without reading the call sites."""
        src = server_source()
        for anchor in ("_PAYMENT_TERMS_SETTINGS_ID = ", "_CREATOR_PAYOUT_SETTINGS_ID = "):
            before = src[: src.index(anchor)]
            # The comment block immediately above it.
            block = before.rsplit("\n\n", 1)[-1]
            assert "creator" in block.lower() and "brand" in block.lower(), anchor


def server_source() -> str:
    return Path(server.__file__).read_text(encoding="utf-8")


class TestThePayoutWindowReads:
    def test_absent_reads_as_the_platform_default_never_zero(self):
        """The absent-reads-safe rule. Every campaign written before this
        field carries no override, and reading that as "paid the same day"
        would publish a promise nobody made across the back catalogue."""
        assert server._creator_payout_days({}, 7) == 7
        assert server._creator_payout_days(None, 7) == 7
        assert server._creator_payout_days({"creator_payout_days": None}, 7) == 7
        # And an unreadable stored value falls back rather than becoming 0.
        assert server._creator_payout_days({"creator_payout_days": "soon"}, 7) == 7
        assert server._creator_payout_days({"creator_payout_days": -3}, 7) == 7

    def test_a_campaign_override_wins(self):
        assert server._creator_payout_days({"creator_payout_days": 2}, 7) == 2

    def test_zero_is_a_real_answer_and_is_not_the_default(self):
        """"Paid the same day" is a promise somebody might make, so 0 has to
        survive the reader rather than being read as absent."""
        assert server._creator_payout_days({"creator_payout_days": 0}, 7) == 0
        assert "same day" in server._payout_promise(0)

    def test_the_promise_reads_as_a_promise(self):
        assert server._payout_promise(7) == "Paid within 7 days of approved delivery."
        assert server._payout_promise(1) == "Paid within 1 day of approved delivery."


class TestTheWindowIsFrozenAtAcceptance:
    """The same rule the cancellation policy and the refund policy hold: a
    later change to the platform number must not reach backwards into an
    arrangement somebody already accepted."""

    def test_the_snapshot_carries_the_window_that_applied(self):
        async def body(db):
            await server.put_creator_payout_window(
                server.CreatorPayoutPayload(days=3), ADMIN
            )
            collab_oid = ObjectId()
            await db.collaborations.insert_one(
                {"_id": collab_oid, "state": "accepted", "agreed_amount": 9000}
            )
            campaign = {"_id": ObjectId(), "title": "Tasting", "compensation_type": "fixed"}
            await server._issue_terms_snapshot(
                {"_id": collab_oid, "agreed_amount": 9000}, campaign
            )

            row = await db.collaborations.find_one({"_id": collab_oid})
            assert row["terms"]["payout"]["days"] == 3

            # The platform moves; the snapshot does not.
            await server.put_creator_payout_window(
                server.CreatorPayoutPayload(days=21), ADMIN
            )
            again = await db.collaborations.find_one({"_id": collab_oid})
            assert again["terms"]["payout"]["days"] == 3

        run(body)


class TestTheDueDateIsADateAndOnlyWhenItMeansSomething:
    def test_there_is_no_due_date_before_approval(self):
        """"Within 7 days" is the policy and belongs on the brief; a date only
        exists once there is an approval to count from."""
        for state in ("applied", "accepted", "attended", "content_submitted"):
            assert server._payout_due_at({"state": state}, {}, 7) is None

    def test_it_counts_from_approval_not_from_entering_the_payment_run(self):
        """**The trap this field exists for.** `state_since` moves again when
        the row reaches `in_payment`, so reading the clock would restart the
        promise every time somebody got round to raising the payment."""
        approved = datetime(2026, 3, 1, tzinfo=timezone.utc)
        collab = {
            "state": "in_payment",
            "content_approved_at": approved,
            # The row moved on a week later. The due date must not move with it.
            "state_since": approved + timedelta(days=7),
        }
        assert server._payout_due_at(collab, {}, 7) == approved + timedelta(days=7)

    def test_a_row_approved_before_the_stamp_falls_back_to_the_clock(self):
        """And the fallback can only place the date *later* than the truth,
        which is the safe direction: a promise that reads later than it was is
        one we are still keeping."""
        since = datetime(2026, 3, 1, tzinfo=timezone.utc)
        collab = {"state": "content_approved", "state_since": since}
        assert server._payout_due_at(collab, {}, 7) == since + timedelta(days=7)

    def test_the_campaign_override_sets_the_date(self):
        approved = datetime(2026, 3, 1, tzinfo=timezone.utc)
        collab = {"state": "content_approved", "content_approved_at": approved}
        due = server._payout_due_at(collab, {"creator_payout_days": 2}, 7)
        assert due == approved + timedelta(days=2)

    def test_approval_stamps_the_anchor(self):
        """Driven through the real handler, because a stamp written by the
        test proves nothing about the handler writing it."""

        async def body(db):
            brand, creator = ObjectId(), ObjectId()
            campaign_oid, collab_oid = ObjectId(), ObjectId()
            await db.campaigns.insert_one(
                {"_id": campaign_oid, "brand_id": brand, "title": "Tasting",
                 "compensation_type": "fixed", "status": "open",
                 "execution_owner": "brand"}
            )
            await db.collaborations.insert_one(
                {"_id": collab_oid, "campaign_id": campaign_oid, "creator_id": creator,
                 "state": "content_submitted", "agreed_amount": 9000}
            )
            await db.brand_profiles.insert_one(
                {"user_id": brand, "verified": True, "business_name": "Toit"}
            )
            await server.brand_approve_content(
                str(collab_oid),
                server.DisclosureCheckPayload(disclosure_confirmed=True),
                {"_id": str(brand), "role": "brand_manager", "name": "Toit",
                 "brand_id": str(brand)},
            )
            row = await db.collaborations.find_one({"_id": collab_oid})
            assert row["state"] == "content_approved"
            assert row.get("content_approved_at") is not None

        run(body)


class TestTheHealthPanelMeasuresThePromise:
    """The promise is only worth making if we can see when we are breaking
    it."""

    def test_a_row_past_its_own_campaigns_window_is_reported(self):
        async def body(db):
            brand, creator = ObjectId(), ObjectId()
            late, ontime = ObjectId(), ObjectId()
            campaign_oid = ObjectId()
            await db.campaigns.insert_one(
                {"_id": campaign_oid, "brand_id": brand, "title": "Tasting",
                 "creator_payout_days": 2}
            )
            await db.creator_profiles.insert_one({"user_id": creator, "name": "Asha"})
            now = datetime.now(timezone.utc)
            await db.collaborations.insert_many([
                {"_id": late, "campaign_id": campaign_oid, "creator_id": creator,
                 "state": "in_payment",
                 "content_approved_at": now - timedelta(days=9)},
                # The control: approved yesterday, well inside a two-day window.
                {"_id": ontime, "campaign_id": campaign_oid, "creator_id": creator,
                 "state": "content_approved",
                 "content_approved_at": now - timedelta(hours=6)},
            ])

            health = await server.admin_health(ADMIN)
            check = next(c for c in health["checks"] if c["key"] == "payouts_late")
            ids = [row["id"] for row in check["items"]]
            assert str(late) in ids
            assert str(ontime) not in ids, "a row inside its window is not late"

        run(body)

    def test_the_order_is_the_fraction_of_the_allowance_used(self):
        """The reading `_overdue_check` settled on. A row one day past a
        same-day promise has burnt more of its allowance than one a day past a
        fortnight, and absolute days over cannot say that — so the fixture is
        built to order differently under the two keys."""

        async def body(db):
            brand, creator = ObjectId(), ObjectId()
            tight, loose = ObjectId(), ObjectId()
            tight_camp, loose_camp = ObjectId(), ObjectId()
            await db.campaigns.insert_many([
                {"_id": tight_camp, "brand_id": brand, "title": "Same day",
                 "creator_payout_days": 1},
                {"_id": loose_camp, "brand_id": brand, "title": "Fortnight",
                 "creator_payout_days": 30},
            ])
            await db.creator_profiles.insert_one({"user_id": creator, "name": "Asha"})
            now = datetime.now(timezone.utc)
            await db.collaborations.insert_many([
                # 3 days over a 1-day window: 4/1 = 4.0 of its allowance.
                {"_id": tight, "campaign_id": tight_camp, "creator_id": creator,
                 "state": "in_payment", "content_approved_at": now - timedelta(days=4)},
                # 10 days over a 30-day window: 40/30 = 1.33 — more days over,
                # less of the allowance used.
                {"_id": loose, "campaign_id": loose_camp, "creator_id": creator,
                 "state": "in_payment", "content_approved_at": now - timedelta(days=40)},
            ])

            health = await server.admin_health(ADMIN)
            check = next(c for c in health["checks"] if c["key"] == "payouts_late")
            ids = [row["id"] for row in check["items"]]
            assert ids[0] == str(tight), "absolute days over would put the other first"
            assert check["presorted"] is True

        run(body)


class TestThePayoutWindowReachesEverySurface:
    """Named rather than swept, because the point of the feature is *where*
    it appears. A brief a creator reads before applying has to carry it."""

    def test_the_creators_campaign_shape(self):
        out = server._serialize_campaign(
            {"_id": ObjectId(), "brand_id": ObjectId(), "creator_payout_days": 3},
            None,
            payout_default=server.CREATOR_PAYOUT_DAYS,
        )
        assert out["payout"]["days"] == 3
        assert "3 days" in out["payout"]["promise"]

    def test_the_owners_campaign_shape(self):
        out = server._serialize_brand_campaign(
            {"_id": ObjectId(), "brand_id": ObjectId()},
            0,
            payout_default=5,
        )
        assert out["payout"]["days"] == 5

    def test_the_share_page(self):
        html = server._share_page_html(
            {"_id": ObjectId(), "title": "Tasting", "creators_needed": 2,
             "compensation_type": "fixed", "budget_per_creator": 9000,
             "creator_payout_days": 4},
            {"business_name": "Toit"},
            2,
            payout_default=server.CREATOR_PAYOUT_DAYS,
        )
        assert "Paid within 4 days of approved delivery." in html

    def test_the_creators_own_collaboration_row(self):
        approved = datetime(2026, 3, 1, tzinfo=timezone.utc)
        row = server._serialize_collab_row(
            {"_id": ObjectId(), "campaign_id": ObjectId(),
             "state": "content_approved", "content_approved_at": approved},
            {"_id": ObjectId(), "creator_payout_days": 3},
            "Toit",
            payout_default=server.CREATOR_PAYOUT_DAYS,
        )
        assert row["payout_due_at"].startswith("2026-03-04")

    def test_the_managers_brief_panel(self):
        """Driven, because this one is built inside an async handler and a
        key that is merely in the dict literal is a key a refactor drops."""

        async def body(db):
            brand, creator, manager = ObjectId(), ObjectId(), ObjectId()
            campaign_oid = ObjectId()
            await db.campaigns.insert_one(
                {"_id": campaign_oid, "brand_id": brand, "title": "Tasting",
                 "manager_id": manager, "execution_owner": "weare",
                 "creator_payout_days": 4, "status": "open"}
            )
            await db.brand_profiles.insert_one(
                {"user_id": brand, "verified": True, "business_name": "Toit"}
            )
            out = await server.campaign_roster(
                str(campaign_oid),
                {"_id": str(manager), "role": "campaign_manager", "name": "Dev"},
            )
            assert out["payout"]["days"] == 4

        run(body)


class TestOnlyStaffSetTheWindow:
    def test_a_brand_editing_its_own_brief_is_refused(self):
        with pytest.raises(HTTPException) as exc:
            server._refuse_brand_payout_window({"creator_payout_days": 1})
        assert exc.value.status_code == 422

    def test_an_edit_that_does_not_mention_it_is_fine(self):
        server._refuse_brand_payout_window({"title": "A new title"})

    def test_the_brands_own_create_payload_has_no_such_key(self):
        """Nothing for the generic copy loop to let through."""
        assert "creator_payout_days" not in server.PostCampaignPayload.model_fields
        assert "creator_payout_days" in server.AdminCreateCampaignPayload.model_fields

    def test_the_settings_route_is_admin_only(self):
        """Not `CONSOLE_ROLES`: a promise the operation makes with its own
        money across every brand is not scoped work."""
        from test_money_paths import guard_allows

        assert guard_allows(server.put_creator_payout_window, "admin")
        assert not guard_allows(server.put_creator_payout_window, "weare_team")


class TestTheResolverIsTheOnlyWriter:
    def test_an_omitted_key_leaves_it_alone(self):
        assert server._resolve_payout_window({}) == {}

    def test_an_explicit_null_clears_the_override(self):
        """A window typed by mistake has to be removable, and `0` is a
        different claim rather than a way of saying "no override"."""
        assert server._resolve_payout_window({"creator_payout_days": None}) == {
            "creator_payout_days": None
        }

    def test_zero_survives(self):
        assert server._resolve_payout_window({"creator_payout_days": 0}) == {
            "creator_payout_days": 0
        }

    def test_an_admin_edit_writes_through_it(self):
        async def body(db):
            brand = ObjectId()
            campaign_oid = ObjectId()
            await db.campaigns.insert_one(
                {"_id": campaign_oid, "brand_id": brand, "title": "Tasting",
                 "status": "open", "creator_payout_days": 9}
            )
            await db.brand_profiles.insert_one(
                {"user_id": brand, "verified": True, "business_name": "Toit"}
            )
            await server.admin_update_campaign(
                str(campaign_oid),
                server.UpdateCampaignPayload(creator_payout_days=None),
                ADMIN,
            )
            row = await db.campaigns.find_one({"_id": campaign_oid})
            assert row["creator_payout_days"] is None, "an explicit null must clear"

        run(body)


# ---------------------------------------------------------------------------
# 2. Barter, postable by a brand
# ---------------------------------------------------------------------------


async def _brand_scene(db, **campaign):
    """A verified brand ready to post."""
    brand = ObjectId()
    await db.users.insert_one(
        {"_id": brand, "role": "brand_manager", "name": "Toit", "brand_id": brand,
         "phone": "+919900000001"}
    )
    await db.brand_profiles.insert_one(
        {"user_id": brand, "verified": True, "business_name": "Toit",
         "verification_state": "verified"}
    )
    return {"_id": str(brand), "role": "brand_manager", "name": "Toit",
            "brand_id": str(brand)}


def _post(**over):
    base = dict(
        title="Tasting night",
        brief="Come and eat.",
        deliverables="1 reel",
        budget_per_creator=0,
        category="fnb",
        area="Indiranagar",
        creators_needed=2,
        campaign_type="personal_table",
        start_date=datetime.now(timezone.utc) + timedelta(days=3),
        end_date=datetime.now(timezone.utc) + timedelta(days=10),
    )
    base.update(over)
    return server.PostCampaignPayload(**base)


class TestABrandMayNowPostBarter:
    def test_the_write_path_accepts_it(self):
        """**The reversal, driven.** The guard used to 422 here."""

        async def body(db):
            brand = await _brand_scene(db)
            out = await server.create_brand_campaign(
                _post(
                    compensation_type="barter",
                    barter_description="Dinner for two, about Rs 4,000.",
                ),
                brand,
            )
            row = await db.campaigns.find_one({"_id": ObjectId(out["id"])})
            assert server._compensation_type(row) == "barter"
            assert row["barter_description"].startswith("Dinner for two")

        run(body)

    def test_the_form_offers_it(self):
        """Genuinely present, not present and disabled — a disabled control is
        a thing somebody re-enables from devtools."""
        src = no_comments(FRONTEND / "lib" / "compensation.js")
        assert '"barter"' in src.split("BRAND_ALLOWED")[1].split("]")[0]

    def test_the_frontend_list_matches_the_server(self):
        src = no_comments(FRONTEND / "lib" / "compensation.js")
        allowed = src.split("BRAND_ALLOWED = [")[1].split("]")[0]
        for kind in server.BRAND_COMPENSATION_TYPES:
            assert f'"{kind}"' in allowed, kind
        assert allowed.count('"') // 2 == len(server.BRAND_COMPENSATION_TYPES)


class TestTheHalfOfTheGuardThatSurvived:
    def test_a_brand_cannot_undo_a_barter_brief_we_made(self):
        """Never about self-serve: this stops a WeAre arrangement being
        silently turned back into a cash liability."""

        async def body(db):
            brand = await _brand_scene(db)
            campaign_oid = ObjectId()
            await db.campaigns.insert_one(
                {"_id": campaign_oid, "brand_id": ObjectId(brand["brand_id"]),
                 "title": "Ours", "status": "draft", "compensation_type": "barter",
                 "barter_description": "A stay", "campaign_type": "personal_table"}
            )
            err = await refuses(
                server.update_brand_campaign(
                    str(campaign_oid),
                    server.UpdateCampaignPayload(compensation_type="fixed"),
                    brand,
                )
            )
            assert err.status_code == 422
            row = await db.campaigns.find_one({"_id": campaign_oid})
            assert server._compensation_type(row) == "barter", "it must not have moved"

        run(body)


class TestABarterBriefHasToSayWhatIsOnOffer:
    """The mitigation that shipped with the reversal. Driven on every write
    path, because a field that is only required in the payload model is not
    required on an edit that changes something else."""

    def test_the_brand_create_path_refuses_an_unstated_one(self):
        async def body(db):
            brand = await _brand_scene(db)
            err = await refuses(
                server.create_brand_campaign(_post(compensation_type="barter"), brand)
            )
            assert err.status_code == 422
            assert await db.campaigns.count_documents({}) == 0, "nothing was written"

        run(body)

    def test_the_brand_edit_path_refuses_switching_without_one(self):
        async def body(db):
            brand = await _brand_scene(db)
            campaign_oid = ObjectId()
            await db.campaigns.insert_one(
                {"_id": campaign_oid, "brand_id": ObjectId(brand["brand_id"]),
                 "title": "Paid", "status": "draft", "compensation_type": "fixed",
                 "campaign_type": "personal_table"}
            )
            err = await refuses(
                server.update_brand_campaign(
                    str(campaign_oid),
                    server.UpdateCampaignPayload(compensation_type="barter"),
                    brand,
                )
            )
            assert err.status_code == 422
            row = await db.campaigns.find_one({"_id": campaign_oid})
            assert server._compensation_type(row) == "fixed", "it must not have moved"

        run(body)

    def test_the_brand_edit_path_refuses_emptying_the_description(self):
        """The third way to arrive at an unstated barter brief, and the one
        the payload cannot see by itself — which is why the guard merges the
        campaign under the update rather than reading the update alone.

        An empty string rather than a `null`, because that is what a form
        sends when somebody deletes the text, and because a bare `null` is
        dropped by the generic copy loop before any guard sees it.
        """
        async def body(db):
            brand = await _brand_scene(db)
            campaign_oid = ObjectId()
            await db.campaigns.insert_one(
                {"_id": campaign_oid, "brand_id": ObjectId(brand["brand_id"]),
                 "title": "Barter", "status": "draft", "compensation_type": "barter",
                 "barter_description": "Dinner", "campaign_type": "personal_table"}
            )
            err = await refuses(
                server.update_brand_campaign(
                    str(campaign_oid),
                    server.UpdateCampaignPayload(barter_description="   "),
                    brand,
                )
            )
            assert err.status_code == 422
            row = await db.campaigns.find_one({"_id": campaign_oid})
            assert row["barter_description"] == "Dinner"

        run(body)

    def test_a_paid_brief_needs_none_of_this(self):
        async def body(db):
            brand = await _brand_scene(db)
            out = await server.create_brand_campaign(
                _post(compensation_type="fixed", budget_per_creator=9000), brand
            )
            assert out["id"]

        run(body)


class TestTravelIsStatedOrNotStated:
    def test_absent_reads_as_unstated_rather_than_as_no(self):
        """Every campaign written before the field. Rendering that as "travel
        not covered" tells a creator something we never said."""
        block = server._travel_block({})
        assert block["stated"] is False
        assert block["covered"] is None
        assert block["text"] is None

    def test_an_explicit_no_is_different_from_silence(self):
        block = server._travel_block({"travel_allowance": False})
        assert block["stated"] is True
        assert block["covered"] is False
        assert "not covered" in block["text"]

    def test_an_amount_rides_with_the_yes(self):
        block = server._travel_block(
            {"travel_allowance": True, "travel_allowance_amount": 500}
        )
        assert block["covered"] is True
        assert "500" in block["text"]

    def test_an_amount_on_a_no_is_dropped(self):
        """A figure describing nothing. Dropped rather than refused, the shape
        `_usage_duration_days` uses."""
        out = server._resolve_barter(
            {"travel_allowance": False, "travel_allowance_amount": 500}
        )
        assert out["travel_allowance_amount"] is None

    def test_it_rides_on_the_brief_a_creator_reads(self):
        out = server._serialize_campaign(
            {"_id": ObjectId(), "brand_id": ObjectId(),
             "travel_allowance": True, "travel_allowance_amount": 300},
            None,
            payout_default=server.CREATOR_PAYOUT_DAYS,
        )
        assert out["travel"]["covered"] is True

    def test_the_offer_itself_rides_on_the_brief_too(self):
        """**The mitigation is only a mitigation where a creator reads it.**
        Requiring the description and then not shipping it to the brief
        would be a field that exists for the admin console."""
        out = server._serialize_campaign(
            {"_id": ObjectId(), "brand_id": ObjectId(),
             "compensation_type": "barter",
             "barter_description": "The full kit, about Rs 3,500."},
            None,
            payout_default=server.CREATOR_PAYOUT_DAYS,
        )
        assert out["barter_description"] == "The full kit, about Rs 3,500."
        # And `None` on a paid brief, where there is nothing to describe.
        paid = server._serialize_campaign(
            {"_id": ObjectId(), "brand_id": ObjectId(), "compensation_type": "fixed"},
            None,
            payout_default=server.CREATOR_PAYOUT_DAYS,
        )
        assert paid["barter_description"] is None

    def test_a_brand_can_set_it(self):
        async def body(db):
            brand = await _brand_scene(db)
            out = await server.create_brand_campaign(
                _post(
                    compensation_type="barter",
                    barter_description="Dinner for two.",
                    travel_allowance=True,
                    travel_allowance_amount=400,
                ),
                brand,
            )
            row = await db.campaigns.find_one({"_id": ObjectId(out["id"])})
            assert row["travel_allowance"] is True
            assert row["travel_allowance_amount"] == 400

        run(body)


class TestTheMoneyPathsStillBehaveOnBarter:
    """More barter briefs means these get exercised far more than they are
    today, so they are tested at the boundary rather than assumed."""

    def test_the_agreed_amount_is_none_rather_than_zero(self):
        """`0` reads as "agreed, nothing" on every surface that shows money."""
        assert server._resolve_agreed_amount({"compensation_type": "barter"}, None) is None
        # And a figure typed against a barter brief is refused rather than
        # quietly recorded: there is no amount to agree, so somebody who typed
        # one has misread the brief and needs telling.
        with pytest.raises(HTTPException) as exc:
            server._resolve_agreed_amount({"compensation_type": "barter"}, 5000)
        assert exc.value.status_code == 422

    def test_barter_is_excluded_from_committed_spend_rather_than_counted_as_zero(self):
        """Counting it at zero would put something in the denominator of "how
        much is spoken for" that was never going to spend any of it."""

        async def body(db):
            campaign_oid = ObjectId()
            await db.campaigns.insert_one(
                {"_id": campaign_oid, "brand_id": ObjectId(), "total_budget": 50000,
                 "compensation_type": "barter"}
            )
            await db.collaborations.insert_many([
                {"_id": ObjectId(), "campaign_id": campaign_oid,
                 "creator_id": ObjectId(), "state": "accepted", "agreed_amount": None},
                {"_id": ObjectId(), "campaign_id": campaign_oid,
                 "creator_id": ObjectId(), "state": "accepted", "agreed_amount": None},
            ])
            committed = await server._committed_amounts_for([campaign_oid])
            row = committed.get(campaign_oid) or {}
            assert (row.get("committed") or 0) == 0
            assert (row.get("collaborations_counted") or 0) == 0, (
                "a barter row must not be counted at zero"
            )

        run(body)

    def test_a_barter_brief_never_refuses_an_acceptance_over_budget(self):
        """`_refuse_over_budget` asks for an amount that *exists*, so barter
        excludes itself by being true of it rather than by a special case."""

        async def body(db):
            campaign_oid = ObjectId()
            campaign = {"_id": campaign_oid, "brand_id": ObjectId(),
                        "total_budget": 1, "compensation_type": "barter"}
            await db.campaigns.insert_one(campaign)
            budget = await server._campaign_budget(campaign)
            # The resolved amount on a barter brief, which is what the gate
            # actually receives.
            amount = server._resolve_agreed_amount(campaign, None)
            assert amount is None
            assert server._budget_refusal(budget, amount) is None
            # The control: the same ₹1 brief does refuse a real figure.
            assert server._budget_refusal(budget, 9000) is not None

        run(body)

    def test_barter_reach_is_kept_out_of_cost_per_thousand(self):
        """Its spend is zero either way; the damage is on the other side of
        the division, where its reach would report a CPM we never achieved."""
        paid, barter = ObjectId(), ObjectId()
        rollup = server._rollup_performance(
            [
                {"collaboration_id": paid, "reach": 10000, "likes": 100},
                {"collaboration_id": barter, "reach": 90000, "likes": 900},
            ],
            {paid},
            10000,
            {barter},
        )
        assert rollup["paid_reach"] == 10000
        assert rollup["barter_reach"] == 90000
        assert rollup["total_reach"] == 100000, "the audience totals keep it"
        # Rs 10,000 over 10,000 paid reach is Rs 1,000 per thousand. With the
        # barter reach in the denominator it would read as 100 — a tenth of
        # the real cost, in a number that goes to a client.
        assert round(rollup["cost_per_thousand_reach"]) == 1000


class TestTheRankingStillKnowsNothingAboutMoney:
    """A flood of barter briefs is not a reason to start ranking paid work
    first — that would quietly make "most relevant" mean "most lucrative"."""

    def test_a_barter_brief_and_a_paid_one_score_the_same_on_fit(self):
        profile = {"niches": ["food"], "city": "Bengaluru"}
        base = {"category": "fnb", "city": "Bengaluru", "title": "Food tasting",
                "brief": "food", "area": "Indiranagar"}
        paid = server.score_campaign_for_creator(
            profile, {**base, "compensation_type": "fixed", "budget_per_creator": 50000}
        )
        barter = server.score_campaign_for_creator(
            profile, {**base, "compensation_type": "barter", "budget_per_creator": 0}
        )
        assert paid == barter


class TestTheFrontendCarriesOneCopyOfEach:
    """The arrangement `followerTiers.js` and `shootWindows.js` use: one copy
    each side and a test that fails if they drift. Both of these render
    before there is anything to fetch — the post form shows the barter
    options before a campaign exists, and a brief falls back to the platform
    promise when no block arrived."""

    def test_the_default_payout_window_does_not_drift(self):
        src = no_comments(FRONTEND / "lib" / "payoutWindow.js")
        assert f"CREATOR_PAYOUT_DAYS = {server.CREATOR_PAYOUT_DAYS};" in src

    def test_the_promise_is_worded_the_same_either_side(self):
        """Read as the two halves either side of the number, because the
        frontend's is a template literal and the server's is an f-string —
        the shape, not the spelling of the interpolation."""
        src = no_comments(FRONTEND / "lib" / "payoutWindow.js")
        head, _, tail = server._payout_promise(7).partition("7 days")
        assert head.strip() in src, head
        assert tail.strip() in src, tail
        # And the zero case, which is a real answer rather than "no window".
        assert server._payout_promise(0) in src

    def test_the_frontend_prefers_the_block_the_server_sent(self):
        """A second definition of the promise is how the brief and the share
        page come to word it differently — so the local builder is the
        fallback, not the path."""
        src = no_comments(FRONTEND / "lib" / "payoutWindow.js")
        body = src.split("export function payoutPromise")[1]
        assert body.index("payout?.promise") < body.index("Paid within")

    def test_the_renderer_computes_no_threshold_of_its_own(self):
        """The lesson `isStale` taught the console: a browser holding its own
        idea of a server rule is a browser that disagrees with it."""
        src = no_comments(FRONTEND / "components" / "campaign" / "PayoutNote.jsx")
        for arithmetic in ("Date.now", "getTime()", "86400", "* 24"):
            assert arithmetic not in src, arithmetic

    def test_the_renderer_never_asks_what_role_is_looking(self):
        """One component for the creator, the manager and the brand — the
        rule `ProcessFlow` and `DisputePanel` are held to."""
        src = no_comments(FRONTEND / "components" / "campaign" / "PayoutNote.jsx")
        for check in ('role ===', 'user?.role', 'isAdmin', 'useAuth'):
            assert check not in src, check


# ---------------------------------------------------------------------------
# 3. The creator's address — the reason, not the field
# ---------------------------------------------------------------------------


class TestTheAddressSaysWhyWeAreAsking:
    NOTE = FRONTEND / "components" / "AddressPicker.jsx"

    def test_the_purpose_is_stated(self):
        """It was asked with a generic privacy note and no stated reason,
        which is the most invasive question on the form presented as the
        blandest."""
        src = no_comments(self.NOTE)
        note = src.split("PRIVATE_ADDRESS_NOTE =")[1].split(";")[0].lower()
        assert "hamper" in note or "product" in note
        assert "deliver" in note

    def test_it_names_the_promise_that_a_brand_never_sees_it(self):
        src = no_comments(self.NOTE)
        note = src.split("PRIVATE_ADDRESS_NOTE =")[1].split(";")[0].lower()
        assert "brand never" in note or "never does" in note

    def test_that_promise_is_actually_true(self):
        """**The reason it is worth saying.** Asserted against the projection
        rather than taken on trust — a privacy claim nothing enforces is the
        one kind of copy that is worse than silence."""
        for field in (
            "full_address",
            "location_lat",
            "location_lng",
            "location_place_id",
        ):
            assert field in server.BRAND_FORBIDDEN_CREATOR_FIELDS, field
            assert field not in server._BRAND_VISIBLE_CREATOR_FIELDS, field

    def test_the_brand_outlet_form_still_overrides_it(self):
        """An outlet is public and a creator's address is not, so the default
        text would be a lie on the brand's form."""
        src = no_comments(FRONTEND / "pages" / "BrandOnboarding.jsx")
        picker = src.split("<AddressPicker")[1].split("/>")[0]
        assert "note=" in picker


class TestTheAddressStaysOptional:
    def test_it_is_not_part_of_completeness(self):
        """Not the price of being looked at — the rule that keeps PAN out."""
        fields = [f for f, _ in server._PROFILE_COMPLETENESS_FIELDS]
        assert "full_address" not in fields
        assert "location_lat" not in fields

    def test_a_profile_with_no_address_still_reaches_a_hundred_percent(self):
        profile = {
            "name": "Asha",
            "city": "Bengaluru",
            "bio": "Food and travel",
            "niches": ["food"],
            "genres": ["reels"],
            "platforms": ["instagram"],
            "instagram_handle": "asha",
            "instagram_profile_url": "https://instagram.com/asha",
            "email": "asha@example.com",
            "follower_count": 12000,
            "base_rate": 9000,
            "profile_image_url": "/uploads/a.jpg",
            "phone": "+919900000001",
        }
        out = server._profile_completeness(profile)
        missing = [row["field"] for row in out["missing"]]
        assert missing == [], missing
        assert out["percent"] == 100


class TestTheAskIsConsequentialRatherThanNagging:
    """A creator who will never do a delivery campaign should never be chased
    for an address."""

    def test_a_delivery_brief_tells_a_creator_with_no_address(self):
        async def body(db):
            brand, creator = ObjectId(), ObjectId()
            campaign_oid = ObjectId()
            await db.brand_profiles.insert_one(
                {"user_id": brand, "verified": True, "business_name": "Toit"}
            )
            await db.campaigns.insert_one(
                {"_id": campaign_oid, "brand_id": brand, "title": "Hamper",
                 "campaign_type": "delivery", "status": "open",
                 "compensation_type": "fixed", "creators_needed": 2}
            )
            await db.creator_profiles.insert_one(
                {"user_id": creator, "verification_status": "verified"}
            )
            await db.users.insert_one(
                {"_id": creator, "role": "creator", "name": "Asha", "status": "active"}
            )
            out = await server.get_campaign(
                str(campaign_oid), {"_id": str(creator), "role": "creator"}
            )
            assert out["needs_delivery_address"] is True

        run(body)

    def test_a_venue_brief_never_mentions_it(self):
        async def body(db):
            brand, creator = ObjectId(), ObjectId()
            campaign_oid = ObjectId()
            await db.brand_profiles.insert_one(
                {"user_id": brand, "verified": True, "business_name": "Toit"}
            )
            await db.campaigns.insert_one(
                {"_id": campaign_oid, "brand_id": brand, "title": "Tasting",
                 "campaign_type": "personal_table", "status": "open",
                 "compensation_type": "fixed", "creators_needed": 2}
            )
            await db.creator_profiles.insert_one(
                {"user_id": creator, "verification_status": "verified"}
            )
            await db.users.insert_one(
                {"_id": creator, "role": "creator", "name": "Asha", "status": "active"}
            )
            out = await server.get_campaign(
                str(campaign_oid), {"_id": str(creator), "role": "creator"}
            )
            assert out["needs_delivery_address"] is False

        run(body)

    def test_a_creator_who_has_one_is_not_prompted(self):
        async def body(db):
            brand, creator = ObjectId(), ObjectId()
            campaign_oid = ObjectId()
            await db.brand_profiles.insert_one(
                {"user_id": brand, "verified": True, "business_name": "Toit"}
            )
            await db.campaigns.insert_one(
                {"_id": campaign_oid, "brand_id": brand, "title": "Hamper",
                 "campaign_type": "delivery", "status": "open",
                 "compensation_type": "fixed", "creators_needed": 2}
            )
            await db.creator_profiles.insert_one(
                {"user_id": creator, "verification_status": "verified",
                 "full_address": "2nd floor, above the pharmacy"}
            )
            await db.users.insert_one(
                {"_id": creator, "role": "creator", "name": "Asha", "status": "active"}
            )
            out = await server.get_campaign(
                str(campaign_oid), {"_id": str(creator), "role": "creator"}
            )
            assert out["needs_delivery_address"] is False

        run(body)
