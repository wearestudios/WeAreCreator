#!/usr/bin/env python3
"""Give every collaboration that already has a fee one history entry.

    python backfill_negotiation_history.py            # dry run: counts only
    python backfill_negotiation_history.py --apply    # write

`negotiation_history` started being kept when `_set_agreed_amount` became the
only writer of `agreed_amount`. Every collaboration agreed before that has a
figure and no record of how it got there, which a history panel would draw as
an empty list beside a number — or worse, as nothing having been agreed.

So each such row gets exactly one entry: `kind` "accept", `by_role` "system",
`source` "backfill", at the best timestamp the row has. The UI draws a
backfilled entry as "recorded before history tracking", never as a step
somebody took, because nobody took it on that date — it is the fee as we found
it.

- **Not run automatically.** A migration that rewrites every collaboration
  belongs to a deploy somebody chose, not to every restart.
- **Idempotent, and safe to run twice or concurrently.** The write's filter is
  the selection's filter — a fee present and no history — so a row that
  already has an entry, from this script or from the app, is never touched.
- **Barter is skipped.** A barter collaboration has no fee, and an entry with
  an amount on one is the thing the app refuses to write.
- **Nothing else is written.** No `updated_at`, no state: a backfill that
  moved a row's clock would make the whole platform read as touched today.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import server  # noqa: E402  (env has to load first)


def _needs_backfill() -> dict:
    return {
        "agreed_amount": {"$ne": None, "$exists": True},
        "$or": [
            {"negotiation_history": {"$exists": False}},
            {"negotiation_history": {"$size": 0}},
        ],
    }


def _best_timestamp(collab: dict):
    """When the fee was agreed, as near as the row can say. `agreed_at` is the
    fact; the rest are progressively worse guesses, and the last — the id's
    own creation time — always exists."""
    for key in ("agreed_at", "state_since", "updated_at", "created_at"):
        if collab.get(key):
            return collab[key]
    return collab["_id"].generation_time


async def backfill(*, apply: bool) -> dict:
    campaigns: dict = {}
    seen = written = skipped_barter = 0
    async for collab in server.db.collaborations.find(_needs_backfill()):
        seen += 1
        cid = collab.get("campaign_id")
        if cid not in campaigns:
            campaigns[cid] = await server.db.campaigns.find_one({"_id": cid}) or {}
        if server._compensation_type(campaigns[cid]) == "barter":
            skipped_barter += 1
            continue
        if not apply:
            continue
        entry = server._negotiation_entry(
            kind="accept",
            amount=collab["agreed_amount"],
            by_role="system",
            by_user_id=None,
            note=None,
            source="backfill",
            at=_best_timestamp(collab),
        )
        result = await server.db.collaborations.update_one(
            {"_id": collab["_id"], **_needs_backfill()},
            {"$push": {"negotiation_history": entry}},
        )
        written += result.modified_count
    return {"candidates": seen, "written": written, "skipped_barter": skipped_barter,
            "applied": apply}


async def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="write; without it, count only")
    args = parser.parse_args(argv)
    print(f"Database: {server.db.name}")
    report = await backfill(apply=args.apply)
    print(report)
    if not args.apply:
        print("Dry run. Re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
