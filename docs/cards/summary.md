# Card: Summary

## Identity

| Field | Value |
|-------|-------|
| Card Type | `summary` |
| Icon | `sparkles` |
| Accent Color | Yellow |
| Module | `SummaryCardModule.swift` |

## Purpose

AI-generated daily or weekly health report. Summarizes meals, nutrition, workouts, weight trends, and portfolio into a markdown report with playful commentary.

## Feed Behavior

| Behavior | Value |
|----------|-------|
| Manual creation ("+") | Yes (triggers LLM generation) |
| Tap → detail | Yes → `SummaryDetailView` |
| Swipe actions | Regenerate |
| Sort priority | 0 (pinned at top) |
| Pinned | Yes — shown when summary exists or after configured hour |

**Auto-generation:** Also generated via background notification task. Both auto and manual creation write to the same `summaries` table.

## Data (More > Data)

`SummaryListView` — browse past summaries by date. Tap to view full text. Swipe to delete.

## Settings

Notification schedule (daily summary time, weekly summary day) — configured in Settings > Notifications.

## Backend

### Tables

| Table | Purpose |
|-------|---------|
| `summaries` | LLM-generated summaries (type='daily'/'weekly', date, summary_text, llm audit) |

### API Endpoints

- `GET /api/summary/daily-detail?date=YYYY-MM-DD` — retrieve stored daily summary
- `POST /api/summary/daily-detail?language=en&date=YYYY-MM-DD` — generate/regenerate
- `GET /api/summary/weekly-detail?date=YYYY-MM-DD` — retrieve stored weekly summary
- `POST /api/summary/weekly-detail?language=en` — generate/regenerate
- `GET /api/summary/list?type=daily&limit=50` — list recent summaries
- `DELETE /api/summary/{id}` — delete a summary
- `GET /api/summary/streak` — meal logging streak

### LLM Context

Daily summary prompt includes: meal details + totals vs targets, weight trends, workout summaries, portfolio value + day change + top movers, logging streak. Built by `_build_daily_context()` in `summary_service.py`.

### Feed Loader

`_load_summary` in `feed_service.py` — fetches via `summary_repo.get_latest("daily", date)`.

## Key Backend Files

- `storage/summary_repo.py` — CRUD + list_recent
- `services/summary_service.py` — context building + LLM generation
- `llm/prompts.py` — `build_daily_detail_prompt()`, `build_weekly_detail_prompt()`
