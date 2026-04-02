# Kaori

Personal AI-powered life management app. Self-hosted, privacy-first.

Kaori is a FastAPI backend that tracks meals, weight, workouts, and more — with LLM-powered analysis. All data stays on your machine.

## Features

- **Meal tracking** — Log meals via photo or text. LLM analyzes nutrition (calories, protein, carbs, fat). Supports reprocessing and rollback.
- **Weight tracking** — Multiple entries per day, trend charts, BMR/TDEE calculations.
- **Workout tracking** — Structured logging with exercises, sets, reps, weights. LLM workout summaries with calorie estimation.
- **Exercise catalog** — Standard exercises + custom additions. Identify gym machines from photos via LLM.
- **Timer presets** — Configurable rest/work timers consumed by the iOS app.
- **User profile** — Height, weight, age, macro targets. Dynamic nutrition targets based on body composition.
- **Multi-LLM support** — Claude CLI, Anthropic API, or Codex CLI (ChatGPT). Switchable per-user.

## Setup

**Requirements:** Python 3.12+, `claude` CLI (for default LLM mode)

```bash
git clone https://github.com/dehuacheng/kaori.git
cd kaori
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Optional: for Anthropic API mode
pip install -e ".[llm-api]"
```

## Running

```bash
# Production
uvicorn kaori.main:app --reload --host 0.0.0.0 --port 8000

# Test mode (uses separate database, safe for development)
KAORI_TEST_MODE=1 uvicorn kaori.main:app --reload --host 0.0.0.0 --port 8001
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KAORI_TOKEN` | `dev-token` | Bearer token for API auth |
| `KAORI_TEST_MODE` | `0` | Use test database when `1` |
| `KAORI_LLM_MODE` | `claude_cli` | LLM backend: `claude_cli`, `claude_api`, or `codex_cli` |
| `ANTHROPIC_API_KEY` | — | Required only for `claude_api` mode |

## Architecture

4-layer separation: **Models** (Pydantic) → **Storage** (SQLite repos) → **Services** (business logic + LLM) → **API** (JSON endpoints).

- SQLite with WAL mode, raw/processed data separation
- LLM results are versioned and rollback-safe
- Bearer token auth (designed for single-user, Tailscale-gated access)

## iOS App

The companion iOS app is at [kaori-ios](https://github.com/dehuacheng/kaori-ios).

## License

Private project.
