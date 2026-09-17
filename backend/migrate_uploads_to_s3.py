#!/usr/bin/env python3
"""Copy every file already on local disk into the configured bucket.

The move to object storage was a change of *where the bytes are*, not of what
a record says: a stored name is still a stored name and a public URL is still
`/uploads/<name>`. So this migration copies files and rewrites nothing in the
database — there is nothing to rewrite, which is the property that made the
change safe to make at all.

**Run it before pointing production at S3, not after.** The order matters: a
box that starts on S3 with an empty bucket serves 404s for every document and
cover that already exists, and the rows that point at them look broken rather
than empty.

    # 1. see what would move, touching nothing
    python migrate_uploads_to_s3.py

    # 2. do it
    python migrate_uploads_to_s3.py --apply

**Idempotent by default**: an object already in the bucket is skipped, so a run
interrupted half way is resumed by running it again. `--overwrite` forces the
copy for the case where a file was replaced on disk after a partial run.

**Nothing is deleted from disk.** The local copy is the fallback if a copy went
wrong, and a migration whose first act is a delete is one nobody can check
afterwards. Remove the directories by hand once the bucket is verified.

It reads `STORAGE_BACKEND`/`S3_*` out of the same environment `server.py` does,
so a bucket this can reach is a bucket the app can reach.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")


def _dirs() -> tuple:
    public = Path(os.environ.get("UPLOAD_DIR", str(ROOT_DIR / "uploads")))
    private = Path(
        os.environ.get("PRIVATE_UPLOAD_DIR", str(ROOT_DIR / "private_uploads"))
    )
    return public, private


def _guess_content_type(path: Path) -> str:
    """The type from the leading bytes, exactly as the upload routes decide it.

    Not from the extension: the extension on disk was itself derived from the
    bytes when the file was stored, so reading it back would be trusting a
    derivation rather than the source. `server.sniff_draft_type` covers the
    widest set — images, PDFs and video — which is what this directory holds.
    """
    import server

    with open(path, "rb") as fh:
        head = fh.read(64)
    sniffed = server.sniff_draft_type(head) or server.sniff_document_type(head)
    return sniffed[0] if sniffed else "application/octet-stream"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually copy. Without it this reports and touches nothing.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="re-copy files already in the bucket (default: skip them).",
    )
    args = parser.parse_args()

    # Forced on so this script can be run against a .env that still says local
    # — which is the ordinary case, since the whole point is to fill the bucket
    # *before* the app is switched over.
    os.environ["STORAGE_BACKEND"] = "s3"
    if not os.environ.get("S3_BUCKET", "").strip():
        print(
            "S3_BUCKET is not set. Configure the bucket in backend/.env first —\n"
            "see DEPLOYMENT.md for the full list.",
            file=sys.stderr,
        )
        return 1

    import server  # after the env is set, so it builds the S3 backend

    storage = server.STORAGE
    public_dir, private_dir = _dirs()

    plan = []
    for directory, private in ((public_dir, False), (private_dir, True)):
        if not directory.is_dir():
            print(f"  {directory} does not exist — nothing to move.")
            continue
        for path in sorted(directory.iterdir()):
            if path.is_file() and not path.name.startswith("."):
                plan.append((path, private))

    if not plan:
        print("Nothing on disk to move.")
        return 0

    total = len(plan)
    copied = skipped = failed = 0
    print(f"{total} file(s) on disk.\n")

    for path, private in plan:
        where = "private" if private else "public"
        key = server.S3Storage.key(path.name, private=private)

        if not args.overwrite and storage.exists(path.name, private=private):
            skipped += 1
            print(f"  skip   {where:<7} {key}  (already there)")
            continue

        if not args.apply:
            print(f"  would  {where:<7} {key}  ({path.stat().st_size} bytes)")
            continue

        try:
            with open(path, "rb") as fh:
                storage.put(
                    path.name,
                    fh,
                    content_type=_guess_content_type(path),
                    private=private,
                )
            copied += 1
            print(f"  copied {where:<7} {key}")
        except Exception as exc:  # one bad file must not end the run
            failed += 1
            print(f"  FAILED {where:<7} {key}: {exc}", file=sys.stderr)

    print()
    if not args.apply:
        print(f"Dry run. {total - skipped} file(s) would be copied, {skipped} skipped.")
        print("Re-run with --apply to do it.")
        return 0

    print(f"Copied {copied}, skipped {skipped}, failed {failed}.")
    if failed:
        print(
            "\nSome files did not copy. Nothing was deleted from disk, so this is\n"
            "safe to run again — it will skip what already landed.",
            file=sys.stderr,
        )
        return 1
    print("\nThe local files were left alone. Verify the bucket, then remove them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
