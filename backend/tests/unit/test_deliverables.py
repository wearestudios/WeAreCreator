"""What a brief asks for, counted rather than described.

`deliverables` was a free-text box. Four brands asking for the same thing wrote
"1 reel + 3 stories", "one reel, three stories", "reel x1, stories x3" and "a
reel and a few stories", so nothing could count what a campaign wanted, a
creator comparing two briefs was comparing prose, and "a few" is not a number
anybody agreed to.

`deliverable_items` is the structured ask and `deliverables` is now **derived
from it** rather than typed. Deriving rather than replacing is what makes this
migration-safe: the campaign search, the CSV, the printable report and the
share page all read the sentence, and a campaign posted before this existed has
a sentence and no structure and goes on working untouched.

What is pinned here:

- one vocabulary, mirrored in `lib/deliverables.js`, and this fails if they
  drift;
- one resolver behind every write path, so the structure and the sentence
  cannot describe different briefs;
- an absent structure reads as `[]`, never as "asked for nothing";
- every surface that emits a fee-bearing campaign emits the items beside the
  sentence.
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
LIB = FRONTEND / "src" / "lib" / "deliverables.js"
PICKER = FRONTEND / "src" / "components" / "DeliverablePicker.jsx"
DISPLAY = FRONTEND / "src" / "components" / "Deliverables.jsx"
POST_FORM = FRONTEND / "src" / "pages" / "PostCampaign.jsx"


def no_comments(path: Path) -> str:
    """Source with its comments stripped — a rule about what the code does must
    not pass on the comment saying it does it."""
    src = path.read_text()
    src = re.sub(r"\{/\*.*?\*/\}", "", src, flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


# ---------------------------------------------------------------------------
# One vocabulary
# ---------------------------------------------------------------------------


def test_the_five_types_are_the_ones_the_product_deals_in():
    assert list(server.DELIVERABLE_TYPES) == [
        "reel",
        "story",
        "static_post",
        "youtube_short",
        "video",
    ]


def test_every_type_has_a_singular_and_a_plural():
    """The derived sentence is read by creators. "3 story" is not English, and
    "1 youtube short" is not the name of anything."""
    for key in server.DELIVERABLE_TYPES:
        assert server._DELIVERABLE_SINGULARS[key]
        assert server._DELIVERABLE_PLURALS[key]
    assert server._DELIVERABLE_SINGULARS["youtube_short"] == "YouTube Short"
    assert server._DELIVERABLE_PLURALS["story"] == "stories"


def test_the_frontend_mirrors_the_vocabulary():
    """`lib/deliverables.js` is a copy, so a test has to fail when it drifts —
    the same arrangement `followerTiers.js` and `shootWindows.js` use."""
    js = LIB.read_text()
    for key, label in server.DELIVERABLE_TYPES.items():
        assert f"{key}: \"{label}\"" in js, f"{key} is missing or relabelled in {LIB.name}"
    for key, word in server._DELIVERABLE_SINGULARS.items():
        assert f"{key}: \"{word}\"" in js, f"singular for {key} drifted"
    for key, word in server._DELIVERABLE_PLURALS.items():
        assert f"{key}: \"{word}\"" in js, f"plural for {key} drifted"
    assert f"MAX_DELIVERABLE_QUANTITY = {server.MAX_DELIVERABLE_QUANTITY}" in js


def test_the_payload_model_accepts_exactly_those_types():
    """Typed on the model rather than checked in the handler, so a fifth format
    cannot arrive through a client nobody updated."""
    for key in server.DELIVERABLE_TYPES:
        server.DeliverableItem(type=key, quantity=1)
    with pytest.raises(Exception):
        server.DeliverableItem(type="carousel", quantity=1)
    with pytest.raises(Exception):
        server.DeliverableItem(type="reel", quantity=0)
    with pytest.raises(Exception):
        server.DeliverableItem(
            type="reel", quantity=server.MAX_DELIVERABLE_QUANTITY + 1
        )


# ---------------------------------------------------------------------------
# Cleaning and the derived sentence
# ---------------------------------------------------------------------------


def test_unknown_types_and_empty_quantities_are_dropped():
    assert server._clean_deliverables(
        [
            {"type": "reel", "quantity": 2},
            {"type": "carousel", "quantity": 3},
            {"type": "story", "quantity": 0},
            {"type": "video", "quantity": "not a number"},
        ]
    ) == [{"type": "reel", "quantity": 2}]


def test_two_rows_of_one_type_are_one_ask():
    """A creator reading "1 reel · 2 reels" would reasonably wonder whether they
    were different reels."""
    assert server._clean_deliverables(
        [{"type": "reel", "quantity": 1}, {"type": "reel", "quantity": 2}]
    ) == [{"type": "reel", "quantity": 3}]


def test_the_order_is_the_vocabularys_own():
    """Two campaigns asking for the same thing read the same way round."""
    scrambled = [
        {"type": "video", "quantity": 1},
        {"type": "reel", "quantity": 1},
        {"type": "story", "quantity": 1},
    ]
    assert [i["type"] for i in server._clean_deliverables(scrambled)] == [
        "reel",
        "story",
        "video",
    ]


def test_the_sentence_counts_and_pluralises():
    assert (
        server._deliverables_text(
            [{"type": "reel", "quantity": 1}, {"type": "story", "quantity": 3}]
        )
        == "1 reel · 3 stories"
    )
    assert (
        server._deliverables_text([{"type": "youtube_short", "quantity": 1}])
        == "1 YouTube Short"
    )


def test_a_quantity_cannot_exceed_the_ceiling():
    assert server._clean_deliverables(
        [{"type": "reel", "quantity": 40}, {"type": "reel", "quantity": 40}]
    ) == [{"type": "reel", "quantity": server.MAX_DELIVERABLE_QUANTITY}]


# ---------------------------------------------------------------------------
# The reader, and campaigns written before the field existed
# ---------------------------------------------------------------------------


def test_an_absent_structure_reads_as_empty_not_as_nothing_asked_for():
    """The migration guarantee. A campaign posted before this field has a
    sentence and no items, and `[]` is what tells every surface to read it."""
    old = {"deliverables": "1 reel + 3 stories, tag @us"}
    assert server._deliverable_items(old) == []
    assert old["deliverables"] == "1 reel + 3 stories, tag @us"


def test_the_reader_cleans_what_it_finds():
    assert server._deliverable_items(
        {"deliverable_items": [{"type": "nope", "quantity": 2}]}
    ) == []


# ---------------------------------------------------------------------------
# One resolver behind every write
# ---------------------------------------------------------------------------


def test_items_win_and_the_sentence_is_derived_from_them():
    out = server._resolve_deliverables(
        [{"type": "reel", "quantity": 2}], "whatever the client sent", True
    )
    assert out == {
        "deliverable_items": [{"type": "reel", "quantity": 2}],
        "deliverables": "2 reels",
    }


def test_a_bare_sentence_is_accepted_and_clears_the_structure():
    """That is the shape a pre-field campaign takes coming back through an edit.
    Writing the sentence without clearing the items would leave a brief whose
    words and whose counted pieces describe different asks."""
    out = server._resolve_deliverables(None, "1 reel + 3 stories", False)
    assert out == {"deliverable_items": [], "deliverables": "1 reel + 3 stories"}


def test_rows_that_all_fall_away_are_refused_rather_than_ignored():
    """A form that looks filled in and asks for nothing."""
    with pytest.raises(HTTPException) as exc:
        server._resolve_deliverables([{"type": "reel", "quantity": 0}], None, True)
    assert exc.value.status_code == 422
    assert "quantity" in exc.value.detail.lower()


def test_nothing_at_all_is_refused_when_it_is_required():
    with pytest.raises(HTTPException) as exc:
        server._resolve_deliverables(None, None, True)
    assert exc.value.status_code == 422


def test_nothing_at_all_is_allowed_when_it_is_not_required():
    """An edit that touches the title leaves the deliverables alone."""
    assert server._resolve_deliverables(None, None, False) == {}


def test_both_write_paths_go_through_the_resolver():
    """Two paths to one field is how two versions of it drift apart — the same
    rule `_resolve_agreed_amount` holds for the fee."""
    src = server.__file__
    body = Path(src).read_text()
    for handler in ("create_brand_campaign", "update_brand_campaign", "admin_update_campaign"):
        start = body.index(f"def {handler}(")
        chunk = body[start : start + 6000]
        assert "_resolve_deliverables(" in chunk, (
            f"{handler} writes deliverables without the resolver"
        )


def test_no_write_path_assigns_the_sentence_directly():
    """`update["deliverables"] = ...` anywhere in a handler is the shape of the
    bug this prevents: a sentence written without the structure it describes."""
    body = Path(server.__file__).read_text()
    assert not re.search(r'^\s*update\["deliverables"\]\s*=', body, re.M)
    assert not re.search(r'^\s*"deliverables":\s*payload\.deliverables', body, re.M)


# ---------------------------------------------------------------------------
# The round trip, through the real handlers
# ---------------------------------------------------------------------------


BRIEF = {
    "title": "Weekend brunch reel",
    "brief": "A brief.",
    "deliverable_items": [
        {"type": "reel", "quantity": 1},
        {"type": "story", "quantity": 3},
    ],
    "budget_per_creator": 8000,
    "category": "fnb",
    "area": "Indiranagar",
    "creators_needed": 2,
    "campaign_type": "group_event",
    "event_date": datetime.now(timezone.utc) + timedelta(days=10),
}


def _post(body: dict):
    """Run the real POST handler against a mock database and return what it
    stored alongside what it answered with."""

    async def go():
        db = AsyncMongoMockClient()["deliverables"]
        original = server.db
        server.db = db
        try:
            uid = ObjectId()
            await db.users.insert_one(
                {"_id": uid, "role": "brand_manager", "name": "Third Wave", "brand_id": uid}
            )
            await db.brand_profiles.insert_one(
                {"user_id": uid, "business_name": "Third Wave", "verified": True}
            )
            user = {"_id": uid, "role": "brand_manager", "name": "Third Wave"}
            payload = server.PostCampaignPayload(**body)
            response = await server.create_brand_campaign(payload, user)
            stored = await db.campaigns.find_one({"title": body["title"]})
            return stored, response
        finally:
            server.db = original

    return asyncio.run(go())


def test_posting_a_brief_stores_the_structure_and_the_derived_sentence():
    stored, response = _post(BRIEF)

    assert stored["deliverable_items"] == [
        {"type": "reel", "quantity": 1},
        {"type": "story", "quantity": 3},
    ]
    assert stored["deliverables"] == "1 reel · 3 stories"
    # And it comes back the same way, so the form that posted it can re-seed.
    assert response["deliverable_items"] == stored["deliverable_items"]
    assert response["deliverables"] == stored["deliverables"]


def test_posting_a_brief_with_no_deliverables_is_refused_with_the_reason():
    with pytest.raises(HTTPException) as exc:
        _post({**BRIEF, "deliverable_items": []})
    assert exc.value.status_code == 422
    assert "deliverable" in str(exc.value.detail).lower()


def test_the_sentence_is_still_what_the_keyword_search_matches():
    """`/campaigns?q=` regexes title, brief and deliverables. Deriving the
    sentence rather than dropping it is what keeps that working."""
    body = Path(server.__file__).read_text()
    assert '{"deliverables": {"$regex": term, "$options": "i"}}' in body


# ---------------------------------------------------------------------------
# What the surfaces get
# ---------------------------------------------------------------------------


def test_every_campaign_serializer_emits_the_items_beside_the_sentence():
    """A surface with the sentence and no items falls back correctly, but a
    serializer that never grew the field is a screen frozen on prose."""
    body = Path(server.__file__).read_text()
    for fn in ("_serialize_campaign", "_serialize_brand_campaign"):
        start = body.index(f"def {fn}(")
        chunk = body[start : start + 6000]
        assert '"deliverables": doc.get("deliverables")' in chunk
        assert '"deliverable_items": _deliverable_items(doc)' in chunk, (
            f"{fn} emits the sentence without the structure"
        )


# ---------------------------------------------------------------------------
# The form
# ---------------------------------------------------------------------------


def test_the_brand_form_has_no_free_text_deliverables_box():
    """The whole point. A textarea beside the picker is the picker being
    optional."""
    src = no_comments(POST_FORM)
    assert "pc-deliverables-input" not in src
    assert "<DeliverablePicker" in src


def test_the_brand_form_posts_the_structured_field():
    src = no_comments(POST_FORM)
    assert "deliverable_items: toDeliverableItems(deliverables)" in src
    assert "deliverables: deliverables.trim()" not in src


def test_the_edit_round_trip_reseeds_the_picker():
    """Re-seeded from the structure, or correcting a typo in the title would
    silently clear what the brief asks for — the same trap the venue fields
    fell into."""
    src = no_comments(POST_FORM)
    assert "fromDeliverableItems(data.deliverable_items)" in src


def test_the_admin_dialog_uses_the_same_picker():
    """An admin editing a brief and a brand posting one must produce the same
    shape, or the console is the way a campaign gets prose again."""
    src = no_comments(FRONTEND / "src" / "components" / "admin" / "dialogs.jsx")
    assert "<DeliverablePicker" in src
    assert "changes.deliverables =" not in src


def test_zero_is_how_the_picker_says_no():
    """No checkbox beside the number: a ticked row with a quantity of nothing
    is a state the control cannot reach because it does not exist."""
    src = no_comments(PICKER)
    assert "checkbox" not in src.lower()
    assert "if (qty === 0) delete out[key]" in src


def test_the_display_falls_back_to_the_sentence():
    """A campaign written before the structured field renders its words, and
    the same component draws both — so no screen has to know which kind of
    campaign it is looking at."""
    src = no_comments(DISPLAY)
    assert "items.length === 0" in src
    assert "campaign?.deliverables" in src


@pytest.mark.parametrize(
    "path",
    [
        "src/pages/CampaignDetail.jsx",
        "src/pages/Campaigns.jsx",
        "src/components/creator/Suggested.jsx",
        "src/components/admin/Reviews.jsx",
        "src/components/admin/CampaignDetailPage.jsx",
    ],
)
def test_no_surface_prints_the_raw_sentence_any_more(path):
    """One component wherever the ask is shown. A surface reaching for
    `.deliverables` directly is one that will go on showing prose after every
    brief has structure."""
    src = no_comments(FRONTEND / path)
    assert not re.search(r"\{\s*\w+\.deliverables\s*\}", src), (
        f"{path} still renders the raw sentence"
    )
