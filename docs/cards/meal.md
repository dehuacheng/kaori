# Card: Meal

## Identity

| Field | Value |
|-------|-------|
| Card Type | `meal` |
| Icon | `fork.knife` |
| Accent Color | Orange |
| Module | `MealCardModule.swift` |

## Purpose

Log meals via one or more photos, free-form text, or both. LLM estimates nutrition (calories, protein, carbs, fat) with historical context — multiple photos are analyzed together in a single request. User can override any estimate.

## Feed Behavior

| Behavior | Value |
|----------|-------|
| Manual creation ("+") | Yes (sheet) |
| Tap → detail | Yes → `MealDetailView` |
| Swipe actions | Delete |
| Sort priority | 10 (chronological) |
| Pinned | No |

## Data (More > Data)

`MealListView` — browse meals by date. Tap to view/edit. Swipe to delete.

## Settings

None (card-level). Nutrition targets are in Profile.

## Backend

### Tables

| Table | Purpose |
|-------|---------|
| `meals` | Raw meal data (date, meal_type, description, photo_path, photo_paths, notes) |
| `meal_analyses` | LLM-generated nutrition (versioned, append-only) |
| `meal_overrides` | User manual corrections (takes precedence) |
| `meal_habit_summaries` | Compacted meal history for LLM context |

### API Endpoints

- `GET /api/meals?date=YYYY-MM-DD` — list meals + totals for a date
- `POST /api/meals` — create (multipart: photos + fields; supports single `photo` or multiple `photos`)
- `GET /api/meals/{id}` — detail
- `PUT /api/meals/{id}` — update
- `DELETE /api/meals/{id}` — delete
- `POST /api/meals/{id}/reprocess` — re-run LLM analysis
- `GET /api/meals/{id}/analyses` — analysis version history
- `POST /api/meals/{id}/analyses/{aid}/activate` — rollback to version

### Feed Loader

`_load_meals` in `feed_service.py` — fetches meals via `meal_service.list_by_date()`.

## Key Backend Files

- `models/meal.py` — MealCreate, MealUpdate, FoodAnalysis
- `storage/meal_repo.py`, `meal_analysis_repo.py`, `meal_override_repo.py`, `meal_history_repo.py`
- `services/meal_service.py` — CRUD + LLM analysis orchestration
- `llm/prompts.py` — `build_photo_analysis_prompt()`, `build_text_analysis_prompt()`
