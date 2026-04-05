# Agent Session Integration (kaori backend)

> Created 2026-04-05 during kaori-agent Phase 4 implementation.
> Updated 2026-04-05: Tasks 1-7 implemented + SSE chat endpoint added.

## Context

kaori-agent Phase 4 stores session data in `agent_*` tables inside kaori.db.
The agent creates tables via CREATE TABLE IF NOT EXISTS on startup. This work
adds backend awareness (schema ownership, REST API, card type, SSE chat) so
iOS can access agent data and run chat conversations.

## Tasks

### 1. Schema — add agent tables to `kaori/database.py` ✅

Added all 5 agent tables + 3 indexes to SCHEMA string. Added `agent_session`
to card preference migration.

### 2. Storage repos — create 5 files in `kaori/storage/` ✅

| File | Purpose |
|------|---------|
| `agent_session_repo.py` | Session CRUD (create, get, list, update, delete) |
| `agent_message_repo.py` | Message append, list, count, get_latest_seq, list_after_seq |
| `agent_memory_repo.py` | Memory get, upsert, delete, list_all |
| `agent_compaction_repo.py` | Compaction get_active, create, list_versions |
| `agent_prompt_repo.py` | Prompt get_active, list, create, update, set_active, delete |

### 3. Service — create `kaori/services/agent_service.py` ✅

Thin orchestration layer delegating to repos.

### 4. API — create `kaori/api/agent.py` ✅

REST endpoints:

```
GET    /api/agent/sessions                 — list sessions (status filter)
POST   /api/agent/sessions                 — create session
GET    /api/agent/sessions/{id}            — session + messages
PUT    /api/agent/sessions/{id}            — update title/status
DELETE /api/agent/sessions/{id}            — delete (cascade)
GET    /api/agent/memory                   — list all memory entries
PUT    /api/agent/memory/{key}             — upsert memory entry
DELETE /api/agent/memory/{key}             — delete memory entry
GET    /api/agent/prompts                  — list personal prompts
POST   /api/agent/prompts                  — create prompt
PUT    /api/agent/prompts/{id}             — update prompt
PUT    /api/agent/prompts/{id}/activate    — set as active
DELETE /api/agent/prompts/{id}             — delete prompt
POST   /api/agent/chat                     — SSE streaming chat
```

### 5. Router — register in `kaori/api/router.py` ✅

### 6. Card type — add to `kaori/models/card.py` ✅

`AGENT_SESSION = "agent_session"` added to `CardType` enum.
Added to `_DEFAULTS` in `card_preference_repo.py`.

### 7. Card design doc — create `docs/cards/agent.md` ✅

### 8. Agent LLM backend + engine + tools ✅ (bonus)

Added beyond original TODO scope:

| File | Purpose |
|------|---------|
| `kaori/llm/agent_backend.py` | AgentLLMBackend ABC + Anthropic/OpenAI implementations |
| `kaori/services/agent_engine.py` | Agentic turn loop (ported from kaori-agent) |
| `kaori/services/agent_tools.py` | 9 server-side tools calling kaori services directly |
| `kaori/services/agent_chat_service.py` | Chat orchestration + SSE event generation |

### 9. Feed integration (future)

Add a loader to `CARD_LOADERS` in `feed_service.py` that shows the latest active
session as a feed card (session title + last message preview).

## Config

The agent chat backend needs LLM API keys:
- `ANTHROPIC_API_KEY` — for Anthropic backend (reuses existing)
- `DEEPSEEK_API_KEY` — for DeepSeek backend (new)
- `KAORI_AGENT_BACKEND` — backend selection (default: "anthropic")
