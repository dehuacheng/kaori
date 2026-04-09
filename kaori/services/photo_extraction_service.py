"""Service for extracting information from feed item photos via LLM."""

import asyncio
import json
import logging

import kaori.llm
from kaori.llm import LLMError
from kaori.config import PHOTOS_DIR
from kaori.database import get_db

logger = logging.getLogger(__name__)


async def extract_photo_description(
    *,
    table: str,
    item_id: int,
    photo_paths: list[str],
) -> str | None:
    """Call codex LLM to describe photo(s) and save the result.

    Args:
        table: "posts" (or "meals" if needed later)
        item_id: row id in the table
        photo_paths: list of relative paths under PHOTOS_DIR
    """
    # Resolve absolute paths, skip missing files
    abs_paths = []
    for p in photo_paths:
        ap = PHOTOS_DIR / p
        if ap.exists():
            abs_paths.append(ap)
        else:
            logger.warning("Photo not found: %s (table=%s, id=%d)", p, table, item_id)

    if not abs_paths:
        return None

    try:
        backend = kaori.llm.get_llm_backend(mode="codex_cli")
        prompt = (
            "Describe these photo(s) in detail. Include:\n"
            "- What is shown (food, location, activity, document, etc.)\n"
            "- Key details visible (text, labels, quantities, people, objects)\n"
            "- Context clues (time of day, setting, mood)\n"
            "Keep it concise but informative (2-4 sentences)."
        )

        if len(abs_paths) == 1:
            response = await backend.analyze_image(str(abs_paths[0]), prompt)
        else:
            # Multi-photo: read bytes and send together
            images = []
            for ap in abs_paths:
                images.append((ap.read_bytes(), "image/jpeg"))
            response = await backend.analyze_images(images, prompt)

        description = response.text.strip()

        db = await get_db()
        try:
            await db.execute(
                f"UPDATE {table} SET photo_description = ? WHERE id = ?",
                (description, item_id),
            )
            await db.commit()
        finally:
            await db.close()

        logger.info("Photo description extracted for %s/%d (%d photos)", table, item_id, len(abs_paths))
        return description

    except (LLMError, Exception):
        logger.exception("Photo extraction failed for %s/%d", table, item_id)
        return None


def trigger_photo_extraction(table: str, item_id: int, photo_paths: list[str]) -> None:
    """Fire-and-forget background extraction for a newly created item."""
    asyncio.create_task(
        extract_photo_description(table=table, item_id=item_id, photo_paths=photo_paths)
    )


def _get_all_photo_paths(row: dict) -> list[str]:
    """Extract all photo paths from a DB row (photo_paths JSON or photo_path fallback)."""
    raw = row.get("photo_paths")
    if raw:
        try:
            paths = json.loads(raw)
            if paths:
                return paths
        except (json.JSONDecodeError, TypeError):
            pass
    single = row.get("photo_path")
    if single:
        return [single]
    return []


async def backfill_photos() -> dict:
    """Process all posts with photos but no photo_description yet."""
    db = await get_db()
    results = {"posts_processed": 0, "errors": 0}
    try:
        cursor = await db.execute(
            "SELECT id, photo_path, photo_paths FROM posts "
            "WHERE photo_path IS NOT NULL AND photo_description IS NULL"
        )
        post_rows = [dict(r) for r in await cursor.fetchall()]
    finally:
        await db.close()

    for row in post_rows:
        paths = _get_all_photo_paths(row)
        if not paths:
            continue
        desc = await extract_photo_description(
            table="posts", item_id=row["id"], photo_paths=paths,
        )
        if desc:
            results["posts_processed"] += 1
        else:
            results["errors"] += 1

    return results
