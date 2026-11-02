"""The whole lifecycle, walked once per ladder, against a running server.

There was no single test proving a collaboration can get from `applied` to
`closed`. The harness in `pipeline.py` stopped at `commercial_agreed` for
months after booking became the creator's alone, and nothing noticed, because
the only symptom was an assertion inside tests that are not run on a PR.

So this walks the real routes, each step taken by the party who owns it, and
reads the stored state back after every step rather than trusting the 200:
a route that answers 200 and writes nothing is the failure that matters here.
"""
import os
import uuid

import pytest
import requests

import pipeline

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "creators@wearemonk.in")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "WeAreMonk@2026")


def _register(session, role):
    r = session.post(
        f"{BASE_URL}/auth/register",
        json={
            "email": f"TEST_{role}-{uuid.uuid4().hex[:10]}@example.com",
            "password": "Password123!",
            "name": f"Test {role.title()}",
            "role": role,
            # Registration refuses without it, since the terms became a record
            # rather than a footnote.
            "accept_terms": True,
        },
    )
    assert r.status_code == 200, r.text


@pytest.fixture
def admin():
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert r.status_code == 200, r.text
    return s


@pytest.fixture
def brand():
    s = requests.Session()
    _register(s, "brand")
    return s


@pytest.fixture
def creator():
    s = requests.Session()
    _register(s, "creator")
    return s, pipeline.user_id_of(s)


LADDERS = {
    # The server's default for a brand-posted brief: weare-run, no draft
    # gate, no booking handshake.
    "plain": dict(ladder=pipeline.PIPELINE, gates={}),
    # Both optional gates on, so the draft review and the slot confirmation
    # are each walked once.
    "draft-gate": dict(
        ladder=pipeline.DRAFT_PIPELINE,
        gates=dict(requires_draft_approval=True, requires_slot_confirmation=True),
    ),
}


@pytest.mark.parametrize("name", list(LADDERS))
def test_a_collaboration_walks_from_applied_to_closed(admin, brand, creator, name):
    expected, gates = LADDERS[name]["ladder"], LADDERS[name]["gates"]
    creator_session, creator_id = creator

    pipeline.complete_creator_profile(creator_session)
    pipeline.verify_creator(admin, creator_id)
    campaign_id = pipeline.seed_open_campaign(brand, admin, **gates)
    collab_id = pipeline.apply_to_campaign(creator_session, campaign_id)
    assert pipeline.current_state(admin, collab_id) == "applied"

    # The ladder is chosen from the server's own `state_order`, not assumed.
    assert pipeline.ladder_for(admin, collab_id) == expected

    walked = []
    for state in pipeline.walk(admin, brand, creator_session, collab_id):
        stored = pipeline.current_state(admin, collab_id)
        assert stored == state, (
            f"after taking the '{state}' step the stored state is '{stored}'"
        )
        if state == "slot_booked":
            # Booked by the creator and, where the brief asks for it, answered
            # by whoever runs it — read from the creator's side, which is the
            # one that says whether they are actually expected.
            assert _creator_row(creator_session, collab_id)["slot_confirmed"] is True
        walked.append(state)
    assert walked == expected

    detail = pipeline.collab_detail(admin, collab_id)
    assert detail["collaboration"]["state"] == "closed"
    assert detail["payment"]["state"] == "paid"
    assert detail["slot"] is not None

    campaign = pipeline.campaign_of(admin, collab_id)
    # The gates the walk exercised are the ones this case asked for — so the
    # draft-gate run really did go through the handshake rather than past it.
    assert bool(campaign.get("requires_slot_confirmation")) == bool(
        gates.get("requires_slot_confirmation")
    )
    assert bool(campaign.get("requires_draft_approval")) == bool(
        gates.get("requires_draft_approval")
    )


def _creator_row(creator_session, collab_id):
    r = creator_session.get(f"{BASE_URL}/creator/dashboard")
    assert r.status_code == 200, r.text
    return next(a for a in r.json()["applications"] if a["id"] == collab_id)


def test_advance_to_stops_at_the_target(admin, brand, creator):
    """The helper other tests use lands exactly where it is asked to."""
    creator_session, creator_id = creator
    collab_id, _ = pipeline.make_collab_in_state(
        admin, brand, creator_session, creator_id, "attended"
    )
    assert pipeline.current_state(admin, collab_id) == "attended"
