"""The five newer overrides: mark received, and the brand's four steps.

`test_on_behalf_overrides.py` holds the first two (booking a slot, confirming
an address). These follow the same pattern exactly, and this file drives each
one against the real handlers and reads the database back:

- **admin only** — the real `require_roles` guard is pulled off the signature
  and run, so a guard listing `weare_team` fails here rather than in review;
- **a reason the affected party reads**, refused when blank;
- **the dispute freeze**, refused with the row unmoved;
- **the record** (who, when, why) on the row and an **audit line of its own**
  with the state before and after;
- **the same move as the owner's route** — each override is driven beside the
  owner's own route on an identical world, and the two rows compared;
- and the one rule only mark-received has: **evidence or nothing**.
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import timedelta

import pytest
from bson import ObjectId
from fastapi import HTTPException, params

import server
import test_lifecycle_harness as harness

ADMIN = harness.ADMIN
REASON = "The brand asked us on the call to take this step for them."


def guard_allows(fn, role):
    """Would FastAPI let this role through? The real `_guard`, not a grep."""
    guard = None
    for p in inspect.signature(fn).parameters.values():
        dep = p.default
        if isinstance(dep, params.Depends) and getattr(dep.dependency, "__name__", "") == "_guard":
            guard = dep.dependency
    assert guard is not None, f"{fn.__name__} declares no require_roles guard"

    async def go():
        try:
            await guard({"_id": str(ObjectId()), "role": role})
            return True
        except HTTPException as err:
            assert err.status_code == 403
            return False

    return asyncio.new_event_loop().run_until_complete(go())


class _Upload:
    """The slice of `UploadFile` `_store_private_upload` touches."""

    def __init__(self, data: bytes, filename: str):
        self._data, self._read, self.filename = data, False, filename

    async def read(self, n=-1):
        if self._read:
            return b""
        self._read = True
        return self._data

    async def close(self):
        return None


def _png():
    return _Upload(b"\x89PNG\r\n\x1a\n" + b"0" * 64, "doorstep.png")


@pytest.fixture(autouse=True)
def _private_dir(tmp_path):
    original = server.PRIVATE_UPLOAD_DIR
    server.PRIVATE_UPLOAD_DIR = tmp_path / "private"
    yield
    server.PRIVATE_UPLOAD_DIR = original


# --- the acts, each as (owner's call, override's call, the state it stands on)

ACTS = {
    "mark_received": dict(
        ladder="delivery", at="dispatched", to="received",
        override=lambda w, reason="x" * 0 or REASON: server.mark_received_on_behalf(
            w["collab_id"], reason=reason, tracking_url="https://track.example/DTDC-77",
            file=None, user=ADMIN,
        ),
        owner=lambda w: server.creator_confirm_delivery_received(
            w["collab_id"], server.ConfirmDeliveryReceivedPayload(), w["creator"]
        ),
        record=lambda c: (c.get("delivery") or {}).get("received_on_behalf"),
        audit="collaboration.delivery_received_on_behalf",
        told="received_for_you",
    ),
    "accept": dict(
        ladder="venue", at="verified", to="accepted",
        override=lambda w, reason=REASON: server.accept_applicant_on_behalf(
            w["collab_id"], server.AcceptOnBehalfPayload(reason=reason), ADMIN
        ),
        owner=lambda w: server.brand_accept_applicant(
            w["collab_id"], server.BrandAcceptPayload(), w["brand"]
        ),
        record=lambda c: c.get("accepted_on_behalf"),
        audit="collaboration.accept_on_behalf",
        told="brand_step_taken_for_you",
    ),
    "approve_draft": dict(
        ladder="venue+draft", at="draft_submitted", to="draft_approved",
        override=lambda w, reason=REASON: server.approve_draft_on_behalf(
            w["collab_id"],
            server.ReviewOnBehalfPayload(reason=reason, disclosure_confirmed=True),
            ADMIN,
        ),
        owner=lambda w: server.approve_draft(
            w["collab_id"], server.DisclosureCheckPayload(disclosure_confirmed=True), w["brand"]
        ),
        record=lambda c: c.get("draft_approved_on_behalf"),
        audit="collaboration.approve_draft_on_behalf",
        told="brand_step_taken_for_you",
    ),
    "request_draft_changes": dict(
        ladder="venue+draft", at="draft_submitted", to="attended",
        override=lambda w, reason=REASON: server.request_draft_changes_on_behalf(
            w["collab_id"],
            server.ChangesOnBehalfPayload(reason=reason, note="Tag the venue in the first frame."),
            ADMIN,
        ),
        owner=lambda w: server.request_draft_changes(
            w["collab_id"],
            server.DraftDecisionPayload(note="Tag the venue in the first frame."),
            w["brand"],
        ),
        record=lambda c: c.get("draft_changes_requested_on_behalf"),
        audit="collaboration.request_draft_changes_on_behalf",
        told="brand_step_taken_for_you",
    ),
    "approve_content": dict(
        ladder="venue", at="content_submitted", to="content_approved",
        override=lambda w, reason=REASON: server.approve_content_on_behalf(
            w["collab_id"],
            server.ReviewOnBehalfPayload(reason=reason, disclosure_confirmed=True),
            ADMIN,
        ),
        owner=lambda w: server.brand_approve_content(
            w["collab_id"], server.DisclosureCheckPayload(disclosure_confirmed=True), w["brand"]
        ),
        record=lambda c: c.get("content_approved_on_behalf"),
        audit="collaboration.approve_content_on_behalf",
        told="brand_step_taken_for_you",
    ),
}

ROUTES = {
    "mark_received": server.mark_received_on_behalf,
    "accept": server.accept_applicant_on_behalf,
    "approve_draft": server.approve_draft_on_behalf,
    "request_draft_changes": server.request_draft_changes_on_behalf,
    "approve_content": server.approve_content_on_behalf,
}


async def _standing(db, act, money="paid", **campaign_set):
    spec = ACTS[act]
    w = await harness._world(db, ladder=spec["ladder"], money=money)
    if campaign_set:
        await db.campaigns.update_one({"_id": w["campaign_oid"]}, {"$set": campaign_set})
    await harness._walk_to(db, w, spec["at"], spec["ladder"], money)
    return w


def _compared(row):
    """What the owner's route and the override must agree on."""
    delivery = row.get("delivery") or {}
    return {
        "state": row["state"],
        "agreed_amount": row.get("agreed_amount"),
        "agreed": row.get("agreed_at") is not None,
        "terms": bool(row.get("terms")),
        "draft_revision_count": row.get("draft_revision_count"),
        "draft_revision_note": row.get("draft_revision_note"),
        "draft_disclosure_check": bool(row.get("draft_disclosure_check")),
        "content_approved_at": row.get("content_approved_at") is not None,
        "content_disclosure_check": bool(row.get("content_disclosure_check")),
        "received_at": delivery.get("received_at") is not None,
    }


# ---------------------------------------------------------------------------


@pytest.mark.parametrize("act", list(ROUTES))
def test_only_an_admin_may_take_it(act):
    fn = ROUTES[act]
    assert guard_allows(fn, "admin")
    for role in ("weare_team", "campaign_manager", "brand_manager", "brand", "creator"):
        assert not guard_allows(fn, role), f"{act} lets {role} through"


@pytest.mark.parametrize("act", list(ROUTES))
def test_it_moves_the_row_exactly_as_the_owner_does(act):
    spec = ACTS[act]

    async def body(db):
        mine = await _standing(db, act)
        await spec["owner"](mine)
        theirs = await _standing(db, act)
        await spec["override"](theirs)
        return (
            await db.collaborations.find_one({"_id": mine["collab_oid"]}),
            await db.collaborations.find_one({"_id": theirs["collab_oid"]}),
        )

    owner_row, override_row = harness.run(body)
    assert owner_row["state"] == spec["to"]
    assert _compared(override_row) == _compared(owner_row)


@pytest.mark.parametrize("act", list(ROUTES))
def test_it_writes_the_record_the_audit_line_and_tells_somebody(act):
    spec = ACTS[act]

    async def body(db):
        w = await _standing(db, act)
        await spec["override"](w)
        row = await db.collaborations.find_one({"_id": w["collab_oid"]})
        line = await db.audit_log.find_one({"action": spec["audit"]})
        told = await db.notifications.find_one({"event": spec["told"]})
        return w, row, line, told

    w, row, line, told = harness.run(body)
    record = spec["record"](row)
    assert record["reason"] == REASON
    assert record["by_name"] == ADMIN["name"]
    assert record["at"] is not None
    assert line is not None, f"no {spec['audit']} line"
    assert line["before"]["state"] == spec["at"]
    assert line["after"]["state"] == spec["to"]
    assert line["after"]["on_behalf"] is True
    assert told is not None
    # The affected party: the creator for their own step, the brand for its.
    assert told["user_id"] == (w["creator_oid"] if act == "mark_received" else w["brand_oid"])
    # And it renders as an override, through the one reader every surface uses.
    block = server._on_behalf_block(row)
    step = {"mark_received": "received", "accept": "accepted",
            "approve_draft": "draft_approved",
            "request_draft_changes": "draft_changes_requested",
            "approve_content": "content_approved"}[act]
    assert block[step]["reason"] == REASON


@pytest.mark.parametrize("act", list(ROUTES))
def test_a_blank_reason_is_refused_and_nothing_moves(act):
    spec = ACTS[act]

    async def body(db):
        w = await _standing(db, act)
        with pytest.raises(HTTPException) as err:
            await spec["override"](w, reason="   ")
        return err.value, await db.collaborations.find_one({"_id": w["collab_oid"]})

    exc, row = harness.run(body)
    assert exc.status_code == 422
    assert row["state"] == spec["at"]


@pytest.mark.parametrize("act", list(ROUTES))
def test_a_dispute_freezes_it(act):
    spec = ACTS[act]

    async def body(db):
        w = await _standing(db, act)
        await db.collaborations.update_one(
            {"_id": w["collab_oid"]},
            {"$set": {"dispute": {"state": "open", "raised_by_role": "creator"}}},
        )
        with pytest.raises(HTTPException) as err:
            await spec["override"](w)
        return err.value, await db.collaborations.find_one({"_id": w["collab_oid"]})

    exc, row = harness.run(body)
    assert exc.status_code == 409 and exc.detail["code"] == "disputed"
    assert row["state"] == spec["at"]
    assert spec["record"](row) is None


@pytest.mark.parametrize("act", ["accept", "approve_draft", "request_draft_changes", "approve_content"])
def test_the_brand_steps_are_only_for_a_brand_run_brief(act):
    """On a weare-run brief these steps are already ours — there is no brand
    to act for, and the ordinary routes take them."""
    spec = ACTS[act]

    async def body(db):
        w = await _standing(db, act)
        await db.campaigns.update_one(
            {"_id": w["campaign_oid"]}, {"$set": {"execution_owner": "weare"}}
        )
        with pytest.raises(HTTPException) as err:
            await spec["override"](w)
        return err.value, await db.collaborations.find_one({"_id": w["collab_oid"]})

    exc, row = harness.run(body)
    assert exc.status_code == 409 and exc.detail["code"] == "weare_run"
    assert row["state"] == spec["at"]


# --- the brand route's own preconditions, held by the override -------------


def test_accept_holds_the_budget_cap():
    async def body(db):
        w = await _standing(db, "accept", total_budget=5000)
        with pytest.raises(HTTPException) as err:
            await ACTS["accept"]["override"](w)
        return err.value, await db.collaborations.find_one({"_id": w["collab_oid"]})

    exc, row = harness.run(body)
    assert exc.status_code in (409, 422)
    assert row["state"] == "verified"


def test_accept_holds_the_brand_verification_rule():
    async def body(db):
        w = await _standing(db, "accept")
        await db.brand_profiles.update_one(
            {"user_id": w["brand_oid"]}, {"$set": {"verified": False}}
        )
        with pytest.raises(HTTPException) as err:
            await ACTS["accept"]["override"](w)
        return err.value, await db.collaborations.find_one({"_id": w["collab_oid"]})

    exc, row = harness.run(body)
    assert exc.status_code == 409
    assert row["state"] == "verified"


@pytest.mark.parametrize("act", ["approve_draft", "approve_content"])
def test_approval_holds_the_disclosure_checkpoint(act):
    async def body(db):
        w = await _standing(db, act)
        route = ROUTES[act]
        with pytest.raises(HTTPException) as err:
            await route(
                w["collab_id"],
                server.ReviewOnBehalfPayload(reason=REASON, disclosure_confirmed=False),
                ADMIN,
            )
        return err.value, await db.collaborations.find_one({"_id": w["collab_oid"]})

    exc, row = harness.run(body)
    assert exc.status_code == 422
    assert row["state"] == ACTS[act]["at"]


@pytest.mark.parametrize("act", ["approve_draft", "request_draft_changes"])
def test_a_draft_whose_window_ran_out_is_not_answered_again(act):
    """The review window settles first. A draft the clock already approved
    must not gain a second approval in the brand's name."""

    async def body(db):
        w = await _standing(db, act)
        await db.collaborations.update_one(
            {"_id": w["collab_oid"]},
            {"$set": {"draft_review_deadline_at": server.datetime.now(server.timezone.utc)
                      - timedelta(hours=1)}},
        )
        with pytest.raises(HTTPException) as err:
            await ACTS[act]["override"](w)
        return err.value, await db.collaborations.find_one({"_id": w["collab_oid"]})

    exc, row = harness.run(body)
    assert exc.status_code == 409
    assert row["state"] == "draft_approved"
    assert row["draft_approved_by"] == "system_auto"
    assert ACTS[act]["record"](row) is None


# --- mark received: evidence, not a reason, is what makes it honest --------


def test_mark_received_refuses_without_evidence():
    async def body(db):
        w = await _standing(db, "mark_received")
        with pytest.raises(HTTPException) as err:
            await server.mark_received_on_behalf(
                w["collab_id"], reason=REASON, tracking_url=None, file=None, user=ADMIN
            )
        return err.value, await db.collaborations.find_one({"_id": w["collab_oid"]})

    exc, row = harness.run(body)
    assert exc.status_code == 422 and exc.detail["code"] == "evidence_required"
    assert row["state"] == "dispatched"


def test_mark_received_refuses_a_link_that_is_not_a_web_address():
    async def body(db):
        w = await _standing(db, "mark_received")
        with pytest.raises(HTTPException) as err:
            await server.mark_received_on_behalf(
                w["collab_id"], reason=REASON, tracking_url="javascript:alert(1)",
                file=None, user=ADMIN,
            )
        return err.value, await db.collaborations.find_one({"_id": w["collab_oid"]})

    exc, row = harness.run(body)
    assert exc.status_code == 422
    assert row["state"] == "dispatched"


def test_mark_received_takes_a_photo_and_keeps_it_private():
    async def body(db):
        w = await _standing(db, "mark_received")
        out = await server.mark_received_on_behalf(
            w["collab_id"], reason=REASON, tracking_url=None, file=_png(), user=ADMIN
        )
        row = await db.collaborations.find_one({"_id": w["collab_oid"]})
        streamed = await server.read_received_evidence(w["collab_id"], ADMIN)
        viewed = await db.audit_log.find_one({"action": "collaboration.received_evidence_view"})
        return out, row, streamed, viewed

    out, row, streamed, viewed = harness.run(body)
    assert row["state"] == "received"
    image = row["delivery"]["received_on_behalf"]["evidence"]["image"]
    assert image["stored_name"].startswith("received-")
    assert image["mime"] == "image/png"
    # What travels is that a photo exists — never a path or a URL to it.
    assert out["on_behalf"]["received"]["evidence"] == {"tracking_url": None, "has_image": True}
    assert "stored_name" not in str(out)
    assert streamed.headers["cache-control"].startswith("no-store")
    assert viewed is not None


def test_mark_received_is_only_for_a_dispatched_delivery():
    async def body(db):
        w = await harness._world(db, ladder="delivery", money="paid")
        await harness._walk_to(db, w, "address_confirmed", "delivery", "paid")
        with pytest.raises(HTTPException) as err:
            await ACTS["mark_received"]["override"](w)
        return err.value

    assert harness.run(body).status_code == 409


# --- the menu ---------------------------------------------------------------


@pytest.mark.parametrize(
    "ladder,at,keys",
    [
        ("venue", "verified", {"accept"}),
        ("venue", "commercial_agreed", {"book_slot"}),
        ("delivery", "commercial_agreed", {"confirm_address"}),
        ("delivery", "dispatched", {"mark_received"}),
        ("venue+draft", "draft_submitted", {"approve_draft", "request_draft_changes"}),
        ("venue", "content_submitted", {"approve_content"}),
        ("venue", "slot_booked", set()),
    ],
)
def test_the_menu_lists_only_what_the_routes_would_take(ladder, at, keys):
    async def body(db):
        w = await harness._world(db, ladder=ladder, money="paid")
        await harness._walk_to(db, w, at, ladder, "paid")
        row = await db.collaborations.find_one({"_id": w["collab_oid"]})
        campaign = await db.campaigns.find_one({"_id": w["campaign_oid"]})
        admin = server._on_behalf_actions(row, campaign, ADMIN)
        team = server._on_behalf_actions(row, campaign, {**ADMIN, "role": "weare_team"})
        frozen = server._on_behalf_actions(
            {**row, "dispute": {"state": "open"}}, campaign, ADMIN
        )
        weare = server._on_behalf_actions(row, {**campaign, "execution_owner": "weare"}, ADMIN)
        return admin, team, frozen, weare

    admin, team, frozen, weare = harness.run(body)
    assert {a["key"] for a in admin} == keys
    assert team == [] and frozen == []
    # On a weare-run brief only the creator's acts remain.
    assert {a["key"] for a in weare} == {k for k in keys if k in
                                         ("book_slot", "confirm_address", "mark_received")}
    for a in admin:
        assert a["side"] == ("creator" if a["key"] in
                             ("book_slot", "confirm_address", "mark_received") else "brand")


def test_the_received_step_is_now_an_override_and_says_why():
    assert server.ON_BEHALF_STEPS == ("slot_booked", "address_confirmed", "received")
    src = inspect.getsource(server)
    comment = src[: src.index("ON_BEHALF_STEPS = (")].rsplit("\n\n", 1)[-1]
    assert "evidence, not a reason" in comment.lower()


# --- the UI -----------------------------------------------------------------

from pathlib import Path  # noqa: E402
import re  # noqa: E402

FRONTEND = Path(server.__file__).resolve().parent.parent / "frontend" / "src"


def test_the_page_offers_the_menu_from_the_server_and_asks_no_role():
    page = (FRONTEND / "components/admin/CollaborationDetailPage.jsx").read_text()
    menu = (FRONTEND / "components/admin/ActOnBehalf.jsx").read_text()
    assert "<ActOnBehalfMenu" in page and "<OnBehalfActDialog" in page
    assert "on_behalf_actions" in page
    for route in ("mark-received", "accept", "approve-draft",
                  "request-draft-changes", "approve-content"):
        assert f"/on-behalf/{route}`" in page, route
    # Split by whose step it is, and nothing here decides who may see it.
    assert '"Creator"' in menu and '"Brand"' in menu
    for src in (page, menu):
        assert not re.search(r"role\s*===\s*['\"](admin|weare_team)['\"]", src)


def test_every_new_step_has_a_sentence_in_both_voices():
    note = (FRONTEND / "components/collab/OnBehalfNote.jsx").read_text()
    for step in ("received", "accepted", "draft_approved",
                 "draft_changes_requested", "content_approved"):
        assert re.search(rf"\b{step}: \{{\s*you:", note), step
    # And the brand's own board renders the block too.
    board = (FRONTEND / "pages/BrandCampaignApplicants.jsx").read_text()
    assert "<OnBehalfNote" in board and "a.on_behalf" in board


def test_the_proof_photo_is_fetched_as_a_blob_never_linked():
    src = (FRONTEND / "components/admin/ReceivedEvidence.jsx").read_text()
    assert 'responseType: "blob"' in src
    assert "URL.revokeObjectURL" in src
    assert "API_BASE" not in src
