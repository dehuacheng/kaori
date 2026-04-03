import json

from kaori.database import get_db


async def get_snapshot(date: str, account_id: int | None = None) -> dict | None:
    """Get a snapshot for a specific date and account (None = combined)."""
    db = await get_db()
    try:
        if account_id is None:
            cursor = await db.execute(
                "SELECT * FROM portfolio_snapshots WHERE date = ? AND account_id IS NULL",
                (date,),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM portfolio_snapshots WHERE date = ? AND account_id = ?",
                (date, account_id),
            )
        row = await cursor.fetchone()
        if not row:
            return None
        result = dict(row)
        if result.get("holdings_json"):
            result["holdings"] = json.loads(result["holdings_json"])
        return result
    finally:
        await db.close()


async def get_snapshots_for_date(date: str) -> list[dict]:
    """Get all snapshots (per-account + combined) for a date."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM portfolio_snapshots WHERE date = ?", (date,)
        )
        results = []
        for row in await cursor.fetchall():
            r = dict(row)
            if r.get("holdings_json"):
                r["holdings"] = json.loads(r["holdings_json"])
            results.append(r)
        return results
    finally:
        await db.close()


async def save_snapshot(
    *,
    date: str,
    account_id: int | None,
    total_value: float,
    total_cost: float | None = None,
    day_change: float | None = None,
    day_change_pct: float | None = None,
    holdings_json: str | None = None,
) -> int:
    """Save or replace a snapshot for a date+account."""
    db = await get_db()
    try:
        # Upsert: delete existing, then insert
        if account_id is None:
            await db.execute(
                "DELETE FROM portfolio_snapshots WHERE date = ? AND account_id IS NULL",
                (date,),
            )
        else:
            await db.execute(
                "DELETE FROM portfolio_snapshots WHERE date = ? AND account_id = ?",
                (date, account_id),
            )
        cursor = await db.execute(
            "INSERT INTO portfolio_snapshots "
            "(date, account_id, total_value, total_cost, day_change, day_change_pct, holdings_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (date, account_id, total_value, total_cost, day_change, day_change_pct, holdings_json),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()
