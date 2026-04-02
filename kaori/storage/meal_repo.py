from kaori.database import get_db

# SQL to join meals with their effective nutrition (override > latest analysis)
_MEAL_WITH_NUTRITION = """
SELECT m.id, m.date, m.meal_type, m.photo_path, m.notes, m.created_at, m.updated_at,
    COALESCE(mo.description, a.description, m.description) as description,
    COALESCE(mo.calories, a.calories) as calories,
    COALESCE(mo.protein_g, a.protein_g) as protein_g,
    COALESCE(mo.carbs_g, a.carbs_g) as carbs_g,
    COALESCE(mo.fat_g, a.fat_g) as fat_g,
    CASE WHEN mo.id IS NOT NULL THEN 0
         WHEN a.id IS NOT NULL THEN 1
         ELSE NULL END as is_estimated,
    a.status as analysis_status,
    a.confidence
FROM meals m
LEFT JOIN meal_overrides mo ON mo.meal_id = m.id
LEFT JOIN meal_analyses a ON a.meal_id = m.id AND a.is_active = 1
"""


async def list_by_date(target_date: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            _MEAL_WITH_NUTRITION + " WHERE m.date = ? ORDER BY m.created_at DESC",
            (target_date,),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def get_totals(target_date: str) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute(
            f"""SELECT
                COALESCE(SUM(COALESCE(mo.calories, a.calories)), 0) as total_cal,
                COALESCE(SUM(COALESCE(mo.protein_g, a.protein_g)), 0) as total_protein,
                COALESCE(SUM(COALESCE(mo.carbs_g, a.carbs_g)), 0) as total_carbs,
                COALESCE(SUM(COALESCE(mo.fat_g, a.fat_g)), 0) as total_fat
            FROM meals m
            LEFT JOIN meal_overrides mo ON mo.meal_id = m.id
            LEFT JOIN meal_analyses a ON a.meal_id = m.id AND a.is_active = 1
            WHERE m.date = ?""",
            (target_date,),
        )
        return dict(await cursor.fetchone())
    finally:
        await db.close()


async def get_by_id(meal_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            _MEAL_WITH_NUTRITION + " WHERE m.id = ?",
            (meal_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_raw(meal_id: int) -> dict | None:
    """Get raw meal data without analysis/override joins."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM meals WHERE id = ?", (meal_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def create(*, date: str, meal_type: str, description: str | None = None,
                 photo_path: str | None = None, notes: str | None = None) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO meals (date, meal_type, description, photo_path, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            (date, meal_type, description, photo_path, notes),
        )
        meal_id = cursor.lastrowid
        await db.commit()
        return meal_id
    finally:
        await db.close()


async def update(meal_id: int, **fields) -> str | None:
    """Update raw meal fields. Returns the meal's date or None if not found."""
    allowed = {"date", "meal_type", "description", "notes"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    db = await get_db()
    try:
        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [meal_id]
            await db.execute(f"UPDATE meals SET {set_clause}, updated_at = datetime('now') WHERE id = ?", values)
            await db.commit()

        cursor = await db.execute("SELECT date FROM meals WHERE id = ?", (meal_id,))
        row = await cursor.fetchone()
        return row["date"] if row else None
    finally:
        await db.close()


async def delete(meal_id: int) -> str | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT date FROM meals WHERE id = ?", (meal_id,))
        row = await cursor.fetchone()
        meal_date = row["date"] if row else None
        await db.execute("DELETE FROM meals WHERE id = ?", (meal_id,))
        await db.commit()
        return meal_date
    finally:
        await db.close()
