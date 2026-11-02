#!/usr/bin/env python3
"""Bring every stored creator payout window inside the public 7-day promise.

    python clamp_payout_days.py            # dry run: lists what would change
    python clamp_payout_days.py --apply    # write, and audit each change

The public site says "paid within 7 days of approval". The window could be
stored anywhere from 0 to 180 days — on the platform setting and per brief —
so the promise was one a form field could quietly break. The ceiling is now 7
(`_CREATOR_PAYOUT_MAX`), and this is the one-off that brings stored values
inside it.

- **The same function the server runs on boot** (`clamp_creator_payout_days`),
  so a deploy clamps whether or not anybody remembers this script. The script
  is for reading the list before it happens, and for the record.
- **Idempotent.** It selects only values above the ceiling, and a value it has
  clamped is no longer above it.
- **Frozen terms are not touched.** A snapshot is what somebody was told at
  acceptance; the due date every surface computes reads the campaign.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import server  # noqa: E402  (env has to load first)


async def main(apply: bool) -> dict:
    report = await server.clamp_creator_payout_days(apply=apply)
    verb = "Clamped" if apply else "Would clamp"
    if report["setting_before"] is not None:
        print(f"{verb} the platform setting: {report['setting_before']} → "
              f"{server._CREATOR_PAYOUT_MAX} days")
    else:
        print("The platform setting is already inside the promise.")
    if not report["campaigns"]:
        print("No campaign carries a window longer than the promise.")
    for c in report["campaigns"]:
        print(f"{verb} {c['reference'] or c['id']}  {c['title']!r}: "
              f"{c['before']} → {c['after']} days")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="write the changes")
    asyncio.run(main(parser.parse_args().apply))
