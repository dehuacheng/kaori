from kaori.database import get_db


async def list_all() -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM timer_presets ORDER BY created_at"
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def get_by_id(preset_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM timer_presets WHERE id = ?", (preset_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def create(
    *,
    name: str,
    rest_seconds: int = 60,
    work_seconds: int = 0,
    sets: int = 3,
    notes: str | None = None,
) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO timer_presets (name, rest_seconds, work_seconds, sets, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, rest_seconds, work_seconds, sets, notes),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def update(preset_id: int, **fields) -> bool:
    allowed = {"name", "rest_seconds", "work_seconds", "sets", "notes"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return False
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [preset_id]
    db = await get_db()
    try:
        cursor = await db.execute(
            f"UPDATE timer_presets SET {set_clause} WHERE id = ?", values
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def delete(preset_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM timer_presets WHERE id = ?", (preset_id,)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()
