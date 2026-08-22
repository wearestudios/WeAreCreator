"""The draft gate: the reviewer sees the work before the audience does.

Until this stage existed, `content_submitted` carried a link to something
already live — so a brand's first sight of the content was after the creator's
followers had had theirs, and "can we change the caption" was a request to
delete a post.

Four rules hold it up.

**Optional per campaign, and absent reads off.** `_requires_draft_approval`
returns False for a campaign with no such field, which is every campaign
written before today. There is no backfill, deliberately: that is the migration
guarantee — anything already past `attended` keeps the exact path it started
on, because the two new states are simply not on its ladder.

**Two ways in, because one of them fails on the phone this runs on.** A
finished reel is often several hundred megabytes; a creator on mobile data
would publish it rather than watch a bar crawl. So an unlisted link is a
first-class option, and both routes go through one `_record_draft` so a file
draft and a link draft cannot diverge in state, audit or notification.

**Private storage.** An unpublished draft is the one thing on this platform
that must not be a guessed URL away from the internet: it lands in
`PRIVATE_UPLOAD_DIR`, never the mounted one, and the only way out is an
audited download.

**The reviewer follows execution_owner**, exactly like the question threads —
same reader, not a second copy.

Most of this runs the real handlers against an in-memory Mongo, for the reason
the export leak tests do: reading the source catches the mistake somebody makes
on purpose, running it catches the one nobody remembered was possible.
"""
import asyncio
import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"


def source(fn):
    return inspect.getsource(fn)


def read(*parts):
    return FRONTEND.joinpath(*parts).read_text()


def _status(coro):
    try:
        asyncio.run(coro)
        return 200
    except HTTPException as e:
        return e.status_code


def _world():
    """One brand with two campaigns — brand-run with draft review on, and
    weare-run with it on — plus one that doesn't review drafts at all. A
    creator standing on `attended` in each."""
    server.db = AsyncMongoMockClient()["t"]
    now = datetime.now(timezone.utc)
    w = {"now": now}

    async def build():
        w["brand_uid"] = ObjectId()
        w["manager_uid"] = ObjectId()
        w["rival_uid"] = ObjectId()
        w["creator_uid"] = ObjectId()
        await server.db.users.insert_many([
            {"_id": w["brand_uid"], "role": "brand_manager", "name": "Priya",
             "phone": "+919800000001"},
            {"_id": w["manager_uid"], "role": "campaign_manager", "name": "Rohan"},
            {"_id": w["rival_uid"], "role": "brand_manager", "name": "Rival"},
            {"_id": w["creator_uid"], "role": "creator", "name": "Asha"},
        ])
        await server.db.brand_profiles.insert_one(
            {"user_id": w["brand_uid"], "business_name": "Blue Tokai", "verified": True}
        )
        base = {
            "brand_id": w["brand_uid"], "status": "in_progress", "title": "Brunch launch",
            "budget_per_creator": 8000, "compensation_type": "fixed",
            "category": "fnb", "area": "Indiranagar", "creators_needed": 3,
            "created_at": now, "event_date": now + timedelta(days=2),
        }
        w["reviewed"] = (await server.db.campaigns.insert_one(
            {**base, "execution_owner": "brand", "manager_id": w["brand_uid"],
             "requires_draft_approval": True}
        )).inserted_id
        w["weare"] = (await server.db.campaigns.insert_one(
            {**base, "title": "Roastery tour", "execution_owner": "weare",
             "manager_id": w["manager_uid"], "requires_draft_approval": True}
        )).inserted_id
        # No `requires_draft_approval` key at all — the shape of every
        # campaign that predates the field.
        w["legacy"] = (await server.db.campaigns.insert_one(
            {**base, "title": "Old brief", "execution_owner": "brand",
             "manager_id": w["brand_uid"]}
        )).inserted_id

        for key, camp in (("collab", "reviewed"), ("weare_collab", "weare"),
                          ("legacy_collab", "legacy")):
            w[key] = (await server.db.collaborations.insert_one({
                "campaign_id": w[camp], "creator_id": w["creator_uid"],
                "state": "attended", "created_at": now, "updated_at": now,
                "agreed_amount": 8000,
            })).inserted_id

    asyncio.run(build())
    w["creator"] = {"_id": str(w["creator_uid"]), "role": "creator", "name": "Asha"}
    w["brand"] = {"_id": str(w["brand_uid"]), "role": "brand_manager", "brand_id": None}
    w["rival"] = {"_id": str(w["rival_uid"]), "role": "brand_manager", "brand_id": None}
    w["manager"] = {"_id": str(w["manager_uid"]), "role": "campaign_manager"}
    w["admin"] = {"_id": str(ObjectId()), "role": "admin", "name": "Admin"}
    return w


def _link(w, collab, user=None, url="https://youtu.be/unlisted", note=None):
    return server.submit_draft_link(
        str(collab),
        server.DraftLinkPayload(draft_url=url, note=note),
        user or w["creator"],
    )


# --- Migration: absent means off ---------------------------------------------


def test_a_campaign_with_no_field_does_not_review_drafts():
    """The whole migration story in one assertion. There is no backfill."""
    assert server._requires_draft_approval({}) is False
    assert server._requires_draft_approval(None) is False
    assert server._requires_draft_approval({"requires_draft_approval": False}) is False
    assert server._requires_draft_approval({"requires_draft_approval": True}) is True


def test_there_is_no_backfill_for_this_field():
    """`showcase`, `execution_owner` and `compensation_type` all backfill at
    startup. This one deliberately doesn't: a backfill would turn the stage on
    under collaborations already past `attended`, which is exactly what the
    brief said must not happen."""
    src = source(server.run_startup_migrations) if hasattr(
        server, "run_startup_migrations"
    ) else ""
    for fn_name in dir(server):
        if not fn_name.startswith("_migrate") and "backfill" not in fn_name:
            continue
        fn = getattr(server, fn_name)
        if inspect.isfunction(fn):
            src += source(fn)
    assert "requires_draft_approval" not in src


def test_an_in_flight_collaboration_keeps_its_ladder():
    """A campaign written before the field: the two new states never appear
    on its bar, so nothing standing on `attended` acquires a step."""
    w = _world()
    campaign = asyncio.run(server.db.campaigns.find_one({"_id": w["legacy"]}))
    bar = server._lifecycle_for({"state": "attended"}, campaign)

    assert not any(s["state"] in server.DRAFT_REVIEW_STATES for s in bar["steps"])
    assert server._next_collab_state("attended", campaign) == "content_submitted"


def test_a_reviewing_campaign_puts_the_draft_between_attended_and_content():
    ladder = server._collab_ladder({"requires_draft_approval": True})
    assert ladder[ladder.index("attended") + 1] == "draft_submitted"
    assert ladder[ladder.index("draft_submitted") + 1] == "draft_approved"
    assert ladder[ladder.index("draft_approved") + 1] == "content_submitted"


# --- Submitting ---------------------------------------------------------------


def test_a_link_draft_moves_the_collaboration_and_records_the_url():
    w = _world()
    out = asyncio.run(_link(w, w["collab"]))

    assert out["state"] == "draft_submitted"
    assert out["kind"] == "link"
    assert out["draft_url"] == "https://youtu.be/unlisted"
    assert out["has_file"] is False


def test_a_draft_cannot_be_sent_on_a_campaign_that_does_not_review_them():
    """409 with the alternative named, not a silent state nobody can leave."""
    w = _world()
    assert _status(_link(w, w["legacy_collab"])) == 409


def test_a_draft_cannot_be_sent_before_the_shoot():
    w = _world()
    asyncio.run(server.db.collaborations.update_one(
        {"_id": w["collab"]}, {"$set": {"state": "slot_booked"}}
    ))
    assert _status(_link(w, w["collab"])) == 409


def test_a_creator_cannot_send_a_draft_on_somebody_else_s_collaboration():
    w = _world()
    other = {"_id": str(ObjectId()), "role": "creator"}
    assert _status(_link(w, w["collab"], other)) == 404


def test_a_draft_can_be_replaced_while_it_waits():
    """Right up until it is approved: a creator noticing a mistake in their
    own cut should not have to ask somebody to reject it first."""
    w = _world()
    asyncio.run(_link(w, w["collab"]))
    out = asyncio.run(_link(w, w["collab"], url="https://youtu.be/better"))

    assert out["draft_url"] == "https://youtu.be/better"
    assert out["state"] == "draft_submitted"


def test_a_draft_link_must_be_a_link():
    w = _world()
    assert _status(_link(w, w["collab"], url="ask me on whatsapp")) == 422


def test_both_submit_routes_go_through_one_recorder():
    """A file draft and a link draft must not diverge in what they do to the
    state, the audit line or the notification."""
    for fn in (server.submit_draft_file, server.submit_draft_link):
        assert "_record_draft(" in source(fn)


# --- Reviewing ----------------------------------------------------------------


def test_the_brand_approves_its_own_brand_run_draft():
    w = _world()
    asyncio.run(_link(w, w["collab"]))
    out = asyncio.run(server.approve_draft(str(w["collab"]), w["brand"]))

    assert out["state"] == "draft_approved"
    assert out["approved_at"]


def test_the_brand_never_reviews_a_weare_run_draft():
    """Handing a campaign to WeAre hands the review with it — and the refusal
    is a 404, so the brand is not told there is a draft to be curious about."""
    w = _world()
    asyncio.run(_link(w, w["weare_collab"]))

    assert _status(server.approve_draft(str(w["weare_collab"]), w["brand"])) == 404
    assert _status(server.read_draft(str(w["weare_collab"]), w["brand"])) == 404
    assert asyncio.run(
        server.approve_draft(str(w["weare_collab"]), w["manager"])
    )["state"] == "draft_approved"


def test_another_brand_gets_a_404_not_a_403():
    w = _world()
    asyncio.run(_link(w, w["collab"]))
    assert _status(server.approve_draft(str(w["collab"]), w["rival"])) == 404


def test_an_admin_reviews_either_kind():
    w = _world()
    asyncio.run(_link(w, w["weare_collab"]))
    assert asyncio.run(
        server.approve_draft(str(w["weare_collab"]), w["admin"])
    )["state"] == "draft_approved"


def test_the_reviewer_rule_is_the_question_thread_s_rule():
    """One reader, not two copies that drift apart."""
    assert "_question_staff_may_see(" in source(server._draft_reviewable_or_404)


def test_approving_nothing_is_refused():
    """There is no draft on this collaboration, so there is nothing to say
    yes to — and inventing `draft_approved` would let the creator skip the
    stage entirely."""
    w = _world()
    assert _status(server.approve_draft(str(w["collab"]), w["brand"])) == 409


# --- Requesting changes -------------------------------------------------------


def _changes(w, collab, user=None, note="Trim the intro"):
    return server.request_draft_changes(
        str(collab), server.DraftDecisionPayload(note=note), user or w["brand"]
    )


def test_requesting_changes_returns_it_to_the_creator_with_the_note():
    w = _world()
    asyncio.run(_link(w, w["collab"]))
    out = asyncio.run(_changes(w, w["collab"]))

    assert out["state"] == "attended"
    assert out["revision_note"] == "Trim the intro"


def test_the_revision_count_climbs_with_each_round():
    """Two revisions is a conversation; five is a brief that was never clear,
    and only a counter shows the difference."""
    w = _world()
    for _ in range(3):
        asyncio.run(_link(w, w["collab"]))
        out = asyncio.run(_changes(w, w["collab"]))

    assert out["revision_count"] == 3


def test_a_send_back_needs_a_reason():
    """A round trip with no note is a round trip wasted."""
    w = _world()
    asyncio.run(_link(w, w["collab"]))
    assert _status(_changes(w, w["collab"], note="   ")) == 422
    assert _status(_changes(w, w["collab"], note=None)) == 422


def test_a_new_draft_clears_the_outstanding_request():
    w = _world()
    asyncio.run(_link(w, w["collab"]))
    asyncio.run(_changes(w, w["collab"]))
    out = asyncio.run(_link(w, w["collab"], url="https://youtu.be/v2"))

    assert out["revision_note"] is None
    assert out["revision_count"] == 1, "the count survives — it is the history"


# --- The gate actually gates --------------------------------------------------


def _submit_content(w, collab, user=None):
    return server.submit_collab_content(
        str(collab),
        server.SubmitContentPayload(content_urls=["https://instagram.com/p/live"]),
        user or w["creator"],
    )


def test_a_live_link_is_refused_before_the_draft_is_approved():
    """The whole point. Accepting a published link straight from `attended`
    would be the route around the stage."""
    w = _world()
    assert _status(_submit_content(w, w["collab"])) == 400

    asyncio.run(_link(w, w["collab"]))
    assert _status(_submit_content(w, w["collab"])) == 400, "not while it waits either"


def test_a_live_link_is_accepted_once_the_draft_is_approved():
    w = _world()
    asyncio.run(_link(w, w["collab"]))
    asyncio.run(server.approve_draft(str(w["collab"]), w["brand"]))
    out = asyncio.run(_submit_content(w, w["collab"]))

    assert out["state"] == "content_submitted"


def test_a_campaign_without_the_stage_behaves_exactly_as_before():
    w = _world()
    out = asyncio.run(_submit_content(w, w["legacy_collab"]))

    assert out["state"] == "content_submitted"


def test_the_admin_console_cannot_fabricate_either_draft_step():
    """A draft has to actually arrive and actually be looked at. Neither is a
    box to tick from the console — the same shape as the two the brand owns."""
    assert server._DRAFT_OWNED_TRANSITIONS == set(server.DRAFT_REVIEW_STATES)
    src = source(server.advance_collaboration)
    assert "_DRAFT_OWNED_TRANSITIONS" in src

    w = _world()
    assert _status(server.advance_collaboration(
        str(w["collab"]), server.AdvanceCollabPayload(from_state="attended"), w["admin"]
    )) == 409


# --- Privacy ------------------------------------------------------------------


def test_the_draft_file_lands_in_private_storage():
    """An unpublished cut must not be one guessed URL away from the internet.
    PRIVATE_UPLOAD_DIR is deliberately not the directory `app.mount`s."""
    assert "PRIVATE_UPLOAD_DIR" in source(server._store_private_upload)
    assert "_store_private_upload(" in source(server.submit_draft_file)
    assert "UPLOAD_DIR" not in source(server.submit_draft_file)


def test_no_payload_ever_carries_the_stored_path():
    """The bytes come out of the audited download route or not at all."""
    w = _world()
    asyncio.run(server.db.collaborations.update_one(
        {"_id": w["collab"]},
        {"$set": {"state": "draft_submitted", "draft": {
            "kind": "file", "stored_name": "draft-secret-name.mp4",
            "original_name": "final cut.mp4", "mime": "video/mp4", "size": 42,
            "submitted_at": w["now"],
        }}},
    ))
    payload = asyncio.run(server.read_draft(str(w["collab"]), w["brand"]))

    assert "secret-name" not in str(payload)
    assert "stored_name" not in payload
    assert payload["has_file"] is True
    assert payload["original_name"] == "final cut.mp4"


def test_reading_the_file_is_audited():
    assert "audit(" in source(server.download_draft_file)
    assert "no-store" in source(server.download_draft_file)


def test_every_draft_route_writes_an_audit_line():
    for fn in (server._record_draft, server.approve_draft, server.request_draft_changes):
        assert "await audit(" in source(fn)
        assert "_campaign_audit_context(" in source(fn)


# --- Notifications ------------------------------------------------------------


def test_the_three_events_are_declared_and_documented():
    """A notification with no NOTIFY_EVENTS entry is one that never sends;
    tests/unit/test_environment.py holds the .env.example half."""
    for event in ("draft_submitted", "draft_approved", "draft_changes_requested"):
        assert event in server.NOTIFY_EVENTS


def test_a_draft_routes_to_whoever_runs_the_campaign():
    """Exactly like a new application: weare-run to the WeAre side, brand-run
    to the brand's own manager."""
    src = source(server._record_draft)
    assert "_weare_runs(campaign)" in src
    assert "notify_weare_team(" in src
    assert "notify_brand_manager(" in src


def test_the_creator_is_told_both_outcomes():
    assert 'collab["creator_id"]' in source(server.approve_draft)
    assert 'collab["creator_id"]' in source(server.request_draft_changes)
    # The note is the message — a send-back saying only "changes requested"
    # sends the creator back to the app to find out what.
    assert "note" in source(server.request_draft_changes).split("await notify(")[1]


# --- What the screens are given -----------------------------------------------


def test_the_application_screen_gets_the_draft_only_where_there_is_one():
    src = source(server.get_application)
    assert "_requires_draft_approval(campaign) else None" in src
    assert "can_review_draft" in src


def test_the_creator_is_asked_for_a_draft_rather_than_a_live_link():
    reviewed = server._creator_next_action(
        {"state": "attended"}, {"requires_draft_approval": True}, True
    )
    plain = server._creator_next_action({"state": "attended"}, {}, True)

    assert reviewed["action"] == "submit_draft"
    assert plain["action"] == "submit_content"


def test_the_outstanding_note_is_what_the_card_says():
    action = server._creator_next_action(
        {"state": "attended", "draft_revision_note": "Trim the intro"},
        {"requires_draft_approval": True},
        True,
    )
    assert "Trim the intro" in action["label"]


def test_the_creator_is_told_the_wait_is_not_theirs():
    action = server._creator_next_action(
        {"state": "draft_submitted"}, {"requires_draft_approval": True}, True
    )
    assert action["waiting_on"] == "brand"


def test_an_approved_draft_puts_the_ball_back_with_the_creator():
    action = server._creator_next_action(
        {"state": "draft_approved"}, {"requires_draft_approval": True}, True
    )
    assert action["action"] == "submit_content"
    assert action["waiting_on"] == "you"


def test_both_new_states_are_in_the_next_action_table():
    for state in server.DRAFT_REVIEW_STATES:
        owner, label, detail = server._NEXT_ACTION[state]
        assert owner and label and detail


def test_a_draft_is_not_a_delivery_a_report_can_describe():
    """Performance is measured on published content. A draft has no reach."""
    for state in server.DRAFT_REVIEW_STATES:
        assert state not in server.DELIVERED_COLLAB_STATES
        assert state in server.COLLAB_GROUP_ONGOING


def test_the_submit_button_agrees_with_what_the_api_will_accept():
    """`can_submit_content` on the creator's row and the state check in
    `submit_collab_content` are two statements of one rule; a disagreement is
    a button that produces a 400."""
    reviewed = {"requires_draft_approval": True}
    row = server._serialize_collab_row
    base = {"_id": ObjectId(), "campaign_id": ObjectId()}

    assert row({**base, "state": "attended"}, {}, None)["can_submit_content"] is True
    assert row({**base, "state": "attended"}, reviewed, None)["can_submit_content"] is False
    assert row({**base, "state": "draft_approved"}, reviewed, None)["can_submit_content"] is True
    assert row({**base, "state": "content_submitted"}, reviewed, None)["can_submit_content"] is True


def test_a_draft_nobody_has_looked_at_reaches_the_health_panel():
    """The one stage where the delay is ours: the creator has done the work
    and is blocked from publishing, and no notification fires twice."""
    src = source(server.admin_health)
    assert '"key": "draft_review_overdue"' in src
    assert "DRAFT_REVIEW_OVERDUE_DAYS" in src
    assert server.DRAFT_REVIEW_OVERDUE_DAYS < server.CONTENT_OVERDUE_DAYS


def test_an_approved_draft_still_counts_as_content_overdue():
    """Said yes, still not out — the same operational problem as never
    having sent anything."""
    src = source(server.admin_health)
    # The `state` clause of that one query, not the block around it: the
    # comment above it says "draft_approved" too, and asserting on prose is
    # how a check passes after the code stops doing what it says.
    block = src[src.index("# 3. Turned up") : src.index('"key": "content_overdue"')]
    clause = block[block.index('"state"') : block.index('"updated_at"')]
    assert "draft_approved" in clause


def test_the_door_roster_counts_a_draft_as_having_turned_up():
    """A creator who attended and sent a cut must not read back as still
    expected on the manager's list."""
    src = source(server._roster_rows)
    assert '"attendance"' in src, "the rollup moved — repoint this test"
    block = src[src.index('"attendance"') :]
    assert "draft_submitted" in block and "draft_approved" in block


# --- The bytes ----------------------------------------------------------------


@pytest.mark.parametrize(
    "head,expected",
    [
        (b"\x00\x00\x00\x20ftypisom", "video/mp4"),
        (b"\x00\x00\x00\x14ftypqt  ", "video/quicktime"),
        (b"\x1a\x45\xdf\xa3", "video/webm"),
        (b"\xff\xd8\xff\xe0", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\n", "image/png"),
    ],
)
def test_the_draft_sniffer_reads_the_leading_bytes(head, expected):
    assert server.sniff_draft_type(head)[0] == expected


@pytest.mark.parametrize("head", [b"%PDF-1.7", b"MZ\x90\x00", b"<html>", b""])
def test_anything_that_is_not_a_video_or_a_still_is_refused(head):
    """A PDF is a valid brand document and not a draft — the two sniffers are
    separate on purpose."""
    assert server.sniff_draft_type(head) is None


def test_the_accepted_types_come_from_the_signature_table():
    """So the browser's `accept=` cannot offer a format the sniffer rejects —
    the same rule ACCEPTED_DOCUMENT_MIMES and ACCEPTED_IMAGE_MIMES follow."""
    assert "video/mp4" in server.ACCEPTED_DRAFT_MIMES
    assert "application/pdf" not in server.ACCEPTED_DRAFT_MIMES


# --- The frontend half --------------------------------------------------------


def test_the_draft_review_stage_is_the_servers_answer_now():
    """The creator's bar used to grow a seventh stage locally when a draft
    existed. The eight-stage process flow makes that a server decision — the
    same "Content review" box on every campaign, meaning the draft where there
    is a gate and the live link where there is not — so there is nothing left
    on the client to get wrong."""
    assert server._stage_of("draft_submitted", {"requires_draft_approval": True}) == (
        "content_review"
    )
    assert server._stage_of("content_submitted", {}) == "content_review"

    src = read("components", "creator", "shared.jsx")
    assert "lifecycleFor" not in src.replace("`lifecycleFor`", "")


def test_the_creator_can_send_either_a_file_or_a_link():
    src = read("components", "creator", "SubmitDraftDialog.jsx")
    assert "/file" in src and "/link" in src
    # The browser sets the multipart boundary; the client's JSON default
    # would make the upload unparseable.
    assert '"Content-Type": undefined' in src


def test_the_review_panel_never_asks_what_role_is_looking():
    """Same rule as the rest of the application screen: every action arrives
    decided, so neither console offers a button the API will refuse."""
    src = read("components", "application", "DraftReview.jsx")
    for tell in ('role === "admin"', 'role === "brand"', "isAdmin", "user.role"):
        assert tell not in src
    assert "canReview" in src


def test_the_send_back_button_needs_its_note():
    src = read("components", "application", "DraftReview.jsx")
    assert "!note.trim()" in src


def test_the_post_form_offers_the_toggle_and_re_seeds_it_on_edit():
    src = read("pages", "PostCampaign.jsx")
    assert "requires_draft_approval: requiresDraft" in src
    assert "setRequiresDraft(Boolean(data.requires_draft_approval))" in src


def test_the_process_flow_has_a_place_for_a_draft():
    """The bar that named `draft_submitted` and `draft_approved` directly is
    gone. Both are the "Content review" stage now — a name a creator can read,
    decided on the server so no screen has to know the two states exist."""
    for state in ("draft_submitted", "draft_approved"):
        assert server._stage_of(state, {"requires_draft_approval": True}) == (
            "content_review"
        )
