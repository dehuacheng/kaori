# TODO: Agent Session Integration (kaori backend)

> Created 2026-04-05 during kaori-agent Phase 4 implementation.
> kaori-agent already creates and uses these tables. This work adds backend
> awareness (schema ownership, REST API, card type) so iOS can access agent data.

## Context

kaori-agent Phase 4 stores session data in `agent_*` tables inside kaori.db.
The agent creates tables via CREATE TABLE IF NOT EXISTS on startup. This TODO
covers the kaori backend adopting those tables and exposing them via REST API
for iOS consumption.

## Tasks

### 1. Schema — add agent tables to `kaori/database.py`

Add to `SCHEMA` string (after `card_preferences`):

```sql
-- Agent chat sessions
CREATE TABLE IF NOT EXISTS agent_sessions (...)
CREATE TABLE IF NOT EXISTS agent_messages (...)
CREATE TABLE IF NOT EXISTS agent_memory (...)
CREATE TABLE IF NOT EXISTS agent_compactions (...)
CREATE TABLE IF NOT EXISTS agent_prompts (...)
-- Indexes
CREATE INDEX IF NOT EXISTS idx_agent_messages_session ...
CREATE INDEX IF NOT EXISTS idx_agent_sessions_status ...
CREATE INDEX IF NOT EXISTS idx_agent_compactions_session ...
```

Full DDL is in `kaori-agent/kaori_agent/session.py` `_AGENT_SCHEMA`.

Add `_migrate_agent_tables(db)` to `init_db()` — no-op if tables already exist.

### 2. Storage repos — create 5 files in `kaori/storage/`

| File | Purpose |
|------|---------|
| `agent_session_repo.py` | Session CRUD (create, get, list, update, delete) |
| `agent_message_repo.py` | Message append, list, count, get_latest_seq |
| `agent_memory_repo.py` | Memory get, upsert, delete, list_all |
| `agent_compaction_repo.py` | Compaction get_active, create, list_versions |
| `agent_prompt_repo.py` | Prompt get_active, list, create, update, set_active, delete |

Follow existing repo pattern: `async def func(...): db = await get_db(); try: ... finally: await db.close()`

### 3. Service — create `kaori/services/agent_service.py`

Thin orchestration layer delegating to repos. No complex business logic.

### 4. API — create `kaori/api/agent.py`

REST endpoints:

```
GET    /api/agent/sessions                 — list sessions (status filter)
GET    /api/agent/sessions/{id}            — session + messages
PUT    /api/agent/sessions/{id}            — update title/status
DELETE /api/agent/sessions/{id}            — delete session + cascade
GET    /api/agent/memory                   — list all memory entries
PUT    /api/agent/memory/{key}             — upsert memory entry
DELETE /api/agent/memory/{key}             — delete memory entry
GET    /api/agent/prompts                  — list personal prompts
POST   /api/agent/prompts                  — create prompt
PUT    /api/agent/prompts/{id}             — update prompt
PUT    /api/agent/prompts/{id}/activate    — set as active
DELETE /api/agent/prompts/{id}             — delete prompt
```

### 5. Router — register in `kaori/api/router.py`

```python
from kaori.api import agent
api_router.include_router(agent.router)
```

### 6. Card type — add to `kaori/models/card.py`

```python
AGENT_SESSION = "agent_session"
```

Add to `_DEFAULTS` in `storage/card_preference_repo.py`:
```python
"agent_session": (1, 0, 99),
```

### 7. Card design doc — create `docs/cards/agent.md`

Follow the template in `docs/cards/README.md`.

### 8. Feed integration (optional, future)

Add a loader to `CARD_LOADERS` in `feed_service.py` that shows the latest active
session as a feed card (session title + last message preview). This enables the
"Agent" card to appear in the iOS feed alongside meals, weight, etc.

## Notes

- All agent tables are `agent_`-prefixed with no FK to existing kaori tables
- kaori-agent will continue to create tables on its own (for standalone use)
- kaori backend adopting the schema is purely for API serving + schema ownership
- iOS integration requires this work + Phase 8 (SwiftUI chat UI) in kaori-ios
