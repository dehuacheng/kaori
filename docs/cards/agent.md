# Card: Agent Session

## Identity
| Field | Value |
|-------|-------|
| Card Type | `agent_session` |
| CardType Enum | `CardType.AGENT_SESSION` |

## Purpose
AI agent chat sessions — multi-turn conversations with tool access to kaori data.
The agent can query meals, weight, workouts, portfolio, and reminders on behalf
of the user, and remember facts across sessions via persistent memory.

## Tables
| Table | Purpose |
|-------|---------|
| `agent_sessions` | Chat sessions (UUID PK, title, status, backend/model, counts) |
| `agent_messages` | Messages within a session (seq-ordered, role, JSON content) |
| `agent_memory` | Cross-session persistent memory (key-value with category) |
| `agent_compactions` | Versioned transcript summaries (rollback-safe) |
| `agent_prompts` | Personal prompt templates (one active at a time) |

## API Endpoints

### Sessions
- `GET /api/agent/sessions` — list sessions (status filter, limit)
- `POST /api/agent/sessions` — create session
- `GET /api/agent/sessions/{id}` — session detail + messages
- `PUT /api/agent/sessions/{id}` — update title/status
- `DELETE /api/agent/sessions/{id}` — delete (cascades messages)

### Chat (SSE)
- `POST /api/agent/chat` — send message, receive streaming events
  - Body: `{"message": str, "session_id": str | null}`
  - Response: `text/event-stream` with JSON events:
    - `session` — `{session_id, title}` (first event)
    - `thinking` — `{text}` (reasoning tokens)
    - `text` — `{text}` (response text delta)
    - `tool_use` — `{name, input}` (tool call)
    - `done` — `{message_count}` (turn complete)
    - `error` — `{message}`

### Memory
- `GET /api/agent/memory` — list all memory entries
- `PUT /api/agent/memory/{key}` — upsert entry
- `DELETE /api/agent/memory/{key}` — delete entry

### Prompts
- `GET /api/agent/prompts` — list prompts
- `POST /api/agent/prompts` — create prompt
- `PUT /api/agent/prompts/{id}` — update prompt
- `PUT /api/agent/prompts/{id}/activate` — set as active
- `DELETE /api/agent/prompts/{id}` — delete prompt

## Feed Loader
Not yet implemented. Future: `_load_agent_session` showing latest active session
as a card (title + last message preview).

## LLM Integration
The agent chat endpoint runs a full agentic turn loop:
1. User message → append to session
2. Build system prompt (personality + memory + date/time)
3. Send to LLM with 9 tool schemas
4. If tool_use → execute tools → feed results back → loop
5. If text → stream to client → persist → done

Tools call kaori services directly (no HTTP round-trip):
`get_feed`, `get_meals`, `get_weight`, `get_profile`, `get_portfolio_summary`,
`get_workouts`, `get_reminders`, `save_memory`, `get_memory`

## Key Files
| File | Purpose |
|------|---------|
| `kaori/models/agent.py` | Pydantic models |
| `kaori/storage/agent_*_repo.py` | 5 storage repos |
| `kaori/services/agent_service.py` | Thin orchestration |
| `kaori/services/agent_chat_service.py` | Chat + SSE orchestration |
| `kaori/services/agent_engine.py` | Agentic turn loop |
| `kaori/services/agent_tools.py` | 9 server-side tools |
| `kaori/llm/agent_backend.py` | LLM abstraction (Anthropic + OpenAI) |
| `kaori/api/agent.py` | REST + SSE endpoints |
