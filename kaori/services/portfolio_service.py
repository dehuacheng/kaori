import json
import logging
from datetime import date, datetime, timezone

from kaori.storage import financial_account_repo, portfolio_holding_repo, portfolio_snapshot_repo, financial_import_repo
from kaori.services import stock_price_service

logger = logging.getLogger("kaori.portfolio")


def _extract_json(text: str) -> dict:
    """Robustly extract a JSON object from LLM output that may contain markdown fences or prose."""
    import re
    text = text.strip()

    # Try 1: direct parse (clean JSON)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try 2: extract from markdown code fence (```json ... ``` or ``` ... ```)
    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try 3: find the first { ... } block (greedy, outermost braces)
    brace_match = re.search(r'\{.*\}', text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract JSON from LLM response (length={len(text)}): {text[:200]}...")


async def list_accounts(account_type: str | None = None) -> list[dict]:
    accounts = await financial_account_repo.list_accounts(account_type)
    # Enrich with holdings count per account
    for acct in accounts:
        holdings = await portfolio_holding_repo.list_by_account(acct["id"])
        acct["holdings_count"] = len(holdings)
    return accounts


async def get_account(account_id: int) -> dict | None:
    return await financial_account_repo.get(account_id)


async def create_account(
    *,
    name: str,
    account_type: str = "brokerage",
    institution: str,
    notes: str | None = None,
) -> dict:
    account_id = await financial_account_repo.create(
        name=name,
        account_type=account_type,
        institution=institution,
        notes=notes,
    )
    return await financial_account_repo.get(account_id)


async def update_account(account_id: int, *, name: str | None = None, notes: str | None = None) -> dict | None:
    await financial_account_repo.update(account_id, name=name, notes=notes)
    return await financial_account_repo.get(account_id)


async def delete_account(account_id: int) -> bool:
    return await financial_account_repo.delete(account_id)


async def list_holdings(account_id: int) -> list[dict]:
    return await portfolio_holding_repo.list_by_account(account_id)


async def create_holding(
    account_id: int,
    *,
    ticker: str,
    shares: float,
    cost_basis: float | None = None,
    notes: str | None = None,
) -> dict:
    holding_id = await portfolio_holding_repo.create(
        account_id=account_id,
        ticker=ticker,
        shares=shares,
        cost_basis=cost_basis,
        notes=notes,
    )
    return await portfolio_holding_repo.get(holding_id)


async def update_holding(
    holding_id: int,
    *,
    ticker: str | None = None,
    shares: float | None = None,
    cost_basis: float | None = None,
    notes: str | None = None,
) -> dict | None:
    await portfolio_holding_repo.update(
        holding_id,
        ticker=ticker,
        shares=shares,
        cost_basis=cost_basis,
        notes=notes,
    )
    return await portfolio_holding_repo.get(holding_id)


async def delete_holding(holding_id: int) -> bool:
    return await portfolio_holding_repo.delete(holding_id)


async def bulk_replace_holdings(account_id: int, holdings: list[dict]) -> dict:
    return await portfolio_holding_repo.bulk_replace(account_id, holdings)


# ---------------------------------------------------------------------------
# Import (Screenshot/PDF + LLM)
# ---------------------------------------------------------------------------


async def create_import(account_id: int, import_type: str, file_path: str | None = None) -> dict:
    analysis_id = await financial_import_repo.create(
        account_id=account_id, import_type=import_type, file_path=file_path,
    )
    return await financial_import_repo.get(analysis_id)


async def get_import(analysis_id: int) -> dict | None:
    return await financial_import_repo.get(analysis_id)


async def list_imports(account_id: int) -> list[dict]:
    return await financial_import_repo.list_by_account(account_id)


async def run_import_analysis(analysis_id: int, file_datas: list[bytes], import_type: str, institution: str, llm_mode: str | None = None):
    """Run LLM analysis on uploaded screenshots or PDF. Runs as background task."""
    import time
    from kaori.llm import get_llm_backend
    from kaori.llm.prompts import build_holdings_extraction_prompt

    await financial_import_repo.update_status(analysis_id, status="analyzing")
    t0 = time.monotonic()

    try:
        llm = get_llm_backend(llm_mode)
        prompt = build_holdings_extraction_prompt(institution)
        sizes = [f"{len(d)/1024:.0f}KB" for d in file_datas]
        logger.info("Import %d: starting LLM analysis (%s, %d files: %s, backend=%s)",
                     analysis_id, import_type, len(file_datas), sizes, type(llm).__name__)

        t1 = time.monotonic()
        if import_type == "screenshot":
            if len(file_datas) == 1:
                response = await llm.analyze_image(file_datas[0], prompt, thinking=False)
            else:
                images = [(data, "image/jpeg") for data in file_datas]
                response = await llm.analyze_images(images, prompt, thinking=False)
        else:  # pdf
            response = await llm.analyze_document(file_datas[0], prompt, thinking=False)
        t2 = time.monotonic()
        logger.info("Import %d: LLM responded in %.1fs (response length=%d)",
                     analysis_id, t2 - t1, len(response.text))

        # Parse the JSON response — robust extraction
        extracted = _extract_json(response.text)
        t3 = time.monotonic()

        await financial_import_repo.update_status(
            analysis_id,
            status="done",
            extracted_json=json.dumps(extracted),
            llm_backend=response.backend,
            model=response.model,
            raw_response=response.text,
        )
        logger.info("Import %d: completed in %.1fs total — %d positions extracted",
                     analysis_id, t3 - t0, len(extracted.get("positions", [])))

    except Exception as e:
        logger.error("Import analysis %d failed: %s", analysis_id, e)
        await financial_import_repo.update_status(
            analysis_id, status="failed", error_message=str(e),
        )


async def confirm_import(analysis_id: int, holdings: list[dict]) -> dict:
    """Confirm extracted holdings from an import — merges with existing (upsert by ticker)."""
    analysis = await financial_import_repo.get(analysis_id)
    if not analysis:
        raise ValueError("Analysis not found")
    account_id = analysis["account_id"]
    result = await portfolio_holding_repo.bulk_merge(account_id, holdings)
    return {"account_id": account_id, **result}


# ---------------------------------------------------------------------------
# Portfolio Summary (powers the feed card)
# ---------------------------------------------------------------------------


def _compute_account_value(holdings: list[dict], prices: dict[str, dict]) -> dict:
    """Compute total value, cost, and day change for a list of holdings with prices."""
    total_value = 0.0
    total_cost = 0.0
    day_change = 0.0
    enriched = []

    for h in holdings:
        ticker = h["ticker"]
        shares = h["shares"]
        cost_basis = h.get("cost_basis")

        if ticker in ("CASH", "MONEY_MARKET"):
            # Cash: value = cost_basis (the cash balance), no day change
            value = cost_basis or 0.0
            total_value += value
            total_cost += value
            enriched.append({
                "ticker": ticker,
                "shares": shares,
                "cost_basis": cost_basis,
                "price": value,
                "market_value": value,
                "day_change": 0.0,
                "day_change_pct": 0.0,
            })
            continue

        price_info = prices.get(ticker)
        if not price_info:
            continue

        current_price = price_info["price"]
        prev_close = price_info.get("previous_close") or current_price
        market_value = shares * current_price
        holding_day_change = shares * (current_price - prev_close)
        holding_day_change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close else 0.0

        total_value += market_value
        if cost_basis:
            total_cost += shares * cost_basis
        day_change += holding_day_change

        enriched.append({
            "ticker": ticker,
            "shares": shares,
            "cost_basis": cost_basis,
            "price": current_price,
            "previous_close": prev_close,
            "market_value": round(market_value, 2),
            "day_change": round(holding_day_change, 2),
            "day_change_pct": round(holding_day_change_pct, 2),
        })

    prev_total = total_value - day_change
    day_change_pct = (day_change / prev_total * 100) if prev_total else 0.0
    total_gain = total_value - total_cost if total_cost else None
    total_gain_pct = (total_gain / total_cost * 100) if total_cost and total_gain is not None else None

    return {
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2) if total_cost else None,
        "day_change": round(day_change, 2),
        "day_change_pct": round(day_change_pct, 2),
        "total_gain": round(total_gain, 2) if total_gain is not None else None,
        "total_gain_pct": round(total_gain_pct, 2) if total_gain_pct is not None else None,
        "holdings": enriched,
    }


async def get_portfolio_summary(target_date: str) -> dict:
    """Get portfolio summary for a given date. Live for today, snapshot for past days."""
    today = date.today().isoformat()
    is_today = target_date == today
    is_live = is_today and stock_price_service._is_market_hours()

    # Get all brokerage accounts
    accounts = await financial_account_repo.list_accounts("brokerage")
    if not accounts:
        return {
            "date": target_date,
            "is_live": False,
            "combined": None,
            "accounts": [],
            "top_movers": [],
            "last_updated": None,
        }

    if is_today:
        return await _build_live_summary(target_date, accounts, is_live)
    else:
        # Past dates: only show data if a snapshot was taken that day
        snapshot = await portfolio_snapshot_repo.get_snapshot(target_date, account_id=None)
        if snapshot:
            return await _build_snapshot_summary(target_date, accounts, snapshot)
        # No snapshot for this date — return empty (no backfill)
        return {
            "date": target_date,
            "is_live": False,
            "combined": None,
            "accounts": [],
            "top_movers": [],
            "last_updated": None,
        }


async def _build_live_summary(target_date: str, accounts: list[dict], is_live: bool) -> dict:
    """Build a live summary from current holdings and prices."""
    # Collect all tickers
    all_tickers = set()
    account_holdings = {}
    for acct in accounts:
        holdings = await portfolio_holding_repo.list_by_account(acct["id"])
        account_holdings[acct["id"]] = holdings
        for h in holdings:
            if h["ticker"] not in ("CASH", "MONEY_MARKET"):
                all_tickers.add(h["ticker"])

    # Fetch prices
    prices = await stock_price_service.get_prices(list(all_tickers))

    # Compute per-account
    combined_value = 0.0
    combined_cost = 0.0
    combined_day_change = 0.0
    account_summaries = []
    all_enriched_holdings = []

    for acct in accounts:
        holdings = account_holdings[acct["id"]]
        if not holdings:
            continue
        result = _compute_account_value(holdings, prices)
        combined_value += result["total_value"]
        if result["total_cost"]:
            combined_cost += result["total_cost"]
        combined_day_change += result["day_change"]
        all_enriched_holdings.extend(result["holdings"])

        account_summaries.append({
            "account_id": acct["id"],
            "name": acct["name"],
            "institution": acct["institution"],
            "total_value": result["total_value"],
            "day_change": result["day_change"],
            "day_change_pct": result["day_change_pct"],
        })

    prev_total = combined_value - combined_day_change
    combined_day_change_pct = (combined_day_change / prev_total * 100) if prev_total else 0.0
    combined_gain = combined_value - combined_cost if combined_cost else None
    combined_gain_pct = (combined_gain / combined_cost * 100) if combined_cost and combined_gain is not None else None

    # Top movers (by absolute day change $)
    movers = sorted(
        [h for h in all_enriched_holdings if h["ticker"] not in ("CASH", "MONEY_MARKET") and h.get("day_change")],
        key=lambda h: abs(h["day_change"]),
        reverse=True,
    )[:5]
    top_movers = [
        {"ticker": m["ticker"], "change_pct": m["day_change_pct"], "change": m["day_change"]}
        for m in movers
    ]

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    return {
        "date": target_date,
        "is_live": is_live,
        "combined": {
            "total_value": round(combined_value, 2),
            "total_cost": round(combined_cost, 2) if combined_cost else None,
            "day_change": round(combined_day_change, 2),
            "day_change_pct": round(combined_day_change_pct, 2),
            "total_gain": round(combined_gain, 2) if combined_gain is not None else None,
            "total_gain_pct": round(combined_gain_pct, 2) if combined_gain_pct is not None else None,
        },
        "accounts": account_summaries,
        "top_movers": top_movers,
        "last_updated": now_utc,
    }


async def _build_snapshot_summary(target_date: str, accounts: list[dict], combined_snapshot: dict) -> dict:
    """Build summary from stored snapshots."""
    account_snapshots = []
    for acct in accounts:
        snap = await portfolio_snapshot_repo.get_snapshot(target_date, account_id=acct["id"])
        if snap:
            account_snapshots.append({
                "account_id": acct["id"],
                "name": acct["name"],
                "institution": acct["institution"],
                "total_value": snap["total_value"],
                "day_change": snap.get("day_change", 0),
                "day_change_pct": snap.get("day_change_pct", 0),
            })

    return {
        "date": target_date,
        "is_live": False,
        "combined": {
            "total_value": combined_snapshot["total_value"],
            "total_cost": combined_snapshot.get("total_cost"),
            "day_change": combined_snapshot.get("day_change", 0),
            "day_change_pct": combined_snapshot.get("day_change_pct", 0),
            "total_gain": None,
            "total_gain_pct": None,
        },
        "accounts": account_snapshots,
        "top_movers": [],
        "last_updated": combined_snapshot.get("created_at"),
    }


async def take_snapshot(target_date: str | None = None) -> dict:
    """Take a snapshot of all brokerage accounts for the given date (default: today)."""
    target_date = target_date or date.today().isoformat()
    accounts = await financial_account_repo.list_accounts("brokerage")

    # Get all tickers and prices
    all_tickers = set()
    account_holdings = {}
    for acct in accounts:
        holdings = await portfolio_holding_repo.list_by_account(acct["id"])
        account_holdings[acct["id"]] = holdings
        for h in holdings:
            if h["ticker"] not in ("CASH", "MONEY_MARKET"):
                all_tickers.add(h["ticker"])

    prices = await stock_price_service.get_prices(list(all_tickers))

    combined_value = 0.0
    combined_cost = 0.0
    combined_day_change = 0.0
    accounts_snapshotted = 0

    for acct in accounts:
        holdings = account_holdings[acct["id"]]
        if not holdings:
            continue
        result = _compute_account_value(holdings, prices)
        combined_value += result["total_value"]
        if result["total_cost"]:
            combined_cost += result["total_cost"]
        combined_day_change += result["day_change"]

        # Save per-account snapshot
        await portfolio_snapshot_repo.save_snapshot(
            date=target_date,
            account_id=acct["id"],
            total_value=result["total_value"],
            total_cost=result["total_cost"],
            day_change=result["day_change"],
            day_change_pct=result["day_change_pct"],
            holdings_json=json.dumps(result["holdings"]),
        )
        accounts_snapshotted += 1

    # Save combined snapshot
    prev_total = combined_value - combined_day_change
    combined_pct = (combined_day_change / prev_total * 100) if prev_total else 0.0

    await portfolio_snapshot_repo.save_snapshot(
        date=target_date,
        account_id=None,
        total_value=round(combined_value, 2),
        total_cost=round(combined_cost, 2) if combined_cost else None,
        day_change=round(combined_day_change, 2),
        day_change_pct=round(combined_pct, 2),
    )

    return {
        "date": target_date,
        "combined_value": round(combined_value, 2),
        "accounts_snapshotted": accounts_snapshotted,
    }
