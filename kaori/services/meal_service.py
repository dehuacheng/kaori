import json
import logging
from datetime import date, datetime, timedelta

from kaori.config import PHOTOS_DIR
from kaori.llm import get_llm_backend, LLMError
from kaori.llm.prompts import (
    build_text_analysis_prompt,
    build_photo_analysis_prompt,
    build_compaction_prompt,
)
from kaori.models.meal import FoodAnalysis
from kaori.services import profile_service
from kaori.storage import meal_repo, meal_analysis_repo, meal_override_repo, meal_history_repo

logger = logging.getLogger(__name__)

FALLBACK = FoodAnalysis(
    description="Could not analyze meal",
    items=[], calories=0, protein_g=0, carbs_g=0, fat_g=0, confidence="low",
)


def auto_detect_meal_type(meal_type: str) -> str:
    if meal_type != "snack":
        return meal_type
    hour = datetime.now().hour
    if hour < 10:
        return "breakfast"
    elif hour < 14:
        return "lunch"
    elif hour < 20:
        return "dinner"
    return "snack"


# ---------------------------------------------------------------------------
# Context building helpers
# ---------------------------------------------------------------------------

def _format_recent_meals(meals: list[dict]) -> str:
    """Format meal records into a readable list for the LLM prompt."""
    if not meals:
        return "No recent meals."
    lines = []
    for m in meals:
        cal = m.get("calories")
        prot = m.get("protein_g")
        desc = m.get("description") or "(no description)"
        nutrition = f"{cal} kcal, P:{prot:.0f}g" if cal and prot else "no nutrition data"
        lines.append(f"- {m['date']} {m['meal_type']}: {desc} ({nutrition})")
    return "\n".join(lines)


async def _build_meal_context() -> str:
    """Build historical context string from user profile + habit summary + recent meals."""
    parts = []

    # Component 0: User profile
    profile = await profile_service.get_profile()
    profile_ctx = profile_service.format_profile_context(profile)
    if profile_ctx:
        parts.append(profile_ctx)

    # Component 1: Meal habit summary
    summary = await meal_history_repo.get_active_summary()
    parts.append("## Meal Habit Summary")
    if summary:
        parts.append(summary["summary_text"])
    else:
        parts.append("No history available yet.")

    # Component 2: Recent meals since cutoff
    since_date = summary["cutoff_date"] if summary else "1970-01-01"
    recent = await meal_history_repo.get_recent_meals(since_date, limit=50)
    parts.append("\n## Recent Meals")
    parts.append(_format_recent_meals(recent))

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------

async def list_by_date(target_date: str) -> list[dict]:
    return await meal_repo.list_by_date(target_date)


async def get_totals(target_date: str) -> dict:
    return await meal_repo.get_totals(target_date)


async def get_by_id(meal_id: int) -> dict | None:
    return await meal_repo.get_by_id(meal_id)


# ---------------------------------------------------------------------------
# Mutation functions
# ---------------------------------------------------------------------------

async def create(*, meal_date: str | None = None, meal_type: str = "snack",
                 description: str | None = None, photo_path: str | None = None,
                 photo_paths: list[str] | None = None,
                 notes: str | None = None) -> tuple[int, bool]:
    """Create a meal. Returns (meal_id, needs_analysis)."""
    target_date = meal_date or date.today().isoformat()
    photo_paths_json = json.dumps(photo_paths) if photo_paths else None
    meal_id = await meal_repo.create(
        date=target_date, meal_type=meal_type,
        description=description, photo_path=photo_path,
        photo_paths=photo_paths_json, notes=notes,
    )
    needs_analysis = photo_path is not None or description is not None
    if needs_analysis:
        await meal_analysis_repo.create(meal_id)
    return meal_id, needs_analysis


async def update(meal_id: int, **fields) -> str | None:
    """Update a meal. Nutrition fields go to overrides, metadata to meals table."""
    nutrition_fields = {k: fields[k] for k in ("calories", "protein_g", "carbs_g", "fat_g")
                        if k in fields and fields[k] is not None}
    meta_fields = {k: fields[k] for k in ("date", "meal_type", "description", "notes")
                   if k in fields and fields[k] is not None}

    if nutrition_fields:
        await meal_override_repo.upsert(meal_id, **nutrition_fields)

    meal_date = await meal_repo.update(meal_id, **meta_fields)
    return meal_date


async def delete(meal_id: int) -> str | None:
    return await meal_repo.delete(meal_id)


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def _parse_analysis_response(raw_text: str) -> FoodAnalysis:
    """Parse LLM response text into FoodAnalysis model."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    data = json.loads(text)

    # Normalize items (Claude may return strings or dicts)
    raw_items = data.get("items", [])
    items = []
    for item in raw_items:
        if isinstance(item, str):
            items.append(item)
        elif isinstance(item, dict):
            name = item.get("name", item.get("item", ""))
            portion = item.get("portion", item.get("quantity", ""))
            items.append(f"{name} ({portion})" if portion else str(name))
        else:
            items.append(str(item))

    return FoodAnalysis(
        description=data.get("description", "Meal"),
        items=items,
        calories=int(data.get("calories", 0)),
        protein_g=float(data.get("protein_g", 0)),
        carbs_g=float(data.get("carbs_g", 0)),
        fat_g=float(data.get("fat_g", 0)),
        confidence=data.get("confidence", "medium"),
    )


async def run_analysis(meal_id: int, *, photo_path: str | None = None,
                       photo_paths: list[str] | None = None,
                       description: str | None = None, notes: str | None = None):
    """Analyze a meal in background. Supports photo(s), text, or both."""
    analysis = await meal_analysis_repo.get_latest_for_meal(meal_id)
    if not analysis:
        return
    analysis_id = analysis["id"]

    await meal_analysis_repo.set_analyzing(analysis_id)

    try:
        profile = await profile_service.get_profile()
        backend = get_llm_backend(mode=profile.get("llm_mode"))
        context = await _build_meal_context()

        # Determine all photo paths to analyze
        all_paths = photo_paths or ([photo_path] if photo_path else [])

        if len(all_paths) > 1:
            # Multiple photos — use analyze_images
            from kaori.storage.file_store import get_resized_image_bytes
            images = [(get_resized_image_bytes(p), "image/jpeg") for p in all_paths]
            prompt = build_photo_analysis_prompt(context, description, notes=notes)
            response = await backend.analyze_images(images, prompt)
        elif len(all_paths) == 1:
            abs_path = str(PHOTOS_DIR / all_paths[0])
            prompt = build_photo_analysis_prompt(context, description, notes=notes)
            response = await backend.analyze_image(abs_path, prompt)
        else:
            prompt = build_text_analysis_prompt(context, description or "", notes=notes)
            response = await backend.complete(prompt)

        result = _parse_analysis_response(response.text)

        await meal_analysis_repo.set_done(
            analysis_id,
            description=result.description,
            items=result.items,
            calories=result.calories,
            protein_g=result.protein_g,
            carbs_g=result.carbs_g,
            fat_g=result.fat_g,
            confidence=result.confidence,
            llm_backend=response.backend,
            model=response.model,
            raw_response=response.text,
        )
        logger.info("Meal %d analysis complete: %d kcal", meal_id, result.calories)

    except (LLMError, json.JSONDecodeError, Exception) as e:
        logger.exception("Analysis failed for meal %d", meal_id)
        await meal_analysis_repo.set_failed(analysis_id, str(e))


# ---------------------------------------------------------------------------
# Reprocessing & rollback
# ---------------------------------------------------------------------------

async def reprocess_meal(meal_id: int) -> int:
    """Re-run LLM analysis on an existing meal. Returns new analysis_id.

    Clears user overrides and creates a new pending analysis
    (which deactivates the previous one).
    """
    raw = await meal_repo.get_raw(meal_id)
    if not raw:
        raise ValueError(f"Meal {meal_id} not found")

    await meal_override_repo.delete(meal_id)
    analysis_id = await meal_analysis_repo.create(meal_id)
    return analysis_id


async def list_analyses(meal_id: int) -> list[dict]:
    """List all analysis versions for a meal."""
    return await meal_analysis_repo.list_for_meal(meal_id)


async def rollback_analysis(meal_id: int, analysis_id: int) -> dict:
    """Rollback to a specific analysis version. Clears overrides."""
    analyses = await meal_analysis_repo.list_for_meal(meal_id)
    valid_ids = {a["id"] for a in analyses}
    if analysis_id not in valid_ids:
        raise ValueError(f"Analysis {analysis_id} does not belong to meal {meal_id}")

    await meal_analysis_repo.set_active(analysis_id, meal_id)
    await meal_override_repo.delete(meal_id)
    return await meal_analysis_repo.get_latest_for_meal(meal_id)


# ---------------------------------------------------------------------------
# History compaction
# ---------------------------------------------------------------------------

async def compact_meal_history() -> dict:
    """Compact recent meals into an updated habit summary.

    Fetches the active summary (if any), collects meals between the old cutoff
    and 7 days ago, sends them to the LLM for summarization, and stores the
    result as a new versioned summary.
    """
    current = await meal_history_repo.get_active_summary()
    old_cutoff = current["cutoff_date"] if current else "1970-01-01"
    old_summary_text = current["summary_text"] if current else None

    # New cutoff: compact everything up to 7 days ago (keep last 7 days as recent detail)
    new_cutoff = (date.today() - timedelta(days=7)).isoformat()

    if new_cutoff <= old_cutoff:
        return {"status": "no_new_meals", "cutoff_date": old_cutoff}

    meals = await meal_history_repo.get_meals_for_compaction(old_cutoff, new_cutoff)
    if not meals:
        return {"status": "no_new_meals", "cutoff_date": old_cutoff}

    meals_text = _format_recent_meals(meals)
    prompt = build_compaction_prompt(old_summary_text, meals_text)

    profile = await profile_service.get_profile()
    backend = get_llm_backend(mode=profile.get("llm_mode"))
    response = await backend.complete(prompt)

    result = await meal_history_repo.create_summary(
        summary_text=response.text.strip(),
        cutoff_date=new_cutoff,
        meal_count=len(meals),
        llm_backend=response.backend,
        model=response.model,
        raw_response=response.text,
    )
    result["status"] = "compacted"
    return result


async def list_history_versions() -> list[dict]:
    return await meal_history_repo.list_summaries()


async def rollback_history(version: int) -> dict:
    return await meal_history_repo.rollback_to_version(version)
