from kaori.database import get_db


async def delete(meal_id: int):
    """Delete the manual override for a meal."""
    db = await get_db()
    try:
        await db.execute("DELETE FROM meal_overrides WHERE meal_id = ?", (meal_id,))
        await db.commit()
    finally:
        await db.close()


async def upsert(meal_id: int, **fields):
    """Create or update a manual override for a meal."""
    allowed = {"description", "calories", "protein_g", "carbs_g", "fat_g"}
    data = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not data:
        return

    db = await get_db()
    try:
        # Check if override exists
        cursor = await db.execute(
            "SELECT id FROM meal_overrides WHERE meal_id = ?", (meal_id,)
        )
        existing = await cursor.fetchone()

        if existing:
            set_clause = ", ".join(f"{k} = ?" for k in data)
            values = list(data.values()) + [meal_id]
            await db.execute(
                f"UPDATE meal_overrides SET {set_clause} WHERE meal_id = ?", values
            )
        else:
            cols = ["meal_id"] + list(data.keys())
            placeholders = ", ".join("?" for _ in cols)
            values = [meal_id] + list(data.values())
            await db.execute(
                f"INSERT INTO meal_overrides ({', '.join(cols)}) VALUES ({placeholders})",
                values,
            )
        await db.commit()
    finally:
        await db.close()
