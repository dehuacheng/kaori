# Kaori — Design Patterns

## Raw / Processed / Override Data Separation

Every data domain follows a 3-table pattern:

| Table | Purpose | Example |
|-------|---------|---------|
| Raw | Exactly what the user provided | `meals` (date, description, photo_path) |
| Analysis | LLM-generated results with audit trail | `meal_analyses` (calories, macros, backend, model, raw_response) |
| Override | User corrections (highest precedence) | `meal_overrides` (calories, macros) |

Query precedence via COALESCE: `override > analysis > raw`

## Versioned LLM Summaries (Rollback-Safe)

When LLM compaction/summarization is used (e.g., meal habit summaries), the data must be:

- **Append-only** — every compaction creates a new row, never overwrites
- **Versioned** — `version` integer (monotonically increasing) + `is_active` flag
- **Rollback-safe** — deactivate bad version, reactivate previous, no data lost
- **Auditable** — every version stores `llm_backend`, `model`, `raw_response`

### Schema Pattern

```sql
CREATE TABLE IF NOT EXISTS <domain>_summaries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    version      INTEGER NOT NULL,
    is_active    INTEGER NOT NULL DEFAULT 1,
    summary_text TEXT    NOT NULL,
    cutoff_date  TEXT    NOT NULL,
    <domain>_count INTEGER NOT NULL,
    llm_backend  TEXT,
    model        TEXT,
    raw_response TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);
```

### Operations

- **Compact**: deactivate current active, insert new row with `version = max + 1, is_active = 1`
- **Rollback**: deactivate current, reactivate target version
- **List**: show all versions for management

### Current Usage

- `meal_habit_summaries` — compacted meal history for context-aware analysis

### Future Usage

Apply this pattern to any domain with LLM-generated summaries: diary summaries, health profiles, coaching notes, etc.

## 4-Layer Architecture

```
models/   → Pydantic data contracts (shared)
storage/  → DB repos (owns all SQL)
services/ → Business logic (orchestrates storage + LLM)
api/      → JSON endpoints | web/ → HTML pages
```

Rules:
- Storage repos own ALL database access
- Services orchestrate storage + LLM, no HTTP concerns
- API routes return JSON only, no template rendering
- Web routes render templates only, business logic in services
- LLM callers depend on `LLMBackend` ABC, never concrete backends
