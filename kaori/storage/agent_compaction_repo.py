from kaori.database import get_db


async def get_active(session_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM agent_compactions "
            "WHERE session_id = ? AND is_active = 1 "
            "ORDER BY version DESC LIMIT 1",
            (session_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def create(
    session_id: str, version: int, summary_text: str,
    messages_summarized: int, up_to_seq: int,
    llm_backend: str | None = None, model: str | None = None,
    raw_response: str | None = None,
) -> dict:
    db = await get_db()
    try:
        # Deactivate previous compactions for this session
        await db.execute(
            "UPDATE agent_compactions SET is_active = 0 WHERE session_id = ?",
            (session_id,),
        )
        cursor = await db.execute(
            "INSERT INTO agent_compactions "
            "(session_id, version, is_active, summary_text, messages_summarized, "
            "up_to_seq, llm_backend, model, raw_response) "
            "VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?)",
            (session_id, version, summary_text, messages_summarized,
             up_to_seq, llm_backend, model, raw_response),
        )
        await db.commit()
        row_id = cursor.lastrowid
        cursor = await db.execute(
            "SELECT * FROM agent_compactions WHERE id = ?", (row_id,)
        )
        return dict(await cursor.fetchone())
    finally:
        await db.close()


async def list_versions(session_id: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM agent_compactions WHERE session_id = ? "
            "ORDER BY version DESC",
            (session_id,),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()
