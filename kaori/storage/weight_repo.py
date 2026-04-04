from kaori.database import get_db


async def get_history(limit: int = 30) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM body_measurements ORDER BY date DESC, created_at DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in await cursor.fetchall()]
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


async def create(*, date: str, weight_kg: float, notes: str | None = None) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO body_measurements (date, weight_kg, notes) VALUES (?, ?, ?)",
            (date, weight_kg, notes),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def update(entry_id: int, *, weight_kg: float, notes: str | None = None):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE body_measurements SET weight_kg = ?, notes = ? WHERE id = ?",
            (weight_kg, notes, entry_id),
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
        cursor = await db.execute("SELECT date, weight_kg FROM body_measurements")
        return {(row["date"], round(row["weight_kg"], 1)) for row in await cursor.fetchall()}
    finally:
        await db.close()
