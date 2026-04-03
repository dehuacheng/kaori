from kaori.database import get_db


async def list_by_account(account_id: int) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM portfolio_holdings WHERE account_id = ? ORDER BY ticker",
            (account_id,),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def get(holding_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM portfolio_holdings WHERE id = ?", (holding_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def create(
    *,
    account_id: int,
    ticker: str,
    shares: float,
    cost_basis: float | None = None,
    notes: str | None = None,
) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO portfolio_holdings (account_id, ticker, shares, cost_basis, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            (account_id, ticker.upper(), shares, cost_basis, notes),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def update(
    holding_id: int,
    *,
    ticker: str | None = None,
    shares: float | None = None,
    cost_basis: float | None = None,
    notes: str | None = None,
) -> bool:
    db = await get_db()
    try:
        fields = []
        values = []
        if ticker is not None:
            fields.append("ticker = ?")
            values.append(ticker.upper())
        if shares is not None:
            fields.append("shares = ?")
            values.append(shares)
        if cost_basis is not None:
            fields.append("cost_basis = ?")
            values.append(cost_basis)
        if notes is not None:
            fields.append("notes = ?")
            values.append(notes)
        if not fields:
            return False
        fields.append("updated_at = datetime('now')")
        values.append(holding_id)
        cursor = await db.execute(
            f"UPDATE portfolio_holdings SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def delete(holding_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM portfolio_holdings WHERE id = ?", (holding_id,)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def bulk_replace(account_id: int, holdings: list[dict]) -> dict:
    """Replace all holdings for an account with the given list."""
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM portfolio_holdings WHERE account_id = ?", (account_id,)
        )
        created = 0
        for h in holdings:
            await db.execute(
                "INSERT INTO portfolio_holdings (account_id, ticker, shares, cost_basis, notes) "
                "VALUES (?, ?, ?, ?, ?)",
                (account_id, h["ticker"].upper(), h["shares"], h.get("cost_basis"), h.get("notes")),
            )
            created += 1
        await db.commit()
        return {"created": created}
    finally:
        await db.close()


async def bulk_merge(account_id: int, holdings: list[dict]) -> dict:
    """Merge holdings into an account: update if ticker exists, insert if new."""
    db = await get_db()
    try:
        # Get existing tickers for this account
        cursor = await db.execute(
            "SELECT id, ticker FROM portfolio_holdings WHERE account_id = ?",
            (account_id,),
        )
        existing = {row["ticker"]: row["id"] for row in await cursor.fetchall()}

        created = 0
        updated = 0
        for h in holdings:
            ticker = h["ticker"].upper()
            if ticker in existing:
                await db.execute(
                    "UPDATE portfolio_holdings SET shares = ?, cost_basis = ?, "
                    "updated_at = datetime('now') WHERE id = ?",
                    (h["shares"], h.get("cost_basis"), existing[ticker]),
                )
                updated += 1
            else:
                await db.execute(
                    "INSERT INTO portfolio_holdings (account_id, ticker, shares, cost_basis, notes) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (account_id, ticker, h["shares"], h.get("cost_basis"), h.get("notes")),
                )
                created += 1
        await db.commit()
        return {"created": created, "updated": updated}
    finally:
        await db.close()


async def get_all_tickers() -> list[str]:
    """Get all unique tickers across all brokerage accounts (excluding CASH/MONEY_MARKET)."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT DISTINCT ticker FROM portfolio_holdings "
            "WHERE ticker NOT IN ('CASH', 'MONEY_MARKET') ORDER BY ticker"
        )
        return [row["ticker"] for row in await cursor.fetchall()]
    finally:
        await db.close()
