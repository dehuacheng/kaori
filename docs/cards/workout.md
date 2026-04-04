# Card: Workout (Manual)

## Identity

| Field | Value |
|-------|-------|
| Card Type | `workout` |
| Icon | `dumbbell.fill` |
| Accent Color | Orange |
| Module | `WorkoutCardModule.swift` |

## Purpose

Manual gym workout logging with structured exercises, sets, reps, and weights. LLM-powered workout summaries with calorie estimation and personal trainer analysis.

## Feed Behavior

| Behavior | Value |
|----------|-------|
| Manual creation ("+") | Yes (full-screen cover) |
| Tap → detail | Yes → `WorkoutDetailView` |
| Swipe actions | Delete |
| Sort priority | 10 (chronological) |
| Pinned | No |

**Special creation flow:** Workout creation opens a full-screen cover (not sheet). A blank workout is created immediately via API. If the user dismisses without adding exercises, the workout is auto-deleted.

## Data (More > Data)

`WorkoutListView` — browse workouts by date. Tap to view/edit exercises and sets.

## Settings (per-card)

`ExerciseManageView` — manage custom exercise types, identify gym machines from photos via LLM.

## Backend

### Tables

| Table | Purpose |
|-------|---------|
| `workouts` | Workout sessions (date, activity_type, duration, calories, source='manual') |
| `workout_exercises` | Exercises within a workout (references exercise_type_id) |
| `exercise_sets` | Individual sets (reps, weight_kg, duration_seconds) |
| `exercise_types` | Exercise catalog (standard library + user-created) |
| `workout_analyses` | LLM-generated analysis (metrics, trainer notes, recommendations) |

### API Endpoints

- `GET /api/workouts?date=YYYY-MM-DD` — list with exercise count
- `POST /api/workouts` — create (optionally with nested exercises/sets)
- `GET /api/workouts/{id}` — full detail tree (exercises + sets)
- `PUT /api/workouts/{id}` — update
- `DELETE /api/workouts/{id}` — delete
- `POST /api/workouts/{id}/summarize` — LLM analysis
- `POST /api/workouts/{id}/exercises` — add exercise
- CRUD for exercises and sets (nested endpoints)

### Feed Loader

Shared `_load_workouts` in `feed_service.py` — routes to `workout` or `healthkit_workout` based on `source` field.

## Key Backend Files

- `models/workout.py` — WorkoutCreate, WorkoutUpdate, WorkoutSummary
- `storage/workout_repo.py` — workout + exercise + set CRUD
- `services/workout_service.py` — CRUD + LLM summarization
- `llm/prompts.py` — `build_workout_summary_prompt()`
