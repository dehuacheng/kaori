# Kaori — Project Instructions

## Overview
Kaori is a personal AI-powered life management app. Codename "Kaori" — not limited to health, designed to expand into calendar, todos, diaries, and more. Privacy-first, self-hosted.

## Architecture (4-Layer Separation)

```
kaori/                  # Backend Python package
  models/               ← Pydantic data contracts (shared across layers)
    meal.py, weight.py, llm.py

  storage/              ← Data persistence (DB repos + file storage)
    meal_repo.py            Raw meal CRUD
    meal_analysis_repo.py   LLM analysis results CRUD
    meal_override_repo.py   User manual corrections
    meal_history_repo.py    Versioned habit summaries + recent meals
    weight_repo.py          Weight CRUD
    profile_repo.py         User profile CRUD
    file_store.py           Photo file management

  llm/                  ← LLM abstraction layer
    base.py                 LLMBackend ABC (the interface)
    claude_cli.py           Claude CLI subprocess backend
    claude_api.py           Anthropic SDK backend
    prompts.py              Prompt templates

  services/             ← Business logic (orchestrates storage + llm)
    meal_service.py         Meal operations + analysis orchestration
    weight_service.py       Weight operations + trends
    profile_service.py      Profile CRUD + LLM context formatting

  api/                  ← JSON API endpoints at /api/*
    router.py               Aggregates all API sub-routers
    meals.py, weight.py, profile.py, test_mode.py

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

## Extensibility Pattern
Adding a new data domain (e.g., diary, calendar, todo):
1. `kaori/models/diary.py` — Pydantic models
2. `kaori/storage/diary_repo.py` + `diary_analysis_repo.py` — DB access
3. `kaori/services/diary_service.py` — Business logic
4. `kaori/api/diary.py` — JSON endpoints
5. `kaori/web/diary.py` + template — Testing UI
6. Add prompt to `kaori/llm/prompts.py`
7. Add SQL tables following raw/analysis/override pattern
8. **Add a feature doc** at `docs/<feature>.md` describing the feature (see below)

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

Existing feature docs: `docs/meals.md`, `docs/weight.md`, `docs/profile.md`, `docs/patterns.md`, `docs/roadmap.md`.

## Conventions
- Python 3.12+, type hints, async where beneficial
- Pydantic models for request/response validation
- Dates stored as `YYYY-MM-DD` text in SQLite, timestamps as ISO-8601
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
