# Card: Reminder/TODO

## Identity

| Field | Value |
|-------|-------|
| Card Type | `reminder` |
| CardType Enum | `CardType.REMINDER` |

## Purpose

Date-targeted items with two subtypes:
- **reminder**: Informational, stays visible until deleted. No checkbox.
- **todo**: Checkable, can be marked done or pushed to a later date.

Overdue items automatically surface on today's feed.

## Feed Behavior

| Behavior | Value |
|----------|-------|
| Manual creation ("+") | Yes |
| Tap → detail | Yes (edit/push/done) |
| Swipe actions | Delete, Done (todo only) |
| Sort priority | 3 (pinned above chronological items) |
| Pinned | Yes |

### Overdue Surfacing

- **Today's feed**: Shows all undone items with `due_date <= tomorrow` (includes overdue + today + tomorrow), plus items completed today. Future reminders beyond tomorrow are hidden.
- **Past dates**: Shows only items with `due_date = that_date` (historical view).
- No cron job needed — the query itself handles surfacing.

### Push to Later Date

Updates `due_date` while preserving `original_date` for audit trail. The item disappears from the current date's feed and appears on the new date.

## Backend

### Tables

| Table | Purpose |
|-------|---------|
| `reminders` | Reminder/TODO items (title, description, due_date, original_date, item_type, is_done, priority) |

### Schema Details

- `due_date` — mutable, updated when pushed
- `original_date` — immutable, set at creation
- `item_type` — `'reminder'` or `'todo'`
- `priority` — 0 (low), 1 (normal), 2 (high)
- `is_done` — only meaningful for TODOs
- `done_at` — timestamp of completion

### API Endpoints

- `GET /api/reminders?date=...` — list for date (today includes overdue)
- `POST /api/reminders` — create {title, description, due_date, item_type, priority}
- `GET /api/reminders/{id}` — detail
- `PUT /api/reminders/{id}` — update fields
- `DELETE /api/reminders/{id}` — delete
- `POST /api/reminders/{id}/push` — push to new date {new_date}
- `POST /api/reminders/{id}/done` — mark done/undone {is_done}

### Feed Loader

`_load_reminders` in `feed_service.py` — uses `reminder_service.list_for_feed()` which branches on today vs past dates.

## Key Backend Files

- `models/reminder.py` — ReminderCreate, ReminderUpdate, ReminderPush, ReminderDone
- `storage/reminder_repo.py` — CRUD + list_active_for_today + push + mark_done
- `services/reminder_service.py` — list_for_feed (overdue logic)
- `api/reminder.py` — REST endpoints + action endpoints
