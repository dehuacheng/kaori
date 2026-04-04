# Card: Nutrition

## Identity

| Field | Value |
|-------|-------|
| Card Type | `nutrition` |
| Icon | `chart.bar.fill` |
| Accent Color | Red |
| Module | `NutritionCardModule.swift` |

## Purpose

Show daily calorie and macro progress bars (calories, protein, carbs, fat) against computed targets. Derived from meal data — not standalone.

## Feed Behavior

| Behavior | Value |
|----------|-------|
| Manual creation ("+") | No (auto-derived from meals) |
| Tap → detail | No |
| Swipe actions | None |
| Sort priority | 2 (pinned below portfolio) |
| Pinned | Yes — always for today (even with zero values), other days only if meals exist |

## Data (More > Data)

None. Analytics (charts) are accessed via the chart icon in the feed nav bar, not the data section.

## Settings

None at card level. Nutrition targets (protein_per_kg, carbs_per_kg, calorie_adjustment_pct) are configured in Profile.

## Backend

No dedicated tables or endpoints. Nutrition totals are computed from `meals` table via `meal_repo.get_totals(date)`.

### Feed Loader

`_load_nutrition` in `feed_service.py` — fetches totals via `meal_repo.get_totals()`.

## Key Backend Files

- `storage/meal_repo.py` — `get_totals(date)` computes nutrition aggregates
- `services/profile_service.py` — `compute_targets()` for BMR/TDEE/macro targets

## Design Note

Nutrition is a **derived card** — it has no own data store, creation flow, or data listing. It exists purely as a feed visualization of meal data. Targets are computed dynamically from profile + latest weight (BMR via Mifflin-St Jeor, TDEE = BMR * 1.2, adjusted by `calorie_adjustment_pct`).
