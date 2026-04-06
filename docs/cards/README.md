# Card Design Docs (Backend)

Every feature in Kaori is a **card type**. Each card has a design doc here covering its backend data model, API endpoints, and feed integration.

**When adding or modifying a card, update its doc here.** See `CLAUDE.md` for the full checklist.

## Cards

| Card Type | Doc | Tables | Feed Loader |
|-----------|-----|--------|-------------|
| `meal` | [meal.md](meal.md) | meals, meal_analyses, meal_overrides, meal_habit_summaries | `_load_meals` |
| `weight` | [weight.md](weight.md) | body_measurements | `_load_weight` |
| `workout` | [workout.md](workout.md) | workouts (source='manual'), workout_exercises, exercise_sets, exercise_types, workout_analyses | `_load_workouts` |
| `healthkit_workout` | [healthkit-workout.md](healthkit-workout.md) | workouts (source='healthkit') | `_load_workouts` (shared) |
| `portfolio` | [portfolio.md](portfolio.md) | financial_accounts, portfolio_holdings, portfolio_snapshots, stock_prices | `_load_portfolio` |
| `nutrition` | [nutrition.md](nutrition.md) | (derived from meals) | `_load_nutrition` |
| `summary` | [summary.md](summary.md) | summaries | `_load_summary` |
| `post` | [post.md](post.md) | posts | `_load_posts` |
| `reminder` | [reminder.md](reminder.md) | reminders | `_load_reminders` |
| `agent_session` | [agent.md](agent.md) | agent_sessions, agent_messages, agent_memory, agent_compactions, agent_prompts | (future) |
| `weather` | [weather.md](weather.md) | weather_location, weather_cache | `_load_weather` |

## Template for New Cards

When creating a new card type, copy this template:

```markdown
# Card: <Name>

## Identity
| Field | Value |
|-------|-------|
| Card Type | `<type_string>` |
| CardType Enum | `CardType.<TYPE>` |

## Purpose
<What this card does and why>

## Tables
| Table | Purpose |
|-------|---------|
| `<table>` | <description> |

## API Endpoints
- `GET /api/<type>` — ...
- `POST /api/<type>` — ...

## Feed Loader
`_load_<type>` in `feed_service.py` — registered in `CARD_LOADERS`.

## LLM Integration (if any)
<Prompt template, context building, analysis flow>
```
