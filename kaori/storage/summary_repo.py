from kaori.database import get_db


async def get_latest(summary_type: str, target_date: str) -> dict | None:
    """Get the most recent summary of the given type for the given date."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM summaries WHERE type = ? AND date = ? ORDER BY id DESC LIMIT 1",
            (summary_type, target_date),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def create(*, summary_type: str, target_date: str, summary_text: str,
                 llm_backend: str | None = None, model: str | None = None,
                 raw_response: str | None = None) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO summaries (type, date, summary_text, llm_backend, model, raw_response) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (summary_type, target_date, summary_text, llm_backend, model, raw_response),
        )
        summary_id = cursor.lastrowid
        await db.commit()
        cursor = await db.execute("SELECT * FROM summaries WHERE id = ?", (summary_id,))
        return dict(await cursor.fetchone())
    finally:
        await db.close()


async def list_recent(summary_type: str, limit: int = 7) -> list[dict]:
    """List the most recent summaries of the given type."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM summaries WHERE type = ? ORDER BY date DESC, id DESC LIMIT ?",
            (summary_type, limit),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()
