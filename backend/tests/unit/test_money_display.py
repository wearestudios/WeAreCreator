"""One rupee formatter, and barter never drawn as rupees.

There were seven `formatRupees` definitions in seven files and they
disagreed: three rounded to the rupee, two printed paise to three places, one
returned `null` where the rest drew a dash. Beside them a dozen screens wrote
`₹${x.toLocaleString("en-IN")}` inline, each with its own idea of a missing
figure. A fee drawn as 12,000 on one screen and 12,000.5 on the next is two
answers to "what was agreed".

And the creator's own card printed `agreed_amount ?? quoted_rate` with a rupee
sign — which on a barter brief, where the agreed amount is `null` on purpose,
printed the creator's own quote as a fee nobody agreed.

`lib/compensation.js` is the one home now (`formatRupees`, `formatInr`,
`formatCollabMoney`). This file fails a second definition, an inline rupee
format, and a card that goes back to the quote.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[3] / "frontend" / "src"
HOME = "lib/compensation.js"

# Drawn product UI on the marketing pages — invented figures in mock cards,
# counted by the copy budgets rather than formatted from data.
EXEMPT_PREFIXES = ("components/marketing/", "content/", "pages/Home.jsx", "pages/For")


def _app_files():
    for path in sorted(SRC.rglob("*")):
        if path.suffix not in (".js", ".jsx") or "node_modules" in path.parts:
            continue
        rel = path.relative_to(SRC).as_posix()
        if rel.startswith(EXEMPT_PREFIXES):
            continue
        yield rel, path.read_text(encoding="utf-8")


def _code(text: str) -> str:
    """Comment lines out, so explaining a removed pattern does not trip it."""
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith(("//", "*", "/*", "{/*"))
    )


def test_there_is_one_rupee_formatter():
    definition = re.compile(r"\b(?:const|let|var|function)\s+formatRupees\b")
    found = [rel for rel, text in _app_files() if definition.search(_code(text))]
    assert found == [HOME], (
        f"formatRupees is defined in {found}. Import it from {HOME} — a second "
        "copy is how one fee reads two ways on two screens."
    )


def test_no_screen_formats_rupees_inline():
    """`₹` and a hand-rolled `toLocaleString` within a line of each other is a
    money display that skipped the formatter."""
    inline = re.compile(r"₹[^\n]*(?:\n[^\n]*)?\.toLocaleString\(")
    offenders = []
    for rel, text in _app_files():
        if rel == HOME:
            continue
        for m in inline.finditer(_code(text)):
            offenders.append(f"{rel}: {m.group(0).strip()[:80]}")
    assert not offenders, "rupees formatted by hand:\n" + "\n".join(offenders)


def test_the_creator_card_draws_barter_as_barter():
    card = (SRC / "components/creator/ActiveCampaigns.jsx").read_text(encoding="utf-8")
    assert "formatCollabMoney" in card
    assert "collab.barter_terms" in card
    assert "collab.compensation_type" in card
    # And the shortfall with its note, on the card of the person it judges.
    assert "<Shortfall" in card and "collab.partial_note" in card


def test_the_creator_row_carries_the_kind_of_money_and_the_partial_note():
    import server

    campaign = {"compensation_type": "barter", "barter_description": "Dinner for two"}
    from bson import ObjectId

    collab = {
        "_id": ObjectId(), "campaign_id": ObjectId(), "state": "content_approved",
        "quoted_rate": 9000, "agreed_amount": None,
        "partial_delivery": True, "partial_note": "Two of three stories, agreed on the call.",
    }
    row = server._serialize_collab_row(collab, campaign, "Toit", payout_default=7)
    assert row["compensation_type"] == "barter"
    assert row["barter_terms"] == "Dinner for two"
    assert row["partial_delivery"] is True
    assert row["partial_note"] == "Two of three stories, agreed on the call."

    paid = server._serialize_collab_row(
        {**collab, "agreed_amount": 12000}, {"compensation_type": "fixed"}, "Toit",
        payout_default=7,
    )
    assert paid["compensation_type"] == "fixed" and paid["barter_terms"] is None


def test_the_formatter_behaves(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    (tmp_path / "compensation.mjs").write_text(
        (SRC / HOME).read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "run.mjs").write_text(
        """
import { formatRupees, formatInr, formatCollabMoney, formatCompensation } from "./compensation.mjs";
console.log(JSON.stringify({
  whole: formatRupees(1250000),
  paise: formatRupees(1234.5),
  string: formatRupees("18000"),
  missing: formatRupees(null),
  missingNull: formatRupees(undefined, { fallback: null }),
  nan: formatRupees(Number.NaN),
  inr: formatInr(18000),
  inrMissing: formatInr(null),
  barter: formatCollabMoney({ compensationType: "barter", agreed: null, quoted: 9000, barterTerms: "Dinner for two" }),
  barterBare: formatCollabMoney({ compensationType: "barter", agreed: null, quoted: 9000 }),
  paid: formatCollabMoney({ compensationType: "fixed", agreed: 12000, quoted: 9000 }),
  quotedOnly: formatCollabMoney({ compensationType: "negotiated", agreed: null, quoted: 9000 }),
  brief: formatCompensation({ compensation_type: "fixed", budget_per_creator: 18000 }).text,
  briefMissing: formatCompensation({ compensation_type: "fixed" }).text,
}));
""",
        encoding="utf-8",
    )
    done = subprocess.run(
        [node, str(tmp_path / "run.mjs")], capture_output=True, text=True, timeout=30
    )
    assert done.returncode == 0, done.stderr
    out = json.loads(done.stdout)
    assert out["whole"] == "12,50,000"  # lakh grouping
    assert out["paise"] == "1,234.5"
    assert out["string"] == "18,000"
    assert out["missing"] == "—" and out["nan"] == "—"
    assert out["missingNull"] is None
    assert out["inr"] == "₹18,000" and out["inrMissing"] == "—"
    assert out["barter"] == {"text": "Barter · Dinner for two", "isBarter": True}
    assert out["barterBare"]["text"] == "Barter"
    assert "₹" not in out["barter"]["text"] and "9,000" not in out["barter"]["text"]
    assert out["paid"]["text"] == "₹12,000" and out["paid"]["quoted"] is False
    assert out["quotedOnly"]["text"] == "₹9,000" and out["quotedOnly"]["quoted"] is True
    assert out["brief"] == "₹18,000"
    assert out["briefMissing"] == "—"
