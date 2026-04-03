# Kaori — Financial Accounts Feature

## Purpose

Track brokerage portfolio value across multiple accounts (Schwab, Fidelity, Moomoo). Show daily portfolio change on the feed. Import holdings via screenshot/PDF + LLM extraction or direct API sync.

## Data Model

### Tables

| Table | Purpose |
|-------|---------|
| `financial_accounts` | Brokerage/bank/credit card accounts (general). Fields: name, account_type, institution, sync_method, api_credentials, last_synced_at |
| `portfolio_holdings` | Current stock positions per account. Fields: ticker, shares, cost_basis |
| `financial_import_analyses` | LLM extraction results from screenshots/PDFs (append-only, auditable) |
| `portfolio_snapshots` | Frozen end-of-day portfolio values per account + combined |
| `stock_prices` | Price cache with staleness tracking |

### Key Design Decisions
- `financial_accounts` is general (supports brokerage, credit_card, bank) for future expansion
- `portfolio_snapshots` with `account_id = NULL` stores combined portfolio total
- Cash/money market tracked with ticker `CASH`/`MONEY_MARKET`, value in `cost_basis`
- Prices cached in `stock_prices` with 5-min TTL during market hours, 1-hour off-hours

## Endpoints

All under `/api/finance`.

### Accounts
- `GET /api/finance/accounts` — list (filterable by `?type=brokerage`)
- `POST /api/finance/accounts` — create {name, account_type, institution}
- `PUT /api/finance/accounts/{id}` — update
- `DELETE /api/finance/accounts/{id}` — delete + cascade

### Holdings
- `GET /api/finance/accounts/{id}/holdings` — list
- `POST /api/finance/accounts/{id}/holdings` — add single
- `PUT /api/finance/holdings/{id}` — update
- `DELETE /api/finance/holdings/{id}` — delete
- `POST /api/finance/accounts/{id}/holdings/bulk` — replace all

### Import (Screenshot/PDF)
- `POST /api/finance/accounts/{id}/import` — upload (multipart), background LLM extraction
- `GET /api/finance/imports/{id}` — poll status + get extracted data
- `POST /api/finance/imports/{id}/confirm` — save confirmed positions

### Portfolio Summary
- `GET /api/finance/portfolio/summary?date=YYYY-MM-DD` — combined + per-account values, day change, top movers
- `POST /api/finance/portfolio/refresh-prices` — force refresh
- `POST /api/finance/portfolio/snapshot` — manual end-of-day snapshot

### Sync Status
- `GET /api/finance/accounts/{id}/sync-status` — connection health

## Key Files

### Backend
| File | Purpose |
|------|---------|
| `kaori/models/finance.py` | Pydantic models |
| `kaori/storage/financial_account_repo.py` | Account CRUD |
| `kaori/storage/portfolio_holding_repo.py` | Holdings CRUD + bulk replace |
| `kaori/storage/financial_import_repo.py` | Import analysis CRUD |
| `kaori/storage/portfolio_snapshot_repo.py` | Snapshot CRUD |
| `kaori/storage/stock_price_repo.py` | Price cache |
| `kaori/services/portfolio_service.py` | Business logic: CRUD, summary, snapshots, import |
| `kaori/services/stock_price_service.py` | yfinance integration + caching |
| `kaori/services/account_sync/__init__.py` | AccountConnector ABC |
| `kaori/services/account_sync/schwab.py` | Schwab connector (stub) |
| `kaori/services/account_sync/moomoo.py` | Moomoo connector (stub) |
| `kaori/api/finance.py` | API endpoints |
| `kaori/llm/prompts.py` | `build_holdings_extraction_prompt()` |

### iOS
| File | Purpose |
|------|---------|
| `Models/Finance.swift` | Codable models |
| `Stores/FinanceStore.swift` | @Observable store |
| `Views/Portfolio/PortfolioFeedCard.swift` | Feed card |
| `Views/Portfolio/PortfolioDetailView.swift` | Detail on tap |
| `Views/Finance/FinanceAccountListView.swift` | Account management |
| `Views/Finance/FinanceAccountDetailView.swift` | Holdings view |
| `Views/Finance/HoldingsImportView.swift` | Screenshot import flow |

## LLM Integration

`build_holdings_extraction_prompt(institution)` in `kaori/llm/prompts.py`. Uses existing `analyze_image()` for screenshots, new `analyze_document()` for PDFs.

## Future

- Plaid connector for credit cards/banks (Chase, Citi, Amex)
- Transaction tracking, daily spending feed card
- Net worth dashboard aggregating all account types
