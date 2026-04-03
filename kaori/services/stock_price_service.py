import asyncio
import logging
from datetime import datetime, timezone

from kaori.storage import stock_price_repo, portfolio_holding_repo

logger = logging.getLogger("kaori.stock_price")

# Cache staleness thresholds (seconds)
MARKET_HOURS_TTL = 300       # 5 minutes during market hours
OFF_HOURS_TTL = 3600         # 1 hour outside market hours


def _is_market_hours() -> bool:
    """Check if US stock market is currently open (9:30 AM - 4:00 PM ET, Mon-Fri)."""
    from zoneinfo import ZoneInfo
    now_et = datetime.now(ZoneInfo("America/New_York"))
    if now_et.weekday() >= 5:  # Saturday, Sunday
        return False
    market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now_et <= market_close


def _cache_is_stale(fetched_at: str) -> bool:
    """Check if a cached price is too old."""
    fetched = datetime.fromisoformat(fetched_at.replace(" ", "T")).replace(tzinfo=timezone.utc)
    age_seconds = (datetime.now(timezone.utc) - fetched).total_seconds()
    ttl = MARKET_HOURS_TTL if _is_market_hours() else OFF_HOURS_TTL
    return age_seconds > ttl


async def _fetch_from_yfinance(tickers: list[str]) -> dict[str, dict]:
    """Fetch current prices from yfinance (runs in thread pool)."""
    if not tickers:
        return {}

    market_open = _is_market_hours()

    def _fetch():
        import yfinance as yf
        results = {}
        data = yf.Tickers(" ".join(tickers))
        for ticker in tickers:
            try:
                t = data.tickers[ticker]
                info = t.fast_info
                last = float(info.last_price)
                prev = float(info.previous_close) if info.previous_close else None
                # Outside market hours, use previous_close as price
                # to avoid showing pre/post-market movements
                price = last if market_open else (prev or last)
                results[ticker] = {
                    "ticker": ticker,
                    "price": price,
                    "previous_close": prev,
                }
            except Exception as e:
                logger.warning("Failed to fetch price for %s: %s", ticker, e)
        return results

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch)


async def get_prices(tickers: list[str]) -> dict[str, dict]:
    """Get current prices for tickers, using cache when fresh enough."""
    if not tickers:
        return {}

    cached = await stock_price_repo.get_latest_prices(tickers)

    # Determine which tickers need refresh
    stale_tickers = []
    for t in tickers:
        if t in ("CASH", "MONEY_MARKET"):
            continue
        if t not in cached or _cache_is_stale(cached[t]["fetched_at"]):
            stale_tickers.append(t)

    if stale_tickers:
        logger.info("Fetching prices for %d stale tickers: %s", len(stale_tickers), stale_tickers)
        fresh = await _fetch_from_yfinance(stale_tickers)
        if fresh:
            await stock_price_repo.save_prices(list(fresh.values()))
            cached.update(fresh)

    return cached


async def refresh_all_prices() -> dict:
    """Force refresh prices for all held tickers."""
    tickers = await portfolio_holding_repo.get_all_tickers()
    if not tickers:
        return {"tickers_updated": 0}

    fresh = await _fetch_from_yfinance(tickers)
    if fresh:
        await stock_price_repo.save_prices(list(fresh.values()))

    return {"tickers_updated": len(fresh)}
