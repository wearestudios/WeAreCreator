"""Three things a person has to be able to say out loud, and one handshake.

**Reference ids.** An ObjectId is not something anybody says on a phone call,
and every record here was addressed by one — so "the campaign ending 4f2a" is
what a support thread turned into. `CMP-0034` reads back, sorts by when it was
made, and fits in a table column. It is a *label*: nothing looks a record up by
it except search, and every route still takes the ObjectId, because a second
identifier that could address a record is a second thing to check permissions
on.

**The booking handshake.** Booking used to be one move: a creator picked a time
and that was the arrangement, with nobody at the venue having agreed to it. It
is now a request and an answer — and deliberately **not** a new state, so the
ladder is untouched and nothing mid-flight is stranded.

**The WeAre-run shield.** Handing a campaign to us is handing over the
shortlisting; the brand used to watch every unchecked pitch arrive anyway.
"""
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


def no_comments(path: Path) -> str:
    src = re.sub(r"\{/\*.*?\*/\}", "", path.read_text(), flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


def run(body):
    async def go():
        db = AsyncMongoMockClient()["refs"]
        original = server.db
        server.db = db
        try:
            return await body(db)
        finally:
            server.db = original

    return asyncio.run(go())


# ---------------------------------------------------------------------------
# Reference ids
# ---------------------------------------------------------------------------


def test_the_four_kinds_have_the_prefixes_asked_for():
    assert server.REFERENCE_PREFIXES == {
        "brand": "BRD",
        "campaign": "CMP",
        "creator": "CRT",
        "collaboration": "COL",
    }


def test_they_are_allocated_in_order_and_never_repeat():
    """A counter in the database rather than a row count: counting rows hands
    out a duplicate the moment anything is ever deleted."""

    async def body(db):
        return [await server._next_reference("campaign") for _ in range(3)]

    assert run(body) == ["CMP-0001", "CMP-0002", "CMP-0003"]


def test_each_kind_counts_on_its_own():
    async def body(db):
        return (
            await server._next_reference("brand"),
            await server._next_reference("creator"),
            await server._next_reference("brand"),
        )

    assert run(body) == ("BRD-0001", "CRT-0001", "BRD-0002")


def test_it_grows_a_digit_rather_than_wrapping():
    """A reference that repeats is worse than a long one."""
    assert server._format_reference("campaign", 99999) == "CMP-99999"
    assert server._format_reference("campaign", 7) == "CMP-0007"


@pytest.mark.parametrize(
    "typed,expected",
    [
        ("BRD-0012", ("brand", "BRD-0012")),
        ("brd12", ("brand", "BRD-0012")),
        ("crt 108", ("creator", "CRT-0108")),
        ("  COL-0456  ", ("collaboration", "COL-0456")),
        ("cmp-34", ("campaign", "CMP-0034")),
    ],
)
def test_a_reference_is_read_the_way_a_person_types_it(typed, expected):
    """The separator and the padding are both optional — one somebody has to
    spell exactly is one they retype three times."""
    assert server.parse_reference(typed) == expected


@pytest.mark.parametrize("typed", ["nonsense", "BRD", "12", "", None, "XYZ-0001"])
def test_anything_else_is_not_a_reference(typed):
    assert server.parse_reference(typed) is None


def test_an_unnumbered_record_reads_as_none_rather_than_an_invented_id():
    """A record the backfill has not reached has no number. A made-up one is
    worse than a blank column, because somebody would quote it."""
    assert server._reference_of({}) is None
    assert server._reference_of(None) is None
    assert server._reference_of({"reference": ""}) is None
    assert server._reference_of({"reference": "CMP-0007"}) == "CMP-0007"


@pytest.mark.parametrize(
    "fn",
    [
        "_serialize_campaign",
        "_serialize_brand_campaign",
        "_brand_visible_creator",
        "_serialize_applicant",
        "_serialize_collab_row",
        "_serialize_admin_collab",
        "_serialize_admin_creator",
        "_admin_brand_fields",
    ],
)
def test_every_entity_serializer_emits_its_reference(fn):
    assert '"reference"' in inspect.getsource(getattr(server, fn)), (
        f"{fn} serves an entity with no readable id on it"
    )


def test_the_creators_reference_is_on_the_brand_allow_list():
    """A label carrying nothing about the person — and the thing a brand and an
    admin quote at each other."""
    assert "reference" in server._BRAND_VISIBLE_CREATOR_FIELDS


def test_a_new_record_is_numbered_when_it_is_made_not_when_it_is_read():
    """So a brand can quote the brief's number in the same breath as posting
    it. Lazily numbering on read would mean two readers racing for one id."""
    for fn in (
        server.create_brand_campaign,
        server.apply_to_campaign,
        server.verify_otp,
    ):
        assert "_next_reference(" in inspect.getsource(fn), (
            f"{fn.__name__} creates a record with no reference"
        )


def test_the_backfill_numbers_everything_and_then_makes_it_unique():
    src = inspect.getsource(server._startup)
    block = src[src.index("# 11. Reference ids.") :]
    for kind in server.REFERENCE_PREFIXES:
        assert f'"{kind}"' in block
    # In creation order, so CMP-0001 is the first brief ever posted rather than
    # whichever row the migration happened to reach first.
    assert 'sort("_id", 1)' in block
    assert 'create_index("reference", unique=True, sparse=True)' in block


def test_a_typed_reference_finds_exactly_one_record():
    async def body(db):
        brand_id, creator_id = ObjectId(), ObjectId()
        await db.brand_profiles.insert_one(
            {"user_id": brand_id, "business_name": "Toit", "reference": "BRD-0001"}
        )
        await db.users.insert_one({"_id": brand_id, "role": "brand_manager", "name": "Toit"})
        campaign_id = (
            await db.campaigns.insert_one(
                {"brand_id": brand_id, "title": "Brunch", "reference": "CMP-0009", "status": "open"}
            )
        ).inserted_id
        await db.creator_profiles.insert_one(
            {"user_id": creator_id, "name": "Aditi", "reference": "CRT-0004"}
        )
        await db.users.insert_one({"_id": creator_id, "role": "creator", "name": "Aditi"})
        await db.collaborations.insert_one(
            {
                "campaign_id": campaign_id,
                "creator_id": creator_id,
                "state": "applied",
                "reference": "COL-0002",
            }
        )
        admin = {"_id": str(ObjectId()), "role": "admin", "name": "Admin"}
        return {
            term: await server.admin_global_search(q=term, user=admin)
            for term in ("BRD-0001", "cmp 9", "CRT-0004", "col-2")
        }

    results = run(body)
    for term, out in results.items():
        rows = [i for g in out["groups"] for i in g["items"]]
        assert len(rows) == 1, f"{term} matched {len(rows)} records"
        assert out["matched_reference"]
    assert results["col-2"]["groups"][0]["items"][0]["href"].startswith(
        "/admin/collaborations/"
    ), "a collaboration reference is the only way to reach one from search"


def test_a_reference_that_names_nothing_falls_back_to_the_ordinary_search():
    async def body(db):
        admin = {"_id": str(ObjectId()), "role": "admin", "name": "Admin"}
        return await server.admin_global_search(q="CMP-9999", user=admin)

    out = run(body)
    assert out["groups"] == []
    assert out.get("matched_reference") is None


# ---------------------------------------------------------------------------
# The booking handshake
# ---------------------------------------------------------------------------


def test_a_booking_made_since_the_handshake_starts_unconfirmed():
    now = datetime.now(timezone.utc)
    assert server._slot_confirmed({"slot_booked_at": now}) is False
    assert server._slot_confirmed({"slot_booked_at": now, "slot_confirmed_at": now}) is True


def test_a_booking_made_before_the_handshake_reads_as_confirmed():
    """**The migration guarantee.** Those bookings were agreed by the only
    mechanism there was — nobody objecting — and reopening them all on deploy
    would put a decision in front of every manager for shoots that already
    happened."""
    assert server._slot_confirmed({"state": "slot_booked"}) is True
    assert server._slot_confirmed({}) is True


def test_the_handshake_is_not_a_new_state():
    """The ladder is untouched, so every transition check and every in-flight
    collaboration is unaffected. That is the whole reason it is a timestamp."""
    assert "slot_pending" not in server.COLLAB_STATE_ORDER
    assert "pending_confirmation" not in server.COLLAB_STATE_ORDER
    assert server.COLLAB_STATE_ORDER.count("slot_booked") == 1


def test_booking_holds_the_seat_immediately():
    """A place somebody is waiting on an answer for is not a place to sell
    twice."""
    src = inspect.getsource(server._claim_slot)
    inc = src.index('"$inc": {"booked_count": 1}')
    confirmed = src.index('"slot_confirmed_at": None')
    assert inc < confirmed, "the seat must be claimed before the collaboration is marked"


def test_the_creator_is_told_it_is_requested_and_not_confirmed():
    """They arrange a day around this. "Booked" when nobody has agreed the time
    is how somebody travels across Bengaluru to a shut venue."""
    src = inspect.getsource(server._claim_slot)
    # The event the creator's notification carries, not the flag on the
    # response — `slot_confirmed: False` in the payload is the same fact said
    # to the client rather than to the creator.
    notice = src[src.index("await notify(") :][:400]
    assert '"slot_requested"' in notice
    assert '"slot_confirmed"' not in notice


def test_nobody_books_on_a_creators_behalf():
    """This route used to write the state and a time straight onto the
    collaboration — an admin deciding when somebody else's day is."""
    src = inspect.getsource(server.advance_collaboration)
    branch = src[src.index('if to_state == "slot_booked":') :][:900]
    assert "409" in branch
    assert "Only the creator can book" in branch
    assert "slot_booked" in server._CREATOR_OWNED_TRANSITIONS


def test_declining_hands_the_seat_back_and_returns_them_to_the_step_before():
    """Which is `commercial_agreed` — the same place cancelling puts them,
    because the thing they now have to do is the same."""
    src = inspect.getsource(server._answer_slot_request)
    assert '"state": "commercial_agreed"' in src
    assert '"$inc": {"booked_count": -1}' in src
    # The collaboration moves first: the other order puts a place on sale while
    # somebody still holds it.
    assert src.index('"state": "commercial_agreed"') < src.index('"booked_count": -1')


def test_the_creator_is_told_either_way():
    """A booking that silently disappears is a creator who turns up."""
    src = inspect.getsource(server._answer_slot_request)
    assert '"slot_confirmed"' in src
    assert '"slot_declined"' in src


def test_the_reason_travels_with_a_declined_slot():
    """Without it they pick the same impossible time again."""
    src = inspect.getsource(server._answer_slot_request)
    assert "slot_declined_reason" in src
    assert "reason" in inspect.signature(server._answer_slot_request).parameters


def test_both_runners_answer_through_one_implementation():
    """Which of the two answers depends on `execution_owner`, and a booking
    that meant different things depending on who confirmed it would not be a
    confirmation. Same rule `_check_in_collaboration` holds."""
    for fn in (
        server.brand_confirm_slot,
        server.brand_decline_slot,
        server.manager_confirm_slot,
        server.manager_decline_slot,
    ):
        assert "_answer_slot_request(" in inspect.getsource(fn)


def test_confirming_writes_no_state():
    """The collaboration is already `slot_booked`; what was missing was
    somebody agreeing to it."""
    src = inspect.getsource(server._answer_slot_request)
    confirm_branch = src[src.index("if confirm:") : src.index("# Declined.")]
    # The `$set` is the write; the filter beside it names `slot_booked` as a
    # precondition, which is the opposite of changing it.
    written = confirm_branch[confirm_branch.index('"$set"') :][:400]
    assert '"state":' not in written
    assert '"slot_confirmed_at": now' in written


def test_the_scheduled_stage_says_which_of_the_two_it_is():
    now = datetime.now(timezone.utc)
    waiting = server._process_flow(
        {"state": "slot_booked", "slot_booked_at": now}, {}, viewer={"role": "creator"}
    )
    agreed = server._process_flow(
        {"state": "slot_booked", "slot_booked_at": now, "slot_confirmed_at": now},
        {},
        viewer={"role": "creator"},
    )

    assert waiting["stage"] == agreed["stage"] == "scheduled"
    assert waiting["next_action"]["label"] == "Your slot is waiting to be confirmed"
    assert agreed["next_action"]["label"] == "Turn up on the day"


def test_the_confirm_button_is_offered_to_the_runner_and_nobody_else():
    src = inspect.getsource(server.get_application)
    assert "can_confirm_slot" in src
    block = src[src.index('"can_confirm_slot"') :][:300]
    # The same reader the draft review uses, so a brand on a weare-run brief
    # never sees it.
    assert "_question_staff_may_see(campaign, user)" in block
    assert "not _slot_confirmed(collab)" in block


# ---------------------------------------------------------------------------
# The WeAre-run shield
# ---------------------------------------------------------------------------


def test_a_brand_run_campaign_shows_the_brand_everything_as_before():
    campaign = {"execution_owner": "brand"}
    assert server._brand_sees_collab(campaign, {"state": "applied"}) is True
    assert server._brand_visible_collab_query(campaign) == {}


def test_a_weare_run_campaign_shows_the_brand_nothing_until_the_fee_is_settled():
    campaign = {"execution_owner": "weare"}
    assert server._brand_sees_collab(campaign, {"state": "applied"}) is False
    assert server._brand_sees_collab(campaign, {"state": "verified"}) is False
    assert (
        server._brand_sees_collab(campaign, {"state": "commercial_agreed", "agreed_at": 1})
        is True
    )


def test_the_line_is_agreed_at_and_it_survives_everything_after_it():
    """A state test would hide a creator the brand had already been shown, the
    moment the collaboration was declined. `agreed_at` is the moment somebody
    at WeAre finished the job, and it does not move."""
    campaign = {"execution_owner": "weare"}
    assert server._brand_sees_collab(campaign, {"state": "declined", "agreed_at": 1}) is True
    assert server._brand_visible_collab_query(campaign) == {"agreed_at": {"$ne": None}}


def test_barter_counts_as_settled():
    """It sets `agreed_at` with no figure, which is right — the work was done,
    there is simply no money in it."""
    campaign = {"execution_owner": "weare"}
    collab = {"state": "commercial_agreed", "agreed_at": 1, "agreed_amount": None}
    assert server._brand_sees_collab(campaign, collab) is True


def test_a_pre_field_campaign_is_brand_run_and_hides_nothing():
    """Campaigns predate `execution_owner`. A shield that switched on for them
    would empty every existing brand's board."""
    assert server._brand_sees_collab({}, {"state": "applied"}) is True


@pytest.mark.parametrize(
    "fn", ["_brand_collab_or_404", "_note_readable_collab_or_404", "list_campaign_applicants"]
)
def test_every_door_onto_an_application_carries_the_shield(fn):
    """**A shield on one of the doors is a shield on neither.** The board could
    hide a raw application while its id, pasted from anywhere, opened the whole
    thing including the pitch."""
    src = inspect.getsource(getattr(server, fn))
    assert "_brand_sees_collab" in src or "_brand_visible_collab_query" in src


def test_the_refusal_is_a_404():
    """Whether the application exists is not the brand's to know yet — the same
    shape as every other ownership refusal here."""
    src = inspect.getsource(server._brand_collab_or_404)
    block = src[src.index("_brand_sees_collab") :][:200]
    assert "404" in block and "403" not in block


def test_weare_can_still_move_its_own_campaign_forward():
    """The brand cannot reach the application at all until we have shortlisted
    it, so refusing the brand-owned transitions to us as well would leave a
    weare-run collaboration stuck at `verified` with nobody able to move it."""
    src = inspect.getsource(server.advance_collaboration)
    assert "if to_state in _BRAND_OWNED_TRANSITIONS and not _weare_runs(campaign or {})" in src


def test_the_brands_waiting_count_ignores_campaigns_it_does_not_run():
    """A badge for work they cannot do, on an applicant they cannot open."""
    src = inspect.getsource(server._awaiting_brand_counts)
    assert '_execution_owner_query("brand")' in src


# ---------------------------------------------------------------------------
# Full pages, and the ids on them
# ---------------------------------------------------------------------------


def test_every_review_queue_links_to_the_whole_record():
    """A queue row is a summary and a peek is a preview. A brand's GST number,
    its registered address and its documents are on its page, and deciding
    without them is deciding on the business name alone."""
    src = no_comments(FRONTEND / "components" / "admin" / "Reviews.jsx")
    for route in ("/admin/creators/", "/admin/campaigns/", "/admin/brands/"):
        assert f"href: (r) => `{route}" in src, f"the {route} queue has no way to the page"
    # And the peek offers it too, rather than being a dead end.
    assert "href={peek ? config.href(peek) : undefined}" in src


@pytest.mark.parametrize(
    "page,action",
    [
        ("BrandDetailPage.jsx", 'action("verify")'),
        ("CreatorDetailPage.jsx", 'action("approve")'),
        ("CampaignDetailPage.jsx", 'action("approve")'),
    ],
)
def test_the_decision_can_be_taken_on_the_page_itself(page, action):
    """Otherwise "open the full page" means losing the queue to read the
    record and then going back to act on it."""
    assert action in no_comments(FRONTEND / "components" / "admin" / page)


def test_the_brands_page_carries_what_the_decision_needs():
    src = no_comments(FRONTEND / "components" / "admin" / "BrandDetailPage.jsx")
    assert "gst_number" in src
    assert "documents" in src


@pytest.mark.parametrize(
    "page",
    ["BrandDetailPage.jsx", "CreatorDetailPage.jsx", "CampaignDetailPage.jsx", "CollaborationDetailPage.jsx"],
)
def test_every_entity_page_prints_its_reference(page):
    assert "reference" in no_comments(FRONTEND / "components" / "admin" / page)


def test_the_palette_shows_and_invites_a_reference():
    src = no_comments(FRONTEND / "components" / "admin" / "CommandPalette.jsx")
    assert "item.reference" in src
    assert "CMP-0034" in src, "the placeholder should say an id is a thing you can type"
