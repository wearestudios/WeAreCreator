""""Still needed before we can check you" has to be true.

The list was pure server state: it named what the *stored* profile was missing
and never looked at the form it sits under. So a brand filled every box, looked
down, and was told the boxes were empty — Category included, which is two
sections up the same page. The Save button that would have made the list agree
is 200px above, in a different section, and `Send for verification` was
disabled with no explanation of which button to press first.

Two halves to the fix, and both are pinned here:

- the checklist **filters the server's list by what is on screen**, so a field
  disappears when it is filled rather than when it is saved — the labels stay
  the server's, so there is still one vocabulary;
- `Send for verification` **saves first**, because the route judges the stored
  profile and noticing a distant Save button is not the price of submitting.

The round trip below is the other half of the guarantee: it drives the real
handler with the body the real form sends, so a field renamed on one side and
not the other fails here rather than in somebody's onboarding.
"""
import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from mongomock_motor import AsyncMongoMockClient

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend"
FORM = FRONTEND / "src" / "pages" / "BrandOnboarding.jsx"


def form_source() -> str:
    """The form with its comments stripped — a rule about what the code does
    must not pass on the comment saying it does it."""
    src = FORM.read_text()
    src = re.sub(r"\{/\*.*?\*/\}", "", src, flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


# Exactly the body `BrandOnboarding.jsx` PUTs, keys and all.
FILLED = {
    "business_name": "Third Wave Coffee",
    "category": "fnb",
    "areas": ["Indiranagar"],
    "tagline": "Coffee, properly",
    "about": "A specialty coffee roaster.",
    "city": "Bengaluru",
    "outlets": [],
    "content_types": [],
    "preferred_follower_tier": None,
    "typical_budget_band": None,
    "legal_entity_name": "Third Wave Coffee Pvt Ltd",
    "business_type": "private_limited",
    "registered_address": "12 MG Road, Bengaluru 560001",
    "gst_number": None,
    "website": None,
    "contact_person_name": "Anish Kamdar",
    "contact_person_designation": "Marketing Lead",
    "contact_email": "Anish@ThirdWave.in",
}


def _save(body: dict):
    """Run the real PUT handler against a mock database, return what it stored
    and what the response said was missing."""

    async def go():
        db = AsyncMongoMockClient()["checklist"]
        original = server.db
        server.db = db
        try:
            uid = ObjectId()
            await db.users.insert_one(
                {"_id": uid, "role": "brand_manager", "name": "Third Wave Coffee"}
            )
            await db.brand_profiles.insert_one(
                {
                    "user_id": uid,
                    "business_name": "Third Wave Coffee",
                    "created_at": datetime.now(timezone.utc),
                }
            )
            payload = server.BrandProfileUpdate(**body)
            response = await server.update_brand_profile(
                payload, {"_id": uid, "role": "brand_manager", "name": "Third Wave"}
            )
            stored = await db.brand_profiles.find_one({"user_id": uid})
            return stored, response
        finally:
            server.db = original

    return asyncio.run(go())


# ---------------------------------------------------------------------------
# The round trip
# ---------------------------------------------------------------------------


def test_a_fully_filled_profile_reports_nothing_missing():
    """The test the checklist bug asked for: save everything, need nothing."""
    stored, response = _save(FILLED)

    assert server._brand_missing_fields(stored) == []
    assert response["verification"]["missing_fields"] == []


def test_every_required_field_survives_the_save_under_its_own_name():
    """A rename on one side and not the other is exactly the bug this guards:
    the value is stored, just not where the checklist looks for it."""
    stored, _ = _save(FILLED)

    for field, label in server._BRAND_REQUIRED_FIELDS:
        assert stored.get(field), f"{label} ({field}) did not survive the save"


def test_the_form_sends_every_field_the_checklist_asks_for():
    """A field the checklist requires and the form never sends is a checklist
    item nobody can ever clear."""
    body = form_source()
    sent = body[body.index('api.put("/brand/profile"') :]
    sent = sent[: sent.index("});")]

    for field, label in server._BRAND_REQUIRED_FIELDS:
        assert f"{field}:" in sent or f"{field},"in sent, (
            f"the form never sends {field} ({label})"
        )


def test_the_update_model_accepts_every_required_field():
    for field, label in server._BRAND_REQUIRED_FIELDS:
        assert field in server.BrandProfileUpdate.model_fields, (
            f"{label} cannot be sent at all"
        )


def test_a_missing_field_is_still_reported():
    """The list has to keep working — a checklist that never says anything is
    as wrong as one that never stops."""
    without_address = {**FILLED, "registered_address": None}
    stored, response = _save(without_address)

    labels = [row["label"] for row in response["verification"]["missing_fields"]]
    assert labels == ["Registered address"]


def test_whitespace_is_not_a_filled_field():
    stored, _ = _save({**FILLED, "contact_person_name": "   "})

    assert [r["field"] for r in server._brand_missing_fields(stored)] == [
        "contact_person_name"
    ]


# ---------------------------------------------------------------------------
# The form
# ---------------------------------------------------------------------------


def test_the_checklist_reads_what_is_on_screen():
    """It named the last save. Somebody who has just filled seven boxes being
    told seven boxes are empty is the whole bug."""
    src = form_source()

    assert "const liveValues = {" in src
    assert "required.filter((m) => !String(liveValues[m.field] ?? \"\").trim())" in src


def test_the_checklist_keeps_the_server_labels():
    """Filtering locally must not become deciding locally: the required set and
    its wording stay the server's, or the form and the 409 disagree."""
    src = form_source()

    # The required set and its wording come off the response; the form only
    # decides which of them are still empty. Which fields are covered is the
    # live-map test below — a shorthand key (`category,`) is a real entry and
    # a substring check for "category:" is not the way to find it. Checked, by
    # writing that check and watching it fail on a field that was there.
    assert "verification?.missing_fields" in src
    assert "m.label" in src, "the list renders the server's label"
    assert "_BRAND_REQUIRED_FIELDS" not in src, "the required set is not copied here"


def test_sending_for_verification_saves_what_is_on_screen_first():
    """The route judges the stored profile. Noticing a Save button two hundred
    pixels up the page is not the price of submitting."""
    src = form_source()
    submit = src[src.index("const onSubmitForVerification") :]
    submit = submit[: submit.index("};")]

    assert "saveProfile(" in submit, "submit does not save first"
    assert submit.index("saveProfile(") < submit.index(
        'api.post("/brand/verification/submit")'
    ), "it submits before it saves"


def test_one_save_implementation_behind_both_buttons():
    src = form_source()

    assert "const saveProfile = async (" in src
    assert src.count('api.put("/brand/profile"') == 1


@pytest.mark.parametrize(
    "field",
    [f for f, _ in server._BRAND_REQUIRED_FIELDS],
)
def test_the_live_map_covers_every_required_field(field):
    """A field absent from `liveValues` reads as empty forever, so it would
    stay on the checklist however full the box is."""
    src = form_source()
    live = src[src.index("const liveValues = {") :]
    live = live[: live.index("};")]

    assert field in live, f"{field} is not in the live-value map"
