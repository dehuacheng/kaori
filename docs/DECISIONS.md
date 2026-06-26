# Decision Log

> Tracks substantial user instructions and project direction changes.
> Each entry summarizes the user's intent so future sessions have full context.

### 2026-03-29 — Initial project scope and vision

**User intent:** Build a privacy-first health tracking app that comprehensively tracks medical records, iOS Health data, exercises, diet, and body weight. The app should serve as personal trainer, nutritionist, primary care doctor, and emotional supporter — proactively asking for data to improve health outcomes. All data stays local (no cloud), LLM calls only via API/CLI.

**Outcome:** Defined 7-phase plan starting with MVP (diet + exercise tracking). Tech stack: FastAPI + HTMX + Alpine.js + SQLite, self-hosted on Apple Silicon MacBook, accessed from iPhone as PWA via Tailscale.

### 2026-03-29 — PWA instead of native iOS app

**User intent:** User asked whether an Apple Developer account is needed. After discussion, chose PWA-first approach to avoid the $99/year developer fee and App Store review process.

**Outcome:** PWA via Safari (add to home screen). Native app deferred to later if needed.

### 2026-03-29 — Claude CLI as LLM backend (no API key)

**User intent:** User doesn't have a separate Anthropic API key but has Claude Code authenticated via OAuth. Wants to use existing auth for meal photo analysis.

**Outcome:** LLM calls go through `claude -p --output-format json --no-session-persistence --model sonnet` as async subprocess. No `anthropic` SDK dependency. See `app/services/llm.py`.

### 2026-03-29 — Strict 3-layer backend/frontend separation

**User intent:** "During design, let's make sure we are clear on the backend design and separate it with front end design to avoid convoluted changes." Wants clean separation so backend logic and frontend templates can evolve independently.

**Outcome:** Refactored to 3-layer architecture: `services/` (business logic + DB), `api/` (JSON endpoints), `pages/` (HTML rendering). Both api/ and pages/ call the same service functions. No business logic in routes.

### 2026-03-29 — Async meal photo analysis with polling UI

**User intent:** After uploading a photo, user saw no feedback. Requested non-blocking async processing with UI updates showing progress.

**Outcome:** Photo analysis runs as `asyncio.create_task` background job. Meals get `analysis_status` column (pending/analyzing/done/failed). HTMX polls `/meals/{id}/status` every 3s until complete.

### 2026-03-31 — Track project evolution via decision log

**User intent:** When user provides substantial instructions/prompts, keep a summary in project docs so the evolution of the project is tracked across sessions.

**Outcome:** Added decision log convention to global CLAUDE.md. Created `docs/DECISIONS.md` in health-tracker with backfilled entries.

### 2026-03-31 — Rename to "Kaori", redesign as personal super app

**User intent:** The app should be a personal super app (codename Kaori), not limited to health. Design must have clean separability between frontend, backend (non-LLM), LLM support, and data model. Support multiple deployment configs: (1) all-local iOS app, (2) home server backend with remote frontends. LLM backend should support both Claude CLI and standard API mode. Data should separate raw from LLM-processed, be extendable for future domains (calendar, todo, diaries). Consider repo splitting: backend as one repo, different frontend repos.

**Outcome:** Major refactor from `health-tracker` (app/) to `kaori` (kaori/). New 4-layer architecture: models/ -> storage/ -> services/ -> api/+web/. Abstract LLM interface (LLMBackend ABC) with CLI and API backends. Database schema splits meals into 3 tables: meals (raw), meal_analyses (LLM results with audit trail), meal_overrides (user corrections). Exercise tracking removed from MVP. Web frontend demoted to "barebone testing UI".

### 2026-03-31 — Remove exercise tracking from MVP

**User intent:** "The exercise seems too simple, we can remove it for now." Exercise tracking added back in Phase 5 with proper structured logging.

**Outcome:** Removed all exercise-related code, DB tables, API endpoints, templates, and nav items.

### 2026-03-31 — Free-form text meals with historical context

**User intent:** Meal input should support free-form text (e.g., "same breakfast as yesterday") with historical context. The system maintains: (1) a compacted summary of meal habits up to date X, (2) actual meals from X to now, (3) current input, (4) user-provided context. These 4 components are fed to the LLM for estimation. Periodic compaction merges (1)+(2) into a new (1).

**Outcome:** Added `meal_habit_summaries` table (versioned, rollback-safe). Text-only and photo+text meals now trigger LLM analysis with historical context. Compaction via `POST /api/meals/compact-history`. Rollback via `POST /api/meals/history-versions/{version}/rollback`.

### 2026-03-31 — Versioned LLM summaries as a project-wide pattern

**User intent:** LLM summarization can corrupt results. Historical summaries must be versioned so rollback is possible. This should be a general design consideration for Kaori whenever LLM compaction is used.

**Outcome:** Established "Versioned LLM Summaries" pattern: append-only rows with `version` + `is_active` flag, full audit trail (`llm_backend`, `model`, `raw_response`). Documented in CLAUDE.md as a reusable pattern for any future LLM-compacted data.

### 2026-04-01 — User profile with personal info and free-form notes

**User intent:** Add a personal status/profile that provides reference context for meals and weights (height, gender, age, activity level, targets). Include a free-form notes field for future LLM use. Profile data should be injected into meal analysis prompts.

**Outcome:** Expanded `user_profile` table with height_cm, gender, birth_date, notes. Added profile_repo, profile_service (with `format_profile_context()`), API/web endpoints. Profile context now included in meal analysis LLM prompts. Migration logic handles existing DBs.

### 2026-04-01 — Reorganize docs into index + individual feature docs

**User intent:** Docs should be shorter individual files with an index for progressive discovery, rather than one large PLAN.md.

**Outcome:** PLAN.md became an index linking to: meals.md, weight.md, profile.md, roadmap.md, patterns.md. Each feature doc covers its own data flow, tables, endpoints, and key files.

### 2026-04-01 — Dynamic nutrition targets, remove activity level

**User intent:** Activity level should be inferred from exercise data later, not manually set. Calorie target should not be a plain number — use per-body-weight protein/carb rates and BMR-based TDEE with a percentage adjustment for personal differences.

**Outcome:** Removed `activity_level`, `target_calories`, `target_protein_g`, `target_deficit_kcal` as stored fields. Added `protein_per_kg` (default 1.6), `carbs_per_kg` (default 3.0), `calorie_adjustment_pct` (default 0). Targets now computed dynamically: BMR via Mifflin-St Jeor, TDEE = BMR * 1.2 (sedentary), adjusted by percentage. Protein/carbs = latest weight * per-kg rate.

### 2026-04-01 — Multiple weight entries per day, date picker for meals/weight

**User intent:** Allow multiple weight logs per day (don't override previous entries). Allow user to specify dates when logging weights and meals (for backfilling). Individual weight entries should be editable and deletable.

**Outcome:** Removed UNIQUE constraint on `body_measurements.date`. Switched from upsert to plain insert. Edit/delete now by `id` instead of by date. Date pickers added to both weight and meal forms. History table shows timestamp for disambiguation. Migration drops old unique index on existing DBs.

### 2026-04-01 — Test mode for safe data development

**User intent:** As the user starts dogfooding the app with real data, they want a clear separation between real and test data. When making data-related changes, develop against test data first (forked from real data). Only migrate real data once features are validated.

**Outcome:** Added `KAORI_TEST_MODE` env var. When enabled, the app uses `data/kaori_test.db` and `data/photos_test/` instead of the real files. A red "TEST MODE" banner appears in the web UI. Fork endpoint (`POST /api/test-mode/fork`) copies real data to test location. Documented as a preferred pattern in CLAUDE.md.

### 2026-04-01 — iOS app as separate repo, start without Apple Dev Account

**User intent:** Build a native iOS client matching all current web UI functionality. Start without a paid Apple Developer Account (free provisioning, 7-day re-signing). The iOS repo should be separate, starting as a frontend-only thin client, with plans to later add iOS-dedicated backend logic (except LLM calls which stay server-side).

**Outcome:** Created `~/Claude/kaori-ios/` as a separate SwiftUI project (iOS 17+). Backend changes: added bearer token auth on `/api/*`, unauthenticated health check at `/api/health`, migrated non-file endpoints (weight, profile, meals PUT) from Form to JSON bodies. iOS app features: Dashboard, Meals (CRUD + photo + AI analysis polling), Weight (CRUD + chart), Profile (view/edit), Settings (server URL/token). Fixed photo mount bug for test mode.

### 2026-04-01 — API endpoints migrated from Form to JSON bodies

**User intent:** Non-file API endpoints should accept JSON bodies instead of form-encoded data for cleaner iOS consumption. Web UI can be freely changed without backward compatibility concerns.

**Outcome:** Changed `POST /api/weight`, `PUT /api/weight/{id}`, `PUT /api/profile`, and `PUT /api/meals/{id}` to accept Pydantic JSON bodies. Web routes (`/weight/`, `/profile/`, `/meals/`) remain unchanged (they use their own form-based handlers). `POST /api/meals` stays multipart (needs file upload).

### 2026-04-01 — Meal reprocessing with rollback

**User intent:** Saved meals should support re-running LLM analysis, especially after updating notes that provide better context. If reprocessing gives bad results, user should be able to rollback to the previous analysis version.

**Outcome:** Added `is_active` flag to `meal_analyses` table (matching the versioned pattern from `meal_habit_summaries`). Reprocessing creates a new analysis row and deactivates the previous one; clears user overrides. Rollback activates any previous version. Notes are now included in LLM prompts. All `MAX(id)` subqueries replaced with `is_active = 1` joins. New endpoints: `POST /api/meals/{id}/reprocess`, `GET /api/meals/{id}/analyses`, `POST /api/meals/{id}/analyses/{aid}/activate`. Meal detail page has "Re-analyze with AI" button and collapsible analysis history.

### 2026-04-01 — Weight training tracking

**User intent:** Track weight training workouts with sets, reps, and weights per exercise. Exercise types should be standard (catalog) or identified from gym machine photos via LLM. Also need a timer with presets for rest/work intervals, to be consumed by the iOS app. Backend + Web UI first, timer is iOS-only frontend feature.

**Outcome:** Added 5 new tables (exercise_types, workouts, workout_exercises, exercise_sets, timer_presets). Seeded 29 standard exercise types. Exercise types can be identified from photos via synchronous LLM call. Workouts support bulk creation with nested exercises + sets. Timer presets store rest/work durations and set count for iOS consumption. Three new API routers, web testing UI with list and detail pages. No changes to existing tables.

### 2026-04-01 — Apple Health compatibility + LLM workout summary + exercise management

**User intent:** Make workout data compatible with Apple Health workouts. Add LLM workout summary to estimate calories at end of workout. Add a settings-style exercise management page for adding custom exercises and identifying machines from photos.

**Outcome:** Added `activity_type`, `duration_minutes`, `calories_burned`, `summary` columns to `workouts` table (via migration). Activity types map to HKWorkoutActivityType enum. Added `POST /api/workouts/{id}/summarize` endpoint that uses LLM to generate a workout summary with calorie estimation based on exercises performed and user's body weight. Added exercise management web page at `/workouts/exercises/manage` with custom exercise creation and photo-based LLM identification. HealthKit stores only aggregate data (calories, duration); Kaori remains source of truth for per-exercise detail. Added `is_enabled` column to `exercise_types` — only enabled exercises appear in workout picker, keeping the selection list manageable. All seeded exercises default to disabled; custom and photo-identified exercises default to enabled. Category icons shown for exercises without photos.

### 2026-04-02 — Notification system (local + LLM daily summary)

**User intent:** Add daily notifications to prompt meal/weight logging. Fixed reminders at configurable times (9am breakfast+weight, 1pm lunch, 8pm dinner). LLM-generated daily summary at 9:30pm that feeds today's meals/macros/streak into the LLM for a personalized notification. Weekly weight trend on Sundays. Each notification type individually toggleable with custom time picker.

**Outcome:** Backend: added `GET /api/summary/daily` (LLM-generated), `GET /api/summary/weekly-weight` (arithmetic), `GET /api/summary/streak`. iOS: local notifications via `UNUserNotificationCenter`, `BGAppRefreshTask` for pre-fetching LLM summary before notification fires (falls back to generic text if backend unreachable). Full notification settings UI with master toggle, per-type toggles, and time pickers. No APNs needed.

### 2026-04-01 — Add Codex CLI (OpenAI/ChatGPT) LLM backend

**User intent:** Explore using OpenAI's Codex CLI (`codex exec`) as an alternative LLM backend for meal analysis, alongside existing Claude backends. Start with Codex CLI only (uses ChatGPT subscription, no API key needed). Backend selection should be per-request from the user profile's `llm_mode` field, not just env var at startup. Test in web UI first, iOS settings toggle deferred.

**Outcome:** Added `CodexCLIBackend` in `kaori/llm/codex_cli.py` — subprocess to `codex exec --json --ephemeral --skip-git-repo-check`, parses NDJSON output. Updated factory `get_llm_backend()` to accept optional `mode` parameter; services read `llm_mode` from profile and pass it. Updated DB CHECK constraint with migration. Exposed `llm_mode` in profile API (`ProfileUpdate`) and web UI (dropdown selector on profile page). Three backends: `claude_cli`, `claude_api`, `codex_cli`.

### 2026-04-02 — Feed-based UI revamp (pulled ahead from Phase 6)

**User intent:** Transform the iOS app from a 4-tab dashboard layout into a feed-based experience. Three tabs: (1) Home feed — multi-day infinite scroll timeline of all daily entries (meals, weight, workouts, AI summaries) as rich cards, with an expanding FAB for quick adding; (2) Management hub — houses all current views (meals, weight, gym, profile, settings) as a menu list; (3) Tools — rest timer entry point, extensible. Data merging is client-side (no new backend endpoints). This redesign is pulled ahead of Phase 5 (diary/todo) since the feed architecture naturally accommodates future data types.

**Outcome:** Design spec finalized. Implementation in 4 phases: A) Tab restructure, B) Feed foundation + FeedStore, C) Rich feed cards, D) Expanding FAB. All existing views preserved and accessible from Tab 2.

### 2026-04-03 — Financial accounts and portfolio tracking

**User intent:** Track brokerage holdings across Schwab, Fidelity, and Moomoo accounts. Import holdings via screenshot or PDF (LLM extracts positions). Show daily portfolio change card on the feed (live for today, frozen snapshots for past days). Manage accounts under More > Data > Finance. Design should be general enough to later add credit card (Citi/Chase/Amex) and bank account tracking. Use direct broker APIs (Schwab, Moomoo) where free, Plaid as future option for banks/cards, screenshot/PDF + LLM as universal fallback.

**Outcome:** Implemented general `financial_accounts` table supporting brokerage/credit_card/bank types. Backend: 6 new tables, portfolio service with yfinance price caching, LLM holdings extraction from multi-photo screenshots, daily snapshot system. iOS: portfolio feed card with background loading and 60s auto-refresh, account management views, multi-photo import with editable review. Broker API connectors (Schwab, Moomoo) stubbed with `AccountConnector` ABC for future implementation.

### 2026-04-04 — Feed-first, card-first architecture refactor

**User intent:** Refactor the app into a "feed-first, card-first" architecture. Every user-facing feature should be a card type — the atomic unit of the app. Each card has: feed rendering, creation via "+", data browsing in More > Data, per-card settings with enable/disable toggle. The goal is a standard module pattern so adding new card types doesn't repeat bugs or require editing 5+ files. Daily summary should be addable via "+" (in addition to auto-generation). Nutrition card should have its own enable/disable toggle. Finance account setup should be parallel to Profile (personal data), not in Settings (app behavior). Backend should provide both unified `/api/feed` endpoint and keep existing per-domain endpoints.

**Outcome:** Backend: added `card_preferences` table, `CardType` enum, unified `GET /api/feed` endpoint aggregating all card types, `GET/PUT /api/feed/card-preferences` endpoints. iOS: introduced `CardModule` protocol, `CardRegistry` (injected via Environment), `FeedStore` (replaces inline feed state in FeedView), `CardPreferenceStore`. Created 6 card modules (Meal, Weight, Workout, Portfolio, Nutrition, Summary). Refactored FeedView to use FeedStore and CardRegistry, ContentView "+" menu to iterate `CardRegistry.addableModules`, MoreView Data section to iterate `CardRegistry.dataModules`, SettingsView to include Card Modules settings. Added Summary creation via "+". Updated both CLAUDE.md files with Card-First Architecture conventions.

### 2026-04-04 — Add Post and Reminder/TODO card types

**User intent:** Expand Kaori beyond health/finance into personal productivity. Two new card types: (1) Post — personal microblog for quick thoughts, like a private Twitter. (2) Reminder/TODO — date-targeted items that stay on top of today's feed as reminders or checkable TODOs that can be marked done or pushed to a later date.

**Outcome:** Backend: added `posts` and `reminders` tables, full 4-layer implementation (models, storage, services, API) for both. Post is pure CRUD with free-form content. Reminder has two subtypes (`reminder`/`todo`), overdue surfacing (today's feed shows all past-due undone items via query logic), push-to-later-date (updates `due_date`, preserves `original_date`), mark-done, and priority (0/1/2). Reminder card pinned at `pin_order=3` (above chronological items). Feed loaders registered in `CARD_LOADERS`. Migration added to seed new card preferences in existing databases.

### 2026-04-04 — Multi-photo support for meals and posts

**User intent:** Allow attaching multiple photos (up to 5) when logging meals and creating posts. Meal photos should all be sent to the LLM for nutrition analysis in a single request. Posts are display-only (no LLM analysis).

**Outcome:** Added `photo_paths TEXT` column (JSON array) to both `meals` and `posts` tables alongside existing `photo_path` (backward compat). Backend API accepts `photos: list[UploadFile]` multipart field. Meal LLM analysis uses `analyze_images()` for multi-photo meals. Codex CLI backend updated to support multi-image via multiple `-i` flags (was previously raising NotSupported). iOS: new `MultiPhotoPickerButton` (camera + library, up to 5, horizontal scroll preview). Feed cards and detail views show horizontal scroll gallery for multiple photos, single scaledToFit for one.

### 2026-04-04 — HealthKit activity type mapping expansion

**User intent:** Stair climbing workouts from Apple Health were being imported as "activity.other". Fix the mapping and add all missing types.

**Outcome:** Added 7 missing activity types (stairClimbing, elliptical, rowing, flexibility, mixedCardio, dance, jumpRope) to both `activityTypeString(from:)` and `workoutActivityType(from:)` in HealthKitManager.swift. Updated backend `ACTIVITY_TYPES` list to include all 19 types. Also added delete swipe action to Summary card (was regenerate-only), and changed weight analytics chart to use minimum value when multiple entries exist per day.

### 2026-04-05 — MCP server for read-only data access

**User intent:** Expose Kaori data to Claude Code and kaori-agent via MCP (Model Context Protocol) instead of building custom tools per-client. Read-only only — no writes. Agent should focus on high-level tasks (querying life data), not low-level coding tools.

**Outcome:** Created `kaori/mcp_server.py` with 15 read-only tools wrapping GET endpoints (feed, meals, weight, profile, portfolio, workouts, summaries, reminders, exercise types). Uses `fastmcp` + `httpx`. Auth via `KAORI_API_TOKEN` env var — no secrets in code. Added `[mcp]` optional dependency group and `kaori-mcp` entry point.

### 2026-04-05 — Agent session REST API + SSE chat endpoint

**User intent:** Expose agent session data via REST API and add an SSE streaming chat endpoint so the iOS app can have a Chat tab for AI agent conversations. The agent engine (agentic turn loop with tool_use) should run server-side on the kaori backend, not on the iOS client.

**Outcome:** Implemented full agent integration: 5 storage repos, service layer, 14 REST endpoints (sessions/memory/prompts CRUD + SSE chat), new `AgentLLMBackend` abstraction (Anthropic + OpenAI-compatible backends), agentic turn loop ported from kaori-agent, 9 server-side tools calling kaori services directly. Added `AGENT_SESSION` to CardType enum. Chat endpoint streams events (thinking/text/tool_use/done) via SSE.

### 2026-04-07 — Bug fix: Portfolio card should freeze at market close

**User intent:** After market close, the portfolio feed card should show frozen end-of-day values instead of continuing to fetch/display stale or zeroed-out data. The card was showing $0 day change after hours due to a price substitution bug.

**Outcome:** Two fixes: (1) Removed `previous_close` price substitution in `stock_price_service._fetch_from_yfinance()` — always use `last_price` so day-change calculations remain correct after hours. (2) Changed `portfolio_service.get_portfolio_summary()` to auto-create and serve a snapshot on first request after market close, freezing the card at close values for the rest of the day.

### 2026-04-11 — Use Kaori personality for summaries + nightly heartbeat

**User intent:** (1) Daily/weekly summary card generation should use the Kaori assistant's personality prompt (from DB or `~/.kaori-agent/personality.md`) instead of the generic "personal health assistant" persona. (2) Add a scheduled nightly heartbeat at 9pm that generates a personal post about the user's day — distinct from a health summary. The nightly post should read like a diary entry, not a report with sections and bullet points.

**Outcome:** (1) Daily/weekly detail summaries now go through `agent_chat_service.chat()` — the agent uses its personality prompt + tools to query data and write the report. No more manual context building or personality injection into one-shot prompts. The notification-level summary (`get_daily_summary`, 140 chars) stays as a simple one-shot LLM call. Extracted `get_personality_text()` helper in `agent_service.py` for shared personality resolution. (2) Added `schedule_enabled`, `schedule_time`, `nightly_prompt_template`, `last_nightly_date` columns to `heartbeat_config`. Background asyncio loop in `main.py` checks once per minute; when current time >= `schedule_time` and today's nightly hasn't run, triggers `trigger_nightly()`. Nightly prompt produces diary-style posts, not structured reports. API: `POST /api/heartbeat/trigger-nightly` for manual testing.

### 2026-04-11 — Daily/weekly summaries default to Chinese

**User intent:** Daily and weekly detail summary prompts in `summary_service.py` should instruct the agent to respond in Chinese rather than English.

**Outcome:** `generate_daily_detail` and `generate_weekly_detail` now hardcode "Respond in Chinese (中文)." in the agent message and default the `language` param to `"zh"`. Section headers in the prompt use bilingual labels (e.g., `营养 Nutrition`, `体重趋势 Weight Trend`) to keep markdown structure recognizable while signaling Chinese output.

### 2026-04-11 — Web search for iOS chat via kaori-agent adapter

**User intent:** iOS chat should have web search. Avoid duplicating the tool across the two projects.

**Outcome:** Installed `kaori-agent` (editable) into kaori's venv. `kaori/services/agent_tools.py` imports `WebSearchTool` from `kaori_agent.tools.web_search` and wraps it in a 10-line adapter subclass of kaori's own `BaseTool` — schema/description/execute logic exist in one place (kaori-agent). Added `python-dotenv` dep and `load_dotenv()` at the top of `kaori/main.py` so the server picks up `TAVILY_API_KEY` from `.env`. Symlinked `~/Claude/kaori/.env` → `~/Claude/kaori-agent/.env` so both projects share one secrets file. Tool count in default registry went 22 → 23.

### 2026-05-10 — Extend vault sync to meals/body/workouts (md + csv)

**User intent:** The existing vault sync mirrors posts/summaries/chats only. Extend it to cover the personal data tables (meals, body_measurements, workouts) so the Obsidian vault becomes both a Google-Drive backup and an LLM-readable knowledge base. Two output forms per domain: per-day/per-entity Markdown for human/LLM browsing, and flat CSV snapshots under `data/` for tools (e.g. the `/cosplay-progress` skill) that prefer tables. Override values must win over LLM analysis. Stay gated by `KAORI_VAULT_SYNC_ENABLED` / disabled in `KAORI_TEST_MODE`. Out of scope: financial/agent/reminder/heartbeat/weather tables.

**Outcome:** Added to `vault_sync_service.py`: `sync_meal_day(date)`, `sync_body_month(date)`, `sync_workout(id, op)`, plus `trigger_*` wrappers and corresponding `_render_*` / `_regen_*_csv` helpers. New layout under `<vault>/<sync_root>/`: `meals/YYYY-MM-DD.md`, `body/YYYY-MM.md`, `workouts/YYYY-MM-DD-workout-<id>.md`, and `data/{meals,body_measurements,workouts}.csv`. CSVs are regenerated in full on every sync (small enough). Wired triggers into `meal_service.create/update/delete/run_analysis/reprocess_meal/rollback_analysis`, `weight_service.log/update/delete/bulk_import`, and `workout_service.create_workout/update_workout/delete_workout/summarize_workout` plus the exercise/set helpers (extended their signatures with optional `workout_id`, passed through from the workout API which has `workout_id` in URL). `meal_service.update` fetches the pre-update date so a date change triggers sync for both old and new days. `sync_workout` clears stale-date files matching `*-workout-<id>.md` before writing the current path. `backfill_all()` gained `meals`/`body`/`workouts` flags with per-domain orphan removal. Verified end-to-end on the live DB: counts match across DB ↔ MD ↔ CSV (meals 161/161/161, body 227/227/227, workouts 28/28/28); live POST + DELETE through the API updates the vault within ~1s; `KAORI_TEST_MODE=1` confirms no vault writes.

### 2026-05-24 — Expand weight card into a measurement card (add waist-at-navel)

**User intent:** Treat the weight card as a general body-measurement card. Add a second measurement: waist circumference measured at the navel. Reuse the existing weight card UI by adding more optional rows; the only validation is that at least one row is non-empty. Analytics page is out of scope for this change.

**Outcome:** Backend: `body_measurements` table now has a nullable `waist_at_navel_cm` column (migration added; existing index/unique-drop migration extended to add the column on existing DBs). `weight_repo` create/update accept both measurements; `weight_service.log/update` thread the new field through and trigger the same vault-month sync. `WeightCreate`/`WeightUpdate` Pydantic models share a base validator that enforces "at least one of weight_kg / waist_at_navel_cm". `weight_service.get_trends` derives latest/avg7d/delta_week from rows that have a weight value (waist-only rows still appear in `weights_asc` for iOS). Vault sync: body markdown table and `body_measurements.csv` gained a `waist_at_navel_cm` column. Web form route updated to accept both as optional. Tests cover waist-only insert, both-measurement insert, missing-both rejection (422), and waist-only update. All 177 backend tests pass. Card type identifier stays "weight" to avoid a card-preferences migration; only the displayed title changed (en: "Measurement", zh: "身体测量").

### 2026-05-25 — Drop web UI for weight; convert weight PUT to patch semantics

**User intent:** Address the code-review findings on the measurement card expansion. The user approved dropping the barebone web UI for weight if it simplifies things — the iOS app is the only real frontend. Also fix the silent-data-loss and crash bugs the review surfaced.

**Outcome:**
- Removed `kaori/web/weight.py`, `templates/weight.html`, the weight section + chart from `templates/dashboard.html`, the weight nav item from `templates/base.html`, and weight imports from `web/dashboard.py` and `web/router.py`. The web UI no longer has any weight surface.
- `summary_service.get_weekly_weight_summary` now filters `weight_kg is not None` before sum/avg/delta math — no more `TypeError` when a waist-only entry exists in the last 7 days.
- `profile_service.get_profile` walks the most recent 30 body_measurements rows and picks the first with a non-null `weight_kg` for BMR/TDEE; a waist-only most-recent row no longer wipes nutrition targets.
- Converted `weight_repo.update` and `weight_service.update` to patch semantics: they now accept a `fields: dict` and build a dynamic `UPDATE … SET <only provided columns>` statement. Empty dict is a no-op. The API handler uses `WeightUpdate.model_dump(exclude_unset=True)` so only fields the client actually sent reach the DB; the PUT response echoes the post-update row. Dropped the at-least-one validator from `WeightUpdate` so notes-only updates are allowed (it stays on `WeightCreate`).
- Deleted `kaori/models/weight.py` and its re-export — the only `WeightCreate` is now the API-local one with the validator, removing the duplicate-name footgun.
- Tests: added `test_update_is_patch_not_replace`, `test_update_notes_only`, and rewrote `test_update_waist_only` (now `test_update_waist_on_weight_only_entry`) to assert the surviving weight after a partial waist update. All 179 backend tests pass.

### 2026-06-25 — Offline-first iOS: local-first cache + outbox (NOT a second backend)

**User intent:** Wants to keep using the app when the laptop backend is offline. Proposed a two-tier system: use laptop backend when online; when offline write to an iOS-side backend; push iOS→laptop on reconnect; iOS holds a full data copy for fast caching. Asked to plan very carefully to preserve all current use cases, with backward compatibility and data safety paramount. LLM calls may stay deferred to when the laptop is online.

**Outcome:** Produced a detailed plan (`docs/plans/ios-offline-sync-plan.html`). Recommended **Option A — make iOS a local-first SQLite cache + durable write "outbox", keeping the laptop as the single source of truth for all business logic, LLM, and vault sync** — rather than reimplementing the Python backend in Swift (rejected: permanent two-codebase parity/drift risk, contradicts data-safety goal). Key enabling work is additive server-side change-tracking: add `sync_uuid` (stable cross-device identity to solve the auto-increment-PK problem), ensure `updated_at` everywhere, a `sync_deletions` tombstone table (hard deletes are otherwise invisible), and two new endpoints `POST /api/sync/push` + `GET /api/sync/changes?since=`. Vault stays one-way/downstream (already hours-tolerant). Phased, reversible rollout: Phase 0 additive metadata (no behavior change) → Phase 1 read replica → Phase 2 outbox for simple cards (weight/posts/reminders) → Phase 3 meals+photos+nested workouts → Phase 4 polish. Awaiting user confirmation of Option A and 4 open decisions before writing the Phase 0 spec.

### 2026-06-25 — Option A confirmed for offline-first iOS

**User intent:** After reviewing the plan, user confirmed Option A (local-first iOS cache + durable outbox, laptop remains single source of truth) over a Swift reimplementation. Also added an explicit constraint: the solution must not drain phone battery.

**Outcome:** Proceeding with Option A. Battery budget captured as a first-class constraint (§11 of the plan: passive `NWPathMonitor` reachability, no polling, no persistent socket, OS-budgeted `BGTaskScheduler` background sync, local reads from the on-device mirror — net lighter than today). Recommended 5-phase rollout: Phase 0 server sync foundation (additive, reversible, decision-free) → Phase 1 sync endpoints + pull-only read replica → Phase 2 outbox + offline writes for simple cards (weight/reminders/posts) → Phase 3 heavy flows (meals+photos, nested workouts) → Phase 4 polish/hardening. Phase 0 can start immediately against a forked test DB with no iOS-side decisions blocking it.

### 2026-06-25 — Phase 0 implemented & validated (against forked test DB)

**User intent:** Start Phase 0 of the offline-first sync rollout against a forked test database, keeping data safety paramount.

**Outcome:** Implemented Phase 0 entirely at the DB layer in `kaori/database.py` (`_migrate_sync_metadata`, run last in `init_db`) — no repo/service code changed, so app behavior is unchanged. Adds `sync_uuid` (UUID, unique-indexed) + `updated_at` to all 27 syncable tables (caches `stock_prices`/`weather_cache`/`portfolio_snapshots` excluded), backfills existing rows, creates the `sync_deletions` tombstone table, and installs 3 triggers per table (assign UUID on insert, bump `updated_at` on update unless caller set it, write a tombstone on delete). Validated on the forked test DB: all rows backfilled with unique UUIDs (81 triggers), migration idempotent on re-run, and live API smoke test (create/update/delete post + feed/meals reads) confirmed auto-UUID, updated_at bump, tombstones, and that `sync_uuid` does NOT leak into API responses. Full pytest suite shows identical results with vs without the migration (58 pre-existing harness/auth failures, 121 pass) — proving zero behavior change. **Production `kaori.db` deliberately left untouched**; migration auto-applies on next launchd restart (take a backup first per the Phase 0 gate). Cascade deletes were confirmed to fire child triggers, so tombstones are complete even for `ON DELETE CASCADE`.

### 2026-06-25 — Phase 1 decisions: GRDB + Tailscale-only

**User intent:** Proceed to Phase 1 (read-replica) of offline-first sync. Chose the iOS DB library and reachability model.

**Outcome:** iOS local mirror will use **GRDB** (built-in ValueObservation → SwiftUI auto-refresh when the mirror updates). Reachability is **Tailscale-only** (single base URL; online = Tailscale path reachable) — simplest, works anywhere, no LAN endpoint-selection logic. Phase 1 scope: server `GET /api/sync/changes?since=<cursor>` (incremental upserts + tombstones since a cursor) is decision-free and being built first against the forked test DB; iOS GRDB read-replica + SyncEngine (pull-only, still writes through live API) follows. No offline writes until Phase 2.
