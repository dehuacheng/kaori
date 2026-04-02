# Workout Tracking

**Status**: 0.2.0 — Apple Health compatibility + LLM workout summary

## Overview

Track weight training workouts: exercises with sets, reps, and weights. Exercise types can be standard (seeded catalog of ~29 exercises), user-created, or identified from a photo of a gym machine via LLM.

Workout data is Apple Health compatible — stores `activity_type`, `duration_minutes`, and `calories_burned` for HealthKit sync by the iOS client.

Timer presets store rest/work interval configurations for the iOS client.

## Data Model

### `exercise_types` — Exercise catalog
- `name` (UNIQUE), `category` (chest/back/legs/shoulders/arms/core/cardio/full_body), `photo_path`, `notes`
- `is_standard`: 1 = seeded (protected from deletion), 0 = user-created
- `is_enabled`: 1 = appears in workout exercise picker, 0 = hidden. Seeded types default to disabled; custom/identified types default to enabled. Toggled via management page or API.

### `workouts` — Sessions (Apple Health compatible)
- `date` (YYYY-MM-DD), `notes`, `activity_type` (HKWorkoutActivityType string), `duration_minutes`, `calories_burned`, `summary`
- `activity_type` defaults to `traditionalStrengthTraining`; also supports `functionalStrengthTraining`, `highIntensityIntervalTraining`, `coreTraining`, `flexibility`, `mixedCardio`, `other`
- `calories_burned` and `summary` are populated by LLM workout summarization
- Multiple workouts per day allowed

### `workout_exercises` — Exercises within a workout
- Links `workout_id` → `exercise_type_id` with `order_index`
- CASCADE delete from parent workout

### `exercise_sets` — Individual sets
- `set_number`, `reps` (nullable), `weight_kg` (nullable), `duration_seconds` (nullable)
- All nullable to support: weighted (reps + weight), bodyweight (reps only), timed (duration only)

### `timer_presets` — Timer configurations
- `name`, `rest_seconds`, `work_seconds`, `sets`
- `work_seconds = 0` means manual advance (strength); `> 0` means timed interval (HIIT)

## Endpoints

### Exercise Types (`/api/exercise-types`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List all (optional `?category=`) |
| POST | `/` | Create custom type |
| POST | `/identify` | Identify from photo (multipart) |
| GET | `/{id}` | Get single type |
| PUT | `/{id}` | Update type |
| POST | `/{id}/enable` | Enable exercise for workout picker |
| POST | `/{id}/disable` | Disable exercise from workout picker |
| DELETE | `/{id}` | Delete (rejects standard or referenced) |

### Workouts (`/api/workouts`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List (`?date=`, `?start_date=`, `?end_date=`) |
| POST | `/` | Create (supports nested exercises + sets, activity_type, duration_minutes) |
| GET | `/{id}` | Get with full exercise/set tree |
| PUT | `/{id}` | Update metadata |
| DELETE | `/{id}` | Delete (cascades) |
| POST | `/{id}/summarize` | LLM-generated summary + calorie estimation |
| POST | `/{id}/exercises` | Add exercise |
| PUT | `/{id}/exercises/{eid}` | Update exercise |
| DELETE | `/{id}/exercises/{eid}` | Remove exercise |
| POST | `/{id}/exercises/{eid}/sets` | Add set |
| PUT | `/{id}/exercises/{eid}/sets/{sid}` | Update set |
| DELETE | `/{id}/exercises/{eid}/sets/{sid}` | Delete set |

### Timer Presets (`/api/timer-presets`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List all |
| POST | `/` | Create |
| GET | `/{id}` | Get single |
| PUT | `/{id}` | Update |
| DELETE | `/{id}` | Delete |

## Web UI
- `/workouts/` — List workouts for a date with prev/next navigation
- `/workouts/{id}` — Workout detail: exercises, sets, summary, "Summarize with AI" button
- `/workouts/exercises/manage` — Exercise type management: list with category icons, enable/disable toggle, add custom, identify from photo, delete custom types

## LLM Integration

### Exercise identification
- `POST /api/exercise-types/identify` sends a photo to LLM
- Synchronous (not background task) — one-shot identification
- Returns existing exercise type if name matches (case-insensitive), otherwise creates new one
- Prompt: `build_exercise_identification_prompt()` in `kaori/llm/prompts.py`

### Workout summary
- `POST /api/workouts/{id}/summarize` calls LLM to analyze completed workout
- Uses user's body weight from profile for calorie estimation
- Returns: total_sets, total_reps, total_volume_kg, estimated_calories, muscle_groups_worked, summary, intensity
- Stores `calories_burned` and `summary` on the workout record
- Prompt: `build_workout_summary_prompt()` in `kaori/llm/prompts.py`

## Apple Health Compatibility
The workout data model maps to Apple HealthKit's `HKWorkout`:
- `activity_type` → `HKWorkoutActivityType` (e.g., `.traditionalStrengthTraining`)
- `duration_minutes` → workout duration
- `calories_burned` → `totalEnergyBurned`
- `date` → workout date

HealthKit does NOT store per-exercise data (sets/reps/weight). Kaori is the source of truth for detailed exercise data; the iOS client syncs aggregate metrics to HealthKit.

## Key Files
| File | Purpose |
|------|---------|
| `kaori/models/workout.py` | Pydantic models (incl. WorkoutSummary, ACTIVITY_TYPES) |
| `kaori/storage/exercise_type_repo.py` | Exercise type CRUD |
| `kaori/storage/workout_repo.py` | Workout + exercises + sets CRUD |
| `kaori/storage/timer_preset_repo.py` | Timer preset CRUD |
| `kaori/services/workout_service.py` | Business logic + LLM identification + summary |
| `kaori/api/exercise_types.py` | Exercise type API |
| `kaori/api/workout.py` | Workout API (incl. summarize endpoint) |
| `kaori/api/timer_presets.py` | Timer preset API |
| `kaori/web/workout.py` | Web testing UI (workouts + exercise management) |
| `kaori/templates/workouts.html` | Workout list template |
| `kaori/templates/workout_detail.html` | Workout detail template |
| `kaori/templates/exercises.html` | Exercise management template |
