"""The brief in pieces, and proof that a story ran.

Four things, and the first two are the same shape of problem: a fact the
product had, that never reached the person who needed it.

- **Story proof.** An Instagram story is gone in twenty-four hours, so a
  submitted link is dead by the time anybody reviews it. A story deliverable
  was the one thing here that could be asked for, delivered, and then not
  verified.
- **The structured brief.** Everything a brand cared about went into one
  free-text box as prose, so the mismatch surfaced at draft review — after the
  shoot, when the fix is a reshoot.
- **Reference ids.** Built end to end on the backend and then not emitted by
  the campaign list or the campaign review queue, so the one place a console
  screen prints a reference for campaigns stayed blank.
- **Partial delivery and underfill.** Both were built and both had a dead end
  in the UI: `can_accept_partial` shipped with no button anywhere, and the
  health panel's three "ways out" carried query strings the campaign page never
  read.

Driven against the real handlers and read back from the database where there is
state to read, for the reason `test_money_paths.py` sets out: a guard that is
present and does nothing keeps the string and loses the protection.
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import server

LOOP = None
FRONTEND = Path(__file__).resolve().parents[3] / "frontend" / "src"


def run(body):
    """One loop per call — see the note in `test_money_paths.py`."""
    global LOOP
    if LOOP is None:
        LOOP = asyncio.new_event_loop()

    async def go():
        db = AsyncMongoMockClient()["brief"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return LOOP.run_until_complete(go())


def read(*parts):
    return (FRONTEND.joinpath(*parts)).read_text()


def _now():
    return datetime.now(timezone.utc)


DAY = (_now() + timedelta(days=14)).replace(hour=13, minute=0, second=0, microsecond=0)
ADMIN = {"_id": str(ObjectId()), "role": "admin", "name": "Admin"}


def _body(**over):
    body = {
        "title": "Two reels for the spring range",
        "brief": "Shoot in store, natural light.",
        "deliverable_items": [{"type": "reel", "quantity": 2}],
        "budget_per_creator": 9000,
        "category": "fashion",
        "area": "Indiranagar",
        "creators_needed": 2,
        "campaign_type": "personal_table",
        "start_date": DAY,
        "end_date": DAY + timedelta(days=7),
    }
    body.update(over)
    return body


# ---------------------------------------------------------------------------
# 1. The structured brief
# ---------------------------------------------------------------------------


class TestTheStructuredHalfOfABrief:
    def test_absent_is_not_stated_rather_than_empty(self):
        """**A brief that named no don'ts has no "Don't" heading.** An empty
        one reads as a brand that had nothing to say about it, which is a
        different claim from never being asked — and every campaign written
        before these fields existed is in exactly that position."""
        assert server._brief_details({}) == {}
        assert server._brief_details(None) == {}
        assert server._brief_checklist_count({}) == 0

    def test_only_the_fields_that_were_filled_come_back(self):
        out = server._brief_details(
            {"brief_dos": ["Show the storefront"], "brief_donts": [], "mandatory_hashtags": []}
        )
        assert out == {"brief_dos": ["Show the storefront"]}

    def test_a_hashtag_is_stored_with_its_hash_however_it_was_typed(self):
        """Somebody types "weare", "#weare" and "# weare" across three briefs
        and a creator comparing two of them is comparing punctuation."""
        out = server._resolve_brief_details(
            {"mandatory_hashtags": ["weare", "#weare", "# weare", "  spring  "]}
        )
        # All three spellings of the first collapse to one row.
        assert out["mandatory_hashtags"] == ["#weare", "#spring"]

    def test_a_handle_is_stored_with_its_at(self):
        out = server._resolve_brief_details({"mandatory_mentions": ["ninthstreet", "@other"]})
        assert out["mandatory_mentions"] == ["@ninthstreet", "@other"]

    def test_a_sigil_only_line_is_dropped_rather_than_stored_bare(self):
        """"#" on its own is a row that renders as a lone hash — a checklist
        item nobody can tick."""
        assert server._resolve_brief_details({"mandatory_hashtags": ["#", " @ "]})[
            "mandatory_hashtags"
        ] == []

    def test_blank_and_duplicate_lines_are_dropped_and_the_list_is_capped(self):
        rows = ["  ", "Show the storefront", "Show the storefront", *[f"x{i}" for i in range(30)]]
        out = server._resolve_brief_details({"brief_dos": rows})["brief_dos"]
        assert out[0] == "Show the storefront"
        assert len(out) == server.MAX_BRIEF_LIST_ITEMS
        assert len(set(out)) == len(out)

    def test_an_asset_link_that_is_not_a_link_is_dropped(self):
        """**A `javascript:` in a field a brand types and a creator clicks** is
        the obvious way to turn a brief into an attack, and the label renders
        as an anchor."""
        out = server._resolve_brief_details(
            {
                "brand_assets": [
                    {"label": "Logo", "url": "javascript:alert(1)"},
                    {"label": "Pack shot", "url": "https://cdn.example.com/pack.png"},
                    {"label": "Same", "url": "https://cdn.example.com/pack.png"},
                ]
            }
        )
        assert out["brand_assets"] == [
            {"label": "Pack shot", "url": "https://cdn.example.com/pack.png"}
        ]

    def test_an_asset_with_no_label_falls_back_to_its_url(self):
        out = server._resolve_brief_details(
            {"brand_assets": [{"url": "https://cdn.example.com/f.png"}]}
        )
        assert out["brand_assets"][0]["label"] == "https://cdn.example.com/f.png"

    def test_an_omitted_key_is_left_alone_and_an_empty_list_clears_it(self):
        """**Two different edits.** Collapsing them would wipe a brief's
        hashtags every time somebody changed its title."""
        assert "brief_dos" not in server._resolve_brief_details({"brief_donts": ["x"]})
        assert server._resolve_brief_details({"brief_dos": []})["brief_dos"] == []

    def test_the_count_ignores_the_assets(self):
        """"6 things to get right" is about instructions. A link to a logo is a
        resource, not a thing to tick off."""
        details = {
            "brief_dos": ["a", "b"],
            "caption_guidance": "Keep it short",
            "brand_assets": [{"label": "Logo", "url": "https://x.test/l.png"}],
        }
        assert server._brief_checklist_count(details) == 3


class TestTheBriefIsWrittenByOneWriterAndReadEverywhere:
    def test_the_brand_create_path_stores_it(self):
        async def body(db):
            brand_oid = ObjectId()
            await db.brand_profiles.insert_one(
                {"user_id": brand_oid, "business_name": "Ninth Street", "verified": True,
                 "verified_at": _now(), "areas": ["Indiranagar"]}
            )
            user = {"_id": str(brand_oid), "role": "brand_manager", "brand_id": brand_oid,
                    "name": "Manager"}
            payload = server.PostCampaignPayload(
                **_body(
                    brief_dos=["Show the storefront"],
                    mandatory_hashtags=["weare"],
                    caption_guidance="Mention the offer ends this month.",
                )
            )
            await server.create_brand_campaign(payload, user)
            return await db.campaigns.find_one({"brand_id": brand_oid})

        doc = run(body)
        assert doc["brief_dos"] == ["Show the storefront"]
        assert doc["mandatory_hashtags"] == ["#weare"]
        assert doc["caption_guidance"] == "Mention the offer ends this month."

    def test_the_brand_edit_path_normalises_the_same_way(self):
        """The edit loop copies the payload generically, so these are popped
        out and resolved — the same reason `_refuse_brand_barter` exists."""

        async def body(db):
            brand_oid, campaign_oid = ObjectId(), ObjectId()
            await db.brand_profiles.insert_one(
                {"user_id": brand_oid, "business_name": "X", "verified": True,
                 "verified_at": _now()}
            )
            await db.campaigns.insert_one(
                {"_id": campaign_oid, "brand_id": brand_oid, "title": "t",
                 "status": "draft", "campaign_type": "personal_table",
                 "compensation_type": "fixed", "brief_dos": ["old"]}
            )
            user = {"_id": str(brand_oid), "role": "brand_manager", "brand_id": brand_oid}
            await server.update_brand_campaign(
                str(campaign_oid),
                server.UpdateCampaignPayload(mandatory_hashtags=["weare"], brief_dos=[]),
                user,
            )
            return await db.campaigns.find_one({"_id": campaign_oid})

        doc = run(body)
        assert doc["mandatory_hashtags"] == ["#weare"]
        # An explicit empty list clears it; the raw payload never lands.
        assert doc["brief_dos"] == []

    def test_the_admin_edit_path_goes_through_the_same_writer(self):
        source = inspect.getsource(server.admin_update_campaign)
        assert "_resolve_brief_details" in source

    def test_every_write_path_uses_the_one_writer(self):
        """A second normaliser is a second idea of what a hashtag is."""
        for fn in (
            server.create_brand_campaign,
            server.update_brand_campaign,
            server.admin_update_campaign,
            server.admin_create_campaign,
        ):
            source = inspect.getsource(fn)
            assert "_resolve_brief_details" in source or "_brief_details_from" in source, fn

    def test_it_rides_on_the_creators_own_shape(self):
        """**The brief is what the creator reads.** Shipping it only to the
        owner would put the checklist in front of the party who wrote it — the
        same mistake the disclosure and usage fields made first time round."""
        doc = {
            "_id": ObjectId(), "brand_id": ObjectId(), "title": "x", "status": "open",
            "brief_donts": ["Don't show the queue"],
        }
        out = server._serialize_campaign(doc, None)
        assert out["brief_details"] == {"brief_donts": ["Don't show the queue"]}

    def test_it_rides_on_the_owners_shape_so_an_edit_round_trip_keeps_it(self):
        doc = {
            "_id": ObjectId(), "brand_id": ObjectId(), "title": "x", "status": "draft",
            "mandatory_hashtags": ["#weare"], "creators_needed": 1,
        }
        out = server._serialize_brand_campaign(doc, 0, 0)
        assert out["brief_details"]["mandatory_hashtags"] == ["#weare"]

    def test_a_duplicate_and_a_template_carry_it(self):
        """**One list, three readers.** A brand that always asks for the same
        hashtag is exactly the brand that duplicates a brief, and a copy that
        dropped these would be quietly weaker than the thing it copied."""
        for field in server.BRIEF_DETAIL_FIELDS:
            assert field in server._CAMPAIGN_BRIEF_FIELDS, field

    def test_the_dates_are_still_not_copied(self):
        """The rule the duplicate exists for, restated now that the brief
        field list has grown: adding something to `_CAMPAIGN_BRIEF_FIELDS`
        must never reach a date."""
        assert not (set(server._CAMPAIGN_BRIEF_FIELDS) & set(server._CAMPAIGN_NOT_COPIED))


class TestTheChecklistReachesEverySurface:
    def test_the_reviewers_screen_gets_it(self):
        """A reviewer had the campaign title and the deliverables sentence;
        everything the brand asked about tags and captions was three screens
        away in a free-text box."""
        source = inspect.getsource(server.get_application)
        assert '"brief_details": _brief_details(campaign)' in source

    def test_the_managers_roster_gets_it(self):
        source = inspect.getsource(server.campaign_roster)
        assert "_brief_details(campaign)" in source

    def test_the_creators_own_row_gets_it(self):
        source = inspect.getsource(server._serialize_collab_row)
        assert "_brief_details(campaign)" in source

    def test_the_frontend_mirrors_the_vocabulary(self):
        """`lib/briefDetails.js` and the server's tables must agree, or a
        field renders under the wrong heading."""
        mirror = read("lib", "briefDetails.js")
        for key in server.BRIEF_LIST_FIELDS:
            assert key in mirror, key
        for key in server.BRIEF_TEXT_FIELDS:
            assert key in mirror, key
        assert f"MAX_BRIEF_LIST_ITEMS = {server.MAX_BRIEF_LIST_ITEMS}" in mirror
        assert f"MAX_BRIEF_ASSETS = {server.MAX_BRIEF_ASSETS}" in mirror

    def test_the_checklist_never_asks_what_role_is_looking(self):
        """One component on four surfaces. The moment it branches on a role it
        is four components sharing a filename."""
        src = read("components", "campaign", "BriefChecklist.jsx")
        for smell in ("role ===", 'role === "admin"', "isAdmin", "user?.role"):
            assert smell not in src, smell

    def test_it_renders_nothing_when_nothing_was_stated(self):
        """An empty box headed "What to check" reads as a fact about the brand
        rather than a question nobody answered — the rule `ShootWindowNote`
        already holds."""
        src = read("components", "campaign", "BriefChecklist.jsx")
        assert "if (!hasBriefDetails(details)) return null;" in src

    def test_it_is_mounted_on_all_four_surfaces(self):
        """A component with no mount is as unreachable as a route with no
        caller — the rule `test_manager_experience.py` had to learn."""
        for parts in (
            ("pages", "CampaignDetail.jsx"),
            ("components", "creator", "ActiveCampaigns.jsx"),
            ("components", "application", "ApplicationDetail.jsx"),
            ("components", "manager", "BriefPanel.jsx"),
        ):
            assert "<BriefChecklist" in read(*parts), parts

    def test_the_editor_sends_every_key_and_not_only_the_filled_ones(self):
        """The server reads an omitted key as "leave it alone", so a form that
        sent only what was typed could add a hashtag and never remove one."""
        src = read("components", "campaign", "BriefDetailsEditor.jsx")
        block = src[src.index("export function toBriefDetails") :]
        for field in server.BRIEF_DETAIL_FIELDS:
            assert field in block, field


# ---------------------------------------------------------------------------
# 2. Story proof
# ---------------------------------------------------------------------------


class TestWhenAScreenshotIsRequired:
    def test_a_brief_with_no_counted_ask_requires_nothing(self):
        """**Absent structure reads as no requirement.** A campaign written
        before `deliverable_items` has a sentence and nothing to count, and a
        rule that fired on a guess would block deliveries on the whole back
        catalogue on the morning it deployed."""
        assert server._requires_story_proof({}) is False
        assert server._requires_story_proof({"deliverables": "a reel and a few stories"}) is False

    def test_it_reads_the_structure_and_never_the_sentence(self):
        assert server._story_quantity({"deliverable_items": [{"type": "story", "quantity": 3}]}) == 3
        assert server._story_quantity({"deliverable_items": [{"type": "reel", "quantity": 3}]}) == 0

    def test_a_link_stays_required_where_anything_else_was_asked_for(self):
        campaign = {
            "deliverable_items": [
                {"type": "story", "quantity": 2},
                {"type": "reel", "quantity": 1},
            ]
        }
        assert server._story_only_ask(campaign) is False
        stop = server._content_submission_refusal(campaign, [], [{"id": "p1"}])
        assert stop["code"] == "content_url_required"

    def test_a_stories_only_brief_makes_the_link_optional(self):
        """**The URL is dead before anybody reads it.** Demanding one means
        demanding a field whose value is known to be useless, and a creator who
        cannot submit without it will paste something that is not the work."""
        campaign = {"deliverable_items": [{"type": "story", "quantity": 2}]}
        assert server._story_only_ask(campaign) is True
        assert server._content_submission_refusal(campaign, [], [{"id": "p1"}]) is None

    def test_no_proof_on_a_story_brief_is_refused_with_a_code(self):
        campaign = {"deliverable_items": [{"type": "story", "quantity": 3}]}
        stop = server._content_submission_refusal(campaign, ["https://x.test/p"], [])
        assert stop["code"] == "story_proof_required"
        assert "3 stories" in stop["message"]

    def test_the_refusal_is_returned_rather_than_raised(self):
        """The same shape `_scheduling_refusal` and `_shoot_time_refusal` use,
        so the route and the flag the form reads share one decider instead of
        one of them being a second implementation."""
        assert server._content_submission_refusal({}, [], []) is not None
        assert server._content_submission_refusal({}, ["https://x.test/p"], []) is None

    def test_the_block_is_decided_server_side(self):
        campaign = {"deliverable_items": [{"type": "story", "quantity": 2}]}
        block = server._proof_block(campaign, {"content_proofs": [{"id": "a"}]})
        assert block["required"] is True
        assert block["link_optional"] is True
        assert block["story_quantity"] == 2
        assert block["count"] == 1


class TestAttachingAndRemovingProof:
    async def _scene(self, db, *, state="attended", stories=2, disputed=False):
        brand_oid, creator_oid = ObjectId(), ObjectId()
        campaign_oid, collab_oid = ObjectId(), ObjectId()
        await db.campaigns.insert_one(
            {"_id": campaign_oid, "brand_id": brand_oid, "title": "Spring stories",
             "status": "in_progress", "execution_owner": "brand",
             "compensation_type": "fixed", "budget_per_creator": 4000,
             "deliverable_items": [{"type": "story", "quantity": stories}]}
        )
        collab = {
            "_id": collab_oid, "campaign_id": campaign_oid, "creator_id": creator_oid,
            "state": state, "state_since": _now(), "agreed_amount": 4000,
        }
        if disputed:
            collab["dispute"] = {"state": "open", "raised_by_role": "creator"}
        await db.collaborations.insert_one(collab)
        return {
            "creator": {"_id": str(creator_oid), "role": "creator", "name": "Asha"},
            "collab_id": str(collab_oid), "collab_oid": collab_oid,
            "campaign_oid": campaign_oid,
        }

    def test_a_screenshot_lands_privately_and_the_route_returns_no_path(self, tmp_path):
        async def body(db):
            s = await self._scene(db)
            block = await server.add_content_proof(
                s["collab_id"], _png_upload(), "Story one", s["creator"]
            )
            row = await db.collaborations.find_one({"_id": s["collab_oid"]})
            return block, row

        original = server.PRIVATE_UPLOAD_DIR
        server.PRIVATE_UPLOAD_DIR = tmp_path / "private"
        try:
            block, row = run(body)
        finally:
            server.PRIVATE_UPLOAD_DIR = original

        assert block["count"] == 1
        item = block["items"][0]
        # The bytes leave through the audited route or not at all.
        assert "stored_name" not in item and "path" not in item and "url" not in item
        assert row["content_proofs"][0]["stored_name"].startswith("proof-")
        assert row["content_proofs"][0]["mime"] == "image/png"

    def test_the_type_comes_from_the_bytes_and_never_the_filename(self, tmp_path):
        """The same rule every upload here holds: "story.png" that is really a
        PDF is refused rather than stored and served back as an image."""

        async def body(db):
            s = await self._scene(db)
            with pytest.raises(HTTPException) as err:
                await server.add_content_proof(
                    s["collab_id"], _pdf_upload(), None, s["creator"]
                )
            return err.value

        original = server.PRIVATE_UPLOAD_DIR
        server.PRIVATE_UPLOAD_DIR = tmp_path / "private"
        try:
            exc = run(body)
        finally:
            server.PRIVATE_UPLOAD_DIR = original
        assert exc.status_code == 422

    def test_a_frozen_collaboration_refuses_a_new_screenshot(self, tmp_path):
        """A dispute is usually *about* what was delivered, so swapping the
        evidence while a mediator is looking at it is the move the freeze
        exists to stop."""

        async def body(db):
            s = await self._scene(db, disputed=True)
            with pytest.raises(HTTPException) as err:
                await server.add_content_proof(
                    s["collab_id"], _png_upload(), None, s["creator"]
                )
            row = await db.collaborations.find_one({"_id": s["collab_oid"]})
            return err.value, row

        original = server.PRIVATE_UPLOAD_DIR
        server.PRIVATE_UPLOAD_DIR = tmp_path / "private"
        try:
            exc, row = run(body)
        finally:
            server.PRIVATE_UPLOAD_DIR = original
        assert exc.status_code == 409
        assert not row.get("content_proofs")

    def test_somebody_elses_collaboration_is_a_404(self, tmp_path):
        async def body(db):
            s = await self._scene(db)
            stranger = {"_id": str(ObjectId()), "role": "creator", "name": "Someone"}
            with pytest.raises(HTTPException) as err:
                await server.add_content_proof(
                    s["collab_id"], _png_upload(), None, stranger
                )
            return err.value

        original = server.PRIVATE_UPLOAD_DIR
        server.PRIVATE_UPLOAD_DIR = tmp_path / "private"
        try:
            exc = run(body)
        finally:
            server.PRIVATE_UPLOAD_DIR = original
        assert exc.status_code == 404

    def test_removing_takes_the_file_with_it(self, tmp_path):
        """A screenshot the creator withdrew is not a record of anything, and
        keeping the bytes of somebody's private screen after they asked for
        them to go is the opposite of what this storage is for."""

        async def body(db):
            s = await self._scene(db)
            block = await server.add_content_proof(
                s["collab_id"], _png_upload(), None, s["creator"]
            )
            row = await db.collaborations.find_one({"_id": s["collab_oid"]})
            stored = row["content_proofs"][0]["stored_name"]
            after = await server.remove_content_proof(
                s["collab_id"], block["items"][0]["id"], s["creator"]
            )
            row2 = await db.collaborations.find_one({"_id": s["collab_oid"]})
            return stored, after, row2

        original = server.PRIVATE_UPLOAD_DIR
        server.PRIVATE_UPLOAD_DIR = tmp_path / "private"
        server.PRIVATE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        try:
            stored, after, row2 = run(body)
        finally:
            server.PRIVATE_UPLOAD_DIR = original
        assert after["count"] == 0
        assert row2["content_proofs"] == []
        assert not (tmp_path / "private" / stored).exists()

    def test_it_cannot_be_swapped_once_the_delivery_was_accepted(self, tmp_path):
        """Evidence that changes after the decision is not evidence."""

        async def body(db):
            s = await self._scene(db, state="content_approved")
            with pytest.raises(HTTPException) as err:
                await server.add_content_proof(
                    s["collab_id"], _png_upload(), None, s["creator"]
                )
            return err.value

        original = server.PRIVATE_UPLOAD_DIR
        server.PRIVATE_UPLOAD_DIR = tmp_path / "private"
        try:
            exc = run(body)
        finally:
            server.PRIVATE_UPLOAD_DIR = original
        assert exc.status_code == 409


class TestSubmittingAStoryDelivery:
    async def _scene(self, db, *, items):
        brand_oid, creator_oid = ObjectId(), ObjectId()
        campaign_oid, collab_oid = ObjectId(), ObjectId()
        await db.users.insert_one(
            {"_id": brand_oid, "role": "brand_manager", "brand_id": brand_oid,
             "phone": "+919900000001"}
        )
        await db.campaigns.insert_one(
            {"_id": campaign_oid, "brand_id": brand_oid, "title": "Spring stories",
             "status": "in_progress", "execution_owner": "brand",
             "compensation_type": "fixed", "budget_per_creator": 4000,
             "deliverable_items": items}
        )
        await db.collaborations.insert_one(
            {"_id": collab_oid, "campaign_id": campaign_oid, "creator_id": creator_oid,
             "state": "attended", "state_since": _now(), "agreed_amount": 4000}
        )
        return {
            "creator": {"_id": str(creator_oid), "role": "creator", "name": "Asha"},
            "collab_id": str(collab_oid), "collab_oid": collab_oid,
        }

    def test_a_story_brief_refuses_a_link_alone_and_does_not_move(self):
        """**Assert on stored state, not only on the exception** — a 409
        raised after the write is not a refusal."""

        async def body(db):
            s = await self._scene(db, items=[{"type": "story", "quantity": 2}])
            with pytest.raises(HTTPException) as err:
                await server.submit_collab_content(
                    s["collab_id"],
                    server.SubmitContentPayload(content_urls=["https://instagram.com/s/1"]),
                    s["creator"],
                )
            return err.value, await db.collaborations.find_one({"_id": s["collab_oid"]})

        exc, row = run(body)
        assert exc.status_code == 422
        assert exc.detail["code"] == "story_proof_required"
        assert row["state"] == "attended"

    def test_a_stories_only_brief_goes_through_on_screenshots_alone(self):
        async def body(db):
            s = await self._scene(db, items=[{"type": "story", "quantity": 1}])
            await db.collaborations.update_one(
                {"_id": s["collab_oid"]},
                {"$set": {"content_proofs": [{"id": "p1", "stored_name": "proof-x.png",
                                              "mime": "image/png", "uploaded_at": _now()}]}},
            )
            out = await server.submit_collab_content(
                s["collab_id"], server.SubmitContentPayload(), s["creator"]
            )
            return out, await db.collaborations.find_one({"_id": s["collab_oid"]})

        out, row = run(body)
        assert row["state"] == "content_submitted"
        assert out["content_urls"] == []
        assert out["proof"]["count"] == 1

    def test_a_reel_brief_still_demands_a_link(self):
        """The change must not quietly make the URL optional everywhere."""

        async def body(db):
            s = await self._scene(db, items=[{"type": "reel", "quantity": 1}])
            with pytest.raises(HTTPException) as err:
                await server.submit_collab_content(
                    s["collab_id"], server.SubmitContentPayload(), s["creator"]
                )
            return err.value, await db.collaborations.find_one({"_id": s["collab_oid"]})

        exc, row = run(body)
        assert exc.status_code == 422
        assert exc.detail["code"] == "content_url_required"
        assert row["state"] == "attended"

    def test_a_pre_field_brief_is_unaffected(self):
        """A campaign with no counted ask keeps exactly the behaviour it had."""

        async def body(db):
            s = await self._scene(db, items=[])
            out = await server.submit_collab_content(
                s["collab_id"],
                server.SubmitContentPayload(content_urls=["https://instagram.com/p/1"]),
                s["creator"],
            )
            return out, await db.collaborations.find_one({"_id": s["collab_oid"]})

        out, row = run(body)
        assert row["state"] == "content_submitted"
        assert out["content_urls"] == ["https://instagram.com/p/1"]


class TestWhoMayReadAScreenshot:
    def test_the_reviewers_route_is_behind_the_staff_door(self):
        """Three doors and a 404 behind each — the same reader the work notes
        use, rather than a second answer to "may this person read this
        collaboration"."""
        source = inspect.getsource(server.read_content_proof)
        assert "_note_readable_collab_or_404" in source
        assert "audit(" in source

    def test_the_reviewers_route_excludes_creators(self):
        roles = _guard_roles(server.read_content_proof)
        assert "creator" not in roles
        assert "admin" in roles

    def test_the_bytes_never_sit_at_a_guessable_address(self):
        """`PRIVATE_UPLOAD_DIR`, deliberately not the mounted one — a
        screenshot of a story routinely catches the viewer list or a DM
        notification."""
        source = inspect.getsource(server.add_content_proof)
        assert "_store_private_upload" in source
        assert "_store_upload(" not in source

    def test_the_response_carries_no_stored_name(self):
        out = server._serialize_proof(
            {"id": "p1", "stored_name": "proof-secret.png", "mime": "image/png",
             "original_name": "IMG_1.png", "size": 12, "uploaded_at": _now()}
        )
        assert "proof-secret.png" not in str(out)
        assert out["original_name"] == "IMG_1.png"

    def test_a_filename_cannot_smuggle_a_header(self):
        """The uploader's filename never touches the filesystem, but it does
        get echoed into `Content-Disposition` — and a quote or a newline in it
        is a header the client parses differently from the one we sent."""
        assert server._safe_download_name('a"b\nc.png') == "abc.png"
        assert server._safe_download_name(None) == "file"
        assert server._safe_download_name("   ") == "file"

    def test_the_creator_reads_their_own_without_an_audit_line(self):
        """Looking at your own upload is not an access worth recording, and a
        log line per thumbnail is noise in the one place somebody goes looking
        for who saw what."""
        source = inspect.getsource(server.read_own_content_proof)
        assert "audit(" not in source


class TestTheProofSurfaces:
    def test_the_creators_form_offers_the_upload(self):
        src = read("components", "creator", "SubmitContentDialog.jsx")
        assert "<StoryProofUpload" in src

    def test_the_reviewer_sees_them_on_the_application_screen(self):
        src = read("components", "application", "ApplicationDetail.jsx")
        assert "<StoryProofReview" in src

    def test_the_form_never_decides_for_itself_whether_a_link_is_needed(self):
        """`proof.link_optional` is the server's answer. A client that worked
        it out would be a second copy of the rule, and the copy is what
        drifts."""
        src = read("components", "creator", "SubmitContentDialog.jsx")
        assert "proof?.link_optional" in src
        assert "deliverable_items" not in src

    def test_the_thumbnail_is_an_authenticated_blob_and_not_a_bare_url(self):
        """The session cookie is `SameSite=None`, so a bare `<img src>` rides
        along in production and silently does not on a plain-http laptop —
        the worst kind of difference. The rule `BrandDocuments` states."""
        src = read("components", "collab", "StoryProof.jsx")
        assert 'responseType: "blob"' in src
        # No bare address anywhere in the component, comments included — the
        # tempting version is exactly the one that half works.
        assert "API_BASE" not in src
        assert "revokeObjectURL" in src


# ---------------------------------------------------------------------------
# 3. Reference ids
# ---------------------------------------------------------------------------


class TestEveryEntityListCarriesItsReference:
    def test_the_campaign_list_emits_one(self):
        """It was the only entity list that did not, so the console's largest
        list was the one place an admin on the phone to a brand could not read
        the number back."""
        source = inspect.getsource(server.list_all_campaigns)
        assert '"reference": _reference_of(d)' in source

    def test_the_campaign_review_queue_emits_one(self):
        """`Reviews.jsx` prints `r.reference` when it is there, and this
        endpoint never sent it — so campaign rows were the one kind that
        stayed blank on a screen already built to show it."""
        source = inspect.getsource(server.list_campaigns_for_review)
        assert '"reference": _reference_of(d)' in source

    def test_the_other_three_still_do(self):
        for fn in (server._serialize_admin_creator, server._admin_brand_fields):
            assert "_reference_of" in inspect.getsource(fn), fn
        assert "_reference_of(collab)" in inspect.getsource(server._serialize_collab_row)

    def test_absent_stays_none_rather_than_being_invented(self):
        """A record the backfill has not reached has no number, and an invented
        one is worse than a blank column because somebody would quote it."""
        assert server._reference_of({}) is None
        assert server._reference_of(None) is None

    def test_a_typed_reference_is_answered_exactly(self):
        # It returns the *canonical* string, not the raw number: what search
        # matches on is the stored value, so "cmp34" and "CMP-0034" have to
        # arrive at one spelling before anything is looked up.
        assert server.parse_reference("CMP-0034") == ("campaign", "CMP-0034")
        assert server.parse_reference("cmp34") == ("campaign", "CMP-0034")
        assert server.parse_reference("crt 108") == ("creator", "CRT-0108")
        assert server.parse_reference("nonsense") is None

    def test_the_three_lists_show_a_reference_column(self):
        for name in ("AdminCreators.jsx", "AdminCampaigns.jsx", "AdminBrands.jsx"):
            src = read("components", "admin", name)
            block = src[src.index('key: "reference"') : src.index('key: "reference"') + 400]
            assert 'header: "Ref"' in block, name
            # Sortable, because a reference sorts by when the record was
            # created — the one ordering an ObjectId column could never show.
            assert "sortable: true" in block, name

    def test_the_palette_still_renders_one(self):
        assert "item.reference" in read("components", "admin", "CommandPalette.jsx")

    def test_the_migration_numbers_in_creation_order(self):
        """`CMP-0001` is the first brief this operation ever posted rather than
        whichever row the migration happened to reach first."""
        source = inspect.getsource(server._startup)
        block = source[source.index("# 11. Reference ids") :]
        assert '.sort("_id", 1)' in block
        assert "unique=True, sparse=True" in block


# ---------------------------------------------------------------------------
# 4. Partial delivery and underfill, end to end
# ---------------------------------------------------------------------------


class TestPartialDeliveryIsReachable:
    def test_the_flag_ships_and_now_has_a_button(self):
        """**`can_accept_partial` was computed, shipped, and rendered by
        nothing.** An admin who opened an application waiting on review could
        read the links and had no way to answer them — the decision existed
        only on the brand's own applicant board."""
        source = inspect.getsource(server.get_application)
        assert '"can_accept_partial"' in source
        src = read("components", "application", "ApplicationDetail.jsx")
        assert "actions.can_accept_partial" in src
        assert "<PartialDeliveryDialog" in src

    def test_the_content_review_actions_have_buttons_too(self):
        """The same gap, on the flag beside it: approving and sending back were
        offered by the payload and by nothing on the page."""
        src = read("components", "application", "ApplicationDetail.jsx")
        assert "actions.can_review_content" in src
        assert "/approve_content" in src
        assert "/request_changes" in src

    def test_the_dialog_gets_the_campaign_shape_it_needs(self):
        """It renders one row per counted deliverable and a pro-rata
        suggestion off the fee, so the payload has to carry both."""
        source = inspect.getsource(server.get_application)
        block = source[source.index('"campaign": {') :]
        for key in ("deliverable_items", "budget_per_creator", "compensation_type"):
            assert key in block, key

    def test_the_disclosure_checkpoint_is_one_component(self):
        """`brand_approve_content` refuses an unconfirmed disclosure, so every
        console that can approve has to ask — and a second copy of the question
        is a second thing to keep in step."""
        assert "DisclosureConfirmDialog" in read("components", "campaign", "CampaignTerms.jsx")
        for parts in (
            ("pages", "BrandCampaignApplicants.jsx"),
            ("components", "application", "ApplicationDetail.jsx"),
        ):
            src = read(*parts)
            assert "DisclosureConfirmDialog" in src, parts
            # Imported, not redefined.
            assert "function DisclosureConfirmDialog" not in src, parts

    def test_the_screen_still_never_asks_what_role_is_looking(self):
        """The rule the shared screen has always held. Adding three buttons is
        exactly the change that would break it."""
        src = read("components", "application", "ApplicationDetail.jsx")
        body = src[src.index("export default function") :]
        for smell in ('role === "admin"', "isAdmin", "user?.role ===", "role !== "):
            assert smell not in body, smell

    def test_accepting_a_partial_lands_on_content_approved(self):
        async def body(db):
            brand_oid, creator_oid = ObjectId(), ObjectId()
            campaign_oid, collab_oid = ObjectId(), ObjectId()
            await db.brand_profiles.insert_one(
                {"user_id": brand_oid, "business_name": "X", "verified": True,
                 "verified_at": _now()}
            )
            await db.campaigns.insert_one(
                {"_id": campaign_oid, "brand_id": brand_oid, "title": "Spring",
                 "status": "in_progress", "execution_owner": "brand",
                 "compensation_type": "negotiated", "budget_per_creator": 9000,
                 "deliverable_items": [{"type": "story", "quantity": 3}]}
            )
            await db.collaborations.insert_one(
                {"_id": collab_oid, "campaign_id": campaign_oid, "creator_id": creator_oid,
                 "state": "content_submitted", "state_since": _now(), "agreed_at": _now(),
                 "agreed_amount": 9000}
            )
            out = await server.accept_partial_delivery(
                str(collab_oid),
                server.PartialDeliveryPayload(
                    # `negotiated`, because on a `fixed` brief the resolver
                    # locks the fee to the brief's own number — that rule is
                    # `test_money_paths.py`'s and is not what this is about.
                    delivered={"story": 2}, agreed_amount=6000,
                    note="Two went up, the third clashed with their own launch.",
                ),
                ADMIN,
            )
            return out, await db.collaborations.find_one({"_id": collab_oid})

        out, row = run(body)
        assert row["state"] == "content_approved"
        assert row["partial_delivery"] is True
        assert row["delivered_items"] == {"story": 2}
        assert out["shortfall"]["delivered_total"] == 2


class TestUnderfillNamesAWayOut:
    def test_the_actions_point_at_something_the_page_can_open(self):
        """**All three used to be decoration.** They carried `?panel=suggested`
        and `?edit=dates` against a page that read neither query string, so
        every "way out" landed on the same screen doing nothing — worse than
        offering none, because somebody clicks and concludes the tool is
        broken."""
        source = inspect.getsource(server.admin_health)
        block = source[source.index('"label": "Invite creators"') : source.index('"key": "underfilling"')]
        assert "?action=invite" in block
        assert "?action=edit" in block
        assert "panel=suggested" not in block

        page = read("components", "admin", "CampaignDetailPage.jsx")
        assert 'params.get("action")' in page
        assert 'setDialog({ kind: action })' in page

    def test_the_param_is_consumed_rather_than_kept(self):
        """Leaving it in the URL reopens the dialog on every reload, and a back
        button that re-opens a form is a back button that lies."""
        page = read("components", "admin", "CampaignDetailPage.jsx")
        block = page[page.index('params.get("action")') : page.index('const loadDetail')]
        assert 'next.delete("action")' in block
        assert "{ replace: true }" in block

    def test_the_edit_dialog_can_actually_change_the_dates(self):
        """"Extend the dates" had nowhere to land: the console's only campaign
        edit form carried a title, a fee, a headcount and the deliverables, and
        no date field anywhere."""
        src = read("components", "admin", "dialogs.jsx")
        # The identifier alone is not the assertion — it appears in the effect
        # that seeds the form too, so a break that empties the rendered list
        # leaves it in place. What has to be true is that a field is *drawn*
        # per date this campaign type carries, and that what leaves the form is
        # an instant rather than a naive local string.
        block = src[src.index("{schedulingDateFields(campaign).map(") :][:1600]
        assert 'type="datetime-local"' in block
        assert "ADMIN_CAMPAIGN_EDIT.date(field)" in block
        assert "fromLocalInput" in src

    def test_the_date_fields_follow_the_campaign_type(self):
        """The server refuses a field foreign to the type outright, so a form
        offering all three would produce a 422 the person filling it in could
        do nothing about."""
        mirror = read("lib", "schedulingShape.js")
        for kind, spec in server._SCHEDULING_BY_TYPE.items():
            dates = [f for f in spec["allowed"] if f.endswith("_date")]
            block = mirror[mirror.index(f"{kind}:") : mirror.index(f"{kind}:") + 200]
            for field in dates:
                assert field in block, (kind, field)

    def test_an_unknown_type_gets_every_date_rather_than_none(self):
        """Campaigns predate types, and returning nothing would make every
        historical brief un-editable on the screen support uses to fix one."""
        mirror = read("lib", "schedulingShape.js")
        tail = mirror[mirror.index("export function schedulingDateFields") :]
        assert "'event_date', 'start_date', 'end_date'" in tail

    def test_the_datetime_helpers_read_and_write_in_ist(self):
        """A `datetime-local` has no zone, so whatever string goes in is read
        back as the reader's own clock — an admin editing from anywhere but
        India would otherwise move the brief by five and a half hours."""
        src = read("lib", "time.js")
        block = src[src.index("export function localInputValue") :]
        assert "dayKey(value)" in block and "timeKey(value)" in block
        assert "+05:30" in block

    def test_the_row_still_carries_the_numbers_beside_the_actions(self):
        """A panel that says "underfilling" and makes you open the campaign to
        find out by how much costs a click per row to read."""
        source = inspect.getsource(server.admin_health)
        assert '"days_left": days_left' in source
        assert '"slots_short": max(0, needed - got)' in source


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _Upload:
    """The slice of `UploadFile` `_store_private_upload` actually touches."""

    def __init__(self, data: bytes, filename: str):
        self._data = data
        self._read = False
        self.filename = filename

    async def read(self, n=-1):
        if self._read:
            return b""
        self._read = True
        return self._data

    async def close(self):
        return None


def _png_upload():
    return _Upload(b"\x89PNG\r\n\x1a\n" + b"0" * 64, "IMG_2201.png")


def _pdf_upload():
    return _Upload(b"%PDF-1.7\n" + b"0" * 64, "story.png")


def _guard_roles(fn):
    """The roles a route's real `require_roles` dependency allows.

    Calling a route function directly skips FastAPI's dependency injection, so
    reading the guard off the signature is the only way to assert on what it
    actually permits — the same instrument `test_money_paths.py` uses.
    """
    import inspect as _inspect

    found = set()
    for param in _inspect.signature(fn).parameters.values():
        dep = getattr(param.default, "dependency", None)
        if dep is None:
            continue
        closure = getattr(dep, "__closure__", None) or ()
        for cell in closure:
            value = cell.cell_contents
            if isinstance(value, tuple) and all(isinstance(v, str) for v in value):
                found.update(value)
    return found
