from kaori.database import get_db


async def get_latest_prices(tickers: list[str]) -> dict[str, dict]:
    """Get the most recent cached price for each ticker."""
    if not tickers:
        return {}
    db = await get_db()
    try:
        placeholders = ",".join("?" for _ in tickers)
        cursor = await db.execute(
            f"SELECT ticker, price, previous_close, fetched_at "
            f"FROM stock_prices "
            f"WHERE id IN ("
            f"  SELECT MAX(id) FROM stock_prices WHERE ticker IN ({placeholders}) GROUP BY ticker"
            f")",
            tickers,
        )
        rows = await cursor.fetchall()
        return {row["ticker"]: dict(row) for row in rows}
    finally:
        await db.close()


async def save_prices(prices: list[dict], source: str = "yfinance"):
    """Save fetched prices to the cache."""
    if not prices:
        return
    db = await get_db()
    try:
        await db.executemany(
            "INSERT INTO stock_prices (ticker, price, previous_close, source) "
            "VALUES (?, ?, ?, ?)",
            [(p["ticker"], p["price"], p.get("previous_close"), source) for p in prices],
        )
        await db.commit()
    finally:
        await db.close()
