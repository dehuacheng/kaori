# Weight Feature

**Status**: In Progress (Phase 1 MVP)

## Overview

Weight logging with multiple entries per day, inline edit/delete, and 7/30-day trend tracking. Weight data feeds into profile target computation (BMR/TDEE).

## Data Model

- `body_measurements` — id, date, weight_kg, notes, created_at
- Multiple entries per day allowed (no unique constraint on date)
- Trends computed from most recent entries (ordered by date DESC, created_at DESC)

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/weight` | Weight history + trends (latest, 7d avg, weekly delta) |
| POST | `/api/weight` | Log weight (insert, not upsert) |
| PUT | `/api/weight/{id}` | Update a weight entry |
| DELETE | `/api/weight/{id}` | Delete a weight entry |

## Web UI

- Date picker in log form (defaults to today, user can backfill)
- History table with inline edit (Alpine.js toggle) and delete with confirmation
- Trend chart (canvas-drawn line chart)
- Stats: current weight, 7-day average, weekly change

## Key Files

- `kaori/models/weight.py` — WeightCreate
- `kaori/storage/weight_repo.py` — create, update, delete, get_history
- `kaori/services/weight_service.py` — log, update, delete, trends, get_profile
