from kaori.database import get_db


async def get_active_summary() -> dict | None:
    """Return the currently active meal habit summary, or None if no compaction has run."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, version, summary_text, cutoff_date, meal_count, "
            "llm_backend, model, created_at "
            "FROM meal_habit_summaries WHERE is_active = 1 "
            "ORDER BY version DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_summary_by_version(version: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, version, is_active, summary_text, cutoff_date, meal_count, "
            "llm_backend, model, raw_response, created_at "
            "FROM meal_habit_summaries WHERE version = ?",
            (version,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def list_summaries() -> list[dict]:
    """List all summary versions (without raw_response for brevity)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, version, is_active, cutoff_date, meal_count, "
            "llm_backend, model, created_at "
            "FROM meal_habit_summaries ORDER BY version DESC"
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def get_recent_meals(since_date: str, limit: int = 50) -> list[dict]:
    """Get meals after since_date with effective nutrition (override > analysis > raw)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT m.date, m.meal_type,
                COALESCE(mo.description, a.description, m.description) as description,
                COALESCE(mo.calories, a.calories) as calories,
                COALESCE(mo.protein_g, a.protein_g) as protein_g,
                COALESCE(mo.carbs_g, a.carbs_g) as carbs_g,
                COALESCE(mo.fat_g, a.fat_g) as fat_g
            FROM meals m
            LEFT JOIN meal_overrides mo ON mo.meal_id = m.id
            LEFT JOIN meal_analyses a ON a.meal_id = m.id AND a.is_active = 1 AND a.status = 'done'
            WHERE m.date > ?
            ORDER BY m.date DESC, m.created_at DESC
            LIMIT ?""",
            (since_date, limit),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def get_meals_for_compaction(from_date: str, to_date: str) -> list[dict]:
    """Get meals in a date range for compaction input."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT m.date, m.meal_type,
                COALESCE(mo.description, a.description, m.description) as description,
                COALESCE(mo.calories, a.calories) as calories,
                COALESCE(mo.protein_g, a.protein_g) as protein_g,
                COALESCE(mo.carbs_g, a.carbs_g) as carbs_g,
                COALESCE(mo.fat_g, a.fat_g) as fat_g
            FROM meals m
            LEFT JOIN meal_overrides mo ON mo.meal_id = m.id
            LEFT JOIN meal_analyses a ON a.meal_id = m.id AND a.is_active = 1 AND a.status = 'done'
            WHERE m.date > ? AND m.date <= ?
            ORDER BY m.date ASC, m.created_at ASC""",
            (from_date, to_date),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def create_summary(*, summary_text: str, cutoff_date: str, meal_count: int,
                         llm_backend: str, model: str, raw_response: str) -> dict:
    """Create a new summary version. Deactivates the current active one."""
    db = await get_db()
    try:
        # Get next version number
        cursor = await db.execute("SELECT COALESCE(MAX(version), 0) FROM meal_habit_summaries")
        row = await cursor.fetchone()
        next_version = row[0] + 1

        # Deactivate current active
        await db.execute("UPDATE meal_habit_summaries SET is_active = 0 WHERE is_active = 1")

        # Insert new active version
        cursor = await db.execute(
            "INSERT INTO meal_habit_summaries "
            "(version, is_active, summary_text, cutoff_date, meal_count, llm_backend, model, raw_response) "
            "VALUES (?, 1, ?, ?, ?, ?, ?, ?)",
            (next_version, summary_text, cutoff_date, meal_count, llm_backend, model, raw_response),
        )
        summary_id = cursor.lastrowid
        await db.commit()
        return {"id": summary_id, "version": next_version, "cutoff_date": cutoff_date, "meal_count": meal_count}
    finally:
        await db.close()


async def rollback_to_version(version: int) -> dict:
    """Deactivate current active summary and reactivate the target version."""
    db = await get_db()
    try:
        # Verify target exists
        cursor = await db.execute(
            "SELECT id, version, summary_text, cutoff_date, meal_count FROM meal_habit_summaries WHERE version = ?",
            (version,),
        )
        target = await cursor.fetchone()
        if not target:
            raise ValueError(f"Summary version {version} not found")

        # Deactivate all, activate target
        await db.execute("UPDATE meal_habit_summaries SET is_active = 0 WHERE is_active = 1")
        await db.execute("UPDATE meal_habit_summaries SET is_active = 1 WHERE version = ?", (version,))
        await db.commit()
        return dict(target)
    finally:
        await db.close()
