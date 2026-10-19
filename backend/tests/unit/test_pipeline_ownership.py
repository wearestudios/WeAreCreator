"""The integration harness agrees with the server about who moves each step.

`tests/pipeline.py` walks collaborations through the lifecycle for the
integration suite, which needs a live server and so cannot gate a PR. It kept
`slot_booked` as an admin step for as long as it took somebody to notice that
the server had made booking the creator's alone: the admin advance answered
409, and every integration test that needed a collaboration past
`commercial_agreed` died there. Nothing in CI could see it.

These read the harness's ownership tables against the server's own sets and
ladders, without a server, so the next ownership change fails here — on the
PR that makes it — naming the state, instead of somewhere deep in a run that
nobody gates on.
"""
import importlib.util
from pathlib import Path

import pytest

import server

_HARNESS = Path(__file__).resolve().parents[1] / "pipeline.py"


def _load_harness():
    # By path rather than by putting `tests/` on sys.path, where its test
    # modules would sit beside this directory's under the same names.
    spec = importlib.util.spec_from_file_location("pipeline_harness", _HARNESS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pipeline = _load_harness()

LADDERS = {
    "plain": (pipeline.PIPELINE, {"campaign_type": "personal_table"}),
    "draft-gate": (
        pipeline.DRAFT_PIPELINE,
        {"campaign_type": "personal_table", "requires_draft_approval": True},
    ),
}


def _owner_of(state):
    owners = [who for who, states in pipeline.OWNERS.items() if state in states]
    assert len(owners) == 1, f"'{state}' has owners {owners}"
    return owners[0]


@pytest.mark.parametrize("name", list(LADDERS))
def test_the_harness_ladder_is_the_one_the_server_walks(name):
    ladder, campaign = LADDERS[name]
    assert ["applied"] + ladder == list(server._collab_ladder(campaign)), (
        f"the server's ladder for a {name} campaign has changed — update "
        "PIPELINE / DRAFT_PIPELINE in tests/pipeline.py to match"
    )


@pytest.mark.parametrize("name", list(LADDERS))
def test_every_step_has_exactly_one_owner(name):
    pipeline.check_ownership(LADDERS[name][0])


def test_the_check_names_a_state_nobody_owns(monkeypatch):
    owners = {k: tuple(s for s in v if s != "attended") for k, v in pipeline.OWNERS.items()}
    monkeypatch.setattr(pipeline, "OWNERS", owners)
    with pytest.raises(AssertionError, match="'attended' is claimed by nobody"):
        pipeline.check_ownership(pipeline.PIPELINE)


def test_the_check_names_a_state_owned_twice(monkeypatch):
    # The exact shape the harness broke in: booking still listed as an admin
    # step after it became the creator's.
    owners = dict(pipeline.OWNERS)
    owners["admin"] = owners["admin"] + ("slot_booked",)
    monkeypatch.setattr(pipeline, "OWNERS", owners)
    with pytest.raises(
        AssertionError, match="'slot_booked' is claimed by more than one owner: admin, creator"
    ):
        pipeline.check_ownership(pipeline.PIPELINE)


def test_no_admin_step_is_one_the_advance_endpoint_refuses():
    """Every state the harness sends to `/admin/collaborations/{id}/advance`
    must be one `advance_collaboration` will actually take."""
    refused = (
        set(server._CREATOR_OWNED_TRANSITIONS)
        | set(server._DRAFT_OWNED_TRANSITIONS)
        # Taken by the advance only on a weare-run brief, and even then it
        # would skip the disclosure check — the harness uses the brand route.
        | set(server._BRAND_OWNED_TRANSITIONS)
        | {"dispatched"}
    )
    sent_to_advance = set(pipeline._ADMIN_STEPS)
    assert not sent_to_advance & refused, (
        f"tests/pipeline.py sends {sorted(sent_to_advance & refused)} to the admin "
        "advance, which refuses them — route them to their owner instead"
    )


@pytest.mark.parametrize("name", list(LADDERS))
def test_each_step_goes_to_the_party_the_server_gives_it_to(name):
    for state in LADDERS[name][0]:
        owner = _owner_of(state)
        if state in server._CREATOR_OWNED_TRANSITIONS:
            assert owner == "creator", f"the server gives '{state}' to the creator"
        if state in server._BRAND_OWNED_TRANSITIONS:
            assert owner == "brand", f"the server gives '{state}' to the campaign's runner"
        if state in server._DRAFT_OWNED_TRANSITIONS:
            assert owner in ("creator", "reviewer"), (
                f"'{state}' is the draft gate's — the creator's upload or the "
                "reviewer's decision, never an advance"
            )
