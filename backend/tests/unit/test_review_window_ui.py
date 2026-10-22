"""The two mechanics on screen: the review countdown and the fee history.

The backend half is driven in `test_draft_review_window.py` and
`test_negotiation_history.py`. This file holds the frontend to it — the same
rule `test_manager_experience.py` states: a route with no caller and a panel
with no mount are the same failure, and both have shipped here before.

The countdown's wording is the one piece of logic that lives in the browser,
so it is *run*, not read: `lib/reviewWindow.js` and the `lib/time.js` it
imports are loaded into node with the clock pinned, and the sentence each
deadline produces is asserted. Reading the source for "tomorrow" would pass
on a function that said it on the wrong day.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import server

ROOT = Path(server.__file__).parent.parent
SRC = ROOT / "frontend" / "src"


def read(rel: str) -> str:
    return (SRC / rel).read_text()


# ---------------------------------------------------------------------------
# The numbers the form offers are the route's
# ---------------------------------------------------------------------------


def test_the_form_bounds_mirror_the_server():
    js = read("lib/reviewWindow.js")
    for name, value in (
        ("DEFAULT_DRAFT_REVIEW_DAYS", server.DEFAULT_DRAFT_REVIEW_DAYS),
        ("DRAFT_REVIEW_DAYS_MIN", server.DRAFT_REVIEW_DAYS_MIN),
        ("DRAFT_REVIEW_DAYS_MAX", server.DRAFT_REVIEW_DAYS_MAX),
    ):
        match = re.search(rf"export const {name} = (\d+);", js)
        assert match and int(match.group(1)) == value, name


def test_both_campaign_forms_offer_the_window():
    post = read("pages/PostCampaign.jsx")
    assert "draft_review_days:" in post and "REVIEW_WINDOW.days" in post
    # Seeded from the stored brief on an edit, or opening the form would
    # quietly reset a brand's choice to the default.
    assert "data.draft_review_days" in post
    edit = read("components/admin/dialogs.jsx")
    assert "changes.draft_review_days" in edit
    assert "campaign.requires_draft_approval" in edit


# ---------------------------------------------------------------------------
# Every route has a caller, and every panel a mount
# ---------------------------------------------------------------------------


def test_every_review_window_control_has_a_caller():
    controls = read("components/application/ReviewWindow.jsx")
    for path in ("extend", "pause", "resume", "approve-now"):
        assert f'path: "{path}"' in controls, path
    assert "/draft-review/${config.path}" in controls


def test_the_countdown_is_mounted_for_all_three_parties():
    draft = read("components/application/DraftReview.jsx")
    assert draft.count("<ReviewWindowNote") == 2  # reviewer's, and everybody else's
    assert "<ReviewWindowControls" in draft and "canManageWindow &&" in draft
    detail = read("components/application/ApplicationDetail.jsx")
    assert "canManageWindow={actions.can_manage_review_window}" in detail
    creator = read("components/creator/ActiveCampaigns.jsx")
    assert "<ReviewWindowNote" in creator and "collab.draft?.review_window" in creator


def test_the_creator_chunk_does_not_carry_the_console_dialogs():
    note = read("components/collab/ReviewWindowNote.jsx")
    assert "components/admin" not in note
    assert "@/components/application/ReviewWindow" not in read("components/creator/ActiveCampaigns.jsx")


def test_the_history_is_mounted_on_every_surface_that_reads_it():
    for rel, prop in (
        ("components/application/ApplicationDetail.jsx", "app.negotiation"),
        ("components/creator/ActiveCampaigns.jsx", "collab.negotiation"),
        ("components/admin/CollaborationDetailPage.jsx", "data.negotiation"),
    ):
        src = read(rel)
        assert "<NegotiationHistory" in src and f"negotiation={{{prop}}}" in src, rel


@pytest.mark.parametrize(
    "rel",
    ["components/collab/NegotiationHistory.jsx", "components/collab/ReviewWindowNote.jsx",
     "components/application/ReviewWindow.jsx"],
)
def test_neither_component_asks_who_is_looking(rel):
    src = read(rel)
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("//"))
    for needle in ("user.role", "useAuth", "isAdmin", '"admin"', "role ==="):
        assert needle not in code, f"{rel}: {needle}"


def test_the_fee_note_says_who_will_read_it():
    detail = read("components/application/ApplicationDetail.jsx")
    assert "note: feeNote.trim()" in detail
    assert "creator and the brand both see this" in detail
    assert "actions.fee_note_required" in detail
    accept = read("pages/BrandCampaignApplicants.jsx")
    assert "Note for our team" not in accept
    assert "creator and our team both see this" in accept
    assert "creator sees this in the fee history" in read("components/brand/PartialDeliveryDialog.jsx")


def test_the_wording_is_built_on_the_ist_helpers():
    js = read("lib/reviewWindow.js")
    assert 'from "@/lib/time"' in js
    assert "toLocale" not in js and "Asia/Kolkata" not in js


# ---------------------------------------------------------------------------
# The sentence, run
# ---------------------------------------------------------------------------


_HARNESS = r"""
import { reviewWindowText } from "./reviewWindow.mjs";
const cases = JSON.parse(process.argv[2]);
const now = new Date(process.argv[3]);
// The helpers read the wall clock for "today"; pin it.
Date.now = () => now.getTime();
const RealDate = Date;
globalThis.Date = class extends RealDate {
    constructor(...a) { super(...(a.length ? a : [now.getTime()])); }
    static now() { return now.getTime(); }
};
const out = cases.map((w) => reviewWindowText(w, now));
console.log(JSON.stringify(out));
"""


def _run(cases, now_iso, tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    rewrite = lambda s: s.replace('"@/lib/time"', '"./time.mjs"')
    (tmp_path / "time.mjs").write_text(read("lib/time.js"))
    (tmp_path / "reviewWindow.mjs").write_text(rewrite(read("lib/reviewWindow.js")))
    (tmp_path / "harness.mjs").write_text(_HARNESS)
    done = subprocess.run(
        [node, str(tmp_path / "harness.mjs"), json.dumps(cases), now_iso],
        capture_output=True, text=True, timeout=30, env={"TZ": "America/Los_Angeles"},
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def _running(deadline):
    return {"deadline_at": deadline, "running": True, "paused": False,
            "frozen_by_dispute": False, "auto_approved_at": None}


def test_days_are_ist_calendar_days_whatever_the_browser_zone(tmp_path):
    # 23:00 IST on 1 Oct. The browser is in Los Angeles on purpose: a
    # countdown read off the reader's own calendar would be a day out.
    now = "2026-10-01T17:30:00Z"
    out = _run([
        _running("2026-10-01T18:00:00Z"),  # 23:30 IST, same day
        _running("2026-10-02T03:30:00Z"),  # 09:00 IST next day — 10h away
        _running("2026-10-03T03:30:00Z"),  # 09:00 IST two days on
        _running("2026-10-08T12:00:00Z"),
        _running("2026-10-01T17:00:00Z"),  # already due, sweep not run yet
    ], now, tmp_path)
    assert [o["text"] for o in out] == [
        "Auto-approves today",
        "Auto-approves tomorrow",
        "Auto-approves in 2 days",
        "Auto-approves in 7 days",
        "Auto-approving now",
    ]
    assert [o["tone"] for o in out] == ["due", "due", "calm", "calm", "due"]
    # The hover carries the instant, in IST: 09:00 on 2 Oct, not 02:30.
    assert "09:00" in out[1]["exact"] or "9:00" in out[1]["exact"]
    assert "02" in out[1]["exact"] and "Oct" in out[1]["exact"]


def test_paused_frozen_and_finished_windows_say_so(tmp_path):
    now = "2026-10-01T06:30:00Z"
    base = _running("2026-10-03T06:30:00Z")
    out = _run([
        {**base, "running": False, "paused": True},
        {**base, "running": False, "frozen_by_dispute": True},
        {**base, "running": False, "auto_approved_at": "2026-10-03T06:31:00Z",
         "approved_via": "review_window_elapsed"},
        {**base, "running": False, "auto_approved_at": "2026-10-02T06:31:00Z",
         "approved_via": "admin_forced"},
        # Approved by a person inside the window: nothing to say.
        {**base, "running": False},
        None,
    ], now, tmp_path)
    assert out[0]["text"] == "Auto-approval is paused by the WeAre team"
    assert out[1]["text"] == "Auto-approval is on hold while the dispute is open"
    assert out[2]["text"] == "Approved automatically when the review window ran out"
    assert out[3]["text"] == "Approved by the WeAre team before the window ran out"
    assert out[4] is None and out[5] is None
