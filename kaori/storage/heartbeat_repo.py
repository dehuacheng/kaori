from kaori.database import get_db


async def get_config() -> dict:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM heartbeat_config WHERE id = 1")
        row = await cursor.fetchone()
        return dict(row) if row else {
            "id": 1, "enabled": 0, "debounce_minutes": 5,
            "prompt_template": None, "last_run_at": None,
            "last_session_id": None, "last_event_type": None,
        }
    finally:
        await db.close()


async def update_config(**fields) -> dict:
    allowed = {"enabled", "debounce_minutes", "prompt_template"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return await get_config()
    # Convert bool to int for SQLite
    if "enabled" in updates:
        updates["enabled"] = int(updates["enabled"])
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())
    db = await get_db()
    try:
        await db.execute(
            f"UPDATE heartbeat_config SET {set_clause}, updated_at = datetime('now') "
            "WHERE id = 1",
            values,
        )
        await db.commit()
        return await get_config()
    finally:
        await db.close()


async def record_run(session_id: str, event_type: str) -> None:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE heartbeat_config SET last_run_at = datetime('now'), "
            "last_session_id = ?, last_event_type = ?, updated_at = datetime('now') "
            "WHERE id = 1",
            (session_id, event_type),
        )
        await db.commit()
    finally:
        await db.close()


async def get_last_run_at() -> str | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT last_run_at FROM heartbeat_config WHERE id = 1"
        )
        row = await cursor.fetchone()
        return row[0] if row else None
    finally:
        await db.close()
