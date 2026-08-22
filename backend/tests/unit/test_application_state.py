"""An approved application must read as approved in every view.

The bug: an admin approved an application and the console went on showing it
as pending. Nothing was wrong with the write — `advance_collaboration` sets
`state: "verified"` under a precondition and it persists — and nothing was
wrong with the brand's board, which reads `state` and labels it correctly.

The console *bucketed* it wrongly. `_APPLICANT_BUCKETS` grouped applicants by
`COLLAB_GROUP_APPLIED`, which is `("applied", "verified")` — so the very state
the Approve button produces was counted in the pending column. The two views
read the same field and disagreed about what it meant.

`COLLAB_GROUP_APPLIED` itself is correct and stays: on a creator's history,
"applied" legitimately covers an application that has been approved by us but
not yet taken on by the brand. The mistake was reusing it for a board that is
reporting on our own approval decision.

The second half of this file pins the *shape* of that board against what the
frontend reads, because the same screen was asking for group keys the server
has never returned.
"""
import json
import re
from pathlib import Path

import pytest

import server

FRONTEND = Path(server.__file__).resolve().parents[1] / "frontend" / "src"
CAMPAIGN_DETAIL_PAGE = FRONTEND / "components" / "admin" / "CampaignDetailPage.jsx"


def _bucket_of(state: str) -> str:
    for name, states in server._APPLICANT_BUCKETS:
        if state in states:
            return name
    raise AssertionError(f"{state!r} is in no applicant bucket at all")


# --- The bug ----------------------------------------------------------------


def test_an_admin_approved_application_is_not_pending():
    """`verified` is what the console's approve action produces. If it buckets
    as `applied`, an admin approves somebody and watches nothing happen."""
    assert _bucket_of("verified") == "approved"


def test_an_application_nobody_has_looked_at_is_pending():
    """The other half — the fix must not empty the pending column."""
    assert _bucket_of("applied") == "applied"


@pytest.mark.parametrize("state", server.COLLAB_GROUP_ONGOING + server.COLLAB_GROUP_COMPLETED)
def test_everything_past_approval_still_reads_as_approved(state):
    assert _bucket_of(state) == "approved"


@pytest.mark.parametrize("state", server.COLLAB_GROUP_ENDED)
def test_declined_and_cancelled_read_as_rejected(state):
    assert _bucket_of(state) == "rejected"


@pytest.mark.parametrize(
    "state", list(server.COLLAB_STATE_ORDER) + list(server.COLLAB_GROUP_ENDED)
)
def test_every_state_lands_in_exactly_one_bucket(state):
    """An applicant that matches no bucket is dropped from a board that claims
    to account for all of them."""
    matches = [name for name, states in server._APPLICANT_BUCKETS if state in states]

    assert len(matches) == 1, f"{state!r} is in buckets {matches}"


def test_creator_history_grouping_is_left_alone():
    """COLLAB_GROUP_APPLIED answers a different question and must keep both
    states. Narrowing it to fix the console would move approved-but-not-yet-
    accepted applications out of a creator's applied count, which is where they
    belong until a brand says yes."""
    assert server.COLLAB_GROUP_APPLIED == ("applied", "verified")


# --- Every view agrees ------------------------------------------------------


def test_the_brand_board_reports_the_same_state():
    """The brand's serializer is the other view of the same collaboration."""
    row = server._serialize_applicant(
        {"_id": "x", "state": "verified"}, {"name": "Asha"}, {"name": "Asha"}, None
    )

    assert row["state"] == "verified"
    assert row["can_accept"] is True, "an approved application is the brand's to accept"


def test_the_brand_board_does_not_offer_accept_before_approval():
    row = server._serialize_applicant(
        {"_id": "x", "state": "applied"}, {"name": "Asha"}, {"name": "Asha"}, None
    )

    assert row["can_accept"] is False


def test_approval_is_what_hands_the_decision_to_the_brand():
    """`verified` is simultaneously 'approved by us' and 'waiting on the
    brand'. Both boards must agree on that, from the one field."""
    approved = _bucket_of("verified") == "approved"
    brand_can_act = server._serialize_applicant(
        {"_id": "x", "state": "verified"}, {}, {}, None
    )["can_accept"]

    assert approved and brand_can_act


# --- The console asks for what the server returns ----------------------------


def test_the_admin_board_returns_one_key_per_bucket():
    """The response spreads `**groups`, so the bucket names *are* the keys the
    frontend has to read."""
    assert [name for name, _ in server._APPLICANT_BUCKETS] == [
        "applied",
        "approved",
        "rejected",
    ]


def test_the_campaign_page_reads_the_keys_the_server_sends():
    """This is the second bug: the page asked for active/completed/ended, which
    the server has never returned, so every group resolved to undefined and the
    section rendered "nobody has applied yet" however many had.

    "Sends" is the handler's whole answer, not just the collaboration buckets:
    `invited` is a fifth group written beside them, because an invitation makes
    no collaboration and a board that listed only those showed a campaign we
    had asked six people to as empty.
    """
    source = CAMPAIGN_DETAIL_PAGE.read_text()
    block = re.search(r"const GROUPS = \[(.*?)\];", source, re.S)
    assert block, "GROUPS not found in CampaignDetailPage.jsx"

    keys = set(re.findall(r'key:\s*"([a-z_]+)"', block.group(1)))

    handler = Path(server.__file__).read_text()
    handler = handler[handler.index("async def admin_campaign_applicants(") :][:6000]
    served = {name for name, _ in server._APPLICANT_BUCKETS}
    served |= set(re.findall(r'groups\["([a-z_]+)"\]\s*=', handler))

    assert keys == served, f"page reads {sorted(keys)}, server sends {sorted(served)}"


def test_the_campaign_page_reads_the_row_fields_the_server_sends():
    """The rows were addressed as `a.id` and `a.creator.name`; this endpoint
    returns `collaboration_id` and a flat `name`, with no nested creator."""
    source = CAMPAIGN_DETAIL_PAGE.read_text()
    applicants = source[source.index('id="applicants"') : source.index('id="payments"')]

    assert "a.collaboration_id" in applicants
    assert "a.creator?.name" not in applicants
    assert "a.creator?.id" not in applicants
    assert not re.search(r"\ba\.id\b", applicants), "a.id is not a field on this endpoint"
