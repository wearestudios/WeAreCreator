"""Keys the server computes for a persona and no screen reads.

Across all three personas the backend decided correctly, sent the answer, and
no screen read it: a suspension the creator met as a 403, a booking that said
"turn up" before the venue agreed, a brief sent back with the reason on the
payload and on no screen, four required reasons that nobody could see. Each one
was a key on a payload a screen already fetched.

So this walks the builders of every persona payload, collects the keys they
emit, and fails on any that no frontend file mentions. **It fails both ways**:
a new unread key fails until it is rendered or listed below with why, and a
listed key that has since been rendered fails until its line is deleted — the
list is a ratchet, not a licence.

"Mentions" is a word-boundary match anywhere in the frontend source, comments
stripped. That is deliberately generous — a key called `state` is "read" by
any file that says `state` — so this is a floor, not a proof: every key it
reports is certainly unread, and it reports nothing that is.
"""
import ast
import functools
import re
from pathlib import Path

import pytest

import server
from test_router_callers import frontend_source

# The builders of what each persona's screens fetch.
PAYLOAD_BUILDERS = (
    "_serialize_collab_row",       # creator: their own card and lists
    "get_creator_dashboard",       # creator: the home page
    "_serialize_campaign",         # creator: a brief
    "_serialize_applicant",        # brand: the applicant board
    "_serialize_brand_campaign",   # brand: their campaigns
    "get_brand_dashboard",         # brand: the home page
    "_brand_profile_response",     # brand: onboarding and the brief form
    "get_application",             # all three: the shared application screen
    "_roster_rows",                # manager: the roster and day plan
    "_serialize_admin_collab",     # admin: a collaboration
    "get_creator_detail",          # admin / team: a creator
    "get_admin_campaign_detail",   # admin / team: a campaign
)

# Mongo pipeline vocabulary, which is a dict literal and not a payload.
_PIPELINE = {"localField", "foreignField", "from", "as"}

# **Known unread, each with why.** Grouped by reason. Deleting a line is the
# goal; adding one needs the sentence.
UNREAD_ALLOWED = {
    # Said in words by the process flow and the next action, which every
    # surface prints; the boolean is there for a test or an integration.
    ("_serialize_collab_row", "slot_confirmed"),
    ("_serialize_applicant", "slot_confirmed"),
    ("get_application", "slot_confirmed"),
    ("_roster_rows", "slot_confirmed"),
    ("_serialize_collab_row", "can_submit_content"),
    # When the fee was agreed. The negotiation history carries the same moment
    # as a dated entry, which is where every screen reads it.
    ("_serialize_collab_row", "agreed_at"),
    ("_serialize_applicant", "agreed_at"),
    ("_serialize_admin_collab", "agreed_at"),
    # Labels and counts nobody has asked to see yet.
    ("_serialize_collab_row", "campaign_reference"),
    ("_serialize_brand_campaign", "awaiting_review"),
    ("_roster_rows", "slot_ends_at"),
    ("get_brand_dashboard", "draft_campaigns"),
    ("get_brand_dashboard", "total_campaigns"),
    ("_brand_profile_response", "can_submit"),
    # The admin's creator and campaign pages: fields the page has room for and
    # does not draw yet. Staff-only, so nothing is withheld from a persona.
    ("get_creator_detail", "applications_open"),
    ("get_creator_detail", "campaign_area"),
    ("get_creator_detail", "campaign_status"),
    ("get_creator_detail", "collaborations_ended"),
    ("get_creator_detail", "pending_review_since"),
    ("get_creator_detail", "slots_booked"),
    ("get_creator_detail", "verified_at"),
    ("get_admin_campaign_detail", "closed_at"),
    ("get_admin_campaign_detail", "paused_at"),
    ("get_admin_campaign_detail", "paused_from_status"),
}


def _keys_of(fn: ast.AST) -> set:
    keys = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Dict):
            for k in node.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    keys.add(k.value)
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.ctx, ast.Store)
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            keys.add(node.slice.value)
    # Dotted keys are query paths (`collab.campaign_id`), not payload keys.
    return {
        k for k in keys if not k.startswith("$") and "." not in k and k not in _PIPELINE
    }


@functools.lru_cache(maxsize=1)
def unread() -> frozenset:
    """Computed once: one tokenised set of the frontend's words, then a set
    lookup per key — a regex per key over the whole source took minutes."""
    tree = ast.parse(Path(server.__file__).read_text())
    fns = {
        n.name: n
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    words = set(re.findall(r"\w+", frontend_source()))
    out = set()
    for name in PAYLOAD_BUILDERS:
        assert name in fns, f"{name} is gone — update PAYLOAD_BUILDERS"
        for key in _keys_of(fns[name]):
            if key not in words:
                out.add((name, key))
    return frozenset(out)


def test_no_new_key_goes_unread():
    new = sorted(unread() - UNREAD_ALLOWED)
    assert not new, (
        "these are computed for a persona and no screen reads them — render "
        f"them, or list them in UNREAD_ALLOWED with why: {new}"
    )


def test_the_allow_list_only_shrinks():
    now_read = sorted(UNREAD_ALLOWED - unread())
    assert not now_read, f"these are read now — delete their lines: {now_read}"


@pytest.mark.parametrize(
    "key",
    [
        # The ones this change rendered, named so a regression reads plainly.
        ("get_creator_dashboard", "block"),
        ("get_creator_dashboard", "held_resolved"),
        ("get_creator_dashboard", "cancel_blocked_reason"),
        ("_serialize_collab_row", "slot_declined_reason"),
        ("_serialize_collab_row", "reschedule_reason"),
        ("_serialize_applicant", "dispute"),
        ("_serialize_applicant", "takedown"),
        ("_serialize_applicant", "ageing"),
        ("_serialize_applicant", "payment"),
        ("_serialize_brand_campaign", "review_reason"),
        ("_serialize_brand_campaign", "pause_reason"),
        ("_serialize_brand_campaign", "commission_percent"),
        ("_serialize_brand_campaign", "campaign_fee"),
        ("_serialize_brand_campaign", "reviewed_at"),
        ("get_brand_dashboard", "publish_block"),
        ("_brand_profile_response", "publish_block"),
        ("_roster_rows", "slot_cancel_reason"),
        ("_serialize_admin_collab", "no_show"),
    ],
)
def test_the_fields_this_change_rendered_are_read(key):
    assert key not in unread()
