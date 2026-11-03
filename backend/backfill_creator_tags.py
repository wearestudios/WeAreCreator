#!/usr/bin/env python3
"""Tag every Instagram-connected creator who has never been tagged.

    python backfill_creator_tags.py --dry-run    # counts and an estimate; no calls
    python backfill_creator_tags.py --apply      # tag, within today's AI budget

New connections are tagged on connect and refreshed weekly; this is for the
creators who connected before tagging existed. It goes through
`server.tag_creator_from_instagram`, so the 24-post cap, the vocabulary, the
area-must-be-named rule and `redact_for_ai` are the app's own and not a copy.

- **A dry run is the default.** `--dry-run` says so explicitly; nothing is
  written and no model or Instagram call is made without `--apply`.
- **Batched under `AI_DAILY_CALL_LIMIT`.** Each creator can cost two provider
  calls (one retry). The run stops when what is left of today's ceiling — read
  from the `ai_calls` log, so other features' calls count — would not cover
  another creator, and says how many remain. Run it again tomorrow; it picks up
  where it stopped, because a tagged creator is no longer selected.
- **Creators who never connected Instagram are not called.** They pick their
  tags in onboarding; the count is reported so nobody wonders where they went.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import ai  # noqa: E402
import niche_tagging  # noqa: E402
import server  # noqa: E402  (env has to load first)

CALLS_PER_CREATOR = 2  # one call, one retry at most
# A creator's 24 captions, for the token estimate in a dry run. An assumption,
# not a measurement — no real captions have been read yet — so it is a flag:
# Instagram allows 2,200 characters and most food captions with their hashtags
# run a few hundred.
DEFAULT_CAPTION_CHARS = 320
# What a full reply looks like: five niches with confidences, three of each
# other kind. Rounded up.
REPLY_TOKENS = 220


def _needs_tagging() -> dict:
    return {"$or": [{"creator_tags.read_at": {"$exists": False}}, {"creator_tags.read_at": None}]}


async def _calls_left_today() -> int:
    since = ai._day_start(datetime.now(timezone.utc))
    used = await server.db.ai_calls.count_documents({"created_at": {"$gte": since}})
    return max(0, ai.daily_call_limit() - used)


def estimate_tokens(caption_chars: int = DEFAULT_CAPTION_CHARS) -> dict:
    """Input and output tokens for one creator, at ~4 characters a token.

    Built from the real payload — the system prompt and `caption_payload`
    over 24 posts — so a longer vocabulary or prompt moves the estimate.
    """
    media = [{"caption": "x" * caption_chars, "media_product_type": "REELS"}] * niche_tagging.POSTS_PER_TAGGING
    payload = json.dumps(niche_tagging.caption_payload(media), ensure_ascii=False)
    schema = json.dumps(niche_tagging.CreatorTagging.model_json_schema())
    chars = len(niche_tagging.CREATOR_PROMPT.system) + len(payload) + len(schema)
    return {"input": round(chars / 4), "output": REPLY_TOKENS}


async def backfill(*, apply: bool, limit: int, caption_chars: int) -> dict:
    connected = await server.db.instagram_connections.find({"status": "connected"}, {"user_id": 1}).to_list(None)
    connected_ids = [c["user_id"] for c in connected]
    total = await server.db.creator_profiles.count_documents({})
    todo = await server.db.creator_profiles.find(
        {"user_id": {"$in": connected_ids}, **_needs_tagging()}, {"user_id": 1}
    ).to_list(None)
    left = await _calls_left_today()
    fits_today = left // CALLS_PER_CREATOR
    tokens = estimate_tokens(caption_chars)
    report = {
        "creators": total,
        "instagram_connected": len(connected_ids),
        "not_connected_pick_in_onboarding": total - len(connected_ids),
        "to_tag": len(todo),
        "ai_calls_left_today": left,
        "creators_that_fit_today": min(fits_today, len(todo), limit),
        "days_needed_at_this_limit": (
            -(-len(todo) // max(1, ai.daily_call_limit() // CALLS_PER_CREATOR)) if todo else 0
        ),
        "estimated_tokens_per_creator": tokens,
        "ai_configured": ai.ai_configured(),
        "instagram_configured": server.instagram_configured(),
        "applied": apply,
    }
    if not apply:
        return report
    if not (ai.ai_configured() and server.instagram_configured()):
        report["stopped"] = "AI or Instagram is not configured; nothing to do"
        return report

    tagged = skipped = 0
    for row in todo[: min(limit, fits_today)]:
        out = await server.tag_creator_from_instagram(row["user_id"], force=True)
        if out.get("tagged"):
            tagged += 1
        else:
            skipped += 1
            if (out.get("reason") or "").startswith("ai: daily_limit"):
                report["stopped"] = "the day's AI ceiling was reached"
                break
    report.update(tagged=tagged, skipped=skipped, remaining=len(todo) - tagged - skipped)
    return report


async def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="count and estimate only (the default)")
    mode.add_argument("--apply", action="store_true", help="tag, within today's AI budget")
    parser.add_argument("--limit", type=int, default=10_000, help="at most this many creators this run")
    parser.add_argument("--caption-chars", type=int, default=DEFAULT_CAPTION_CHARS,
                        help="average caption length for the token estimate")
    args = parser.parse_args(argv)
    print(f"Database: {server.db.name}")
    report = await backfill(apply=args.apply, limit=args.limit, caption_chars=args.caption_chars)
    print(json.dumps(report, indent=2, default=str))
    if not args.apply:
        print("Dry run. Nothing was called or written. Re-run with --apply to tag.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
