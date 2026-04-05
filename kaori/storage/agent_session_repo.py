import uuid

from kaori.database import get_db


async def create(backend: str | None = None, model: str | None = None) -> dict:
    session_id = str(uuid.uuid4())
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO agent_sessions (id, backend, model) VALUES (?, ?, ?)",
            (session_id, backend, model),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM agent_sessions WHERE id = ?", (session_id,)
        )
        return dict(await cursor.fetchone())
    finally:
        await db.close()


async def get(session_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM agent_sessions WHERE id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def list_all(status: str | None = "active", limit: int = 50) -> list[dict]:
    db = await get_db()
    try:
        if status:
            cursor = await db.execute(
                "SELECT * FROM agent_sessions WHERE status = ? "
                "ORDER BY updated_at DESC LIMIT ?",
                (status, limit),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM agent_sessions ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def update(session_id: str, **fields) -> dict | None:
    allowed = {"title", "status", "message_count", "token_count_approx"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return await get(session_id)
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())
    db = await get_db()
    try:
        await db.execute(
            f"UPDATE agent_sessions SET {set_clause}, updated_at = datetime('now') "
            f"WHERE id = ?",
            values + [session_id],
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM agent_sessions WHERE id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def delete(session_id: str) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM agent_sessions WHERE id = ?", (session_id,)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()
