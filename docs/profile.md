# Profile Feature

**Status**: In Progress (Phase 1 MVP)

## Overview

Single-user profile storing personal information and nutrition parameters. Calorie and macro targets are computed dynamically from body stats + latest weight, not stored as static numbers.

## Stored Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| display_name | text | "User" | User's name |
| height_cm | real | null | Height in centimeters |
| gender | text | null | male / female / other |
| birth_date | text | null | YYYY-MM-DD (age computed dynamically) |
| protein_per_kg | real | 1.6 | Protein target per kg body weight |
| carbs_per_kg | real | 3.0 | Carbs target per kg body weight |
| calorie_adjustment_pct | real | 0 | % adjustment to TDEE (negative = deficit, positive = surplus) |
| llm_mode | text | "claude_cli" | LLM backend selection |
| notes | text | null | Free-form field for LLM context |

## Computed Targets

Computed at query time from stored fields + latest weight from `body_measurements`:

| Target | Formula |
|--------|---------|
| BMR | Mifflin-St Jeor: `10*weight + 6.25*height - 5*age + 5` (male) or `-161` (female) |
| TDEE | `BMR * 1.2` (sedentary baseline) |
| target_calories | `TDEE * (1 + calorie_adjustment_pct / 100)` |
| target_protein_g | `weight_kg * protein_per_kg` |
| target_carbs_g | `weight_kg * carbs_per_kg` |

Activity level is intentionally excluded — it will be inferred from exercise/training data in Phase 5.

## LLM Context Integration

Profile data is formatted and injected into meal analysis prompts via `profile_service.format_profile_context()`. Includes computed targets and the free-form `notes` field.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/profile` | Full profile with computed targets |
| PUT | `/api/profile` | Update stored profile fields |

## Key Files

- `kaori/storage/profile_repo.py` — get, update
- `kaori/services/profile_service.py` — get (with computed targets), update, format_profile_context, compute_targets
- `kaori/api/profile.py` — JSON endpoints
- `kaori/web/profile.py` — HTML form
- `kaori/templates/profile.html` — profile edit page with computed targets display
