# Kaori — Project Instructions

## Overview
Kaori is a personal AI-powered life management app. Codename "Kaori" — not limited to health, designed to expand into calendar, todos, diaries, and more. Privacy-first, self-hosted.

## Architecture (4-Layer Separation)

```
kaori/                  # Backend Python package
  models/               ← Pydantic data contracts (shared across layers)
    meal.py, weight.py, finance.py, llm.py

  storage/              ← Data persistence (DB repos + file storage)
    meal_repo.py            Raw meal CRUD
    meal_analysis_repo.py   LLM analysis results CRUD
    meal_override_repo.py   User manual corrections
    meal_history_repo.py    Versioned habit summaries + recent meals
    weight_repo.py          Weight CRUD
    profile_repo.py         User profile CRUD
    file_store.py           Photo file management
    financial_account_repo.py  Financial account CRUD
    portfolio_holding_repo.py  Brokerage holdings CRUD + merge
    portfolio_snapshot_repo.py Daily portfolio snapshots
    stock_price_repo.py     Stock price cache
    financial_import_repo.py Screenshot/PDF import analysis
    agent_session_repo.py   Agent chat session CRUD
    agent_message_repo.py   Agent message persistence
    agent_memory_repo.py    Agent cross-session memory
    agent_compaction_repo.py Agent transcript compaction
    agent_prompt_repo.py    Agent personal prompts

  llm/                  ← LLM abstraction layer
    base.py                 LLMBackend ABC (the interface)
    claude_cli.py           Claude CLI subprocess backend
    claude_api.py           Anthropic SDK backend
    prompts.py              Prompt templates
    agent_backend.py        AgentLLMBackend ABC (chat + tool_use + streaming)

  services/             ← Business logic (orchestrates storage + llm)
    meal_service.py         Meal operations + analysis orchestration
    weight_service.py       Weight operations + trends
    portfolio_service.py    Financial accounts + portfolio summary
    stock_price_service.py  Stock price fetching + caching
    account_sync/           Brokerage API connectors (Schwab, Moomoo stubs)
    profile_service.py      Profile CRUD + LLM context formatting
    agent_service.py        Agent session/memory/prompt orchestration
    agent_chat_service.py   Agent chat turn loop + SSE streaming
    agent_engine.py         Agentic turn loop (tool_use loop)
    agent_tools.py          Server-side agent tools (9 tools)

  api/                  ← JSON API endpoints at /api/*
    router.py               Aggregates all API sub-routers
    meals.py, weight.py, profile.py, finance.py, test_mode.py
    agent.py                Agent sessions/memory/prompts + SSE chat

  web/                  ← HTML pages (barebone testing frontend)
    router.py               Aggregates all web sub-routers
    dashboard.py, meals.py, weight.py, profile.py

  templates/            ← Jinja2 HTML (HTMX + Alpine.js)
  static/               ← CSS, JS, PWA manifest
  main.py               ← FastAPI app, mounts api + web
```

## Data Model: Raw vs Processed Separation
- **Raw tables** store exactly what the user provided (meals, body_measurements)
- **Analysis tables** store LLM-generated results (meal_analyses) with audit trail (backend, model, raw_response)
- **Override tables** store user corrections (meal_overrides) that take precedence over LLM results
- **Summary tables** store LLM-compacted summaries (meal_habit_summaries) — versioned and rollback-safe
- Pattern for new data types: `raw_table` + `analysis_table` + optional `override_table`

## Versioned LLM Summaries Pattern (Rollback-Safe)
When LLM compaction/summarization is used (e.g., meal habit summaries), data must be:
- **Append-only**: every compaction creates a new row, never overwrites
- **Versioned**: each row has a `version` (monotonically increasing) and `is_active` flag
- **Rollback-safe**: deactivate bad version, reactivate previous — no data lost
- **Auditable**: every version preserves `llm_backend`, `model`, `raw_response`
- Apply this pattern to any future LLM-compacted data (diary summaries, health profiles, etc.)

## Test Mode (Data Safety Pattern)
When developing features that touch data (schema changes, new tables, migrations), **always work in test mode first**:

1. **Fork real data**: `POST /api/test-mode/fork` (while running in production mode) — copies `kaori.db` + `photos/` to `kaori_test.db` + `photos_test/`
2. **Develop in test mode**: `KAORI_TEST_MODE=1 uvicorn kaori.main:app --reload ...` — all reads/writes go to the test DB. A red "TEST MODE" banner is shown in the web UI.
3. **Iterate**: Build and validate the feature against the test copy. Real data is never touched.
4. **Graduate to production**: Once the feature is stable, stop test mode, apply any schema migrations to the real DB, and restart normally.

```bash
# Fork real data to test
curl -X POST http://localhost:8000/api/test-mode/fork

# Run both side by side (production :8000, test :8001)
uvicorn kaori.main:app --reload --host 0.0.0.0 --port 8000 &
KAORI_TEST_MODE=1 uvicorn kaori.main:app --reload --host 0.0.0.0 --port 8001 &
```

- `KAORI_TEST_MODE` env var controls which DB/photos dir is used (`data/kaori_test.db` vs `data/kaori.db`)
- **Convention**: production on port 8000, test on port 8001
- Test data files are gitignored (under `data/`)
- The fork can be re-run anytime to get a fresh snapshot of real data
- Both servers can run simultaneously — compare behavior side by side

## Rules
- Storage repos own ALL database access. No `get_db()` calls outside `storage/`.
- Services orchestrate storage + LLM. No HTTP concerns.
- API routes return JSON only. No template rendering.
- Web routes render templates only. Business logic stays in services.
- LLM callers depend only on `LLMBackend` ABC, never on concrete backends.

## Backend Patterns
- **FastAPI route ordering matters:** place specific string path routes BEFORE generic parameterized routes (e.g., `/items/search` before `/items/{id}`) to avoid path conflicts.
- **JSON contracts:** When adding new model fields, test JSON encoding/decoding round-trips between Python (Pydantic) and Swift (Codable). Silent decoding failures are hard to trace.

## Workflow Preferences
- After making a plan, start implementing code changes promptly. Do not spend extended time reading files and planning without producing edits — the user prefers iterative progress over exhaustive upfront analysis.

## MCP Server (Read-Only)

Kaori exposes a read-only MCP server at `kaori/mcp_server.py` for querying personal data
from Claude Code, kaori-agent, or any MCP client. **15 tools**, all GET requests.

```bash
# Install
pip install -e ".[mcp]"

# Run standalone (stdio transport)
KAORI_API_TOKEN=<token> python -m kaori.mcp_server
```

**Claude Code config** (add to `.claude/settings.json` or project `.mcp.json`):
```json
{
  "mcpServers": {
    "kaori": {
      "command": "python",
      "args": ["-m", "kaori.mcp_server"],
      "cwd": "/path/to/kaori",
      "env": {
        "KAORI_API_URL": "http://localhost:8000",
        "KAORI_API_TOKEN": "<token>"
      }
    }
  }
}
```

**Tools:** `get_feed`, `get_meals`, `get_meal_detail`, `get_weight`, `get_profile`,
`get_portfolio_summary`, `get_financial_accounts`, `get_account_holdings`,
`get_workouts`, `get_workout_detail`, `get_daily_summary`, `get_weekly_summary`,
`get_reminders`, `get_meal_streak`, `get_exercise_types`

## Agent Chat API

Kaori backend hosts an AI agent chat service with SSE streaming. The agent can
query all kaori data via 17 server-side tools (no HTTP round-trip — calls services directly).
Full parity with the MCP server tools plus 2 agent-only memory tools.

**Dependencies:** `pip install -e ".[agent]"` (adds `anthropic`, `openai` SDKs + `pyyaml`)

**Config (resolution order):**
1. Environment vars: `KAORI_AGENT_BACKEND`, `DEEPSEEK_API_KEY`, etc.
2. Shared config: `~/.kaori-agent/config.yaml` (same file used by kaori-agent CLI)
3. Defaults: `anthropic` backend, `claude-sonnet-4-6` model

**Endpoints:**
- `POST /api/agent/chat` — SSE streaming chat (body: `{message, session_id?}`)
- `GET/POST/PUT/DELETE /api/agent/sessions` — session CRUD
- `GET/PUT/DELETE /api/agent/memory` — cross-session memory
- `GET/POST/PUT/DELETE /api/agent/prompts` — personal prompt management

**Architecture:** `AgentLLMBackend` ABC (in `llm/agent_backend.py`) is separate from the
existing `LLMBackend` ABC. The agent backend handles chat + tool_use + streaming; the
existing backend handles one-shot tasks (meal analysis, summaries). They do not interfere.

**Frontend parity (READ before changing prompt/persona/memory/context behavior):**
The agent has multiple frontends (this backend → iOS, plus the standalone CLI in
`../kaori-agent`). Anything that affects what the model sees or how it surfaces
non-chat output (memory saves, mode flips, etc.) must be **shared code**, not a
parallel implementation. Single source of truth lives in `kaori_agent` (the library).
Do not write a new `_build_system_prompt` here. See `../kaori-agent/docs/FRONTEND-PARITY.md`.

## Key Decisions
- **Codename**: Kaori — personal super app, not just health
- **Frontend**: Server-rendered HTML (HTMX + Alpine.js) is barebone testing UI only. Primary frontends will be separate repos (iOS, web SPA).
- **Database**: SQLite with WAL mode. `data/kaori.db`
- **LLM**: Abstract interface with two backends. Default: Claude CLI (`claude -p`). Optional: Anthropic API (`pip install kaori[llm-api]`). Controlled by `KAORI_LLM_MODE` env var.
- **Auth**: Bearer token (single-user, Tailscale-gated).
- **Privacy**: All data stays local by default.

## Running
```bash
cd ~/Claude/kaori
source .venv/bin/activate

# Production (port 8000) + Test mode (port 8001) side by side:
uvicorn kaori.main:app --reload --host 0.0.0.0 --port 8000 &
KAORI_TEST_MODE=1 uvicorn kaori.main:app --reload --host 0.0.0.0 --port 8001 &

# Or individually:
uvicorn kaori.main:app --reload --host 0.0.0.0 --port 8000
KAORI_TEST_MODE=1 uvicorn kaori.main:app --reload --host 0.0.0.0 --port 8001
```
- **Port 8000**: production (real data)
- **Port 8001**: test mode (test data, red banner)
- Requires `claude` CLI in PATH for default LLM mode. For API mode: set `ANTHROPIC_API_KEY` and `KAORI_LLM_MODE=claude_api`.

## Card-First Architecture

Kaori is a **feed-first, card-first** app. Every user-facing feature is a **card type** — the atomic unit of the app. Before adding a new feature or modifying an existing one, think: "which card does this belong to?"

### Design Principles
1. **No card is special in the feed.** The backend `feed_service.py` uses a `CARD_LOADERS` registry — a dict mapping `CardType` → async loader function. Adding a new card type means adding ONE line to this dict.
2. **Parallel development.** Two developers can build different card types simultaneously. Each card type is fully self-contained in its own domain files (models, storage, services, api). Shared files need only trivial 1-line additions (enum value, loader registration, router include).
3. **Data section is for data.** The feed shows cards. The data section shows raw data for browsing/editing/deleting. Analytics are separate.

### Card Types
Each card type is defined in `models/card.py` (`CardType` enum). Current types: `meal`, `weight`, `workout`, `healthkit_workout`, `portfolio`, `nutrition`, `summary`, `post`, `reminder`, `agent_session`.

### Feed Service Registry
`services/feed_service.py` uses a `CARD_LOADERS` dict to aggregate data. Each loader is an async function `(date_str, group) -> None` that populates a `FeedDateGroup`. No hardcoded if-blocks per card type.

### Adding or Editing a Card
**Read `docs/cards/HOWTO.md` first** — it has the full-stack checklist (backend + iOS), file-by-file, with the items-based vs singleton distinction. Covers both new cards and common edit patterns (adding fields, changing swipe actions, etc.).

- Per-card design docs: `docs/cards/<type>.md` (index: `docs/cards/README.md`)
- Simplest reference card: Post (`models/post.py`, `storage/post_repo.py`, `services/post_service.py`, `api/post.py`)

### Card Preferences
Per-card-type enable/disable stored in `card_preferences` table. Exposed via `GET/PUT /api/feed/card-preferences`. The iOS app hides disabled cards from feed, "+" menu, and Data tab.

### Feed Endpoint
`GET /api/feed?start_date=...&end_date=...` iterates `CARD_LOADERS` for each date, respecting card preferences. Per-domain endpoints (`/api/meals`, `/api/weight`, etc.) remain available for direct access.

### Pre-Commit Design Check
Before pushing to GitHub, verify the feed aggregation logic is generic (no per-type if-blocks):
```bash
# The _build_date_group and get_feed functions must NOT reference specific CardTypes.
# CardType refs are fine in loader functions (_load_meals etc.) and CARD_LOADERS dict.
python3 -c "
import re, sys
with open('kaori/services/feed_service.py') as f:
    text = f.read()
# Extract _build_date_group and get_feed function bodies
for fn in ['_build_date_group', 'get_feed']:
    match = re.search(rf'(async def {fn}\b.*?)(?=\nasync def |\nCARD_LOADERS|\Z)', text, re.S)
    if match and 'CardType.' in match.group(1):
        print(f'FAIL: {fn} references specific CardType values'); sys.exit(1)
print('OK: feed aggregation is card-type-agnostic')
"
```

## Feature Documentation
When adding a new feature or function, create or update a doc in `docs/` and link it from the Feature Docs table in `docs/PLAN.md`. Each feature doc should cover:
- **Purpose**: what the feature does and why
- **Data model**: tables, fields, relationships
- **Endpoints**: API routes and web routes
- **Key files**: which source files implement it
- **LLM integration** (if any): prompts, analysis flow

### Feature versioning
Each feature doc is tracked with a version in `docs/PLAN.md`:
- **0.x.y** — in development, not yet stable
- **1.0.0** — feature complete and validated with real data
- Bump **minor** (0.x.0) for new capabilities; bump **patch** (0.0.x) for fixes/refinements
- When making changes to a feature, bump its version in the PLAN.md table and note what changed in the feature doc

Existing feature docs: `docs/meals.md`, `docs/weight.md`, `docs/profile.md`, `docs/workout.md`, `docs/finance.md`, `docs/patterns.md`, `docs/roadmap.md`.

## Photo Handling
- All uploaded photos are resized to **max 1600px** and saved as **JPEG quality 85** in `save_photo()` (`storage/file_store.py`)
- Handles HEIC→JPEG, PNG→JPEG conversion (convert to RGB first)
- Photos stored in `data/photos/{YYYY}/{MM}/{DD}/{uuid}.jpg`
- Served as static files at `/photos/{path}`
- For LLM analysis, photos are further resized to 1024px / quality 80 via `get_resized_image_bytes()`
- Migration script: `scripts/compress_photos.py` (with `--dry-run` flag, respects `KAORI_TEST_MODE`)

## Unit Preferences
- Three independent unit settings on `user_profile`:
  - `unit_body_weight`: `kg` or `lb` (default: `kg`)
  - `unit_height`: `cm` or `in` (default: `cm`)
  - `unit_exercise_weight`: `kg` or `lb` (default: `kg`)
- **DB always stores metric** (kg, cm). Conversion happens at the client display/input layer.
- Unit preferences are included in LLM context (`format_profile_context()`) so AI summaries use user's preferred units.
- Profile API (`GET/PUT /api/profile`) exposes all three fields.

## AI Summaries
- `GET /api/summary/daily-detail?date=YYYY-MM-DD` — retrieve existing daily summary
- `POST /api/summary/daily-detail?language=en/zh&date=YYYY-MM-DD` — generate/regenerate
- `GET /api/summary/weekly-detail` — retrieve weekly summary
- `POST /api/summary/weekly-detail?language=en/zh` — generate/regenerate
- Summaries stored in `summaries` table, LLM-generated markdown with `## Section` headers
- iOS prefetches via background task 1 hour before notification time

## Conventions
- Python 3.12+, type hints, async where beneficial
- Pydantic models for request/response validation
- Dates stored as `YYYY-MM-DD` text in SQLite, timestamps as UTC via `datetime('now')`
- Meal analysis (photo or text) runs in background (asyncio.create_task), UI polls via HTMX
- Text-only meals are analyzed with historical context (user profile + habit summary + recent meals)
- Meal history compaction: `POST /api/meals/compact-history` to compress older meals into a summary
- Weight: multiple entries per day allowed, CRUD by id (not date)
- Nutrition targets computed dynamically from profile + latest weight (BMR/TDEE), not stored statically
- Both meals and weight forms expose date pickers for backfilling entries

## README — Bilingual (EN/CN)
- `README.md` contains both English and Chinese versions using `<details>` toggles.
- **When updating the README, always update both language sections to keep them in sync.**
- English is open by default; Chinese is collapsed.

## Docs
- Feature docs, design patterns, and decision log live in `docs/`
- See `docs/PLAN.md` for the index of all documentation
