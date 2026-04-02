from kaori.database import get_db


async def list_all(category: str | None = None) -> list[dict]:
    db = await get_db()
    try:
        if category:
            cursor = await db.execute(
                "SELECT * FROM exercise_types WHERE category = ? ORDER BY name",
                (category,),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM exercise_types ORDER BY category, name"
            )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def list_enabled() -> list[dict]:
    """List only enabled exercise types (for workout picker)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM exercise_types WHERE is_enabled = 1 ORDER BY category, name"
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def get_by_id(type_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM exercise_types WHERE id = ?", (type_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_by_name(name: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM exercise_types WHERE LOWER(name) = LOWER(?)", (name,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def create(
    *,
    name: str,
    category: str | None = None,
    photo_path: str | None = None,
    notes: str | None = None,
    is_standard: int = 0,
    is_enabled: int = 1,
    status: str = "done",
) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO exercise_types (name, category, photo_path, notes, is_standard, is_enabled, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, category, photo_path, notes, is_standard, is_enabled, status),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def update(type_id: int, **fields) -> bool:
    allowed = {"name", "category", "photo_path", "notes", "is_enabled", "status"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return False
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [type_id]
    db = await get_db()
    try:
        cursor = await db.execute(
            f"UPDATE exercise_types SET {set_clause} WHERE id = ?", values
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def set_enabled(type_id: int, enabled: bool) -> bool:
    """Toggle an exercise type's enabled status."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE exercise_types SET is_enabled = ? WHERE id = ?",
            (1 if enabled else 0, type_id),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def delete(type_id: int) -> bool:
    """Delete a custom exercise type. Refuses to delete standard or referenced types."""
    db = await get_db()
    try:
        # Check if standard
        cursor = await db.execute(
            "SELECT is_standard FROM exercise_types WHERE id = ?", (type_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return False
        if row["is_standard"]:
            raise ValueError("Cannot delete a standard exercise type")
        # Check if referenced by workout_exercises
        cursor = await db.execute(
            "SELECT COUNT(*) FROM workout_exercises WHERE exercise_type_id = ?",
            (type_id,),
        )
        count = (await cursor.fetchone())[0]
        if count > 0:
            raise ValueError("Cannot delete exercise type used in workouts")
        cursor = await db.execute(
            "DELETE FROM exercise_types WHERE id = ?", (type_id,)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()
