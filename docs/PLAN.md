# Kaori — Project Plan Index

Build a personal AI-powered life management app (codename "Kaori"). Self-hosted on Apple Silicon MacBook, accessed from iPhone via Tailscale.

## Architecture

```
Frontend (any)                       Backend (kaori/ package)
+------------------+                 +----------------------------------------+
| iOS app          |                 | FastAPI API layer (/api/*)             |
| Web SPA          |  -- HTTPS -->   | Services (business logic)              |
| PWA (testing)    |  (Tailscale)    | LLM layer (CLI or API, abstract)       |
+------------------+                 | Storage (SQLite + files)               |
                                     +----------------------------------------+
```

| Component | Choice |
|-----------|--------|
| Backend | FastAPI + Python 3.12+ |
| Database | SQLite (WAL mode), raw/processed data separation |
| LLM | Abstract interface: Claude CLI or Anthropic API |
| Testing Frontend | HTMX + Alpine.js + Jinja2 (barebone) |
| Hosting | Apple Silicon MacBook |
| Network | Tailscale (iPhone <-> MacBook) |

### Repo Strategy
- `kaori` — Backend package (API, services, LLM, storage). This repo.
- Future: separate repos for iOS frontend, web SPA frontend.

---

## Feature Docs

| Doc | Version | Status | Description |
|-----|---------|--------|-------------|
| [meals.md](meals.md) | 0.2.0 | In Progress | Meal logging — photo, text, LLM analysis, reprocessing & rollback |
| [weight.md](weight.md) | 0.1.0 | In Progress | Weight tracking, trends, body measurements |
| [profile.md](profile.md) | 0.1.0 | In Progress | User profile, targets, personal info, free-form notes |
| [workout.md](workout.md) | 0.2.0 | In Progress | Workout tracking — exercises, sets, reps, weights, timer presets, Apple Health, LLM summary |
| [roadmap.md](roadmap.md) | — | Reference | Phased roadmap (Phases 2–7) |

### Version scheme
- **0.x.y** — in development, not yet stable
- **1.0.0** — feature complete and validated with real data
- Bump **minor** (0.x.0) for new capabilities; bump **patch** (0.0.x) for fixes/refinements

## Cross-Cutting Patterns

| Doc | Description |
|-----|-------------|
| [patterns.md](patterns.md) | Reusable design patterns (versioned LLM summaries, raw/processed separation) |

## Decision History

| Doc | Description |
|-----|-------------|
| [DECISIONS.md](DECISIONS.md) | Chronological log of all project direction changes |
