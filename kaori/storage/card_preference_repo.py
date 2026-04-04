from kaori.database import get_db
from kaori.models.card import CardType


# Default preferences: card_type -> (enabled, pinned, pin_order)
_DEFAULTS = {
    CardType.SUMMARY: (True, True, 0),
    CardType.PORTFOLIO: (True, True, 1),
    CardType.NUTRITION: (True, True, 2),
    CardType.MEAL: (True, False, 99),
    CardType.WEIGHT: (True, False, 99),
    CardType.WORKOUT: (True, False, 99),
    CardType.HEALTHKIT_WORKOUT: (True, False, 99),
}


async def _ensure_seeded(db):
    """Seed default card preferences if table is empty."""
    cursor = await db.execute("SELECT COUNT(*) FROM card_preferences")
    count = (await cursor.fetchone())[0]
    if count > 0:
        return
    for card_type, (enabled, pinned, pin_order) in _DEFAULTS.items():
        await db.execute(
            "INSERT INTO card_preferences (card_type, enabled, pinned, pin_order) "
            "VALUES (?, ?, ?, ?)",
            (card_type.value, int(enabled), int(pinned), pin_order),
        )
    await db.commit()


async def get_all() -> list[dict]:
    db = await get_db()
    try:
        await _ensure_seeded(db)
        cursor = await db.execute(
            "SELECT * FROM card_preferences ORDER BY pin_order, card_type"
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def get(card_type: str) -> dict | None:
    db = await get_db()
    try:
        await _ensure_seeded(db)
        cursor = await db.execute(
            "SELECT * FROM card_preferences WHERE card_type = ?", (card_type,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def upsert(card_type: str, **fields) -> dict:
    """Update card preference fields. Only updates provided non-None fields."""
    allowed = {"enabled", "pinned", "pin_order"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return await get(card_type)

    db = await get_db()
    try:
        await _ensure_seeded(db)
        # Convert bools to ints for SQLite
        for k in ("enabled", "pinned"):
            if k in updates:
                updates[k] = int(updates[k])

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values())
        await db.execute(
            f"UPDATE card_preferences SET {set_clause}, "
            f"updated_at = datetime('now') WHERE card_type = ?",
            values + [card_type],
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM card_preferences WHERE card_type = ?", (card_type,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else {}
    finally:
        await db.close()
