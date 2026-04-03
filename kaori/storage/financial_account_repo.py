from kaori.database import get_db


async def list_accounts(account_type: str | None = None) -> list[dict]:
    db = await get_db()
    try:
        if account_type:
            cursor = await db.execute(
                "SELECT * FROM financial_accounts WHERE account_type = ? ORDER BY created_at DESC",
                (account_type,),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM financial_accounts ORDER BY account_type, created_at DESC"
            )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def get(account_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM financial_accounts WHERE id = ?", (account_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def create(
    *,
    name: str,
    account_type: str,
    institution: str,
    sync_method: str = "manual",
    notes: str | None = None,
) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO financial_accounts (name, account_type, institution, sync_method, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, account_type, institution, sync_method, notes),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def update(
    account_id: int,
    *,
    name: str | None = None,
    notes: str | None = None,
    sync_method: str | None = None,
    api_credentials: str | None = None,
    last_synced_at: str | None = None,
) -> bool:
    db = await get_db()
    try:
        fields = []
        values = []
        if name is not None:
            fields.append("name = ?")
            values.append(name)
        if notes is not None:
            fields.append("notes = ?")
            values.append(notes)
        if sync_method is not None:
            fields.append("sync_method = ?")
            values.append(sync_method)
        if api_credentials is not None:
            fields.append("api_credentials = ?")
            values.append(api_credentials)
        if last_synced_at is not None:
            fields.append("last_synced_at = ?")
            values.append(last_synced_at)
        if not fields:
            return False
        fields.append("updated_at = datetime('now')")
        values.append(account_id)
        cursor = await db.execute(
            f"UPDATE financial_accounts SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def delete(account_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM financial_accounts WHERE id = ?", (account_id,)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()
