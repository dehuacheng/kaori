from kaori.database import get_db


# Column allowlist for partial updates. Order doesn't matter — the SQL is built
# dynamically from the fields the caller actually provides.
_UPDATABLE_COLUMNS = {"weight_kg", "waist_at_navel_cm", "notes"}


async def get_history(limit: int = 30) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM body_measurements ORDER BY date DESC, created_at DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def get_by_id(entry_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM body_measurements WHERE id = ?", (entry_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def list_by_date(target_date: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM body_measurements WHERE date = ? ORDER BY created_at DESC",
            (target_date,),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def create(
    *,
    date: str,
    weight_kg: float | None = None,
    waist_at_navel_cm: float | None = None,
    notes: str | None = None,
) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO body_measurements (date, weight_kg, waist_at_navel_cm, notes) "
            "VALUES (?, ?, ?, ?)",
            (date, weight_kg, waist_at_navel_cm, notes),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def update(entry_id: int, fields: dict):
    """Patch-style update: only the columns present in `fields` are written.

    Pass `{"weight_kg": 80.0}` to set just the weight without touching waist or
    notes. Unknown keys are silently ignored. An empty `fields` is a no-op.
    """
    cleaned = {k: v for k, v in fields.items() if k in _UPDATABLE_COLUMNS}
    if not cleaned:
        return
    assignments = ", ".join(f"{col} = ?" for col in cleaned)
    params = list(cleaned.values()) + [entry_id]
    db = await get_db()
    try:
        await db.execute(
            f"UPDATE body_measurements SET {assignments} WHERE id = ?",
            params,
        )
        await db.commit()
    finally:
        await db.close()


async def delete(entry_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM body_measurements WHERE id = ?", (entry_id,)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def get_existing_date_weight_pairs() -> set[tuple[str, float]]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT date, weight_kg FROM body_measurements WHERE weight_kg IS NOT NULL"
        )
        return {(row["date"], round(row["weight_kg"], 1)) for row in await cursor.fetchall()}
    finally:
        await db.close()
