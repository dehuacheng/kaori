from kaori.database import get_db


async def list_all() -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM agent_prompts ORDER BY name"
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def get(prompt_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM agent_prompts WHERE id = ?", (prompt_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_active() -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM agent_prompts WHERE is_active = 1 LIMIT 1"
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def create(name: str, prompt_text: str) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO agent_prompts (name, prompt_text) VALUES (?, ?)",
            (name, prompt_text),
        )
        await db.commit()
        row_id = cursor.lastrowid
        cursor = await db.execute(
            "SELECT * FROM agent_prompts WHERE id = ?", (row_id,)
        )
        return dict(await cursor.fetchone())
    finally:
        await db.close()


async def update(prompt_id: int, **fields) -> dict | None:
    allowed = {"name", "prompt_text"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return await get(prompt_id)
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())
    db = await get_db()
    try:
        await db.execute(
            f"UPDATE agent_prompts SET {set_clause}, updated_at = datetime('now') "
            f"WHERE id = ?",
            values + [prompt_id],
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM agent_prompts WHERE id = ?", (prompt_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def set_active(prompt_id: int) -> dict | None:
    db = await get_db()
    try:
        # Deactivate all
        await db.execute("UPDATE agent_prompts SET is_active = 0")
        # Activate the target
        await db.execute(
            "UPDATE agent_prompts SET is_active = 1, updated_at = datetime('now') "
            "WHERE id = ?",
            (prompt_id,),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM agent_prompts WHERE id = ?", (prompt_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def delete(prompt_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM agent_prompts WHERE id = ?", (prompt_id,)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()
