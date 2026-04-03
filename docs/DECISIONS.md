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
