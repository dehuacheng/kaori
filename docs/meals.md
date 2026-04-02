# Meals Feature

**Status**: In Progress (Phase 1 MVP)

## Overview

Log meals via photo, free-form text, or both. LLM estimates calories/macros with historical context. User can override any estimate.

## Data Flow

1. User submits meal (text description, photo, or both)
2. Raw input stored in `meals` table
3. Background task fires LLM analysis with context:
   - User profile (height, gender, age, targets, notes)
   - Meal habit summary (compacted history)
   - Recent meals (last 50 since compaction cutoff)
   - Current input (description + photo)
4. LLM result stored in `meal_analyses` (with audit: backend, model, raw_response)
5. User can override via `meal_overrides` (takes precedence)

## Text Input with Historical Context

Supports free-form text like "same breakfast as yesterday" or "a bowl of ramen from the place near my office". The LLM context includes:

| Component | Source | Purpose |
|-----------|--------|---------|
| User profile | `user_profile` table | Calorie targets, personal stats |
| Habit summary | `meal_habit_summaries` (active) | Compacted patterns up to cutoff date |
| Recent meals | `meals` + joins (after cutoff) | Detailed recent history for reference matching |
| Current input | Form submission | What the user just typed/uploaded |

## Meal Habit Compaction

Periodic summarization of meal history into a compact profile:
- `POST /api/meals/compact-history` — compacts meals older than 7 days
- Creates versioned summary (append-only, rollback-safe — see [patterns.md](patterns.md))
- `GET /api/meals/history-versions` — list all versions
- `POST /api/meals/history-versions/{v}/rollback` — reactivate a previous version

## Reprocessing & Rollback

Re-run LLM analysis on an existing meal — useful after updating notes or when results are unsatisfactory.

**How it works:**
1. User clicks "Re-analyze with AI" on meal detail page
2. User overrides are cleared (user is requesting fresh LLM estimate)
3. A new `meal_analyses` row is created (`is_active=1`), previous row deactivated
4. Background analysis runs with current description + notes + photo
5. If results are bad, user can rollback to any previous analysis version

**Analysis versioning:** Each meal can have multiple analyses. The `is_active` flag determines which one is used (same pattern as `meal_habit_summaries`). Rollback = deactivate current, activate target.

**Notes in prompts:** The `notes` field is included in both text and photo analysis prompts, providing additional context like "small portion" or "dressing on the side".

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/meals/{id}/reprocess` | Trigger re-analysis |
| GET | `/api/meals/{id}/analyses` | List all analysis versions |
| POST | `/api/meals/{id}/analyses/{aid}/activate` | Rollback to version |

## Tables

- `meals` — raw user input (date, meal_type, description, photo_path, notes)
- `meal_analyses` — LLM results (calories, macros, confidence, audit trail, `is_active` flag for versioning)
- `meal_overrides` — user corrections (takes precedence in COALESCE join)
- `meal_habit_summaries` — versioned compacted history

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/meals` | List meals for date |
| POST | `/api/meals` | Create meal (text/photo/both) |
| GET | `/api/meals/{id}` | Get single meal |
| PUT | `/api/meals/{id}` | Update meal |
| DELETE | `/api/meals/{id}` | Delete meal |
| POST | `/api/meals/{id}/reprocess` | Re-run LLM analysis |
| GET | `/api/meals/{id}/analyses` | List analysis versions |
| POST | `/api/meals/{id}/analyses/{aid}/activate` | Activate a specific version |
| POST | `/api/meals/compact-history` | Run compaction |
| GET | `/api/meals/history-versions` | List summary versions |
| POST | `/api/meals/history-versions/{v}/rollback` | Rollback summary |

## Key Files

- `kaori/models/meal.py` — MealCreate, MealUpdate, FoodAnalysis
- `kaori/storage/meal_repo.py` — meal CRUD with COALESCE join
- `kaori/storage/meal_analysis_repo.py` — analysis lifecycle
- `kaori/storage/meal_override_repo.py` — user corrections
- `kaori/storage/meal_history_repo.py` — versioned summaries
- `kaori/services/meal_service.py` — orchestration, context building, compaction
- `kaori/llm/prompts.py` — prompt builders (text, photo, compaction)
