# Card: Portfolio

## Identity

| Field | Value |
|-------|-------|
| Card Type | `portfolio` |
| Icon | `chart.line.uptrend.xyaxis` |
| Accent Color | Green |
| Module | `PortfolioCardModule.swift` |

## Purpose

Show combined brokerage portfolio value, daily change, per-account breakdown, and top stock movers. Live prices on market days, frozen snapshots for past days.

## Feed Behavior

| Behavior | Value |
|----------|-------|
| Manual creation ("+") | No (auto-added if brokerage accounts exist) |
| Tap → detail | Yes → `PortfolioDetailView` |
| Swipe actions | None |
| Sort priority | 1 (pinned near top) |
| Pinned | Yes — today only, market days only (Mon–Fri) |

**Auto-refresh:** Portfolio data refreshes every 60 seconds on market days via `FeedStore.startPortfolioRefresh()`.

## Data (More > Data)

`PortfolioDetailView` — full portfolio breakdown by account with holdings.

## Settings

None. Account management is under More > Finances.

## Backend

### Tables

| Table | Purpose |
|-------|---------|
| `financial_accounts` | Brokerage/bank/credit card accounts |
| `portfolio_holdings` | Stock positions per account (ticker, shares, cost_basis) |
| `portfolio_snapshots` | Frozen end-of-day values (date, total_value, holdings_json) |
| `stock_prices` | Price cache (ticker, price, fetched_at, TTL-based staleness) |
| `financial_import_analyses` | LLM extraction from screenshots/PDFs |

### API Endpoints

- `GET /api/finance/portfolio/summary?date=YYYY-MM-DD` — combined + per-account, live or snapshot
- `POST /api/finance/portfolio/refresh-prices` — force price refresh
- `POST /api/finance/portfolio/snapshot` — manual end-of-day snapshot
- Account/holdings CRUD under `/api/finance/accounts/...`
- Import: `POST /api/finance/accounts/{id}/import` → `GET /api/finance/imports/{id}` → `POST /api/finance/imports/{id}/confirm`

### Feed Loader

`_load_portfolio` in `feed_service.py` — fetches via `portfolio_service.get_portfolio_summary()`.

## Key Backend Files

- `models/finance.py` — AccountCreate, HoldingCreate, HoldingBulkRequest
- `storage/financial_account_repo.py`, `portfolio_holding_repo.py`, `portfolio_snapshot_repo.py`, `stock_price_repo.py`, `financial_import_repo.py`
- `services/portfolio_service.py` — account CRUD, portfolio summary, import analysis
- `services/stock_price_service.py` — yfinance price fetching + caching
