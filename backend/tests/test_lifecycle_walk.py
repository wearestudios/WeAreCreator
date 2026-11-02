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


# Every ladder the server can hand a collaboration — the venue and delivery
# halves, with and without the draft gate — once with money and once without.
# The draft-gate runs also turn the booking handshake on, so it is walked too.
CASES = [
    (shape, money)
    for shape in ("venue", "venue+draft", "delivery", "delivery+draft")
    for money in ("paid", "barter")
]


def _gates(shape, money):
    gates = {
        "campaign_type": "delivery" if shape.startswith("delivery") else "personal_table",
        "compensation_type": "barter" if money == "barter" else None,
    }
    if shape.endswith("+draft"):
        gates.update(requires_draft_approval=True)
        if shape.startswith("venue"):
            gates.update(requires_slot_confirmation=True)
    return gates


@pytest.mark.parametrize("shape,money", CASES, ids=[f"{s}-{m}" for s, m in CASES])
def test_a_collaboration_walks_from_applied_to_closed(admin, brand, creator, shape, money):
    expected = pipeline.LADDERS[(shape, money)]
    gates = _gates(shape, money)
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
        # **Each persona's next action, after every step.** The creator's card
        # and the console's own button are read off the live payloads, and
        # checked against the rung — the delivery brief that told a creator to
        # book a slot, and the barter brief whose only button led into a
        # payment it could never reach, were both this check missing.
        want = pipeline.creator_next_action(state, expected)
        if want is not None:
            assert _creator_next(creator_session, collab_id)["action"] == want, state
        detail = pipeline.collab_detail(admin, collab_id)["collaboration"]
        if state != "closed":
            nxt = expected[expected.index(state) + 1]
            assert detail["next_state"] == nxt, (state, detail["next_state"])
        if state == "slot_booked":
            # Booked by the creator and, where the brief asks for it, answered
            # by whoever runs it — read from the creator's side, which is the
            # one that says whether they are actually expected.
            assert _creator_row(creator_session, collab_id)["slot_confirmed"] is True
        walked.append(state)
    assert walked == expected

    detail = pipeline.collab_detail(admin, collab_id)
    assert detail["collaboration"]["state"] == "closed"
    if money == "paid":
        assert detail["payment"]["state"] == "paid"
    else:
        # No money moved, so no payment was ever raised.
        assert not detail.get("payment")
    if shape.startswith("venue"):
        assert detail["slot"] is not None

    campaign = pipeline.campaign_of(admin, collab_id)
    assert bool(campaign.get("requires_draft_approval")) == shape.endswith("+draft")


@pytest.mark.parametrize("resolution", ["refund", "cancelled"])
@pytest.mark.parametrize("money", ["paid", "barter"])
def test_a_dispute_that_ends_it_leaves_a_terminal_record(admin, brand, creator, money, resolution):
    """Refund and call-off both end the arrangement: the stored row is
    `cancelled`, the payment (where there is one) is cancelled, and nobody is
    told to do anything next. The refund used to leave the row live."""
    creator_session, creator_id = creator
    collab_id, _ = pipeline.make_collab_in_state(
        admin, brand, creator_session, creator_id, "content_approved",
        compensation_type="barter" if money == "barter" else None,
    )
    pipeline.raise_dispute(creator_session, collab_id)
    pipeline.resolve_dispute(admin, collab_id, resolution)

    detail = pipeline.collab_detail(admin, collab_id)
    collab = detail["collaboration"]
    assert collab["state"] == "cancelled"
    if detail.get("payment"):
        assert detail["payment"]["state"] == "cancelled"
    assert collab["next_state"] is None


def _creator_next(creator_session, collab_id):
    """The creator's next action, off whichever dashboard row carries it —
    the active rows do, the flat applications list does not."""
    r = creator_session.get(f"{BASE_URL}/creator/dashboard")
    assert r.status_code == 200, r.text

    def rows(node):
        if isinstance(node, dict):
            if node.get("id") == collab_id and "next_action" in node:
                yield node
            for v in node.values():
                yield from rows(v)
        elif isinstance(node, list):
            for v in node:
                yield from rows(v)

    found = next(rows(r.json()), None)
    assert found is not None, "the creator's dashboard has no active row for this collaboration"
    return found["next_action"]


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
