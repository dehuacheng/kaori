from kaori.database import get_db


async def get() -> dict:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM user_profile WHERE id = 1")
        return dict(await cursor.fetchone())
    finally:
        await db.close()


async def update(**fields) -> dict:
    """Update profile fields. Only updates provided non-None fields."""
    allowed = {
        "display_name", "height_cm", "gender", "birth_date",
        "protein_per_kg", "carbs_per_kg", "calorie_adjustment_pct",
        "llm_mode", "notes",
    }
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return await get()

    db = await get_db()
    try:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values())
        await db.execute(
            f"UPDATE user_profile SET {set_clause}, updated_at = datetime('now') WHERE id = 1",
            values,
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM user_profile WHERE id = 1")
        return dict(await cursor.fetchone())
    finally:
        await db.close()
