from kaori.database import get_db


async def append(
    session_id: str, seq: int, role: str, content: str,
    token_count_approx: int = 0,
) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO agent_messages (session_id, seq, role, content, token_count_approx) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, seq, role, content, token_count_approx),
        )
        await db.commit()
        row_id = cursor.lastrowid
        cursor = await db.execute(
            "SELECT * FROM agent_messages WHERE id = ?", (row_id,)
        )
        return dict(await cursor.fetchone())
    finally:
        await db.close()


async def list_by_session(session_id: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM agent_messages WHERE session_id = ? ORDER BY seq",
            (session_id,),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def count(session_id: str) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM agent_messages WHERE session_id = ?",
            (session_id,),
        )
        return (await cursor.fetchone())[0]
    finally:
        await db.close()


async def get_latest_seq(session_id: str) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT MAX(seq) FROM agent_messages WHERE session_id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row[0] is not None else 0
    finally:
        await db.close()


async def list_after_seq(session_id: str, after_seq: int) -> list[dict]:
    """Get messages with seq > after_seq (for post-compaction reconstruction)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM agent_messages WHERE session_id = ? AND seq > ? ORDER BY seq",
            (session_id, after_seq),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()
