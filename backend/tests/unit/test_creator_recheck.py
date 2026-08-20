"""Re-approval when a creator changes something we verified.

A verified creator who changes their handle, their links or where the money
goes has changed one of the things we actually checked. They keep their
approval and their place in the directory — but new pitches wait until we have
looked again.

The set is `MATERIAL_PROFILE_FIELDS`, in one place, deliberately. It used to be
three fields inline in the update handler, which missed YouTube, Facebook and
every payout detail. Everything else on the form — the About paragraph, the
neighbourhood, their rate, what they cover — is theirs to change freely, and
putting somebody back in a queue for fixing a typo is how a profile stops being
kept up to date at all.

**A re-check is not a downgrade.** `verification_status` stays `verified` and
`pending_review` goes true. Sending them back to `pending` would erase the
record that they were ever approved — the reason suspension is separate from
rejection — and would empty the admin queue, which keys on exactly that pair.
"""
import inspect
import re
from pathlib import Path

import pytest

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"


def verified(**kw):
    base = {"verification_status": "verified", "pending_review": False}
    base.update(kw)
    return base


# --- What counts as material ------------------------------------------------


@pytest.mark.parametrize(
    "field",
    ["name", "instagram_handle", "instagram_profile_url", "youtube_url",
     "facebook_url", "payout_upi", "payout_account_name", "pan", "gstin"],
)
def test_the_things_we_verified_are_material(field):
    assert field in server.MATERIAL_PROFILE_FIELDS


def test_city_stays_material():
    """It was material before this change and still is — a brand filters on it
    and a shoot is booked on it."""
    assert "city" in server.MATERIAL_PROFILE_FIELDS


@pytest.mark.parametrize(
    "field", ["about", "address", "base_rate", "niches", "genres", "platforms",
              "full_address", "location_lat", "profile_image_url", "follower_count"]
)
def test_the_rest_is_theirs_to_change(field):
    """A re-check on a typo is how a profile stops being kept up to date."""
    assert field not in server.MATERIAL_PROFILE_FIELDS


def test_every_material_field_has_words_for_the_creator():
    """The notice names what changed. A field with no label would produce
    "you changed instagram_handle"."""
    for field, label in server.MATERIAL_PROFILE_FIELDS.items():
        assert label and not label.startswith(field), f"{field} has no human label"


def test_it_is_defined_in_exactly_one_place():
    source = inspect.getsource(server.update_creator_profile)

    assert "material_fields" not in source, "the old inline list is gone"
    assert "_material_changes(existing, update)" in source


# --- Detecting a change -----------------------------------------------------


def test_a_changed_material_field_is_detected():
    changed = server._material_changes({"instagram_handle": "asha"}, {"instagram_handle": "asha2"})

    assert changed == ["your Instagram handle"]


def test_resending_the_same_value_is_not_a_change():
    """A form that round-trips every field sends all of them on every save."""
    assert server._material_changes({"name": "Asha"}, {"name": "Asha"}) == []


def test_a_field_absent_from_the_save_is_not_a_change():
    """Partial saves are the norm — an omitted key means "leave it alone"."""
    assert server._material_changes({"name": "Asha"}, {"about": "hello"}) == []


def test_empty_and_none_are_the_same_absence():
    """"" and None both mean "not set"; treating them as different would
    re-check somebody for clearing a field they never filled."""
    assert server._material_changes({"youtube_url": None}, {"youtube_url": ""}) == []


def test_several_changes_are_all_named():
    changed = server._material_changes(
        {"name": "A", "pan": None}, {"name": "B", "pan": "ABCDE1234F"}
    )

    assert len(changed) == 2


# --- What the state means ---------------------------------------------------


def test_a_rechecking_creator_is_still_verified():
    assert server._awaiting_recheck(verified(pending_review=True)) is True


def test_a_settled_verified_creator_is_not_rechecking():
    assert server._awaiting_recheck(verified()) is False


def test_someone_never_approved_is_not_rechecking():
    """`pending_review` on an unverified profile means "submitted", which is a
    different queue and a different message."""
    assert server._awaiting_recheck(
        {"verification_status": "pending", "pending_review": True}
    ) is False


def test_a_recheck_never_rewrites_verification_status():
    """The whole design decision, as an assertion."""
    source = inspect.getsource(server.update_creator_profile)

    assert 'update["verification_status"]' not in source


def test_the_admin_queue_still_keys_on_the_same_pair():
    """Downgrading to `pending` would empty this."""
    source = Path(server.__file__).read_text()

    assert '{"verification_status": "verified", "pending_review": True}' in source


# --- What it blocks, and what it does not -----------------------------------


# The three doors all go through `_creator_block` now, which folds the
# re-check together with suspension and a lapsed verification. Asserted on the
# behaviour rather than on the call, so the next thing folded in there does not
# break these — what matters is that a re-checking creator is refused, not
# which function says so.
def _blocked_reason(**profile):
    return server._creator_block({"verification_status": "verified", **profile}, {})


def test_new_applications_are_refused_while_rechecking():
    assert _blocked_reason(pending_review=True)["code"] == "pending_recheck"
    assert "another look" in _blocked_reason(pending_review=True)["message"]
    # And the apply route consults it.
    assert "_creator_block(" in inspect.getsource(server.apply_to_campaign)


def test_a_creator_in_good_standing_is_not_blocked():
    """The other half of the rule, and the one that would break silently: a
    gate that refuses everybody passes every "is it refused" test."""
    assert server._creator_block({"verification_status": "verified"}, {}) is None


def test_the_button_agrees_with_the_api():
    """`can_apply` is computed server-side so the UI never offers a pitch the
    API will refuse — and through the *same reader*, or the two drift."""
    source = inspect.getsource(server.get_campaign)

    assert "_creator_block(" in source


def test_an_invite_to_a_rechecking_creator_is_refused():
    """They cannot accept it, so the invite would go nowhere — the same
    reasoning the unverified check already gives."""
    source = inspect.getsource(server._invite_creators)

    assert "_creator_block(" in source


def test_nothing_touches_existing_collaborations():
    """Accepted work carries on. The gate is on the act of applying, so this
    is a matter of where the check is *not*."""
    source = inspect.getsource(server.update_creator_profile)

    assert "collaborations" not in source, (
        "a profile edit must not reach into collaborations"
    )


def test_the_message_says_what_changed_and_how_long():
    message = server._recheck_message(
        {"pending_review_fields": ["your Instagram handle"]}
    )

    assert "your Instagram handle" in message
    assert "48 hours" in message
    assert "already been accepted" in message, "it has to say existing work is safe"


def test_the_message_copes_with_no_recorded_fields():
    """Profiles that went pending before this shipped have no field list."""
    message = server._recheck_message({})

    assert "something on your profile" in message
    assert "48 hours" in message


# --- Telling them, once -----------------------------------------------------


def test_they_are_told_on_the_way_in_and_not_again():
    source = inspect.getsource(server.update_creator_profile)
    block = source[source.index("if changed_labels and not bool"):][:400]

    assert 'not bool(existing.get("pending_review"))' in block, (
        "saving again while already pending must not notify a second time"
    )
    assert "notify(" in block


def test_the_recheck_is_audited():
    source = inspect.getsource(server.update_creator_profile)

    assert "creator.profile_recheck" in source


def test_a_decision_clears_the_flag_and_the_labels():
    """Stale labels would make the next re-check tell them about a change we
    already looked at."""
    source = inspect.getsource(server._set_creator_verification)

    assert '"pending_review": False' in source
    assert '"pending_review_fields": []' in source


# --- The creator can see all of this ----------------------------------------


def test_the_profile_payload_carries_what_is_being_rechecked():
    source = inspect.getsource(server._serialize_creator_profile)

    assert "pending_review_fields" in source


def test_the_admin_sees_which_fields_changed():
    """Otherwise a re-check is a diff against a profile nobody kept a copy of."""
    source = inspect.getsource(server.get_creator_detail)

    assert "pending_review_fields" in source


# --- The frontend -----------------------------------------------------------


def test_there_is_a_read_only_profile_page():
    page = FRONTEND / "pages" / "CreatorProfile.jsx"

    assert page.is_file()
    source = page.read_text()
    # It reads; it does not write.
    assert "api.put" not in source and "api.post" not in source


def test_the_profile_page_links_to_editing_rather_than_being_the_editor():
    source = (FRONTEND / "pages" / "CreatorProfile.jsx").read_text()

    assert '"/onboarding/creator"' in source
    assert "<Input" not in source, "a read-only view has no inputs"


def test_the_profile_page_shows_the_recheck_notice():
    source = (FRONTEND / "pages" / "CreatorProfile.jsx").read_text()

    assert "pending_review_fields" in source
    assert "48 hours" in source


def test_the_route_exists_and_is_creator_only():
    source = (FRONTEND / "App.js").read_text()
    block = source[source.index('path="/profile"'):][:300]

    assert 'roles={["creator"]}' in block
    assert "<CreatorProfile />" in block


def test_the_avatar_menu_is_creator_only():
    """An admin's navigation is the console; a brand's is its dashboard.
    Neither has a profile this would open onto."""
    source = (FRONTEND / "components" / "Navbar.jsx").read_text()

    assert 'user.role === "creator" ? (' in source
    assert "CreatorAvatarMenu" in source


def test_the_menu_offers_exactly_the_two_things_asked_for():
    source = (FRONTEND / "components" / "CreatorAvatarMenu.jsx").read_text()

    assert "My profile" in source
    assert "Log out" in source
    assert '"/profile"' in source


def test_the_menu_closes_on_escape_and_outside_click():
    """A menu that only closes by picking something is one people tap around."""
    source = (FRONTEND / "components" / "CreatorAvatarMenu.jsx").read_text()

    assert '"Escape"' in source
    assert "mousedown" in source
