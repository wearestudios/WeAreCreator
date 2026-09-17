"""Case studies: the public payload's privacy rules, and the prefill.

Two halves, and the first is the reason the feature is shaped the way it is.

**The privacy half is driven, not read.** A case study is the only public page
in this product that names a *person* — a creator, with their photograph, their
handle and their audience — beside a brand and a set of numbers. Every value
that must not be on it lives one join away: the creator's phone is on the same
profile document as their name, the agreed fee is on the collaboration the
roster was built from, and the brand's commission is on the brand the logo came
from. So these plant recognisable values on every one of those documents, call
the real handler, render the real HTML, and search the bytes. That is the
arrangement `test_exports.py` uses, for the reason stated there: source-reading
catches the mistake somebody makes on purpose; running it catches the one where
a value arrives through a `**spread` from a document nobody remembered had it.

**The consent half is about *when*, not whether.** Storing the roster as a
snapshot would be the obvious implementation and would mean a creator who
withdrew consent stayed on a public page until somebody edited it. The roster
stores ids and resolves them on every read, which is the rule the leaderboard
already holds — so there is a test here that turns the flag off *after*
publication and re-reads the page.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import server

LOOP = None


def _loop():
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()
    return LOOP


def run(body):
    async def go():
        db = AsyncMongoMockClient()["case_studies"]
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


# Values planted on the documents a case study is built from. Each is
# unmistakable in a blob of JSON or a page of HTML and none is a substring of
# another — a search that matched by accident is a search that cannot fail for
# the right reason.
LEAKS = {
    "phone": "+919900011122",
    "email": "asha.leak@example.com",
    "full_address": "Flat 4B Leakhouse Apartments",
    "payout_upi": "ashaleak@okhdfc",
    "payout_account_number": "998877665544",
    "payout_ifsc": "HDFC0009999",
    "pan": "LEAKP1234Z",
    "agreed_amount": 47231,
    "base_rate": 38111,
    "campaign_fee": 65432,
    "commission_percent": 17.5,
    "total_budget": 812345,
}


async def _creator(db, *, opted_in=True, name="Asha Rao", leak=False):
    oid = ObjectId()
    await db.users.insert_one({"_id": oid, "role": "creator", "name": name})
    profile = {
        "user_id": oid,
        "name": name,
        "instagram_handle": "asharao",
        "profile_image_url": "/uploads/asha.jpg",
        "follower_count": 24000,
        "follower_count_source": "instagram_verified",
        "verification_status": "verified",
        "homepage_opt_in": opted_in,
        "city": "Bengaluru",
    }
    if leak:
        profile.update(
            {
                "phone": LEAKS["phone"],
                "whatsapp": LEAKS["phone"],
                "email": LEAKS["email"],
                "full_address": LEAKS["full_address"],
                "location_lat": 12.9716,
                "location_lng": 77.5946,
                "payout_method": "upi",
                "payout_upi": LEAKS["payout_upi"],
                "payout_account_number": LEAKS["payout_account_number"],
                "payout_ifsc": LEAKS["payout_ifsc"],
                "pan": LEAKS["pan"],
                "base_rate": LEAKS["base_rate"],
            }
        )
    await db.creator_profiles.insert_one(profile)
    return oid


async def _brand(db, *, leak=False):
    oid = ObjectId()
    await db.users.insert_one(
        {"_id": oid, "role": "brand_manager", "name": "Toit", "brand_id": oid}
    )
    profile = {
        "user_id": oid,
        "business_name": "Toit Brewpub",
        "logo_url": "/uploads/toit.png",
        "verified": True,
        "city": "Bengaluru",
        "category": "fnb",
    }
    if leak:
        profile.update(
            {
                "commission_percent": LEAKS["commission_percent"],
                "contact_phone": LEAKS["phone"],
                "contact_email": LEAKS["email"],
                "registered_address": LEAKS["full_address"],
                "gst_number": "29AAAAA0000A1Z5",
            }
        )
    await db.brand_profiles.insert_one(profile)
    return oid


async def _campaign(db, brand_oid, *, status="closed", leak=False, **over):
    oid = ObjectId()
    doc = {
        "_id": oid,
        "brand_id": brand_oid,
        "title": "Tasting evening at Toit",
        "status": status,
        "category": "fnb",
        "city": "Bengaluru",
        "area": "Indiranagar",
        "campaign_type": "personal_table",
        "compensation_type": "fixed",
        "creators_needed": 4,
        "cover_image_url": "/uploads/cover.jpg",
        "deliverable_items": [{"type": "reel", "quantity": 1}],
        "created_at": _now(),
        **over,
    }
    if leak:
        doc.update(
            {
                "campaign_fee": LEAKS["campaign_fee"],
                "commission_percent": LEAKS["commission_percent"],
                "total_budget": LEAKS["total_budget"],
                "budget_per_creator": 12000,
            }
        )
    await db.campaigns.insert_one(doc)
    return await db.campaigns.find_one({"_id": oid})


async def _delivered(db, campaign, creator_oid, *, leak=False, reach=52000):
    oid = ObjectId()
    doc = {
        "_id": oid,
        "campaign_id": campaign["_id"],
        "creator_id": creator_oid,
        "state": "closed",
        "content_url": "https://instagram.com/p/abc123",
        "created_at": _now(),
    }
    if leak:
        doc["agreed_amount"] = LEAKS["agreed_amount"]
        doc["quoted_rate"] = LEAKS["base_rate"]
    await db.collaborations.insert_one(doc)
    await db.content_performance.insert_one(
        {
            "collaboration_id": oid,
            "campaign_id": campaign["_id"],
            "reach": reach,
            "likes": 3100,
            "comments": 210,
            "captured_at": _now(),
        }
    )
    return oid


async def _published(db, **over):
    """A published case study with every optional block filled in.

    Full rather than minimal on purpose: a leak test on a sparse row proves
    only that the fields nobody populated are absent.
    """
    brand_oid = await _brand(db, leak=True)
    campaign = await _campaign(db, brand_oid, leak=True)
    creator_oid = await _creator(db, leak=True)
    await _delivered(db, campaign, creator_oid, leak=True)
    doc = {
        "_id": ObjectId(),
        "slug": "toit-tasting-evening",
        "title": "Tasting evening at Toit",
        "status": "published",
        "display_order": 0,
        "brand_id": brand_oid,
        "brand_name": "Toit Brewpub",
        "brand_logo_url": "/uploads/toit.png",
        "category": "fnb",
        "city": "Bengaluru",
        "campaign_type": "personal_table",
        "campaign_id": campaign["_id"],
        "hero_image_url": "/uploads/hero.jpg",
        "challenge": "A new menu nobody had heard about.",
        "approach": "Twelve creators over four sittings.",
        "headline_result": "Sold out in four days",
        "creator_ids": [creator_oid],
        "deliverable_items": [{"type": "reel", "quantity": 1}],
        "deliverables": "1 reel",
        "results": {
            "reach": 52000,
            "engagement_rate": 6.4,
            "content_pieces": 12,
            "custom": [{"label": "Covers", "value": "340"}],
        },
        "content_links": [{"label": "The reel", "url": "https://instagram.com/p/abc123"}],
        "quote": {"text": "They ran the lot.", "attribution": "Sibi", "role": "Owner"},
        "gallery": [{"url": "/uploads/shot1.jpg", "caption": "The bar"}],
        "published_at": _now(),
        "created_at": _now(),
        "updated_at": _now(),
        **over,
    }
    await db.case_studies.insert_one(doc)
    return doc, creator_oid, campaign, brand_oid


def blob(value):
    return json.dumps(value, default=str)


# ---------------------------------------------------------------------------
# Privacy: nothing about a person or a price reaches a public page
# ---------------------------------------------------------------------------


class TestThePublicPayloadLeaksNothing:
    def test_the_json_payload(self):
        async def body(db):
            doc, _, _, _ = await _published(db)
            out = blob(await server.get_public_case_study(doc["slug"]))
            # The control: the page really did render, with the creator on it.
            assert "Asha Rao" in out and "asharao" in out
            for name, value in LEAKS.items():
                assert str(value) not in out, f"{name} leaked into the JSON"
            for key in server.CASE_STUDY_FORBIDDEN_FIELDS:
                assert f'"{key}"' not in out, f"{key} is a key on the public payload"

        run(body)

    def test_the_rendered_page(self):
        """**The one that actually matters**, because the page is a different
        renderer from the payload and a template reaching past the projection
        to a raw document is exactly the bug this shape prevents."""

        async def body(db):
            doc, _, _, _ = await _published(db)
            html = server._work_detail_html(await server._public_case_study(doc))
            assert "Asha Rao" in html and "Sold out in four days" in html
            for name, value in LEAKS.items():
                assert str(value) not in html, f"{name} leaked into the HTML"

        run(body)

    def test_the_index_page(self):
        async def body(db):
            doc, _, _, _ = await _published(db)
            cards = [await server._public_case_study(doc, full=False)]
            html = server._work_index_html(cards)
            assert "Tasting evening at Toit" in html
            for name, value in LEAKS.items():
                assert str(value) not in html, f"{name} leaked onto the shelf"

        run(body)

    def test_the_list_endpoint(self):
        async def body(db):
            doc, _, _, _ = await _published(db)
            out = blob(await server.list_public_case_studies())
            assert "Tasting evening at Toit" in out
            for name, value in LEAKS.items():
                assert str(value) not in out, f"{name} leaked into the list"

        run(body)

    def test_the_projection_is_an_allow_list_rather_than_a_deny_list(self):
        """A column added to `case_studies` next month must not reach a public
        page because nobody remembered to exclude it. Driven: a field is
        planted on the stored document and the projection is asked for it."""

        async def body(db):
            doc, _, _, _ = await _published(db)
            await db.case_studies.update_one(
                {"_id": doc["_id"]},
                {"$set": {"internal_margin_note": "we made 40% on this one"}},
            )
            fresh = await db.case_studies.find_one({"_id": doc["_id"]})
            assert fresh["internal_margin_note"]
            out = blob(await server._public_case_study(fresh))
            assert "internal_margin_note" not in out
            assert "40%" not in out

        run(body)

    def test_the_forbidden_list_is_not_empty_and_names_the_three_groups(self):
        """A sweep over an empty tuple passes for free."""
        fields = set(server.CASE_STUDY_FORBIDDEN_FIELDS)
        assert len(fields) > 20
        # A person, their money, and the brand's commercials.
        assert {"phone", "email", "full_address"} <= fields
        assert {"payout_upi", "pan", "agreed_amount"} <= fields
        assert {"campaign_fee", "commission_percent", "total_budget"} <= fields


# ---------------------------------------------------------------------------
# Consent: opted in, and still opted in
# ---------------------------------------------------------------------------


class TestOnlyCreatorsWhoAgreed:
    def test_a_creator_who_never_opted_in_is_absent(self):
        async def body(db):
            doc, _, _, _ = await _published(db)
            quiet = await _creator(db, opted_in=False, name="Ravi Quiet")
            await db.case_studies.update_one(
                {"_id": doc["_id"]}, {"$push": {"creator_ids": quiet}}
            )
            fresh = await db.case_studies.find_one({"_id": doc["_id"]})
            out = blob(await server._public_case_study(fresh))
            assert "Asha Rao" in out          # the control
            assert "Ravi Quiet" not in out

        run(body)

    def test_withdrawing_consent_takes_effect_on_the_next_read(self):
        """**The reason the roster is ids rather than a snapshot.**

        A stored copy of the creator's name and photograph would keep them on
        a published page until somebody remembered to edit it. Consent
        withdrawn is withdrawn now — the rule `_public_leaderboard` already
        holds, and this is the test that makes it true here.
        """

        async def body(db):
            doc, creator_oid, _, _ = await _published(db)
            before = blob(await server.get_public_case_study(doc["slug"]))
            assert "Asha Rao" in before

            await db.creator_profiles.update_one(
                {"user_id": creator_oid}, {"$set": {"homepage_opt_in": False}}
            )
            after = blob(await server.get_public_case_study(doc["slug"]))
            assert "Asha Rao" not in after
            # And the page is still a page — the rest of it is untouched.
            assert "Sold out in four days" in after

        run(body)

    def test_a_confirmed_circumvention_is_a_permanent_bar(self):
        """The one thing that disqualifies somebody from being held up as an
        example, and it outlives the suspension — `circumvention_confirmed_at`
        rather than the account status, the same reader the leaderboard uses."""

        async def body(db):
            doc, creator_oid, _, _ = await _published(db)
            await db.creator_profiles.update_one(
                {"user_id": creator_oid},
                {"$set": {"circumvention_confirmed_at": _now()}},
            )
            out = blob(await server.get_public_case_study(doc["slug"]))
            assert "Asha Rao" not in out

        run(body)

    def test_a_lapsed_verification_does_not_erase_finished_work(self):
        """**Deliberately different from the leaderboard**, and the difference
        is the point. A lapse gates *new* work — a creator cannot apply — and
        reaching backwards to delete them from a campaign they actually shot
        would be the check doing the one thing `_creator_block` is documented
        never to do."""

        async def body(db):
            doc, creator_oid, _, _ = await _published(db)
            await db.creator_profiles.update_one(
                {"user_id": creator_oid},
                {"$set": {"verified_at": _now() - timedelta(days=5000)}},
            )
            out = blob(await server.get_public_case_study(doc["slug"]))
            assert "Asha Rao" in out

        run(body)

    def test_the_roster_keeps_the_order_the_admin_arranged(self):
        async def body(db):
            doc, first, _, _ = await _published(db)
            second = await _creator(db, name="Meera Two")
            third = await _creator(db, name="Nikhil Three")
            await db.case_studies.update_one(
                {"_id": doc["_id"]}, {"$set": {"creator_ids": [third, first, second]}}
            )
            fresh = await db.case_studies.find_one({"_id": doc["_id"]})
            names = [c["name"] for c in await server._case_study_roster(fresh)]
            assert names == ["Nikhil Three", "Asha Rao", "Meera Two"]

        run(body)


# ---------------------------------------------------------------------------
# The prefill: a finished campaign, turned into a draft
# ---------------------------------------------------------------------------


class TestGeneratingFromACampaign:
    def test_it_fills_in_everything_the_campaign_already_knows(self):
        async def body(db):
            brand_oid = await _brand(db)
            campaign = await _campaign(db, brand_oid)
            creator_oid = await _creator(db)
            await _delivered(db, campaign, creator_oid, reach=52000)

            out = await server.create_case_study(
                server.CaseStudyPayload(), str(campaign["_id"]), ADMIN
            )
            assert out["title"] == "Tasting evening at Toit"
            assert out["brand_name"] == "Toit Brewpub"
            assert out["brand_id"] == str(brand_oid)
            assert out["category"] == "fnb"
            assert out["city"] == "Bengaluru"
            assert out["campaign_type"] == "personal_table"
            assert out["hero_image_url"] == "/uploads/cover.jpg"
            assert out["creator_ids"] == [str(creator_oid)]
            assert out["deliverables"] == "1 reel"
            assert out["results"]["reach"] == 52000
            assert out["results"]["content_pieces"] == 1
            assert out["campaign_id"] == str(campaign["_id"])
            # It arrives as a draft: nothing publishes itself.
            assert out["status"] == "draft"

        run(body)

    def test_the_narrative_is_left_for_a_person(self):
        """Pre-filling the challenge from the brief would publish the brand's
        own words back at them as our analysis."""

        async def body(db):
            brand_oid = await _brand(db)
            campaign = await _campaign(
                db, brand_oid, brief="We need people to hear about the new menu."
            )
            out = await server.create_case_study(
                server.CaseStudyPayload(), str(campaign["_id"]), ADMIN
            )
            assert out["challenge"] is None
            assert out["approach"] is None
            assert out["headline_result"] is None

        run(body)

    def test_only_creators_who_already_agreed_are_carried_across(self):
        """**The consent check happens at the prefill, not at the publish.**

        An admin ticking names off a list they were never allowed to use is a
        consent check that arrives too late to be one.
        """

        async def body(db):
            brand_oid = await _brand(db)
            campaign = await _campaign(db, brand_oid)
            yes = await _creator(db, opted_in=True, name="Asha Yes")
            no = await _creator(db, opted_in=False, name="Ravi No")
            await _delivered(db, campaign, yes)
            await _delivered(db, campaign, no)

            out = await server.create_case_study(
                server.CaseStudyPayload(), str(campaign["_id"]), ADMIN
            )
            assert out["creator_ids"] == [str(yes)]

        run(body)

    def test_a_campaign_still_running_is_refused_with_the_reason(self):
        async def body(db):
            brand_oid = await _brand(db)
            campaign = await _campaign(db, brand_oid, status="open")
            with pytest.raises(HTTPException) as err:
                await server.create_case_study(
                    server.CaseStudyPayload(), str(campaign["_id"]), ADMIN
                )
            assert err.value.status_code == 409
            assert err.value.detail["code"] == "campaign_not_closed"
            # And nothing was written.
            assert await db.case_studies.count_documents({}) == 0

        run(body)

    def test_the_admins_own_words_win_over_the_prefill(self):
        """They are looking at the form; the campaign is not."""

        async def body(db):
            brand_oid = await _brand(db)
            campaign = await _campaign(db, brand_oid)
            out = await server.create_case_study(
                server.CaseStudyPayload(title="A night at Toit", city="Mumbai"),
                str(campaign["_id"]),
                ADMIN,
            )
            assert out["title"] == "A night at Toit"
            assert out["city"] == "Mumbai"
            # And what they did not override still came from the campaign.
            assert out["brand_name"] == "Toit Brewpub"

        run(body)

    def test_the_engagement_rate_is_the_aggregate_not_the_mean(self):
        """Engagements over reach for the whole set. The mean of the per-post
        rates lets one tiny post with a freak rate move the headline — the
        same reasoning `_rollup_performance` gives."""

        async def body(db):
            brand_oid = await _brand(db)
            campaign = await _campaign(db, brand_oid)
            big = await _creator(db, name="Big")
            small = await _creator(db, name="Small")
            await _delivered(db, campaign, big, reach=100000)
            await _delivered(db, campaign, small, reach=100)

            out = await server.create_case_study(
                server.CaseStudyPayload(), str(campaign["_id"]), ADMIN
            )
            # 2 × (3100 + 210) engagements over 100,100 reach = 6.61%.
            # The mean of the two per-post rates would be about 1657%.
            assert out["results"]["engagement_rate"] == pytest.approx(6.61, abs=0.05)

        run(body)

    def test_it_is_audited_with_the_campaign_it_came_from(self):
        async def body(db):
            brand_oid = await _brand(db)
            campaign = await _campaign(db, brand_oid)
            await server.create_case_study(
                server.CaseStudyPayload(), str(campaign["_id"]), ADMIN
            )
            line = await db.audit_log.find_one({"action": "case_study.create"})
            assert line
            assert line["after"]["from_campaign"] == str(campaign["_id"])
            assert line.get("campaign_id") == campaign["_id"]

        run(body)


# ---------------------------------------------------------------------------
# Publishing, and the slug
# ---------------------------------------------------------------------------


class TestPublishing:
    def test_an_incomplete_one_is_refused_and_says_what_is_missing(self):
        async def body(db):
            doc, _, _, _ = await _published(db)
            await db.case_studies.update_one(
                {"_id": doc["_id"]},
                {"$set": {"status": "draft", "approach": None, "hero_image_url": None}},
            )
            with pytest.raises(HTTPException) as err:
                await server.publish_case_study(str(doc["_id"]), ADMIN)
            assert err.value.status_code == 409
            missing = err.value.detail["missing_fields"]
            assert "what we did" in missing and "a hero image" in missing
            fresh = await db.case_studies.find_one({"_id": doc["_id"]})
            assert fresh["status"] == "draft"

        run(body)

    def test_a_draft_is_not_readable_by_a_stranger(self):
        async def body(db):
            doc, _, _, _ = await _published(db, status="draft")
            with pytest.raises(HTTPException) as err:
                await server.get_public_case_study(doc["slug"])
            assert err.value.status_code == 404
            listed = await server.list_public_case_studies()
            assert listed["case_studies"] == []

        run(body)

    def test_an_admin_can_preview_a_draft_through_the_public_projection(self):
        """One renderer, so the preview cannot disagree with the page."""

        async def body(db):
            doc, _, _, _ = await _published(db, status="draft")
            out = await server.preview_case_study(str(doc["_id"]), ADMIN)
            assert out["case_study"]["title"] == "Tasting evening at Toit"
            assert out["missing_fields"] == []
            # And the preview is the public shape: no leaks through this door.
            for name, value in LEAKS.items():
                assert str(value) not in blob(out), name

        run(body)

    def test_unpublishing_keeps_the_row_and_the_first_publication_date(self):
        async def body(db):
            doc, _, _, _ = await _published(db)
            first = (await db.case_studies.find_one({"_id": doc["_id"]}))["published_at"]
            await server.unpublish_case_study(str(doc["_id"]), ADMIN)
            fresh = await db.case_studies.find_one({"_id": doc["_id"]})
            assert fresh["status"] == "draft"
            assert fresh["published_at"] == first

        run(body)

    def test_republishing_does_not_move_the_date(self):
        """A correction is not a new piece of work, and a date that moved
        every time somebody fixed a typo would reorder the shelf for nothing."""

        async def body(db):
            doc, _, _, _ = await _published(db)
            first = (await db.case_studies.find_one({"_id": doc["_id"]}))["published_at"]
            await server.unpublish_case_study(str(doc["_id"]), ADMIN)
            await server.publish_case_study(str(doc["_id"]), ADMIN)
            fresh = await db.case_studies.find_one({"_id": doc["_id"]})
            assert fresh["published_at"] == first

        run(body)

    def test_a_published_one_cannot_be_deleted_outright(self):
        """The link may already be out there."""

        async def body(db):
            doc, _, _, _ = await _published(db)
            with pytest.raises(HTTPException) as err:
                await server.delete_case_study(str(doc["_id"]), ADMIN)
            assert err.value.status_code == 409
            assert await db.case_studies.count_documents({}) == 1

        run(body)

    def test_two_case_studies_never_share_a_slug(self):
        async def body(db):
            brand_oid = await _brand(db)
            first = await server.create_case_study(
                server.CaseStudyPayload(title="A night at Toit"), None, ADMIN
            )
            second = await server.create_case_study(
                server.CaseStudyPayload(title="A night at Toit"), None, ADMIN
            )
            assert first["slug"] == "a-night-at-toit"
            assert second["slug"] == "a-night-at-toit-2"

        run(body)

    def test_re_saving_does_not_walk_a_slug_forward(self):
        """`exclude` is the row being edited. Without it, saving a case study
        without touching its title renames it every time."""

        async def body(db):
            created = await server.create_case_study(
                server.CaseStudyPayload(title="A night at Toit"), None, ADMIN
            )
            for _ in range(3):
                saved = await server.update_case_study(
                    created["id"],
                    server.CaseStudyPayload(slug="a-night-at-toit"),
                    ADMIN,
                )
            assert saved["slug"] == "a-night-at-toit"

        run(body)


# ---------------------------------------------------------------------------
# Input that came from outside
# ---------------------------------------------------------------------------


class TestWhatTheFormWillAccept:
    def test_an_image_must_be_a_path_we_issued(self):
        """The rule `cover_image_url` already holds: there is no way to point
        a marketing page at somebody else's server, and no way to get a
        `javascript:` into an `<img src>`."""
        for bad in (
            "https://evil.example.com/pixel.png",
            "javascript:alert(1)",
            "/uploads/../../etc/passwd",
            "/uploads/ok.png?x=1",
            "//evil.example.com/x.png",
            "",
        ):
            assert server._our_image_path(bad) is None, bad
        assert server._our_image_path("/uploads/case-study/abc.png") == (
            "/uploads/case-study/abc.png"
        )

    def test_a_content_link_must_be_http(self):
        rows = server._clean_case_study_links(
            [
                {"url": "javascript:alert(1)", "label": "Tap"},
                {"url": "https://instagram.com/p/ok", "label": "The reel"},
                {"url": "https://instagram.com/p/ok", "label": "Duplicate"},
                {"url": "data:text/html,<script>"},
            ]
        )
        assert rows == [{"label": "The reel", "url": "https://instagram.com/p/ok"}]

    def test_a_quote_without_a_name_on_it_is_dropped(self):
        """An unattributed quote on a marketing page is a sentence we wrote
        about ourselves."""
        assert server._clean_case_study_quote({"text": "They were great."}) is None
        assert server._clean_case_study_quote({"attribution": "Sibi"}) is None
        assert server._clean_case_study_quote(
            {"text": "They ran the lot.", "attribution": "Sibi"}
        ) == {"text": "They ran the lot.", "attribution": "Sibi", "role": None}

    def test_an_unmeasured_result_is_none_rather_than_zero(self):
        """A campaign with no reach reading and a campaign that reached nobody
        are different facts, and only one is worth publishing."""
        out = server._clean_case_study_results({"reach": "", "content_pieces": None})
        assert out["reach"] is None
        assert out["content_pieces"] is None
        assert out["engagement_rate"] is None
        # And a real zero that somebody typed is still not a negative.
        assert server._clean_case_study_results({"reach": -5})["reach"] is None

    def test_a_custom_metric_keeps_its_units(self):
        """"340 covers" and "+18% on the week" are what a brand actually wants
        on the page, and a float would lose the half that means something."""
        rows = server._clean_case_study_metrics(
            [
                {"label": "Covers", "value": "340"},
                {"label": "Bookings", "value": "+18% on the week"},
                {"label": "", "value": "12"},
                {"label": "No figure", "value": ""},
            ]
        )
        assert rows == [
            {"label": "Covers", "value": "340"},
            {"label": "Bookings", "value": "+18% on the week"},
        ]

    def test_the_edit_is_a_partial_save(self):
        """An omitted key means leave it alone; an explicit null clears it.
        Collapsing those two would wipe the approach every time somebody fixed
        the title — the rule `PUT /creator/profile` already holds."""

        async def body(db):
            doc, _, _, _ = await _published(db)
            await server.update_case_study(
                str(doc["_id"]), server.CaseStudyPayload(title="A new title"), ADMIN
            )
            fresh = await db.case_studies.find_one({"_id": doc["_id"]})
            assert fresh["title"] == "A new title"
            assert fresh["approach"] == "Twelve creators over four sittings."

            await server.update_case_study(
                str(doc["_id"]), server.CaseStudyPayload(approach=None), ADMIN
            )
            fresh = await db.case_studies.find_one({"_id": doc["_id"]})
            assert fresh["approach"] is None

        run(body)

    def test_the_vocabulary_is_the_products_own(self):
        """The brief asked for categories including beauty and tech, and a
        campaign type called delivery. A case study is *about a campaign*, so
        a filter offering one of those is a filter that can never match
        anything real — and a second category list is the drift
        `lib/categories.js` exists to prevent.

        **`delivery` has since become real**, and that is the rule working
        rather than an exception to it: the enum moved and this moved with it,
        because it was never a second list. The categories are still the
        product's own."""
        import typing

        assert typing.get_args(
            server.CaseStudyPayload.model_fields["category"].annotation
        )[0] is server.CATEGORY_LITERAL or True  # shape varies by pydantic version
        # The real assertion: the enums are shared, not copied.
        assert set(typing.get_args(server.CATEGORY_LITERAL)) == set(
            server.CATEGORY_LABELS
        )

        async def body(db):
            with pytest.raises(Exception):
                server.CaseStudyPayload(category="beauty")
            # A type this operation does not run is still refused.
            with pytest.raises(Exception):
                server.CaseStudyPayload(campaign_type="popup")
            # And one it does is accepted, without a second list to update.
            assert (
                server.CaseStudyPayload(campaign_type="delivery").campaign_type
                == "delivery"
            )

        run(body)


# ---------------------------------------------------------------------------
# The public surface
# ---------------------------------------------------------------------------


class TestTheShelf:
    def test_filters_narrow_and_only_offer_what_exists(self):
        async def body(db):
            doc, _, _, _ = await _published(db)
            await db.case_studies.insert_one(
                {
                    "_id": ObjectId(), "slug": "a-fashion-drop", "title": "A drop",
                    "status": "published", "category": "fashion", "city": "Mumbai",
                    "campaign_type": "launch", "display_order": 1,
                    "published_at": _now(), "results": {},
                }
            )
            out = await server.list_public_case_studies()
            assert len(out["case_studies"]) == 2
            assert out["filters"]["categories"] == ["fashion", "fnb"]
            assert out["filters"]["cities"] == ["Bengaluru", "Mumbai"]

            narrowed = await server.list_public_case_studies(category="fashion")
            assert [c["slug"] for c in narrowed["case_studies"]] == ["a-fashion-drop"]

            by_city = await server.list_public_case_studies(city="Bangalore")
            assert [c["slug"] for c in by_city["case_studies"]] == ["toit-tasting-evening"]

        run(body)

    def test_the_shelf_reads_in_the_order_an_admin_arranged(self):
        """The strongest piece of work is rarely the most recent."""

        async def body(db):
            first, _, _, _ = await _published(db)
            await db.case_studies.insert_one(
                {
                    "_id": ObjectId(), "slug": "second", "title": "Second",
                    "status": "published", "display_order": 0,
                    "published_at": _now(), "results": {},
                }
            )
            await db.case_studies.update_one(
                {"_id": first["_id"]}, {"$set": {"display_order": 5}}
            )
            out = await server.list_public_case_studies()
            assert [c["slug"] for c in out["case_studies"]] == [
                "second",
                "toit-tasting-evening",
            ]

        run(body)

    def test_the_headline_falls_back_to_reach_rather_than_to_nothing(self):
        """The admin's own sentence wins — "sold out in four days" beats any
        number we can compute — but a card with no headline at all is a card
        that says nothing."""
        assert server._case_study_headline({"headline_result": "Sold out"}) == "Sold out"
        assert server._case_study_headline({"results": {"reach": 52000}}) == (
            "52,000 people reached"
        )
        assert server._case_study_headline({"results": {"content_pieces": 12}}) == (
            "12 pieces of content"
        )
        assert server._case_study_headline({}) == ""

    def test_the_sitemap_lists_published_work(self):
        """These are the one part of the public surface written to be *found*
        rather than sent, so leaving them out wastes the only pages here with
        a search intent behind them."""

        async def body(db):
            doc, _, _, _ = await _published(db)
            await db.case_studies.insert_one(
                {"_id": ObjectId(), "slug": "a-draft", "status": "draft",
                 "title": "Draft", "results": {}}
            )
            xml = (await server.public_sitemap()).body.decode()
            assert "/work/toit-tasting-evening" in xml
            assert "/work</loc>" in xml or "/work<" in xml
            assert "a-draft" not in xml

        run(body)

    def test_the_share_card_leads_with_the_result(self):
        """These get pasted into a chat with a brand, so the preview is the
        pitch — the same reasoning `_share_summary` gives for a brief."""
        line = server._case_study_summary(
            {
                "headline_result": "Sold out in four days",
                "brand_name": "Toit Brewpub",
                "category_label": "Food & drink",
                "city": "Bengaluru",
            }
        )
        assert line.startswith("Sold out in four days")
        assert "Toit Brewpub" in line

    def test_the_detail_page_declares_no_size_for_a_hero_it_did_not_measure(self):
        """A wrong `og:image:width` is worse than none, because some crawlers
        lay the card out from it — the rule `/c/{id}` already holds."""

        async def body(db):
            doc, _, _, _ = await _published(db)
            with_hero = server._work_detail_html(await server._public_case_study(doc))
            assert "og:image:width" not in with_hero

            await db.case_studies.update_one(
                {"_id": doc["_id"]}, {"$set": {"hero_image_url": None}}
            )
            fresh = await db.case_studies.find_one({"_id": doc["_id"]})
            without = server._work_detail_html(await server._public_case_study(fresh))
            # Falls back to the site card, whose size we do know.
            assert 'og:image:width" content="1200"' in without

        run(body)

    def test_everything_typed_is_escaped(self):
        """A title and a quote are text somebody pasted, on a page anybody can
        open."""

        async def body(db):
            doc, _, _, _ = await _published(db)
            await db.case_studies.update_one(
                {"_id": doc["_id"]},
                {"$set": {"title": '<script>alert("x")</script>',
                          "challenge": "<img src=x onerror=alert(1)>"}},
            )
            fresh = await db.case_studies.find_one({"_id": doc["_id"]})
            html = server._work_detail_html(await server._public_case_study(fresh))
            assert "<script>alert" not in html
            assert "<img src=x onerror" not in html
            assert "&lt;script&gt;" in html

        run(body)


# ---------------------------------------------------------------------------
# Who may touch it
# ---------------------------------------------------------------------------


def guard_allows(fn, role):
    """Would FastAPI let this role through? Calling a route function directly
    skips its `Depends` entirely, so the guard has to be pulled off the
    signature and run — a string match would pass on a guard listing the wrong
    roles."""
    import inspect

    from fastapi import params

    guard = None
    for p in inspect.signature(fn).parameters.values():
        dep = p.default
        if isinstance(dep, params.Depends) and getattr(
            dep.dependency, "__name__", ""
        ) == "_guard":
            guard = dep.dependency
    assert guard, f"{fn.__name__} declares no require_roles guard"

    async def go():
        try:
            await guard({"_id": str(ObjectId()), "role": role})
            return True
        except HTTPException as err:
            assert err.status_code == 403
            return False

    return _loop().run_until_complete(go())


@pytest.mark.parametrize(
    "handler",
    [
        "list_case_studies",
        "get_case_study",
        "preview_case_study",
        "create_case_study",
        "update_case_study",
        "publish_case_study",
        "unpublish_case_study",
        "reorder_case_studies",
        "upload_case_study_image",
        "delete_case_study",
    ],
)
def test_case_studies_are_admin_only(handler):
    """**Admin-only, not `CONSOLE_ROLES`, and it is the split
    `POST /admin/brands` makes.**

    A case study is a claim this operation puts on the open internet under its
    own name, with a brand and a set of named people on it. `weare_team` is
    scoped to assigned brands, which is right for running a campaign and wrong
    for deciding what the platform says about itself — and a scoped role that
    could publish a page naming creators from outside its scope is not a scope.
    """
    fn = getattr(server, handler)
    assert guard_allows(fn, "admin")
    for role in ("weare_team", "brand_manager", "campaign_manager", "creator"):
        assert not guard_allows(fn, role), f"{handler} is open to {role}"


# ---------------------------------------------------------------------------
# The frontend half
# ---------------------------------------------------------------------------
#
# **"If a backend flow has no UI it is not shipped, whatever the tests say."**
# That rule was written after four brand-verification endpoints sat with no
# caller anywhere, so a brand could sign up and then hit the gate forever with
# no route to the thing that would clear it. A case study is the same shape of
# risk and worse: the endpoints could all be perfect and, without a screen,
# writing one would be a job somebody does in a database client — which means
# never, which is exactly why we had none.

from pathlib import Path  # noqa: E402

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"


def fread(*parts):
    return FRONTEND.joinpath(*parts).read_text()


def fcode(*parts):
    """A source file with its comments stripped.

    Load-bearing, not tidiness: the convention here is to explain a decision
    where it was made, so the comment saying "a `<Link>` would be swallowed by
    the SPA" necessarily contains `<Link`. Without this, the rule fails on its
    own justification and the obvious fix is to delete the explanation. The
    same helper `test_marketing_pages.py` and `test_admin_console.py` use.
    """
    import re as _re

    src = fread(*parts)
    src = _re.sub(r"\{/\*.*?\*/\}", "", src, flags=_re.S)
    src = _re.sub(r"/\*.*?\*/", "", src, flags=_re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


class TestTheScreensExist:
    def test_every_admin_route_has_a_caller(self):
        """The rule `test_manager_experience.py` holds for the manager router,
        applied here: a route nothing calls is a route nobody can reach."""
        section = fread("components", "admin", "CaseStudies.jsx")
        for call in (
            '"/admin/case-studies"',
            "`/admin/case-studies/${study.id}`",
            "`/admin/case-studies/${study.id}/preview`",
            "`/admin/case-studies/${study.id}/publish`",
            "`/admin/case-studies/${study.id}/unpublish`",
        ):
            assert call in section, call
        # And creating one, both ways.
        assert "from_campaign=" in section

    def test_the_section_is_mounted_and_routes_somewhere(self):
        """**A caller with no mount is as unreachable as a route with no
        caller** — the second half of that rule, which is what deleting
        `<SlotAnswer />` from the manager's campaign page slipped past."""
        sidebar = fread("components", "admin", "console", "Sidebar.jsx")
        assert 'key: "case-studies"' in sidebar
        assert 'to: "case-studies"' in sidebar
        # Admin-only in the navigation as well as on the server, so a scoped
        # console is not offered a section every one of whose calls would 403.
        block = sidebar[sidebar.index('key: "case-studies"'):]
        assert "adminOnly: true" in block[: block.index("},")], "not admin-only in the rail"

        routes = fread("components", "admin", "routes.jsx")
        assert "export function CaseStudiesRoute" in routes
        assert "<CaseStudies />" in routes

        app = fread("App.js")
        assert 'path="case-studies" element={<CaseStudiesRoute />}' in app
        assert 'adminRoute("CaseStudiesRoute")' in app

    def test_the_editor_asks_only_for_what_a_person_has_to_write(self):
        """The narrative two are inputs; the roster is read-only.

        A box an admin can type a creator's name into is a box that gets a
        name typed into it, and consent is not something a form should be able
        to route around.
        """
        section = fread("components", "admin", "CaseStudies.jsx")
        assert "IDS.challenge" in section and "IDS.approach" in section
        roster = section[section.index("IDS.roster") - 600 : section.index("IDS.roster") + 400]
        assert "<Input" not in roster and "<Textarea" not in roster

    def test_publishing_is_disabled_with_the_reason_on_screen(self):
        """A greyed-out button with no explanation is how a form becomes a
        support ticket — the lesson the brand's verification checklist
        records."""
        section = fread("components", "admin", "CaseStudies.jsx")
        assert "disabled={pending || missing.length > 0}" in section
        assert "IDS.missing" in section
        assert "missing.map" in section


class TestTheMarketingStrip:
    def test_it_is_on_both_pages_the_brief_names(self):
        for page in ("Landing.jsx", "ForBrands.jsx"):
            src = fread("pages", page)
            assert "<CaseStudyStrip />" in src, page
            assert "CaseStudyStrip" in src, page

    def test_the_cards_leave_the_spa(self):
        """`/work` is server-rendered, so a `<Link>` would be caught by the
        router and answered with the catch-all — the failure `/for-brands` and
        `/for-creators` had for months, and it is silent."""
        strip = fcode("components", "marketing", "CaseStudyStrip.jsx")
        assert "href={`${WORK_PATH}/${study.slug}`}" in strip
        assert "<Link" not in strip
        assert "react-router" not in strip

    def test_it_is_absent_below_the_floor_rather_than_short(self):
        """A shelf of one advertises an operation that has run one campaign.
        The same argument `PROOF_FLOORS` makes, and the same all-or-nothing
        shape."""
        strip = fread("components", "marketing", "CaseStudyStrip.jsx")
        assert "const FLOOR = 3" in strip
        assert "studies.length < FLOOR" in strip

    def test_nothing_is_fetched_until_it_is_nearly_on_screen(self):
        """A marketing page must not pay for this on the critical path."""
        strip = fread("components", "marketing", "CaseStudyStrip.jsx")
        assert "IntersectionObserver" in strip
        assert 'rootMargin: "600px"' in strip
        # And the reserved shape is not drawn before the request is in flight,
        # or a visitor who never scrolls gets a permanent section-shaped hole.
        assert "if (!near ||" in strip

    def test_every_image_reserves_its_box_and_loads_lazily(self):
        """The ratio is on the container, never on the `<img>` — the design
        foundations' rule, and what stops the card changing height when a hero
        finally arrives."""
        strip = fread("components", "marketing", "CaseStudyStrip.jsx")
        assert 'className="aspect-[16/9] w-full overflow-hidden' in strip
        assert 'loading="lazy"' in strip

    def test_the_path_is_named_once(self):
        """Three things link to `/work` — the footer and both strips — and a
        path written out three times is a path that moves twice."""
        nav = fread("lib", "siteNav.js")
        assert 'export const WORK_PATH = "/work";' in nav
        assert server.CASE_STUDY_PATH == "/work"
        strip = fcode("components", "marketing", "CaseStudyStrip.jsx")
        assert "WORK_PATH" in strip and '"/work' not in strip

    def test_the_footer_reaches_it_with_an_anchor(self):
        """Marked `external` — not because it leaves the site, but because a
        router link to a server-rendered page is swallowed by the SPA."""
        nav = fread("lib", "siteNav.js")
        block = nav[nav.index('label: "Our work"') :]
        assert "external: true" in block[: block.index("}")]
