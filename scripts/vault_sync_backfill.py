#!/usr/bin/env python3
"""Reconcile the Obsidian vault zone with kaori SQLite.

Idempotent: writes any missing/stale `.md` files for posts/summaries, copies
photo attachments, and removes orphaned files whose source rows no longer exist.

Reads kaori config (respects KAORI_TEST_MODE, KAORI_VAULT_PATH, etc.).

Usage:
    python -m scripts.vault_sync_backfill                 # full sweep
    python -m scripts.vault_sync_backfill --dry-run       # report only
    python -m scripts.vault_sync_backfill --posts-only
    python -m scripts.vault_sync_backfill --summaries-only
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kaori.config import (  # noqa: E402
    TEST_MODE,
    VAULT_PATH,
    VAULT_SYNC_ENABLED,
    VAULT_SYNC_ROOT,
)
from kaori.services import vault_sync_service  # noqa: E402


async def _run(args: argparse.Namespace) -> dict:
    return await vault_sync_service.backfill_all(
        dry_run=args.dry_run,
        posts=not args.summaries_only,
        summaries=not args.posts_only,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--posts-only", action="store_true")
    grp.add_argument("--summaries-only", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="run even if KAORI_VAULT_SYNC_ENABLED is false",
    )
    args = parser.parse_args()

    if TEST_MODE:
        print("KAORI_TEST_MODE is on — refusing to write to the real vault.", file=sys.stderr)
        return 1

    if not VAULT_SYNC_ENABLED and not args.force:
        print("KAORI_VAULT_SYNC_ENABLED is false. Use --force to run anyway.", file=sys.stderr)
        return 1

    print(f"Vault: {VAULT_PATH / VAULT_SYNC_ROOT}")
    if args.dry_run:
        print("DRY RUN — no files will be written.")

    report = asyncio.run(_run(args))

    print()
    print("=== Backfill report ===")
    for k, v in report.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
