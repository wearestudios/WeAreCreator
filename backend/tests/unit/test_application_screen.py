"""The application screen: one lifecycle, one next action, one set of rules.

Two things this file holds.

**The commercial is captured before an application can move on.** A negotiated
brief has no fee until somebody agrees one, so the fee step refuses without a
figure. A fixed brief's fee is set by the brief, so a per-creator number cannot
quietly rewrite it. A barter brief has no figure at all — and until this, the
fee step demanded one whatever the campaign was, which left every barter
collaboration stuck at `accepted` with no way out.

**Both writers enforce it identically.** The admin advances through
`advance_collaboration`; the brand records the fee through
`brand_record_agreed_amount`. Two paths to one state is exactly how the states
drift apart, so both go through `_resolve_agreed_amount`.
"""
import ast
import inspect
import re
from pathlib import Path

import pytest
from fastapi import HTTPException

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"


def campaign(ctype, budget=5000):
    return {"compensation_type": ctype, "budget_per_creator": budget}


# --- What each kind of brief requires ---------------------------------------


def test_negotiated_refuses_without_an_amount():
    with pytest.raises(HTTPException) as err:
        server._resolve_agreed_amount(campaign("negotiated"), None)

    assert err.value.status_code == 422
    assert "agreed amount" in str(err.value.detail).lower()


def test_negotiated_records_what_was_typed():
    assert server._resolve_agreed_amount(campaign("negotiated"), 7500) == 7500.0


def test_negotiated_refuses_a_nonsense_amount():
    with pytest.raises(HTTPException):
        server._resolve_agreed_amount(campaign("negotiated"), 0)


def test_fixed_prefills_from_the_brief():
    """No amount needed — the brief already said what this pays."""
    assert server._resolve_agreed_amount(campaign("fixed"), None) == 5000.0


def test_fixed_accepts_the_matching_amount():
    """A form that echoes the locked figure back is not an error."""
    assert server._resolve_agreed_amount(campaign("fixed"), 5000) == 5000.0


def test_fixed_refuses_a_different_amount():
    """Locked means locked: a fixed brief pays every creator the same, so a
    per-creator figure here would be a commercial nobody agreed to."""
    with pytest.raises(HTTPException) as err:
        server._resolve_agreed_amount(campaign("fixed"), 9999)

    assert "fixed-fee" in str(err.value.detail)


def test_barter_records_no_amount():
    """None, not 0. Zero reads as "agreed, nothing" on every surface that
    shows money."""
    assert server._resolve_agreed_amount(campaign("barter"), None) is None


def test_barter_refuses_an_amount():
    with pytest.raises(HTTPException) as err:
        server._resolve_agreed_amount(campaign("barter"), 5000)

    assert "barter" in str(err.value.detail).lower()


def test_a_campaign_with_no_type_is_treated_as_fixed():
    """Campaigns predate the field; `_compensation_type` reads a missing one as
    fixed, and this must follow it rather than inventing a fourth behaviour."""
    assert server._resolve_agreed_amount({"budget_per_creator": 4000}, None) == 4000.0


# --- Both writers enforce the same rule -------------------------------------


@pytest.mark.parametrize(
    "fn", [server.advance_collaboration, server.brand_record_agreed_amount]
)
def test_both_fee_writers_go_through_the_resolver(fn):
    assert "_resolve_agreed_amount" in inspect.getsource(fn)


def test_the_brand_writer_no_longer_casts_the_amount_itself():
    """It used to do `round(float(payload.agreed_amount), 2)` unconditionally,
    which is what made barter unreachable on this path too."""
    source = inspect.getsource(server.brand_record_agreed_amount)

    assert "float(payload.agreed_amount)" not in source


def test_the_payload_allows_an_absent_amount():
    """Required at the model level would refuse barter before any handler could
    decide, and the model cannot see the campaign."""
    field = server.AgreedAmountPayload.model_fields["agreed_amount"]

    assert field.default is None
    assert server.AgreedAmountPayload(agreed_amount=None).agreed_amount is None


# --- Whose move is it -------------------------------------------------------


def test_every_state_says_who_acts_next():
    every = set(server.COLLAB_STATE_ORDER) | set(server.TERMINAL_COLLAB_STATES)

    assert every <= set(server._NEXT_ACTION), "a state with no next action"


def test_after_the_fee_is_agreed_the_creator_acts():
    """The point of the fee step: it hands over. If this says anything else,
    the status bar tells an admin to wait on themselves."""
    action = server._next_action({"state": "commercial_agreed"}, campaign("negotiated"))

    assert action["owner"] == "creator"


def test_approval_hands_the_application_to_the_brand():
    assert server._next_action({"state": "verified"})["owner"] == "brand"


def test_an_unapproved_application_is_ours():
    assert server._next_action({"state": "applied"})["owner"] == "admin"


def test_a_finished_application_waits_on_nobody():
    for state in server.TERMINAL_COLLAB_STATES:
        assert server._next_action({"state": state})["owner"] is None


def test_a_personal_table_tells_the_creator_to_pick_a_time():
    """Same step, different instruction: a launch has one time everybody
    shares, a personal table is a window the creator chooses inside."""
    fixed_time = server._next_action(
        {"state": "commercial_agreed"}, {"campaign_type": "launch"}
    )
    own_time = server._next_action(
        {"state": "commercial_agreed"}, {"campaign_type": "personal_table"}
    )

    assert own_time["label"] != fixed_time["label"]
    assert "time" in own_time["label"].lower()


# --- The status bar ---------------------------------------------------------


def test_the_lifecycle_carries_every_step_in_order():
    bar = server._lifecycle_for({"state": "accepted"})

    assert [s["state"] for s in bar["steps"]] == server.COLLAB_STATE_ORDER


def test_the_lifecycle_marks_exactly_one_step_current():
    bar = server._lifecycle_for({"state": "slot_booked"})

    assert [s["state"] for s in bar["steps"] if s["current"]] == ["slot_booked"]


def test_the_lifecycle_marks_everything_before_it_done():
    bar = server._lifecycle_for({"state": "attended"})
    done = [s["state"] for s in bar["steps"] if s["done"]]

    assert done == server.COLLAB_STATE_ORDER[: server.COLLAB_STATE_ORDER.index("attended")]


def test_an_exit_is_not_a_step_on_the_bar():
    """Declined and cancelled are the bar stopping, not an eleventh box."""
    bar = server._lifecycle_for({"state": "declined"})

    assert bar["exited"] is True
    assert not any(s["current"] for s in bar["steps"])
    assert not any(s["done"] for s in bar["steps"])


def test_closed_is_the_end_of_the_ladder_not_an_exit():
    bar = server._lifecycle_for({"state": "closed"})

    assert bar["exited"] is False
    assert bar["steps"][-1]["current"] is True


# --- The commercial block the screen renders --------------------------------


@pytest.mark.parametrize(
    "ctype,required,locked,applies",
    [
        ("negotiated", True, False, True),
        ("fixed", False, True, True),
        ("barter", False, False, False),
    ],
)
def test_the_commercial_block_says_how_the_fee_field_behaves(ctype, required, locked, applies):
    block = server._commercial_for(campaign(ctype), {})

    assert block["amount_required"] is required
    assert block["amount_locked"] is locked
    assert block["amount_applies"] is applies


def test_a_locked_fee_ships_the_figure_to_lock_to():
    assert server._commercial_for(campaign("fixed"), {})["locked_amount"] == 5000


def test_only_a_locked_fee_ships_one():
    for ctype in ("negotiated", "barter"):
        assert server._commercial_for(campaign(ctype), {})["locked_amount"] is None


# --- The screen's own endpoint ----------------------------------------------


def test_the_application_endpoint_is_gated_to_the_three_who_may_see_it():
    source = inspect.getsource(server.get_application)

    assert "_note_readable_collab_or_404" in source, "same three doors as the notes"
    assert "require_roles" in source


def test_the_application_endpoint_projects_the_creator_through_the_allow_list():
    """Shared component, shared payload: a contact detail rendered for one role
    is one waiting to be rendered for the other."""
    source = inspect.getsource(server.get_application)

    assert "_brand_visible_creator" in source


def test_the_brand_never_gets_a_contact_detail_from_it():
    source = inspect.getsource(server.get_application)

    for forbidden in server.BRAND_FORBIDDEN_CREATOR_FIELDS:
        assert f'"{forbidden}"' not in source


# --- The screen reads what the server sends ---------------------------------


def _component(name):
    return (FRONTEND / "components" / "application" / name).read_text()


def test_the_screen_does_not_rebuild_the_state_machine():
    """The steps come from the server. A second copy of the ladder in the
    client is a second thing to keep in step, and drift shows up as a screen
    confidently telling somebody the wrong thing."""
    bar = _component("LifecycleBar.jsx")

    assert "lifecycle.steps" in bar or "steps = []" in bar
    assert "COLLAB_STATE_ORDER" not in bar


def test_the_screen_asks_the_server_which_fee_control_to_draw():
    detail = _component("ApplicationDetail.jsx")

    for flag in ("amount_required", "amount_locked", "amount_applies"):
        assert flag in detail


def test_the_screen_does_not_decide_permissions_by_role():
    """It asks "may this be done", never "am I an admin" — the server already
    knows, and a second opinion in the client is one that can be wrong."""
    detail = _component("ApplicationDetail.jsx")
    code = re.sub(r"//.*|/\*.*?\*/", "", detail, flags=re.S)

    assert 'role === "admin"' not in code
    assert "user?.role" not in code


def test_the_screen_sends_no_amount_when_the_server_owns_it():
    """Barter and a locked fee are the server's numbers. Echoing one back is
    how a stale form rewrites a commercial."""
    detail = _component("ApplicationDetail.jsx")

    assert "commercial.amount_required" in detail
    assert "agreed_amount: Number(amount)" in detail


def test_both_routes_render_the_one_component():
    app_js = (FRONTEND / "App.js").read_text()

    assert app_js.count("<ApplicationDetail") == 2
    assert "/brand/applications/:id" in app_js
    assert 'path="applications/:id"' in app_js
