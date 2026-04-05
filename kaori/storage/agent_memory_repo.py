from kaori.database import get_db


async def list_all(category: str | None = None) -> list[dict]:
    db = await get_db()
    try:
        if category:
            cursor = await db.execute(
                "SELECT * FROM agent_memory WHERE category = ? ORDER BY key",
                (category,),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM agent_memory ORDER BY key"
            )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def get(key: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM agent_memory WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def upsert(
    key: str, value: str, category: str = "general", source: str | None = None,
) -> dict:
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO agent_memory (key, value, category, source) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET "
            "value = excluded.value, category = excluded.category, "
            "source = excluded.source, updated_at = datetime('now')",
            (key, value, category, source),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM agent_memory WHERE key = ?", (key,)
        )
        return dict(await cursor.fetchone())
    finally:
        await db.close()


async def delete(key: str) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM agent_memory WHERE key = ?", (key,)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()
