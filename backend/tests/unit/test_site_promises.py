"""Every promise the public site makes, held to the code that keeps it.

`test_site_claims.py` refuses the sentences the product could not back. This
is the other direction: three claims that are made, and each is checked
against the field or function that makes it true, so deleting the thing
behind a promise fails here rather than leaving the site saying it.

- **The review clock** — "a draft nobody answers is approved when its window
  ends". Needs `draft_review_days` on the brief and `_approve_draft_by_window`.
- **The revision cap** — "1 of 2 used". Needs `revisions_included` on the
  brief, frozen into the terms, and a send-back refused past it.
- **"Paid within 7 days of approval"** — needs the payout window to be
  impossible to set longer than seven days, anywhere.

Then the behaviour, driven against the real handlers and read back: the cap's
refusal, the extra-round request and answer, the snapshot freezing the number;
the payout window's bounds, the clamp and the day-5 queue flag; and barter
being opt-in for a creator's feed, and labelled wherever it appears.
"""

from __future__ import annotations

import inspect
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException
from pydantic import ValidationError

import server
import test_lifecycle_harness as harness
from test_site_claims import _everything, content

FRONTEND = Path(server.__file__).resolve().parent.parent / "frontend" / "src"
ADMIN = harness.ADMIN


def _now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# The claims, and what each one needs to be true
# ---------------------------------------------------------------------------


class TestEachClaimHasItsCode:
    def test_the_review_clock_claim_needs_the_timer(self):
        text = _everything()
        # Home's promise band carried "approved when its window ends" until
        # home was cut to two sections; /for-creators' clock card and the
        # brands FAQ still make the claim.
        claims_clock = any(
            phrase in text
            for phrase in ("approved when its window", "approved automatically",
                           "approved if nobody answers within its review window")
        )
        assert claims_clock, "the review clock is no longer claimed — remove this test with it"
        assert "draft_review_days" in server.PostCampaignPayload.model_fields
        assert callable(getattr(server, "_approve_draft_by_window", None))
        # Worded to the timer's rules, not past them: an admin can pause a
        # window, so "never" and "forever" are not true.
        for overreach in ("stall forever", "can't stall", "never stall", "forever"):
            assert overreach not in text, overreach

    def test_the_clock_claims_quote_the_real_window(self):
        text = _everything()
        assert "three days" in text and "one to fourteen" in text
        assert server.DEFAULT_DRAFT_REVIEW_DAYS == 3
        assert (server.DRAFT_REVIEW_DAYS_MIN, server.DRAFT_REVIEW_DAYS_MAX) == (1, 14)
        faq = [i for i in content()["BRANDS"]["faq"]["items"] if i["q"] == "What if I don't review in time?"]
        assert len(faq) == 1
        # Our team reviews drafts on every brand-posted brief, and the FAQ
        # says so rather than implying the brand is the reviewer.
        assert "our team" in faq[0]["a"].lower()
        assert server.NEW_CAMPAIGN_EXECUTION_OWNER == "weare"

    def test_the_revision_cap_claim_needs_the_cap(self):
        text = _everything()
        assert "1 of 2 used" in text and "cap on revisions" in text
        assert "revisions_included" in server.PostCampaignPayload.model_fields
        assert "revisions_included" in server._build_terms({}, {}, payout_default=7)
        assert server._revision_allowance(
            {"terms": {"revisions_included": 2}, "revisions_used": 1}
        )["label"] == "1 of 2 used"
        chips = content()["CREATORS"]["briefs"]["card"]["chips"]
        assert f"{server.DEFAULT_REVISIONS_INCLUDED} rounds of changes" in chips

    def test_within_seven_days_needs_a_window_that_cannot_be_longer(self):
        assert "within 7 days" in _everything()
        assert server.CREATOR_PAYOUT_DAYS == 7
        assert server._CREATOR_PAYOUT_MAX == 7
        for model in (server.CreatorPayoutPayload,):
            with pytest.raises(ValidationError):
                model(days=8)
        for model in (server.UpdateCampaignPayload, server.AdminCreateCampaignPayload):
            field = model.model_fields["creator_payout_days"]
            limits = [m.le for m in field.metadata if hasattr(m, "le")]
            assert limits == [7], (model.__name__, limits)
        # And an out-of-range stored value never reads as a promise.
        assert server._clean_payout_days(30) is None

    def test_no_comment_still_says_a_restored_claim_is_missing(self):
        src = (FRONTEND / "content" / "marketing.js").read_text()
        assert "not on this tree" not in src.lower()
        assert "there is no cap" not in src.lower()

    def test_the_frontend_mirrors_the_cap_bounds(self):
        src = (FRONTEND / "lib" / "revisions.js").read_text()
        for name, value in (
            ("DEFAULT_REVISIONS_INCLUDED", server.DEFAULT_REVISIONS_INCLUDED),
            ("REVISIONS_INCLUDED_MIN", server.REVISIONS_INCLUDED_MIN),
            ("REVISIONS_INCLUDED_MAX", server.REVISIONS_INCLUDED_MAX),
        ):
            assert re.search(rf"export const {name} = {value};", src), name


# ---------------------------------------------------------------------------
# The revision cap, driven
# ---------------------------------------------------------------------------


async def _at(db, at, *, ladder="venue", money="paid", **campaign_set):
    w = await harness._world(db, ladder=ladder, money=money)
    if campaign_set:
        await db.campaigns.update_one({"_id": w["campaign_oid"]}, {"$set": campaign_set})
    await harness._walk_to(db, w, at, ladder, money)
    return w


async def _send_back(w):
    return await server.brand_request_changes(
        w["collab_id"], server.DecisionPayload(reason="Tag the venue in the first frame."),
        w["brand"],
    )


async def _resubmit(w):
    await server.submit_collab_content(
        w["collab_id"],
        server.SubmitContentPayload(content_urls=["https://www.instagram.com/reel/abc123/"]),
        w["creator"],
    )


class TestTheRevisionCap:
    def test_the_snapshot_freezes_the_number_at_acceptance(self):
        """Edit the brief afterwards and the collaboration keeps its number."""

        async def body(db):
            w = await _at(db, "content_submitted", revisions_included=1)
            await db.campaigns.update_one(
                {"_id": w["campaign_oid"]}, {"$set": {"revisions_included": 5}}
            )
            return await db.collaborations.find_one({"_id": w["collab_oid"]})

        row = harness.run(body)
        assert row["terms"]["revisions_included"] == 1
        assert server._revision_allowance(row)["label"] == "0 of 1 used"

    def test_a_weare_run_collaboration_freezes_it_when_the_fee_is_agreed(self):
        """Accepted through the console's Advance, which records no fee and
        froze nothing — so the terms freeze at the fee, the first moment every
        term is known."""

        async def body(db):
            w = await harness._world(db, ladder="venue", money="paid")
            await db.campaigns.update_one(
                {"_id": w["campaign_oid"]},
                {"$set": {"execution_owner": "weare", "revisions_included": 3}},
            )
            # The weare-run path: every step through the console's Advance.
            for frm in ("applied", "verified"):
                await harness._advance(w, frm)
            accepted = await db.collaborations.find_one({"_id": w["collab_oid"]})
            assert "terms" not in accepted, "Advance into accepted froze nothing, as before"
            await harness._advance(w, "accepted", agreed_amount=12000)
            return await db.collaborations.find_one({"_id": w["collab_oid"]})

        row = harness.run(body)
        assert row["terms"]["revisions_included"] == 3

    def test_a_send_back_past_the_rounds_is_refused_and_nothing_moves(self):
        async def body(db):
            w = await _at(db, "content_submitted", revisions_included=1)
            await _send_back(w)
            await _resubmit(w)
            with pytest.raises(HTTPException) as err:
                await _send_back(w)
            return err.value, await db.collaborations.find_one({"_id": w["collab_oid"]})

        exc, row = harness.run(body)
        assert exc.status_code == 409
        assert exc.detail["code"] == "no_revisions_left"
        assert exc.detail["message"] == "No revisions left — approve, or ask for an extra round."
        assert row["state"] == "content_submitted"
        assert row["revisions_used"] == 1

    def test_draft_and_live_send_backs_share_one_allowance(self):
        async def body(db):
            w = await _at(db, "draft_submitted", ladder="venue+draft", revisions_included=1)
            await server.request_draft_changes(
                w["collab_id"], server.DraftDecisionPayload(note="Lighter grade."), w["brand"]
            )
            row = await db.collaborations.find_one({"_id": w["collab_oid"]})
            return row

        row = harness.run(body)
        assert row["revisions_used"] == 1
        assert server._revision_allowance(row)["exhausted"] is True

    def test_the_admin_on_behalf_send_back_respects_the_cap(self):
        async def body(db):
            w = await _at(db, "draft_submitted", ladder="venue+draft", revisions_included=0)
            with pytest.raises(HTTPException) as err:
                await server.request_draft_changes_on_behalf(
                    w["collab_id"],
                    server.ChangesOnBehalfPayload(reason="The brand asked us to.", note="Lighter."),
                    ADMIN,
                )
            return err.value, await db.collaborations.find_one({"_id": w["collab_oid"]})

        exc, row = harness.run(body)
        assert exc.status_code == 409 and exc.detail["code"] == "no_revisions_left"
        assert row["state"] == "draft_submitted"

    def test_an_extra_round_is_asked_then_accepted_and_written_down(self):
        async def body(db):
            w = await _at(db, "content_submitted", revisions_included=0)
            asked = await server.request_extra_revision(
                w["collab_id"], server.ExtraRevisionRequestPayload(note="The caption needs the date."),
                w["brand"],
            )
            mid = await db.collaborations.find_one({"_id": w["collab_oid"]})
            await server.accept_extra_revision(
                w["collab_id"], server.ExtraRevisionAnswerPayload(), w["creator"]
            )
            await _send_back(w)
            after = await db.collaborations.find_one({"_id": w["collab_oid"]})
            told = await db.notifications.find_one({"event": "extra_revision_requested"})
            return asked, mid, after, told, w

        asked, mid, after, told, w = harness.run(body)
        assert asked["revisions"]["extra_pending"] is True
        assert server._serialize_collab_row(mid, {}, "Toit", payout_default=7)["can_answer_extra_revision"]
        assert after["revisions_extra"] == 1
        assert after["extra_revision_request"]["state"] == "accepted"
        # The send-back the extra round paid for went through, and the round
        # is spent.
        assert after["state"] == "attended" and after["revisions_used"] == 1
        entry = after["negotiation_history"][-1]
        assert entry["kind"] == "extra_revision" and entry["amount"] is None
        assert entry["by_role"] == "creator"
        assert told["user_id"] == w["creator_oid"]

    def test_a_declined_extra_round_adds_nothing(self):
        async def body(db):
            w = await _at(db, "content_submitted", revisions_included=0)
            await server.request_extra_revision(
                w["collab_id"], server.ExtraRevisionRequestPayload(), w["brand"]
            )
            await server.decline_extra_revision(
                w["collab_id"], server.ExtraRevisionAnswerPayload(), w["creator"]
            )
            with pytest.raises(HTTPException) as err:
                await _send_back(w)
            return err.value, await db.collaborations.find_one({"_id": w["collab_oid"]})

        exc, row = harness.run(body)
        assert exc.detail["code"] == "no_revisions_left"
        assert row["extra_revision_request"]["state"] == "declined"
        assert not row.get("revisions_extra")

    def test_asking_for_more_is_refused_while_rounds_remain(self):
        async def body(db):
            w = await _at(db, "content_submitted", revisions_included=2)
            with pytest.raises(HTTPException) as err:
                await server.request_extra_revision(
                    w["collab_id"], server.ExtraRevisionRequestPayload(), w["brand"]
                )
            return err.value

        assert harness.run(body).status_code == 409

    def test_a_brand_on_a_weare_run_brief_cannot_ask(self):
        async def body(db):
            w = await _at(db, "content_submitted", revisions_included=0)
            await db.campaigns.update_one(
                {"_id": w["campaign_oid"]}, {"$set": {"execution_owner": "weare"}}
            )
            with pytest.raises(HTTPException) as err:
                await server.request_extra_revision(
                    w["collab_id"], server.ExtraRevisionRequestPayload(), w["brand"]
                )
            return err.value

        assert harness.run(body).status_code == 404

    def test_a_collaboration_from_before_the_cap_is_unlimited(self):
        """Nothing in flight changes: no snapshot, or a snapshot without the
        number, reads as unlimited and every send-back still goes through."""

        async def body(db):
            w = await _at(db, "content_submitted")
            await db.collaborations.update_one(
                {"_id": w["collab_oid"]}, {"$unset": {"terms.revisions_included": ""}}
            )
            for _ in range(4):
                await _send_back(w)
                await _resubmit(w)
            return await db.collaborations.find_one({"_id": w["collab_oid"]})

        row = harness.run(body)
        allowance = server._revision_allowance(row)
        assert allowance["unlimited"] is True and allowance["label"] is None
        assert row["state"] == "content_submitted"

    def test_both_sides_read_the_same_words(self):
        page = (FRONTEND / "components" / "collab" / "RevisionAllowance.jsx").read_text()
        assert "revisions.label" in page
        assert "No revisions left — approve, or ask for an extra round." in page
        for path in ("components/creator/ActiveCampaigns.jsx",
                     "components/application/ApplicationDetail.jsx",
                     "pages/BrandCampaignApplicants.jsx"):
            assert "<RevisionAllowance" in (FRONTEND / path).read_text(), path
        # Shown on the brief before applying, and asked on the brief form.
        assert "revisions_included" in (FRONTEND / "pages" / "CampaignDetail.jsx").read_text()
        assert "revisions_included" in (FRONTEND / "pages" / "PostCampaign.jsx").read_text()


# ---------------------------------------------------------------------------
# "Paid within 7 days", driven
# ---------------------------------------------------------------------------


class TestPaidWithinSevenDays:
    def test_the_platform_setting_refuses_more_than_seven(self):
        with pytest.raises(ValidationError):
            server.CreatorPayoutPayload(days=8)
        assert server.CreatorPayoutPayload(days=7).days == 7
        assert server.CreatorPayoutPayload(days=0).days == 0

    def test_the_campaign_field_refuses_more_than_seven(self):
        with pytest.raises(ValidationError):
            server.UpdateCampaignPayload(creator_payout_days=30)
        assert server.UpdateCampaignPayload(creator_payout_days=7).creator_payout_days == 7

    def test_the_clamp_brings_every_stored_window_inside_and_lists_it(self):
        async def body(db):
            server._CREATOR_PAYOUT_CACHE["at"] = None
            await db.platform_settings.insert_one({"_id": "creator_payout_days", "days": 21})
            long_, short, unset = ObjectId(), ObjectId(), ObjectId()
            await db.campaigns.insert_many([
                {"_id": long_, "title": "Slow brief", "reference": "CMP-0007",
                 "creator_payout_days": 30},
                {"_id": short, "title": "Quick brief", "creator_payout_days": 3},
                {"_id": unset, "title": "Default brief"},
            ])
            dry = await server.clamp_creator_payout_days(apply=False)
            untouched = await db.campaigns.find_one({"_id": long_})
            report = await server.clamp_creator_payout_days()
            again = await server.clamp_creator_payout_days()
            setting = await db.platform_settings.find_one({"_id": "creator_payout_days"})
            rows = {d["_id"]: d async for d in db.campaigns.find({})}
            audits = await db.audit_log.count_documents(
                {"action": {"$in": ["campaign.payout_window_clamped",
                                    "settings.creator_payout_clamped"]}}
            )
            server._CREATOR_PAYOUT_CACHE["at"] = None
            return dry, untouched, report, again, setting, rows, audits, long_, short, unset

        dry, untouched, report, again, setting, rows, audits, long_, short, unset = harness.run(body)
        assert untouched["creator_payout_days"] == 30, "a dry run wrote"
        assert report["setting_before"] == 21 and setting["days"] == 7
        assert [(c["reference"], c["title"], c["before"], c["after"]) for c in report["campaigns"]] == [
            ("CMP-0007", "Slow brief", 30, 7)
        ]
        assert rows[long_]["creator_payout_days"] == 7
        assert rows[short]["creator_payout_days"] == 3
        assert "creator_payout_days" not in rows[unset]
        assert again == {"setting_before": None, "campaigns": []}
        assert audits == 2

    def test_the_clamp_runs_on_boot(self):
        assert "await clamp_creator_payout_days()" in inspect.getsource(server._startup)

    @pytest.mark.parametrize(
        "days,money,paid,flagged",
        [
            (5, "paid", False, True),
            (4, "paid", False, False),
            (6, "paid", True, False),
            (5, "barter", False, False),
        ],
    )
    def test_the_queue_is_told_on_day_five(self, days, money, paid, flagged):
        campaign = {"compensation_type": "fixed" if money == "paid" else "barter"}
        collab = {"state": "in_payment", "content_approved_at": _now() - timedelta(days=days, hours=1)}
        payment = {"state": "paid" if paid else "pending"}
        alert = server._payout_alert(collab, campaign, payment)
        assert alert["payout_at_risk"] is flagged
        if flagged:
            assert alert["payout_unpaid_days"] == days
            assert alert["payout_due_at"] is not None

    def test_the_admin_row_carries_the_flag_and_the_queue_reads_it(self):
        row = server._serialize_admin_collab(
            {"_id": ObjectId(), "campaign_id": ObjectId(), "state": "content_approved",
             "content_approved_at": _now() - timedelta(days=5, hours=2)},
            {"compensation_type": "fixed"}, "Toit", {}, {}, None,
        )
        assert row["payout_at_risk"] is True
        queue = (FRONTEND / "components" / "admin" / "ActionQueue.jsx").read_text()
        assert "payout_at_risk" in queue and "7-day promise" in queue


# ---------------------------------------------------------------------------
# Barter, opt-in for a creator's feed
# ---------------------------------------------------------------------------


async def _feed_world(db):
    brand, creator = ObjectId(), ObjectId()
    await db.users.insert_one({"_id": creator, "role": "creator", "name": "Asha"})
    await db.creator_profiles.insert_one(
        {"user_id": creator, "verification_status": "verified", "niches": ["food"], "city": "Bengaluru"}
    )
    base = {"brand_id": brand, "status": "open", "category": "fnb",
            "created_at": _now(), "start_date": _now(), "end_date": _now() + timedelta(days=20)}
    await db.campaigns.insert_many([
        {**base, "title": "Paid tasting", "compensation_type": "fixed", "budget_per_creator": 9000},
        {**base, "title": "Dinner for two", "compensation_type": "barter",
         "barter_description": "Dinner for two", "budget_per_creator": 5000},
    ])
    return {"_id": str(creator), "role": "creator", "name": "Asha"}, creator


def _titles(response):
    """`list_campaigns` answers a JSONResponse, because it sets the count
    header; the rows are its body."""
    import json

    rows = json.loads(response.body) if hasattr(response, "body") else response
    return {r["title"] for r in rows}


class TestBarterIsOptIn:
    def test_hidden_by_default_and_the_count_agrees(self):
        async def body(db):
            user, _ = await _feed_world(db)
            return await server.list_campaigns(user=user)

        rows = harness.run(body)
        assert _titles(rows) == {"Paid tasting"}

    def test_shown_once_the_creator_switches_it_on(self):
        async def body(db):
            user, oid = await _feed_world(db)
            await server.update_creator_profile(
                server.CreatorProfileUpdate(show_barter_briefs=True), user
            )
            stored = await db.creator_profiles.find_one({"user_id": oid})
            return stored, await server.list_campaigns(user=user)

        stored, rows = harness.run(body)
        assert stored["show_barter_briefs"] is True
        assert _titles(rows) == {"Paid tasting", "Dinner for two"}

    def test_the_setting_is_not_material_and_not_completeness(self):
        assert "show_barter_briefs" not in server.MATERIAL_PROFILE_FIELDS
        assert "show_barter_briefs" not in [f for f, _ in server._PROFILE_COMPLETENESS_FIELDS]
        assert server._shows_barter_briefs({}) is False

    def test_the_filter_options_and_suggestions_follow_the_setting(self):
        async def body(db):
            user, oid = await _feed_world(db)
            hidden = await server.campaign_filters(user)
            suggested = await server._suggested_campaigns(
                await db.creator_profiles.find_one({"user_id": oid}), set()
            )
            await db.creator_profiles.update_one({"user_id": oid}, {"$set": {"show_barter_briefs": True}})
            shown = await server.campaign_filters(user)
            return hidden, suggested, shown

        hidden, suggested, shown = harness.run(body)
        assert "barter" not in hidden["compensation_types"]
        assert "barter" in shown["compensation_types"]
        assert all(s.get("compensation_type") != "barter" for s in suggested)

    def test_an_admin_browsing_the_feed_sees_everything(self):
        async def body(db):
            await _feed_world(db)
            return await server.list_campaigns(user=ADMIN)

        assert _titles(harness.run(body)) == {"Paid tasting", "Dinner for two"}

    def test_barter_is_labelled_on_the_feed_card_and_the_invitation(self):
        label = (FRONTEND / "components" / "BarterLabel.jsx").read_text()
        assert "isBarter(campaign)" in label and ">\n            Barter\n" in label.replace("\r", "")
        assert "<BarterLabel" in (FRONTEND / "pages" / "Campaigns.jsx").read_text()
        assert "<BarterLabel" in (FRONTEND / "components" / "creator" / "Invitations.jsx").read_text()
        # The invitation carries the kind of money, so the label can read it.
        row = server._serialize_invitation(
            {"_id": ObjectId(), "campaign_id": ObjectId(), "creator_id": ObjectId(),
             "created_at": _now(), "status": "sent"},
            {"_id": ObjectId(), "title": "Dinner", "compensation_type": "barter"},
        )
        assert row["compensation_type"] == "barter"

    def test_the_switch_is_on_the_feed_and_says_what_it_does(self):
        toggle = (FRONTEND / "components" / "creator" / "BarterFeedToggle.jsx").read_text()
        assert "Show barter briefs (a meal or product instead of a fee)" in toggle
        assert "show_barter_briefs" in toggle
        assert "<BarterFeedToggle" in (FRONTEND / "pages" / "Campaigns.jsx").read_text()
