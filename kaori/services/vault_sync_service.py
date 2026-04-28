"""One-way sync: kaori posts/summaries → Obsidian vault as Markdown.

SQLite is the source of truth. Vault gets fire-and-forget mirrors triggered from
the service layer after DB writes succeed. All errors are logged; sync failure
must never break the API request that triggered it.

This module is a no-op when KAORI_VAULT_SYNC_ENABLED is false or when
KAORI_TEST_MODE is true (test runs must never touch the real vault).

Layout under <vault>/<sync_root>/:
    posts/YYYY-MM-DD-post-<id>.md
    summaries/daily/YYYY-MM-DD.md      (latest daily per date)
    summaries/weekly/YYYY-Www.md       (latest weekly per ISO week)
    attachments/post-<id>/<filename>
"""

import asyncio
import json
import logging
import os
import shutil
from datetime import date as date_cls
from pathlib import Path
from typing import Literal

from kaori.config import (
    PHOTOS_DIR,
    TEST_MODE,
    VAULT_PATH,
    VAULT_SYNC_ENABLED,
    VAULT_SYNC_ROOT,
)
from kaori.storage import post_repo, summary_repo

logger = logging.getLogger(__name__)

# Single global lock: serializes vault writes within the process. Fine for a
# personal-scale app; avoids the unbounded growth of per-id lock dicts.
_sync_lock = asyncio.Lock()

# Strong refs to in-flight fire-and-forget tasks. asyncio only holds weak refs,
# so without this an unreferenced task can be GC'd mid-execution.
_pending_tasks: set[asyncio.Task] = set()


def _sync_active() -> bool:
    """True if vault sync should perform writes. Test mode always disables it."""
    return VAULT_SYNC_ENABLED and not TEST_MODE


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _vault_root() -> Path:
    return VAULT_PATH / VAULT_SYNC_ROOT


def _post_md_path(row: dict) -> Path:
    return _vault_root() / "posts" / f"{row['date']}-post-{row['id']}.md"


def _post_attach_dir(post_id: int) -> Path:
    return _vault_root() / "attachments" / f"post-{post_id}"


def _summary_md_path(row: dict) -> Path:
    if row["type"] == "weekly":
        try:
            d = date_cls.fromisoformat(row["date"])
            iso_year, iso_week, _ = d.isocalendar()
            name = f"{iso_year}-W{iso_week:02d}.md"
        except ValueError:
            name = f"{row['date']}.md"
        return _vault_root() / "summaries" / "weekly" / name
    return _vault_root() / "summaries" / "daily" / f"{row['date']}.md"


def _photo_rel_paths(row: dict) -> list[str]:
    raw = row.get("photo_paths")
    if raw:
        try:
            paths = json.loads(raw)
            if paths:
                return list(paths)
        except (json.JSONDecodeError, TypeError):
            pass
    single = row.get("photo_path")
    return [single] if single else []


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _yaml_scalar(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return json.dumps(str(v), ensure_ascii=False)


def _render_post(row: dict, attachment_filenames: list[str]) -> str:
    fm = "\n".join([
        "---",
        "source: kaori",
        "kind: post",
        f"post_id: {int(row['id'])}",
        f"date: {row['date']}",
        f"created_at: {_yaml_scalar(row.get('created_at'))}",
        f"updated_at: {_yaml_scalar(row.get('updated_at'))}",
        f"title: {_yaml_scalar(row.get('title'))}",
        f"is_pinned: {_yaml_scalar(bool(row.get('is_pinned')))}",
        f"post_source: {_yaml_scalar(row.get('source') or 'user')}",
        "tags: [kaori, post]",
        "---",
        "",
    ])
    body = (row.get("content") or "").rstrip()
    parts = [fm, body, ""]

    if attachment_filenames:
        parts.append("## Photos")
        parts.append("")
        rel_dir = f"../attachments/post-{int(row['id'])}"
        for fn in attachment_filenames:
            parts.append(f"![{fn}]({rel_dir}/{fn})")
        desc = (row.get("photo_description") or "").strip()
        if desc:
            parts.append("")
            parts.append("> _Photo description (LLM-extracted):_")
            for line in desc.splitlines():
                parts.append(f"> {line}")
        parts.append("")

    return "\n".join(parts)


def _render_summary(row: dict) -> str:
    fm = "\n".join([
        "---",
        "source: kaori",
        "kind: summary",
        f"summary_type: {row['type']}",
        f"date: {row['date']}",
        f"created_at: {_yaml_scalar(row.get('created_at'))}",
        f"llm_backend: {_yaml_scalar(row.get('llm_backend'))}",
        f"model: {_yaml_scalar(row.get('model'))}",
        f"summary_id: {int(row['id'])}",
        f"tags: [kaori, summary, {row['type']}]",
        "---",
        "",
    ])
    body = (row.get("summary_text") or "").rstrip() + "\n"
    return fm + body


# ---------------------------------------------------------------------------
# Filesystem
# ---------------------------------------------------------------------------

def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def _sync_attachments(post_id: int, photo_rel_paths: list[str]) -> list[str]:
    """Copy photos into attachments/post-<id>/, prune orphans. Returns filenames now present."""
    attach_dir = _post_attach_dir(post_id)
    desired: dict[str, Path] = {}
    for rel in photo_rel_paths:
        if not rel:
            continue
        src = PHOTOS_DIR / rel
        if not src.exists():
            logger.warning("vault_sync: source photo missing %s (post %d)", src, post_id)
            continue
        desired[Path(rel).name] = src

    if not desired:
        if attach_dir.exists():
            shutil.rmtree(attach_dir, ignore_errors=True)
        return []

    attach_dir.mkdir(parents=True, exist_ok=True)
    existing = {p.name: p for p in attach_dir.iterdir() if p.is_file()}

    for name in list(existing):
        if name not in desired:
            existing[name].unlink(missing_ok=True)

    for name, src in desired.items():
        dst = attach_dir / name
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dst)

    return sorted(desired.keys())


def _delete_post_files(post_id: int) -> None:
    for p in (_vault_root() / "posts").glob(f"*-post-{post_id}.md"):
        p.unlink(missing_ok=True)
    shutil.rmtree(_post_attach_dir(post_id), ignore_errors=True)


# ---------------------------------------------------------------------------
# Public sync API
# ---------------------------------------------------------------------------

async def sync_post(post_id: int, op: Literal["create", "update", "delete"]) -> None:
    if not _sync_active():
        return
    async with _sync_lock:
        if op == "delete":
            _delete_post_files(post_id)
            logger.info("vault_sync: deleted post %d", post_id)
            return
        row = await post_repo.get(post_id)
        if not row:
            logger.warning("vault_sync: post %d not found (op=%s)", post_id, op)
            return
        attachments = _sync_attachments(post_id, _photo_rel_paths(row))
        _atomic_write_text(_post_md_path(row), _render_post(row, attachments))
        logger.info("vault_sync: wrote post %d (%s)", post_id, op)


async def sync_summary(summary_id: int) -> None:
    if not _sync_active():
        return
    async with _sync_lock:
        row = await summary_repo.get_by_id(summary_id)
        if not row:
            logger.warning("vault_sync: summary %d not found", summary_id)
            return
        # Only mirror if this is the latest summary for (type, date) — older retriggers stay in DB only.
        latest = await summary_repo.get_latest(row["type"], row["date"])
        if latest and latest["id"] != summary_id:
            logger.info("vault_sync: summary %d superseded by %d, skipping", summary_id, latest["id"])
            return
        _atomic_write_text(_summary_md_path(row), _render_summary(row))
        logger.info("vault_sync: wrote summary %d (%s/%s)", summary_id, row["type"], row["date"])


# ---------------------------------------------------------------------------
# Backfill
# ---------------------------------------------------------------------------

async def backfill_all(*, dry_run: bool = False, posts: bool = True, summaries: bool = True) -> dict:
    """Reconcile the vault zone with the DB. Idempotent."""
    report = {
        "posts_written": 0, "posts_orphans_removed": 0,
        "summaries_written": 0, "summaries_orphans_removed": 0,
        "dry_run": dry_run,
    }
    root = _vault_root()

    if posts:
        all_posts = await post_repo.get_history(limit=10_000)
        live_ids = {int(p["id"]) for p in all_posts}
        for p in all_posts:
            attachments = _photo_rel_paths(p)
            if not dry_run:
                names = _sync_attachments(int(p["id"]), attachments)
                _atomic_write_text(_post_md_path(p), _render_post(p, names))
            report["posts_written"] += 1
        posts_dir = root / "posts"
        if posts_dir.exists():
            for f in posts_dir.glob("*-post-*.md"):
                try:
                    pid = int(f.stem.rsplit("-post-", 1)[1])
                except (ValueError, IndexError):
                    continue
                if pid not in live_ids:
                    if not dry_run:
                        f.unlink(missing_ok=True)
                        shutil.rmtree(_post_attach_dir(pid), ignore_errors=True)
                    report["posts_orphans_removed"] += 1

    if summaries:
        for stype in ("daily", "weekly"):
            recents = await summary_repo.list_recent(stype, limit=10_000)
            seen_keys: set[str] = set()
            expected_files: set[Path] = set()
            for s in recents:
                key = f"{s['type']}|{s['date']}"
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                expected_files.add(_summary_md_path(s))
                if not dry_run:
                    _atomic_write_text(_summary_md_path(s), _render_summary(s))
                report["summaries_written"] += 1
            sub_dir = root / "summaries" / stype
            if sub_dir.exists():
                for f in sub_dir.glob("*.md"):
                    if f not in expected_files:
                        if not dry_run:
                            f.unlink(missing_ok=True)
                        report["summaries_orphans_removed"] += 1

    return report


# ---------------------------------------------------------------------------
# Fire-and-forget triggers (called from service layer)
# ---------------------------------------------------------------------------

def _safe(coro) -> None:
    async def runner():
        try:
            await coro
        except Exception:
            logger.exception("vault_sync: background task failed")
    task = asyncio.create_task(runner())
    _pending_tasks.add(task)
    task.add_done_callback(_pending_tasks.discard)


def trigger_sync_post(post_id: int, op: Literal["create", "update", "delete"]) -> None:
    if not _sync_active():
        return
    _safe(sync_post(post_id, op))


def trigger_sync_summary(summary_id: int) -> None:
    if not _sync_active():
        return
    _safe(sync_summary(summary_id))
