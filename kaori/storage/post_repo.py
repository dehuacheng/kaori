from kaori.database import get_db


async def list_by_date(date_str: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM posts WHERE date = ? ORDER BY created_at DESC",
            (date_str,),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def get(post_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def create(*, date: str, title: str | None = None, content: str,
                 photo_path: str | None = None, photo_paths: str | None = None) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO posts (date, title, content, photo_path, photo_paths) VALUES (?, ?, ?, ?, ?)",
            (date, title, content, photo_path, photo_paths),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def update(post_id: int, **fields) -> None:
    allowed = {"title", "content", "is_pinned"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return
    # Convert bool to int for SQLite
    if "is_pinned" in updates:
        updates["is_pinned"] = int(updates["is_pinned"])
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())
    db = await get_db()
    try:
        await db.execute(
            f"UPDATE posts SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            values + [post_id],
        )
        await db.commit()
    finally:
        await db.close()


async def delete(post_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def get_history(limit: int = 50) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM posts ORDER BY date DESC, created_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()
