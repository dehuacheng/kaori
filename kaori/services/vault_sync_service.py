"""One-way sync: kaori personal data → Obsidian vault as Markdown + CSV snapshots.

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
    chats/YYYY-MM-DD-session-<uuid>.md (one file per user-source agent session)
    meals/YYYY-MM-DD.md                (one file per day; rewritten in full on any change)
    body/YYYY-MM.md                    (rolling per-month table of weights)
    workouts/YYYY-MM-DD-workout-<id>.md (one file per workout; sets + LLM summary)
    data/meals.csv                     (flat snapshot for skills)
    data/body_measurements.csv         (flat snapshot for skills)
    data/workouts.csv                  (flat snapshot for skills)
"""

import asyncio
import csv
import io
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
from kaori.database import get_db
from kaori.storage import (
    agent_message_repo,
    agent_session_repo,
    meal_repo,
    post_repo,
    summary_repo,
    weight_repo,
    workout_analysis_repo,
    workout_repo,
)

# Cap each tool result block included in the rendered chat transcript.
# Long JSON dumps from feed snapshots etc. would otherwise dominate the file.
_TOOL_RESULT_RENDER_MAX = 4000

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


def _session_md_path(row: dict) -> Path:
    created = (row.get("created_at") or "")[:10] or "undated"
    return _vault_root() / "chats" / f"{created}-session-{row['id']}.md"


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


def _extract_text(content) -> str:
    """Pull plain text out of an Anthropic-style message content (str or block list)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                t = block.get("text")
                if t:
                    out.append(t)
        return "\n\n".join(out)
    return str(content)


def _render_message(msg_row: dict) -> str:
    """Render a single agent_messages row to a markdown block.

    Tolerates malformed JSON and unfamiliar shapes — falls back to a fenced raw dump
    rather than raising, since vault sync must not break on a single bad row.
    """
    role = msg_row.get("role") or "unknown"
    raw = msg_row.get("content") or ""
    try:
        msg = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return f"## {role.title()}\n\n```\n{raw}\n```\n"
    if not isinstance(msg, dict):
        return f"## {role.title()}\n\n```\n{raw}\n```\n"

    parts: list[str] = []
    content = msg.get("content")

    if role == "user":
        parts.append("## User")
        text = _extract_text(content).strip()
        if text:
            parts.extend(["", text])
    elif role == "assistant":
        parts.append("## Assistant")
        thinking = (msg.get("_thinking") or "").strip()
        if thinking:
            parts.append("")
            parts.append("> _Thinking:_")
            for line in thinking.splitlines():
                parts.append(f"> {line}")
        text = _extract_text(content).strip()
        if text:
            parts.extend(["", text])
        # Anthropic tool_use blocks live inside content list.
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    name = block.get("name", "?")
                    inp = json.dumps(block.get("input", {}), ensure_ascii=False, indent=2)
                    parts.extend(["", f"**Tool call:** `{name}`", "```json", inp, "```"])
        # OpenAI/DeepSeek tool_calls are a sibling field; arguments is a JSON string.
        for tc in msg.get("tool_calls") or []:
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") or {}
            name = fn.get("name", "?")
            raw_args = fn.get("arguments", "")
            try:
                inp = json.dumps(json.loads(raw_args), ensure_ascii=False, indent=2)
            except (json.JSONDecodeError, TypeError):
                inp = raw_args
            parts.extend(["", f"**Tool call:** `{name}`", "```json", inp, "```"])
    elif role == "tool_result":
        # Anthropic format: content is a list of {type:"tool_result", tool_use_id, content, _output}
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                output = block.get("_output")
                if not output:
                    output = _extract_text(block.get("content"))
                output = (output or "").rstrip()
                if len(output) > _TOOL_RESULT_RENDER_MAX:
                    output = output[:_TOOL_RESULT_RENDER_MAX] + "\n… [truncated]"
                parts.extend(["### Tool result", "", "```", output, "```"])
        else:
            # OpenAI-shaped: {role: "tool", tool_call_id, content, _output}
            output = msg.get("_output") or (content if isinstance(content, str) else "")
            if len(output) > _TOOL_RESULT_RENDER_MAX:
                output = output[:_TOOL_RESULT_RENDER_MAX] + "\n… [truncated]"
            parts.extend(["### Tool result", "", "```", output.rstrip(), "```"])
    elif role == "summary":
        parts.append("## (compaction summary)")
        text = _extract_text(content).strip()
        if text:
            parts.extend(["", text])
    else:
        parts.append(f"## {role.title()}")
        text = _extract_text(content).strip()
        if text:
            parts.extend(["", text])

    parts.append("")
    return "\n".join(parts)


def _render_session(row: dict, messages: list[dict]) -> str:
    fm = "\n".join([
        "---",
        "source: kaori",
        "kind: chat_session",
        f"session_id: {_yaml_scalar(row['id'])}",
        f"title: {_yaml_scalar(row.get('title'))}",
        f"status: {_yaml_scalar(row.get('status') or 'active')}",
        f"backend: {_yaml_scalar(row.get('backend'))}",
        f"model: {_yaml_scalar(row.get('model'))}",
        f"post_source: {_yaml_scalar(row.get('source') or 'user')}",
        f"message_count: {int(row.get('message_count') or 0)}",
        f"token_count_approx: {int(row.get('token_count_approx') or 0)}",
        f"created_at: {_yaml_scalar(row.get('created_at'))}",
        f"updated_at: {_yaml_scalar(row.get('updated_at'))}",
        f"summary_updated_at: {_yaml_scalar(row.get('summary_updated_at'))}",
        "tags: [kaori, chat]",
        "---",
        "",
    ])
    parts: list[str] = [fm]

    summary = (row.get("summary") or "").strip()
    if summary:
        parts.append("## Summary")
        parts.append("")
        parts.append(summary)
        parts.append("")

    parts.append("## Transcript")
    parts.append("")
    for m in messages:
        parts.append(_render_message(m))

    return "\n".join(parts)


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


def _delete_session_files(session_id: str) -> None:
    for p in (_vault_root() / "chats").glob(f"*-session-{session_id}.md"):
        p.unlink(missing_ok=True)


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


async def sync_session(session_id: str, op: Literal["create", "update", "delete"]) -> None:
    """Mirror an agent chat session to the vault. Heartbeat sessions are skipped."""
    if not _sync_active():
        return
    async with _sync_lock:
        if op == "delete":
            _delete_session_files(session_id)
            logger.info("vault_sync: deleted session %s", session_id)
            return
        row = await agent_session_repo.get(session_id)
        if not row:
            logger.warning("vault_sync: session %s not found (op=%s)", session_id, op)
            return
        if (row.get("source") or "user") != "user":
            # Heartbeat / agent-self sessions: not human chats — skip.
            return
        messages = await agent_message_repo.list_by_session(session_id)
        _atomic_write_text(_session_md_path(row), _render_session(row, messages))
        logger.info("vault_sync: wrote session %s (%s, %d msgs)", session_id, op, len(messages))


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

async def backfill_all(
    *,
    dry_run: bool = False,
    posts: bool = True,
    summaries: bool = True,
    sessions: bool = True,
    meals: bool = True,
    body: bool = True,
    workouts: bool = True,
) -> dict:
    """Reconcile the vault zone with the DB. Idempotent."""
    report = {
        "posts_written": 0, "posts_orphans_removed": 0,
        "summaries_written": 0, "summaries_orphans_removed": 0,
        "sessions_written": 0, "sessions_orphans_removed": 0,
        "meals_days_written": 0, "meals_orphans_removed": 0, "meals_csv_rows": 0,
        "body_months_written": 0, "body_orphans_removed": 0, "body_csv_rows": 0,
        "workouts_written": 0, "workouts_orphans_removed": 0, "workouts_csv_rows": 0,
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

    if sessions:
        all_sessions = await agent_session_repo.list_all(
            status=None, source="user", limit=10_000,
        )
        live_ids = {s["id"] for s in all_sessions}
        for s in all_sessions:
            if not dry_run:
                msgs = await agent_message_repo.list_by_session(s["id"])
                _atomic_write_text(_session_md_path(s), _render_session(s, msgs))
            report["sessions_written"] += 1
        chats_dir = root / "chats"
        if chats_dir.exists():
            for f in chats_dir.glob("*-session-*.md"):
                try:
                    sid = f.stem.rsplit("-session-", 1)[1]
                except IndexError:
                    continue
                if sid not in live_ids:
                    if not dry_run:
                        f.unlink(missing_ok=True)
                    report["sessions_orphans_removed"] += 1

    if meals:
        # Group every meal by its date, then write one .md per date.
        all_meals = await _all_meals_with_nutrition()
        by_date: dict[str, list[dict]] = {}
        for m in all_meals:
            by_date.setdefault(m["date"], []).append(m)
        for d, day_meals in by_date.items():
            if not dry_run:
                _atomic_write_text(_meal_day_md_path(d), _render_meal_day(d, day_meals))
            report["meals_days_written"] += 1
        meals_dir = root / "meals"
        if meals_dir.exists():
            live_dates = set(by_date.keys())
            for f in meals_dir.glob("*.md"):
                if f.stem not in live_dates:
                    if not dry_run:
                        f.unlink(missing_ok=True)
                    report["meals_orphans_removed"] += 1
        if not dry_run:
            report["meals_csv_rows"] = await _regen_meals_csv()

    if body:
        all_body = await _all_body_measurements_asc()
        by_month: dict[str, list[dict]] = {}
        for r in all_body:
            by_month.setdefault(r["date"][:7], []).append(r)
        for month, rows in by_month.items():
            if not dry_run:
                # Pass any date in the month; _body_month_md_path slices to YYYY-MM.
                _atomic_write_text(
                    _body_month_md_path(rows[0]["date"]),
                    _render_body_month(month, rows),
                )
            report["body_months_written"] += 1
        body_dir = root / "body"
        if body_dir.exists():
            live_months = set(by_month.keys())
            for f in body_dir.glob("*.md"):
                if f.stem not in live_months:
                    if not dry_run:
                        f.unlink(missing_ok=True)
                    report["body_orphans_removed"] += 1
        if not dry_run:
            report["body_csv_rows"] = await _regen_body_csv()

    if workouts:
        # list_workouts returns shallow rows; we need the full tree per workout.
        shallow = await workout_repo.list_workouts(limit=10_000)
        live_ids: set[int] = set()
        for s in shallow:
            wid = int(s["id"])
            live_ids.add(wid)
            workout = await workout_repo.get_workout(wid)
            if not workout:
                continue
            analysis = await workout_analysis_repo.get_active(wid)
            if not dry_run:
                target = _workout_md_path(workout)
                # Wipe any stale-date file for this workout id before writing the current one.
                for p in (root / "workouts").glob(f"*-workout-{wid}.md"):
                    if p != target:
                        p.unlink(missing_ok=True)
                _atomic_write_text(target, _render_workout(workout, analysis))
            report["workouts_written"] += 1
        workouts_dir = root / "workouts"
        if workouts_dir.exists():
            for f in workouts_dir.glob("*-workout-*.md"):
                try:
                    wid = int(f.stem.rsplit("-workout-", 1)[1])
                except (ValueError, IndexError):
                    continue
                if wid not in live_ids:
                    if not dry_run:
                        f.unlink(missing_ok=True)
                    report["workouts_orphans_removed"] += 1
        if not dry_run:
            report["workouts_csv_rows"] = await _regen_workouts_csv()

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


def trigger_sync_session(session_id: str, op: Literal["create", "update", "delete"]) -> None:
    if not _sync_active():
        return
    _safe(sync_session(session_id, op))


# ===========================================================================
# Personal-data domains: meals / body measurements / workouts
#
# Same patterns as posts/summaries/sessions above, but with two output forms:
#   - per-day or per-entity Markdown for human/LLM browsing
#   - flat CSV snapshots under data/ for tools that prefer tables
# CSVs are tiny — regenerated in full on every sync.
# ===========================================================================

# ---------------------------------------------------------------------------
# Path helpers (extended)
# ---------------------------------------------------------------------------

def _meal_day_md_path(date_str: str) -> Path:
    return _vault_root() / "meals" / f"{date_str}.md"


def _body_month_md_path(date_str: str) -> Path:
    """date_str is YYYY-MM-DD; we use the YYYY-MM prefix as the file name."""
    return _vault_root() / "body" / f"{date_str[:7]}.md"


def _workout_md_path(workout: dict) -> Path:
    return _vault_root() / "workouts" / f"{workout['date']}-workout-{int(workout['id'])}.md"


def _data_csv_path(name: str) -> Path:
    return _vault_root() / "data" / f"{name}.csv"


# ---------------------------------------------------------------------------
# Rendering helpers (extended)
# ---------------------------------------------------------------------------

def _fmt_num(v) -> str:
    """Format a number for markdown tables: '' for None, trim trailing .0."""
    if v is None:
        return ""
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else f"{v:g}"
    return str(v)


def _md_cell(s: str | None) -> str:
    """Sanitize a string for inclusion in a markdown table cell."""
    if not s:
        return ""
    return s.replace("|", "\\|").replace("\n", " ").strip()


def _render_meal_day(date_str: str, meals: list[dict]) -> str:
    """Render one day's meals. Sorted by created_at then id (stable chronological order)."""
    sorted_meals = sorted(meals, key=lambda m: (m.get("created_at") or "", int(m.get("id", 0))))
    fm = "\n".join([
        "---",
        "source: kaori",
        "kind: meals_day",
        f"date: {date_str}",
        f"meal_count: {len(sorted_meals)}",
        "tags: [kaori, meals]",
        "---",
        "",
    ])
    parts: list[str] = [fm, f"# {date_str} — meals", ""]

    total_cal = total_p = total_c = total_f = 0.0
    have_any_nutrition = False
    for m in sorted_meals:
        mtype = m.get("meal_type") or "meal"
        meal_id = int(m["id"])
        desc = (m.get("description") or "(no description)").strip()
        parts.append(f"## {mtype} — meal_id {meal_id}")
        parts.append("")
        parts.append(desc)
        cal = m.get("calories")
        p = m.get("protein_g")
        c = m.get("carbs_g")
        f = m.get("fat_g")
        if cal is not None or p is not None or c is not None or f is not None:
            have_any_nutrition = True
            parts.append("")
            bullets = []
            if cal is not None:
                bullets.append(f"- {_fmt_num(cal)} kcal")
                total_cal += cal
            if p is not None:
                bullets.append(f"- protein: {_fmt_num(p)} g")
                total_p += p
            if c is not None:
                bullets.append(f"- carbs: {_fmt_num(c)} g")
                total_c += c
            if f is not None:
                bullets.append(f"- fat: {_fmt_num(f)} g")
                total_f += f
            parts.extend(bullets)
        notes = (m.get("notes") or "").strip()
        if notes:
            parts.append("")
            parts.append(f"_notes: {notes}_")
        parts.append("")

    if have_any_nutrition:
        parts.append("---")
        parts.append("")
        parts.append(
            f"**Day total:** {_fmt_num(total_cal)} kcal · "
            f"P {_fmt_num(total_p)}g · "
            f"C {_fmt_num(total_c)}g · "
            f"F {_fmt_num(total_f)}g"
        )
        parts.append("")

    return "\n".join(parts)


def _render_body_month(month_str: str, rows: list[dict]) -> str:
    """rows: body_measurements for the month, ordered by date asc, id asc."""
    fm = "\n".join([
        "---",
        "source: kaori",
        "kind: body_month",
        f"month: {month_str}",
        f"entries: {len(rows)}",
        "tags: [kaori, body]",
        "---",
        "",
    ])
    parts: list[str] = [fm, f"# Body — {month_str}", ""]
    if not rows:
        parts.append("(no entries)")
        parts.append("")
        return "\n".join(parts)
    parts.append("| date | weight (kg) | waist@navel (cm) | notes |")
    parts.append("|------|-------------|------------------|-------|")
    for r in rows:
        parts.append(
            f"| {r['date']} | {_fmt_num(r.get('weight_kg'))} | "
            f"{_fmt_num(r.get('waist_at_navel_cm'))} | {_md_cell(r.get('notes'))} |"
        )
    parts.append("")
    return "\n".join(parts)


def _render_workout(workout: dict, analysis: dict | None) -> str:
    fm = "\n".join([
        "---",
        "source: kaori",
        "kind: workout",
        f"workout_id: {int(workout['id'])}",
        f"date: {workout['date']}",
        f"activity_type: {_yaml_scalar(workout.get('activity_type'))}",
        f"duration_minutes: {_yaml_scalar(workout.get('duration_minutes'))}",
        f"calories_burned: {_yaml_scalar(workout.get('calories_burned'))}",
        f"workout_source: {_yaml_scalar(workout.get('source') or 'manual')}",
        f"created_at: {_yaml_scalar(workout.get('created_at'))}",
        "tags: [kaori, workout]",
        "---",
        "",
    ])
    parts: list[str] = [fm, f"# Workout {workout['date']} — id {int(workout['id'])}", ""]

    if analysis:
        summary = (analysis.get("summary") or "").strip()
        if summary:
            parts.append("## Summary")
            parts.append("")
            parts.append(summary)
            parts.append("")
        trainer = (analysis.get("trainer_notes") or "").strip()
        if trainer:
            parts.append("> _Trainer notes:_")
            for ln in trainer.splitlines():
                parts.append(f"> {ln}")
            parts.append("")

    if (workout.get("notes") or "").strip():
        parts.append("## Notes")
        parts.append("")
        parts.append(workout["notes"].strip())
        parts.append("")

    parts.append("## Exercises")
    parts.append("")
    for ex in workout.get("exercises", []):
        cat = ex.get("exercise_category") or "—"
        parts.append(f"### {ex.get('exercise_name', 'unknown')} ({cat})")
        parts.append("")
        sets = ex.get("sets") or []
        if sets:
            parts.append("| set | reps | weight (kg) | duration (s) | notes |")
            parts.append("|-----|------|-------------|--------------|-------|")
            for s in sets:
                parts.append(
                    f"| {s.get('set_number', '')} | {_fmt_num(s.get('reps'))} | "
                    f"{_fmt_num(s.get('weight_kg'))} | {_fmt_num(s.get('duration_seconds'))} | "
                    f"{_md_cell(s.get('notes'))} |"
                )
            parts.append("")
        ex_notes = (ex.get("notes") or "").strip()
        if ex_notes:
            parts.append(f"_{ex_notes}_")
            parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    """Atomic CSV write. csv.writer handles quoting/escaping."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    _atomic_write_text(path, buf.getvalue())


def _csv_num(v) -> str:
    """CSV numeric cell: blank for None, integer if whole, else float repr."""
    if v is None:
        return ""
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else repr(v)
    return str(v)


# ---------------------------------------------------------------------------
# Bulk DB readers (vault-only — kept here to avoid leaking joins into repos
# that don't need them)
# ---------------------------------------------------------------------------

async def _all_meals_with_nutrition() -> list[dict]:
    """Every meal with override>analysis-merged nutrition, oldest first."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT m.id, m.date, m.meal_type, m.notes, "
            "COALESCE(mo.description, a.description, m.description) AS description, "
            "COALESCE(mo.calories, a.calories) AS calories, "
            "COALESCE(mo.protein_g, a.protein_g) AS protein_g, "
            "COALESCE(mo.carbs_g, a.carbs_g) AS carbs_g, "
            "COALESCE(mo.fat_g, a.fat_g) AS fat_g "
            "FROM meals m "
            "LEFT JOIN meal_overrides mo ON mo.meal_id = m.id "
            "LEFT JOIN meal_analyses a ON a.meal_id = m.id AND a.is_active = 1 "
            "ORDER BY m.date ASC, m.id ASC"
        )
        return [dict(r) for r in await cursor.fetchall()]
    finally:
        await db.close()


async def _all_body_measurements_asc() -> list[dict]:
    """Every body measurement, oldest first (ascending by date, then id)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, date, weight_kg, waist_at_navel_cm, notes, created_at "
            "FROM body_measurements "
            "ORDER BY date ASC, id ASC"
        )
        return [dict(r) for r in await cursor.fetchall()]
    finally:
        await db.close()


async def _all_workouts_summary() -> list[dict]:
    """Every workout joined with its active analysis totals, oldest first."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT w.id, w.date, w.activity_type, w.duration_minutes, "
            "wa.total_volume_kg, wa.total_sets, wa.total_reps "
            "FROM workouts w "
            "LEFT JOIN workout_analyses wa ON wa.workout_id = w.id AND wa.is_active = 1 "
            "ORDER BY w.date ASC, w.id ASC"
        )
        return [dict(r) for r in await cursor.fetchall()]
    finally:
        await db.close()


async def _meal_dates_with_rows() -> set[str]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT DISTINCT date FROM meals")
        return {r["date"] for r in await cursor.fetchall()}
    finally:
        await db.close()


async def _body_months_with_rows() -> set[str]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT DISTINCT substr(date, 1, 7) AS m FROM body_measurements")
        return {r["m"] for r in await cursor.fetchall()}
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# CSV regeneration (lock-agnostic — callers should hold _sync_lock when called
# from a sync_*; backfill_all calls them directly with no concurrent triggers)
# ---------------------------------------------------------------------------

async def _regen_meals_csv() -> int:
    rows = await _all_meals_with_nutrition()
    _write_csv(
        _data_csv_path("meals"),
        ["date", "meal_id", "meal_type", "kcal", "protein_g", "carbs_g", "fat_g", "description"],
        [
            [
                r["date"], int(r["id"]), r.get("meal_type") or "",
                _csv_num(r.get("calories")),
                _csv_num(r.get("protein_g")),
                _csv_num(r.get("carbs_g")),
                _csv_num(r.get("fat_g")),
                (r.get("description") or "").replace("\n", " ").strip(),
            ]
            for r in rows
        ],
    )
    return len(rows)


async def _regen_body_csv() -> int:
    rows = await _all_body_measurements_asc()
    _write_csv(
        _data_csv_path("body_measurements"),
        ["date", "weight_kg", "waist_at_navel_cm", "notes"],
        [
            [
                r["date"],
                _csv_num(r.get("weight_kg")),
                _csv_num(r.get("waist_at_navel_cm")),
                (r.get("notes") or "").replace("\n", " ").strip(),
            ]
            for r in rows
        ],
    )
    return len(rows)


async def _regen_workouts_csv() -> int:
    rows = await _all_workouts_summary()
    _write_csv(
        _data_csv_path("workouts"),
        ["date", "workout_id", "activity_type", "duration_min", "total_volume_kg", "total_sets", "total_reps"],
        [
            [
                r["date"], int(r["id"]),
                r.get("activity_type") or "",
                _csv_num(r.get("duration_minutes")),
                _csv_num(r.get("total_volume_kg")),
                _csv_num(r.get("total_sets")),
                _csv_num(r.get("total_reps")),
            ]
            for r in rows
        ],
    )
    return len(rows)


# ---------------------------------------------------------------------------
# File deletion helpers
# ---------------------------------------------------------------------------

def _delete_workout_files(workout_id: int) -> None:
    """Delete any *-workout-<id>.md (handles date renames as well as deletes)."""
    for p in (_vault_root() / "workouts").glob(f"*-workout-{int(workout_id)}.md"):
        p.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Public sync API (extended)
# ---------------------------------------------------------------------------

async def sync_meal_day(date_str: str) -> None:
    """Rewrite meals/<date>.md from current DB. Removes file when no meals remain."""
    if not _sync_active():
        return
    async with _sync_lock:
        meals = await meal_repo.list_by_date(date_str)
        path = _meal_day_md_path(date_str)
        if not meals:
            path.unlink(missing_ok=True)
            logger.info("vault_sync: removed empty meals %s", date_str)
        else:
            _atomic_write_text(path, _render_meal_day(date_str, meals))
            logger.info("vault_sync: wrote meals %s (%d entries)", date_str, len(meals))
        try:
            n = await _regen_meals_csv()
            logger.debug("vault_sync: meals.csv regenerated (%d rows)", n)
        except Exception:
            logger.exception("vault_sync: meals.csv regeneration failed")


async def sync_body_month(date_str: str) -> None:
    """Rewrite body/<YYYY-MM>.md from current DB. Removes file when month is empty."""
    if not _sync_active():
        return
    month = date_str[:7]
    async with _sync_lock:
        rows = await _body_rows_for_month(month)
        path = _body_month_md_path(date_str)
        if not rows:
            path.unlink(missing_ok=True)
            logger.info("vault_sync: removed empty body %s", month)
        else:
            _atomic_write_text(path, _render_body_month(month, rows))
            logger.info("vault_sync: wrote body %s (%d entries)", month, len(rows))
        try:
            n = await _regen_body_csv()
            logger.debug("vault_sync: body_measurements.csv regenerated (%d rows)", n)
        except Exception:
            logger.exception("vault_sync: body_measurements.csv regeneration failed")


async def _body_rows_for_month(month: str) -> list[dict]:
    """Body measurements for a YYYY-MM, oldest first (stable order)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, date, weight_kg, waist_at_navel_cm, notes, created_at "
            "FROM body_measurements "
            "WHERE date LIKE ? ORDER BY date ASC, id ASC",
            (f"{month}-%",),
        )
        return [dict(r) for r in await cursor.fetchall()]
    finally:
        await db.close()


async def sync_workout(workout_id: int, op: Literal["create", "update", "delete"]) -> None:
    """Mirror a workout to the vault. On update we also clear stale-date files."""
    if not _sync_active():
        return
    async with _sync_lock:
        if op == "delete":
            _delete_workout_files(workout_id)
            logger.info("vault_sync: deleted workout %d", workout_id)
        else:
            workout = await workout_repo.get_workout(workout_id)
            if not workout:
                logger.warning("vault_sync: workout %d not found (op=%s)", workout_id, op)
            else:
                analysis = await workout_analysis_repo.get_active(workout_id)
                # Clear any stale path (date may have changed since last sync) before writing the current one.
                target = _workout_md_path(workout)
                for p in (_vault_root() / "workouts").glob(f"*-workout-{int(workout_id)}.md"):
                    if p != target:
                        p.unlink(missing_ok=True)
                _atomic_write_text(target, _render_workout(workout, analysis))
                logger.info("vault_sync: wrote workout %d (%s)", workout_id, op)
        try:
            n = await _regen_workouts_csv()
            logger.debug("vault_sync: workouts.csv regenerated (%d rows)", n)
        except Exception:
            logger.exception("vault_sync: workouts.csv regeneration failed")


# ---------------------------------------------------------------------------
# Triggers (extended)
# ---------------------------------------------------------------------------

def trigger_sync_meal_day(date_str: str | None) -> None:
    if not _sync_active() or not date_str:
        return
    _safe(sync_meal_day(date_str))


def trigger_sync_body_month(date_str: str | None) -> None:
    if not _sync_active() or not date_str:
        return
    _safe(sync_body_month(date_str))


def trigger_sync_workout(workout_id: int | None, op: Literal["create", "update", "delete"]) -> None:
    if not _sync_active() or workout_id is None:
        return
    _safe(sync_workout(int(workout_id), op))
