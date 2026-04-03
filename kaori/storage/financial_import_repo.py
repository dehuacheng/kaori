from kaori.database import get_db


async def create(
    *,
    account_id: int,
    import_type: str,
    file_path: str | None = None,
) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO financial_import_analyses (account_id, import_type, file_path) "
            "VALUES (?, ?, ?)",
            (account_id, import_type, file_path),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def get(analysis_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM financial_import_analyses WHERE id = ?", (analysis_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def update_status(
    analysis_id: int,
    *,
    status: str,
    extracted_json: str | None = None,
    llm_backend: str | None = None,
    model: str | None = None,
    raw_response: str | None = None,
    error_message: str | None = None,
):
    db = await get_db()
    try:
        fields = ["status = ?"]
        values = [status]
        if extracted_json is not None:
            fields.append("extracted_json = ?")
            values.append(extracted_json)
        if llm_backend is not None:
            fields.append("llm_backend = ?")
            values.append(llm_backend)
        if model is not None:
            fields.append("model = ?")
            values.append(model)
        if raw_response is not None:
            fields.append("raw_response = ?")
            values.append(raw_response)
        if error_message is not None:
            fields.append("error_message = ?")
            values.append(error_message)
        if status == "done" or status == "failed":
            fields.append("completed_at = datetime('now')")
        values.append(analysis_id)
        await db.execute(
            f"UPDATE financial_import_analyses SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        await db.commit()
    finally:
        await db.close()


async def list_by_account(account_id: int) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM financial_import_analyses WHERE account_id = ? ORDER BY created_at DESC",
            (account_id,),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()
