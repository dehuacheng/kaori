# Card: Weight

## Identity

| Field | Value |
|-------|-------|
| Card Type | `weight` |
| Icon | `scalemass.fill` |
| Accent Color | Cyan |
| Module | `WeightCardModule.swift` |

## Purpose

Track body weight over time. Multiple entries per day allowed. Supports kg/lb unit preference. Weight data feeds BMR/TDEE calculations for nutrition targets.

## Feed Behavior

| Behavior | Value |
|----------|-------|
| Manual creation ("+") | Yes (sheet) |
| Tap → detail | No |
| Swipe actions | Delete |
| Sort priority | 10 (chronological) |
| Pinned | No |

## Data (More > Data)

`WeightView` — weight entries list with chart view, quick stats (latest, 7d avg, week change). Supports date navigation.

## Settings

None. Unit preference (kg/lb) is in Settings > Units.

## Backend

### Tables

| Table | Purpose |
|-------|---------|
| `body_measurements` | Weight entries (date, weight_kg, notes). Multiple per day allowed. |

### API Endpoints

- `GET /api/weight` — trends (latest, avg, delta) + entries
- `POST /api/weight` — log entry {date, weight_kg, notes}
- `PUT /api/weight/{id}` — update
- `DELETE /api/weight/{id}` — delete
- `POST /api/weight/bulk-import` — bulk import (from Apple Health)

### Feed Loader

`_load_weight` in `feed_service.py` — fetches via `weight_repo.list_by_date()`.

## Key Backend Files

- `models/weight.py` — WeightCreate
- `storage/weight_repo.py` — CRUD + list_by_date + bulk import
- `services/weight_service.py` — trends computation (latest, 7d avg, delta)
