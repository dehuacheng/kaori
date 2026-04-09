from kaori.database import get_db


async def create(
    *, filename: str, original_type: str,
    raw_file_path: str, raw_file_paths: str | None = None,
    page_count: int = 1,
) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO documents (filename, original_type, raw_file_path, raw_file_paths, page_count) "
            "VALUES (?, ?, ?, ?, ?)",
            (filename, original_type, raw_file_path, raw_file_paths, page_count),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def update_extraction(doc_id: int, *, extracted_text: str, summary: str) -> None:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE documents SET extracted_text = ?, summary = ?, status = 'done' "
            "WHERE id = ?",
            (extracted_text, summary, doc_id),
        )
        await db.commit()
    finally:
        await db.close()


async def set_failed(doc_id: int, error: str) -> None:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE documents SET status = 'failed', error_message = ? WHERE id = ?",
            (error, doc_id),
        )
        await db.commit()
    finally:
        await db.close()


async def get(doc_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def list_all() -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, filename, original_type, summary, status, created_at "
            "FROM documents ORDER BY created_at DESC"
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def search(query: str) -> list[dict]:
    db = await get_db()
    try:
        like = f"%{query}%"
        cursor = await db.execute(
            "SELECT id, filename, original_type, summary, status, created_at "
            "FROM documents "
            "WHERE summary LIKE ? OR extracted_text LIKE ? OR filename LIKE ? "
            "ORDER BY created_at DESC",
            (like, like, like),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def delete(doc_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()
