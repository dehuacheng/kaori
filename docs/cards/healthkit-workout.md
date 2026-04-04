# Card: HealthKit Workout (Imported)

## Identity

| Field | Value |
|-------|-------|
| Card Type | `healthkit_workout` |
| Icon | `figure.run` |
| Accent Color | Green |
| Module | `HealthKitWorkoutCardModule.swift` |

## Purpose

Read-only display of workouts imported from Apple Health (walking, running, cycling, etc.). Shows duration, distance, calories, and pace. Distinct from manual gym workouts — no exercise/set editing.

## Feed Behavior

| Behavior | Value |
|----------|-------|
| Manual creation ("+") | No (auto-imported from HealthKit) |
| Tap → detail | Yes → `ImportedWorkoutDetailView` |
| Swipe actions | Delete |
| Sort priority | 10 (chronological) |
| Pinned | No |

## Data (More > Data)

None (shares workout list with manual workouts in `WorkoutListView`).

## Settings

None. Apple Health import is in Settings > Apple Health.

## Backend

### Tables

Same `workouts` table as manual workouts, but with `source = 'healthkit'`. The `source` column distinguishes imported from manual workouts.

### API

Same endpoints as manual workouts. The `source` field is set to `"healthkit"` on creation.

### Feed Loader

Shared `_load_workouts` in `feed_service.py` — checks `source` field and tags items as `CardType.HEALTHKIT_WORKOUT`.

## Key Backend Files

- Same as `workout` — `storage/workout_repo.py`, `services/workout_service.py`
- Distinguished by `source = 'healthkit'` column in `workouts` table

## Design Note

Split from the manual `workout` card type to avoid conditional logic bugs. The backend stores both in the same `workouts` table with a `source` field (`'manual'` vs `'healthkit'`). The feed loader checks `source` and tags items with the appropriate `CardType`. Frontend treats them as two independent card modules with different detail views and behavior.
