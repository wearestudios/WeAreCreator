"""The console overview's top half (board 27), held to its sources.

`Today.test.jsx` renders it; these hold the wiring a render cannot see — that
the overview and the action queue share one definition of "waiting", that the
amber payouts tile is the server's flag rather than a date worked out in the
browser, and that no period the API does not serve is claimed on screen.
"""
from pathlib import Path
import re

import server

SRC = Path(server.__file__).resolve().parents[1] / "frontend" / "src"
ADMIN = SRC / "components" / "admin"


def _code(path):
    return "\n".join(
        line for line in path.read_text().splitlines() if not line.strip().startswith(("//", "*", "/*"))
    )


TODAY = _code(ADMIN / "Today.jsx")
QUEUE = _code(ADMIN / "ActionQueue.jsx")


def test_the_overview_and_the_queue_share_one_definition_of_waiting():
    """The tiles, the heading's total and the card count the queue's rows —
    the function `/admin/queue` itself draws from — not the sidebar's badges,
    which count a different set."""
    assert "export async function loadQueueRows" in QUEUE
    assert "await loadQueueRows(allAccess)" in QUEUE, "the queue stopped using its own loader"
    assert 'import { KIND_META, loadQueueRows } from "./ActionQueue"' in TODAY
    assert "awaiting_total" not in TODAY and "awaiting." not in TODAY


def test_the_payouts_tile_is_amber_on_the_servers_flag():
    """Day five of the seven-day promise is `payout_at_risk`, decided on the
    server; the tile reads it and works no date out for itself."""
    assert "urgent: Boolean(row.payout_at_risk)" in QUEUE
    assert "const atRisk = rows.filter((r) => r.urgent)" in TODAY
    assert 't.kind === "payment" && atRisk.length > 0' in TODAY
    for arithmetic in ("86400000", "getTime()", "Date.now()", "differenceIn"):
        assert arithmetic not in TODAY, arithmetic


def test_no_period_the_api_does_not_serve_is_claimed():
    """No endpoint serves a calendar month, so the column is not headed "This
    month": each figure carries the window it is served for."""
    assert "This month" not in TODAY
    assert "window_days" in TODAY and "window_weeks" in TODAY
    assert "all time" in TODAY


def test_the_admin_only_reads_are_asked_for_by_admins_only():
    """`/admin/intelligence` and a campaign's summary are an admin's; a team
    member's overview must not fire a request that 403s."""
    assert 'allAccess ? api.get("/admin/intelligence")' in TODAY
    assert 'if (allAccess && aiLive("campaignSummary"))' in TODAY


def test_one_action_per_row_and_it_goes_where_the_decision_is_made():
    """Every review opens a full page carrying the approval actions, so the
    card's one button is a link there rather than a second copy of them."""
    block = TODAY[TODAY.index("const ROW_ACTION = {"):TODAY.index("export function rowState")]
    for kind in ("payment", "question", "collaboration", "campaign", "brand", "creator"):
        assert re.search(rf"\b{kind}: \{{ verb:", block), kind
    assert "api.post" not in TODAY


def test_states_are_drawn_by_the_consoles_one_component():
    assert "<StatusTag chip tone={s.tone}" in TODAY
    assert "<Pill" not in TODAY
