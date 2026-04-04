from kaori.database import get_db


async def list_by_date(date_str: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM reminders WHERE due_date = ? "
            "ORDER BY priority DESC, created_at ASC",
            (date_str,),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def list_active_for_today(today: str, tomorrow: str) -> list[dict]:
    """Get active reminders for today's feed.

    Includes: overdue undone items, today's items, and items due tomorrow
    (so upcoming reminders surface a day early). Also includes items
    completed today.
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM reminders "
            "WHERE (due_date <= ? AND is_done = 0) "
            "   OR (due_date = ? AND is_done = 1) "
            "ORDER BY is_done ASC, priority DESC, created_at ASC",
            (tomorrow, today),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def get(reminder_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM reminders WHERE id = ?", (reminder_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def create(
    *,
    title: str,
    description: str | None = None,
    due_date: str,
    original_date: str,
    item_type: str = "todo",
    priority: int = 1,
) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO reminders (title, description, due_date, original_date, "
            "item_type, priority) VALUES (?, ?, ?, ?, ?, ?)",
            (title, description, due_date, original_date, item_type, priority),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def update(reminder_id: int, **fields) -> None:
    allowed = {"title", "description", "due_date", "item_type", "priority"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())
    db = await get_db()
    try:
        await db.execute(
            f"UPDATE reminders SET {set_clause}, updated_at = datetime('now') "
            f"WHERE id = ?",
            values + [reminder_id],
        )
        await db.commit()
    finally:
        await db.close()


async def mark_done(reminder_id: int, is_done: bool) -> None:
    db = await get_db()
    try:
        done_at = "datetime('now')" if is_done else "NULL"
        await db.execute(
            f"UPDATE reminders SET is_done = ?, done_at = {done_at}, "
            f"updated_at = datetime('now') WHERE id = ?",
            (int(is_done), reminder_id),
        )
        await db.commit()
    finally:
        await db.close()


async def push(reminder_id: int, new_date: str) -> None:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE reminders SET due_date = ?, updated_at = datetime('now') "
            "WHERE id = ?",
            (new_date, reminder_id),
        )
        await db.commit()
    finally:
        await db.close()


async def delete(reminder_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM reminders WHERE id = ?", (reminder_id,)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def get_history(limit: int = 50) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM reminders ORDER BY due_date DESC, created_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()
