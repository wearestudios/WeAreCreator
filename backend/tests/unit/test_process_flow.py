"""The application, read as one process.

**Eight friendly stages over twelve internal states, and the states did not
change.** The ladder in `COLLAB_STATE_ORDER` is the machine — it is what
transitions are checked against, what audit lines name, and what a 409 is about
— and it is unreadable: "commercial agreed", "draft approved" and "in payment"
are twelve boxes describing our bookkeeping, and nobody reading them can tell
which one means "nearly done".

So `_process_flow` is a presentation over the machine. Nothing in it decides
anything; it groups. What is pinned here:

- every state lands in exactly one stage, and a state missing from the mapping
  fails here rather than silently rendering nothing;
- the same eight reach the creator, the brand and the admin — that was the
  reported problem, three surfaces with three different pictures;
- the *voice* changes and the picture does not: the party who has to act reads
  an instruction, everybody else reads the wait;
- an exit is a banner, not a ninth box.
"""
import inspect
import re
from pathlib import Path

import pytest

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"
FLOW = FRONTEND / "components" / "application" / "ProcessFlow.jsx"


def no_comments(path: Path) -> str:
    src = re.sub(r"\{/\*.*?\*/\}", "", path.read_text(), flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


DRAFT = {"requires_draft_approval": True}
PLAIN = {}
CREATOR = {"role": "creator"}
BRAND = {"role": "brand_manager"}
ADMIN = {"role": "admin"}


# ---------------------------------------------------------------------------
# The eight
# ---------------------------------------------------------------------------


def test_the_eight_stages_are_the_ones_asked_for():
    assert [label for _, label in server.PROCESS_STAGES] == [
        "Submitted",
        "Verified",
        "Negotiated",
        "Scheduled",
        "Attended",
        "Content review",
        "Content delivery",
        "Payment",
    ]


@pytest.mark.parametrize("campaign", [DRAFT, PLAIN], ids=["draft-gate", "no-gate"])
def test_every_internal_state_lands_in_exactly_one_stage(campaign):
    """A state with no stage renders as nothing at all — a stepper that has
    quietly stopped tracking the thing it is about."""
    for state in server.COLLAB_STATE_ORDER:
        stage = server._stage_of(state, campaign)
        assert stage in server.PROCESS_STAGE_KEYS, f"{state} maps to {stage!r}"


def test_the_grouping_is_the_one_the_brief_named():
    """Applied is Submitted; verified *and* accepted are Verified; and so on.
    Spelled out rather than derived, because this table is the whole feature."""
    assert server._stage_of("applied", DRAFT) == "submitted"
    assert server._stage_of("verified", DRAFT) == "verified"
    assert server._stage_of("accepted", DRAFT) == "verified"
    assert server._stage_of("commercial_agreed", DRAFT) == "negotiated"
    assert server._stage_of("slot_booked", DRAFT) == "scheduled"
    assert server._stage_of("attended", DRAFT) == "attended"
    assert server._stage_of("draft_submitted", DRAFT) == "content_review"
    assert server._stage_of("draft_approved", DRAFT) == "content_review"
    assert server._stage_of("content_submitted", DRAFT) == "content_delivery"
    assert server._stage_of("in_payment", DRAFT) == "payment"
    assert server._stage_of("closed", DRAFT) == "payment"


def test_without_a_draft_gate_the_two_content_stages_shift_by_one():
    """**Not a fudge to keep the count at eight.** Without the gate the live
    link *is* the thing being reviewed, and approving it is the delivery being
    accepted. With the gate, the draft is the review and the live post is the
    delivery. What would be false is drawing a "Content review" stage on a
    campaign that never reviews anything."""
    assert server._stage_of("content_submitted", PLAIN) == "content_review"
    assert server._stage_of("content_approved", PLAIN) == "content_delivery"
    # And the draft states are simply not reachable there — they are not on
    # that campaign's ladder at all.
    assert "draft_submitted" not in server._collab_ladder(PLAIN)


def test_the_underlying_ladder_is_untouched():
    """The whole point of a presentation layer. If this ever fails, the flow
    stopped being a view and started being a second state machine."""
    assert server.COLLAB_STATE_ORDER == [
        "applied",
        "verified",
        "accepted",
        "commercial_agreed",
        "slot_booked",
        "attended",
        "draft_submitted",
        "draft_approved",
        "content_submitted",
        "content_approved",
        "in_payment",
        "closed",
    ]


# ---------------------------------------------------------------------------
# Where it stands
# ---------------------------------------------------------------------------


def test_the_stages_before_the_current_one_are_done_and_the_rest_are_not():
    flow = server._process_flow({"state": "attended"}, DRAFT)

    done = [s["key"] for s in flow["stages"] if s["done"]]
    current = [s["key"] for s in flow["stages"] if s["current"]]
    assert current == ["attended"]
    assert done == ["submitted", "verified", "negotiated", "scheduled"]
    assert flow["stage_number"] == 5
    assert flow["stage_count"] == 8


def test_an_exit_stands_on_no_stage_at_all():
    """It is the line stopping, not a ninth box."""
    for state in ("declined", "cancelled"):
        flow = server._process_flow({"state": state}, DRAFT)
        assert flow["stage"] is None
        assert flow["stage_number"] is None
        assert not any(s["current"] for s in flow["stages"])
        assert flow["banner"]["tone"] == "ended"


def test_changes_requested_is_a_banner_on_the_stage_it_is_already_on():
    """A send-back is this stage again, with a reason. Drawing it as a step
    backwards would lose the fact that the work exists."""
    flow = server._process_flow(
        {"state": "attended", "draft_revision_note": "Re-shoot the opening"}, DRAFT
    )
    assert flow["stage"] == "attended"
    assert flow["banner"] == {
        "tone": "attention",
        "title": "Changes requested",
        "detail": "Re-shoot the opening",
    }


def test_a_plain_attended_carries_no_banner():
    assert server._process_flow({"state": "attended"}, DRAFT)["banner"] is None


# ---------------------------------------------------------------------------
# One picture, three voices
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("viewer", [CREATOR, BRAND, ADMIN, None])
def test_every_viewer_sees_the_same_stages_in_the_same_place(viewer):
    """This is the reported bug, pinned: the creator's own bar had six stages,
    the console had the raw twelve, and the brand had neither, so "where is
    this" had a different answer depending on who was asked."""
    flow = server._process_flow({"state": "commercial_agreed"}, DRAFT, viewer=viewer)

    assert [s["key"] for s in flow["stages"]] == list(server.PROCESS_STAGE_KEYS)
    assert flow["stage"] == "negotiated"
    assert flow["stage_number"] == 3


def test_the_party_who_must_act_reads_an_instruction():
    creator = server._process_flow({"state": "commercial_agreed"}, DRAFT, viewer=CREATOR)
    assert creator["next_action"]["label"] == "Pick your slot"
    assert creator["next_action"]["owner"] == "creator"


def test_everybody_else_reads_the_wait():
    for viewer in (BRAND, ADMIN, None):
        flow = server._process_flow({"state": "commercial_agreed"}, DRAFT, viewer=viewer)
        assert flow["next_action"]["label"] == "Waiting for the creator to pick a slot"


def test_the_instruction_names_the_thing_and_not_the_state():
    """"Upload your draft", not "draft_submitted". The whole reason the states
    are not shown."""
    said = {
        server._process_flow({"state": s}, DRAFT, viewer=CREATOR)["next_action"]["label"]
        for s in ("attended", "draft_approved")
    }
    assert said == {"Upload your draft", "Publish and send the live link"}
    assert not any("_" in phrase for phrase in said)


def test_the_same_state_says_different_things_on_the_two_kinds_of_campaign():
    """After attendance, one campaign wants a draft and the other wants a live
    link — same state, and the creator is the one who has to act on the
    difference."""
    with_gate = server._process_flow({"state": "attended"}, DRAFT, viewer=CREATOR)
    without = server._process_flow({"state": "attended"}, PLAIN, viewer=CREATOR)

    assert with_gate["next_action"]["label"] == "Upload your draft"
    assert without["next_action"]["label"] == "Publish and send the link"


def test_on_a_weare_run_campaign_the_brands_steps_are_ours():
    """A creator told "the brand is reviewing your draft" when our own manager
    is, is a screen lying twice a day."""
    weare = {"execution_owner": "weare", "requires_draft_approval": True}
    flow = server._process_flow({"state": "draft_submitted"}, weare)
    assert flow["next_action"]["owner"] == "admin"

    brand_run = {"execution_owner": "brand", "requires_draft_approval": True}
    assert (
        server._process_flow({"state": "draft_submitted"}, brand_run)["next_action"]["owner"]
        == "brand"
    )


# ---------------------------------------------------------------------------
# Where it is shipped
# ---------------------------------------------------------------------------


def test_the_flow_rides_on_the_lifecycle_every_application_payload_carries():
    flow = server._lifecycle_for({"state": "applied"}, DRAFT)["process"]
    assert [s["key"] for s in flow["stages"]] == list(server.PROCESS_STAGE_KEYS)


@pytest.mark.parametrize(
    "fn", ["_serialize_collab_row", "_serialize_applicant", "get_application"]
)
def test_all_three_views_are_served_the_flow(fn):
    """The creator's dashboard row, the brand's applicant row and the shared
    application screen. One of the three missing it is one surface back to
    guessing."""
    src = inspect.getsource(getattr(server, fn))
    assert "_process_flow(" in src or "_lifecycle_for(" in src, (
        f"{fn} serves an application with no process flow on it"
    )


def test_the_viewer_reaches_the_flow_from_the_request():
    """`/applications/{id}` is read by all three roles off one component, so
    the voice has to be decided from who called rather than from anything the
    client says about itself."""
    src = inspect.getsource(server.get_application)
    assert "viewer=user" in src


# ---------------------------------------------------------------------------
# The component
# ---------------------------------------------------------------------------


def test_the_component_never_asks_who_is_looking():
    """The rule the shared application screen already holds. The server picked
    the voice; a role check here would be a second, disagreeing answer."""
    src = no_comments(FLOW)
    for smell in ('role ===', 'user?.role', 'isAdmin', 'is_admin'):
        assert smell not in src, f"ProcessFlow branches on {smell}"


def test_the_component_does_not_rebuild_the_stage_list():
    """It draws what it is given. A local copy of the eight would drift from
    the server's the first time one was renamed."""
    src = no_comments(FLOW)
    assert "process.stages" in src or "stages = []" in src
    for label in ("Content review", "Negotiated", "Submitted"):
        assert label not in src, f"the component hardcodes the stage label {label!r}"


def test_on_a_phone_it_collapses_to_the_current_stage_and_a_count():
    """Eight boxes on a 390px screen are eight illegible boxes."""
    src = no_comments(FLOW)
    assert "useWide" in src
    assert "Stage ${number} of ${count}" in src
    assert "aria-expanded" in src


@pytest.mark.parametrize(
    "path",
    [
        "components/application/ApplicationDetail.jsx",
        "components/creator/ActiveCampaigns.jsx",
        "pages/BrandCampaignApplicants.jsx",
    ],
)
def test_all_three_surfaces_draw_the_same_component(path):
    assert "<ProcessFlow" in no_comments(FRONTEND / path)


def test_the_creators_own_six_stage_bar_is_gone():
    """It was the third copy of the lifecycle in this repository, and the three
    disagreed. Leaving it beside the shared one would be the drift the whole
    change exists to end."""
    shared = no_comments(FRONTEND / "components" / "creator" / "shared.jsx")
    assert "export const LIFECYCLE" not in shared
    assert "export const lifecycleFor" not in shared
    assert "export const stageIndexFor" not in shared
