"""Being asked, and being taken on.

Two bugs with one root: **the only thing every "who is on this campaign" view
read was `collaborations`.**

- An **invitation** creates no collaboration, so a creator who was asked saw
  nothing anywhere in the app — the invite existed as a WhatsApp message and a
  database row, and if they missed the message they never found out. The two
  applicant boards had the same hole from the other side: a campaign we had
  invited six people to looked empty.
- An **approved application** is a collaboration, and the complaint was that it
  did not appear under its campaign. That one is pinned here as a regression
  test across all three views at once, which is what the report asked for:
  admin, brand and creator must agree about the same row.

Everything below drives the real handlers against a mock database, so a bucket
renamed on one side and not the other fails here rather than in a console.
"""
import asyncio
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend"


def no_comments(path: Path) -> str:
    src = path.read_text()
    src = re.sub(r"\{/\*.*?\*/\}", "", src, flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


class World:
    """One brand, one creator, one admin and one live campaign."""

    def __init__(self):
        self.db = AsyncMongoMockClient()["invites"]

    async def build(self):
        db = self.db
        now = datetime.now(timezone.utc)
        self.brand_id, self.creator_id, self.admin_id = (
            ObjectId(),
            ObjectId(),
            ObjectId(),
        )
        await db.users.insert_many(
            [
                {"_id": self.brand_id, "role": "brand_manager", "name": "Toit"},
                {
                    "_id": self.creator_id,
                    "role": "creator",
                    "name": "Aditi Rao",
                    "phone": "+919900000001",
                },
                {"_id": self.admin_id, "role": "admin", "name": "Admin"},
            ]
        )
        await db.brand_profiles.insert_one(
            {"user_id": self.brand_id, "business_name": "Toit", "verified": True}
        )
        await db.creator_profiles.insert_one(
            {
                "user_id": self.creator_id,
                "name": "Aditi Rao",
                "verification_status": "verified",
            }
        )
        self.campaign_id = (
            await db.campaigns.insert_one(
                {
                    "title": "Winter menu tasting",
                    "brand_id": self.brand_id,
                    "status": "open",
                    "campaign_type": "group_event",
                    "event_date": now + timedelta(days=5),
                    "creators_needed": 3,
                    "filled_slots": 0,
                    "created_at": now,
                    "compensation_type": "fixed",
                    "budget_per_creator": 8000,
                    "area": "Indiranagar",
                }
            )
        ).inserted_id

        self.admin = {"_id": str(self.admin_id), "role": "admin", "name": "Admin"}
        self.brand = {
            "_id": str(self.brand_id),
            "role": "brand_manager",
            "name": "Toit",
        }
        self.creator = {
            "_id": str(self.creator_id),
            "role": "creator",
            "name": "Aditi Rao",
        }

    async def invite(self, note="We'd love to have you", campaign_id=None):
        now = datetime.now(timezone.utc)
        return (
            await self.db.campaign_invitations.insert_one(
                {
                    "campaign_id": campaign_id or self.campaign_id,
                    "creator_id": self.creator_id,
                    "brand_id": self.brand_id,
                    "invited_by": self.admin_id,
                    "note": note,
                    "state": "sent",
                    "created_at": now,
                    "updated_at": now,
                }
            )
        ).inserted_id

    # The three views, in the three roles' own words.
    async def creator_view(self):
        return await server.get_creator_dashboard(self.creator)

    async def admin_board(self):
        return await server.admin_campaign_applicants(str(self.campaign_id), self.admin)

    async def brand_board(self):
        return await server.list_campaign_applicants(str(self.campaign_id), self.brand)


def run(body):
    """Drive one coroutine against a fresh mock database."""

    async def go():
        world = World()
        original = server.db
        server.db = world.db
        try:
            await world.build()
            return await body(world)
        finally:
            server.db = original

    return asyncio.run(go())


# ---------------------------------------------------------------------------
# An invitation is visible the moment it is sent
# ---------------------------------------------------------------------------


def test_an_unanswered_invitation_reaches_the_creators_own_view():
    """The bug: invited, and nothing anywhere in the app said so."""

    async def body(w):
        await w.invite()
        return await w.creator_view()

    dash = run(body)
    assert [(i["campaign_title"], i["state"], i["open"]) for i in dash["invitations"]] == [
        ("Winter menu tasting", "sent", True)
    ]
    # And it counts, so the tab badge is not "nothing for you".
    assert dash["totals"]["invitations"] == 1


def test_the_invitation_carries_what_is_needed_to_answer_it():
    """An invitation with no brief attached is a notification, not something
    you can act on — and the note is the reason this is not a mailshot."""

    async def body(w):
        await w.invite()
        return (await w.creator_view())["invitations"][0]

    invite = run(body)
    assert invite["campaign_id"]
    assert invite["campaign_title"] == "Winter menu tasting"
    assert invite["brand_name"] == "Toit"
    assert invite["note"] == "We'd love to have you"
    assert invite["budget_per_creator"] == 8000
    assert invite["compensation_type"] == "fixed"


def test_an_unanswered_invitation_reaches_both_applicant_boards():
    """From the other side: a campaign six people were asked to looked empty."""

    async def body(w):
        await w.invite()
        return await w.admin_board(), await w.brand_board()

    admin, brand = run(body)
    assert len(admin["invited"]) == 1
    assert admin["invited"][0]["state"] == "invited"
    # No collaboration exists, so there is no id — and a made-up one is an id
    # somebody tries to act on.
    assert admin["invited"][0]["collaboration_id"] is None
    assert admin["invited"][0]["invitation_id"]
    assert len(brand["invited"]) == 1
    assert brand["totals"]["invited"] == 1


def test_the_brand_never_sees_a_way_to_contact_an_invited_creator():
    """The invited rows are a brand-facing surface like any other, so they go
    through the allow-list rather than being assembled by hand."""

    async def body(w):
        await w.db.creator_profiles.update_one(
            {"user_id": w.creator_id},
            {
                "$set": {
                    "phone": "+919812345678",
                    "email": "aditi@example.com",
                    "full_address": "4th floor, 22 Church Street",
                    "location_lat": 12.9716,
                }
            },
        )
        await w.invite()
        return await w.brand_board()

    brand = run(body)
    blob = repr(brand)
    for planted in ("919812345678", "aditi@example.com", "Church Street", "12.9716"):
        assert planted not in blob, f"{planted} reached a brand response"
    for key in server.BRAND_FORBIDDEN_CREATOR_FIELDS:
        assert key not in brand["invited"][0]


# ---------------------------------------------------------------------------
# Answering it
# ---------------------------------------------------------------------------


def test_accepting_an_invitation_makes_an_application():
    """Accepting is applying with the door already open — it goes through
    `apply_to_campaign` so there is one definition of what an application is."""

    async def body(w):
        invite_id = await w.invite()
        await server.accept_invitation(
            str(invite_id),
            server.ApplyPayload(pitch="Yes please", quoted_rate=8000),
            w.creator,
        )
        return (
            await w.creator_view(),
            await w.admin_board(),
            await w.brand_board(),
            await w.db.campaign_invitations.find_one({"_id": invite_id}),
        )

    dash, admin, brand, row = run(body)

    # It leaves the invitation list as a decision and joins the applications.
    assert [i["open"] for i in dash["invitations"]] == [False]
    assert dash["totals"]["invitations"] == 0
    assert [r["state"] for r in dash["applications"]] == ["applied"]

    # And moves across both boards in the same breath — nobody is on them twice.
    assert len(admin["invited"]) == 0
    assert len(admin["applied"]) == 1
    assert len(brand["invited"]) == 0
    assert len(brand["applicants"]) == 1

    assert row["state"] == "accepted"
    assert row["responded_at"]


def test_declining_leaves_no_collaboration_and_no_bar_on_applying():
    async def body(w):
        invite_id = await w.invite()
        await server.decline_invitation(str(invite_id), w.creator)
        return (
            await w.creator_view(),
            await w.db.collaborations.count_documents({}),
            await w.admin_board(),
        )

    dash, collabs, admin = run(body)
    assert [i["state"] for i in dash["invitations"]] == ["declined"]
    assert [i["open"] for i in dash["invitations"]] == [False]
    assert collabs == 0
    # Off the board: it is answered, and the answer was no.
    assert len(admin["invited"]) == 0


@pytest.mark.parametrize("answer", ["accept", "decline"])
def test_an_invitation_can_only_be_answered_once(answer):
    async def body(w):
        invite_id = await w.invite()
        if answer == "accept":
            await server.accept_invitation(
                str(invite_id),
                server.ApplyPayload(pitch="Yes", quoted_rate=8000),
                w.creator,
            )
            with pytest.raises(HTTPException) as exc:
                await server.accept_invitation(
                    str(invite_id),
                    server.ApplyPayload(pitch="Yes", quoted_rate=8000),
                    w.creator,
                )
        else:
            await server.decline_invitation(str(invite_id), w.creator)
            with pytest.raises(HTTPException) as exc:
                await server.decline_invitation(str(invite_id), w.creator)
        return exc.value

    err = run(body)
    assert err.status_code == 409
    assert "already answered" in err.detail


def test_somebody_elses_invitation_is_a_404_not_a_403():
    """Whether an invitation exists is itself not answered — the same rule the
    private briefs and the work notes hold."""

    async def body(w):
        invite_id = await w.invite()
        stranger = {"_id": str(ObjectId()), "role": "creator", "name": "Someone"}
        with pytest.raises(HTTPException) as exc:
            await server.decline_invitation(str(invite_id), stranger)
        return exc.value

    err = run(body)
    assert err.status_code == 404


def test_an_invitation_to_a_closed_brief_is_history_not_a_button():
    """Offering an Accept that would 404 is worse than saying it has closed."""

    async def body(w):
        invite_id = await w.invite()
        await w.db.campaigns.update_one(
            {"_id": w.campaign_id}, {"$set": {"status": "closed"}}
        )
        dash = await w.creator_view()
        return dash, invite_id

    dash, _ = run(body)
    assert [i["state"] for i in dash["invitations"]] == ["sent"]
    assert [i["open"] for i in dash["invitations"]] == [False]
    assert dash["totals"]["invitations"] == 0


# ---------------------------------------------------------------------------
# The approved application, in all three views at once
# ---------------------------------------------------------------------------


def test_an_approved_application_is_listed_under_its_campaign_everywhere():
    """The reported bug, pinned across the three views that must agree.

    Driven through the real transitions rather than by writing `accepted` into
    the database, because the complaint was about what the boards *show* after
    the real sequence of moves.
    """

    async def body(w):
        await server.apply_to_campaign(
            str(w.campaign_id),
            server.ApplyPayload(pitch="I'd love to", quoted_rate=8000),
            w.creator,
        )
        collab = await w.db.collaborations.find_one({})
        # Admin verifies, brand accepts — each step by whoever owns it.
        await server.advance_collaboration(
            str(collab["_id"]),
            server.AdvanceCollabPayload(from_state="applied"),
            w.admin,
        )
        await server.brand_accept_applicant(
            str(collab["_id"]), server.BrandAcceptPayload(), w.brand
        )
        return (
            await w.creator_view(),
            await w.admin_board(),
            await w.brand_board(),
            await w.db.collaborations.find_one({"_id": collab["_id"]}),
        )

    dash, admin, brand, row = run(body)

    assert row["state"] == "accepted"

    # Admin: under the campaign, in the approved group and nowhere else.
    assert [a["state"] for a in admin["approved"]] == ["accepted"]
    assert admin["applied"] == []
    assert admin["rejected"] == []

    # Brand: on its own board, with the same state.
    assert [a["state"] for a in brand["applicants"]] == ["accepted"]

    # Creator: in the active work, not left sitting under pitches.
    active = [r["state"] for r in dash["collaborations"].get("active", [])]
    assert active == ["accepted"]
    assert dash["collaborations"].get("applied", []) == []


def test_every_collaboration_state_lands_in_exactly_one_board_bucket():
    """An applicant whose state belongs to no bucket vanishes from a board that
    is supposed to account for everybody — which is the shape of the original
    complaint, and is why the assertion beside `_APPLICANT_BUCKETS` exists."""
    buckets = [states for _, states in server._APPLICANT_BUCKETS]
    for state in set(server.COLLAB_STATE_ORDER) | set(server.TERMINAL_COLLAB_STATES):
        hits = [i for i, states in enumerate(buckets) if state in states]
        assert len(hits) == 1, f"{state} belongs to {len(hits)} buckets"


def test_invited_is_not_one_of_the_collaboration_buckets():
    """It is a fifth group on the board and not a state on the ladder: there is
    no collaboration, so there is nothing to approve."""
    assert "invited" not in server.COLLAB_STATE_ORDER
    for _, states in server._APPLICANT_BUCKETS:
        assert "invited" not in states


# ---------------------------------------------------------------------------
# The surfaces
# ---------------------------------------------------------------------------


def test_the_creators_applications_view_carries_the_accept_and_the_decline():
    """"Not invisible until they act" was the requirement, and the two answers
    have to be on the row — a link to somewhere the answer might be is the
    thing this replaces."""
    src = no_comments(FRONTEND / "src" / "components" / "creator" / "Invitations.jsx")
    assert "/creator/invitations/${accepting.id}/accept" in src
    assert "/creator/invitations/${invite.id}/decline" in src
    assert "invitationAccept" in src and "invitationDecline" in src

    applications = no_comments(
        FRONTEND / "src" / "components" / "creator" / "Applications.jsx"
    )
    assert "<Invitations" in applications, (
        "the invitations do not appear in the applications view"
    )


def test_the_applications_tab_counts_open_invitations():
    src = no_comments(FRONTEND / "src" / "pages" / "Dashboard.jsx")
    block = src[src.index("const applicationsCount") :][:320]
    assert "invitations" in block, "the tab badge ignores unanswered invitations"


def test_an_answered_invitation_is_not_offered_again_by_the_ui():
    """`open` is decided server-side and the list filters on it, so a closed
    brief or an already-answered invitation shows no buttons."""
    src = no_comments(FRONTEND / "src" / "components" / "creator" / "Invitations.jsx")
    assert "filter((i) => i.open)" in src


def test_both_applicant_boards_render_the_invited_group():
    admin = no_comments(
        FRONTEND / "src" / "components" / "admin" / "CampaignDetailPage.jsx"
    )
    assert '{ key: "invited"' in admin

    brand = no_comments(FRONTEND / "src" / "pages" / "BrandCampaignApplicants.jsx")
    assert "InvitedStrip" in brand
    assert "data.invited" in brand
