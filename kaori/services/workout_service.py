import json
import logging
from datetime import date

from kaori.llm import get_llm_backend, LLMError
from kaori.llm.prompts import build_exercise_identification_prompt, build_workout_summary_prompt
from kaori.storage.file_store import get_resized_image_bytes
from kaori.models.workout import ExerciseIdentification, WorkoutSummary
from kaori.services import profile_service
from kaori.storage import exercise_type_repo, workout_repo, timer_preset_repo, workout_analysis_repo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exercise types
# ---------------------------------------------------------------------------

async def list_exercise_types(category: str | None = None) -> list[dict]:
    return await exercise_type_repo.list_all(category)


async def list_enabled_exercise_types() -> list[dict]:
    """List only enabled exercise types (for workout picker)."""
    return await exercise_type_repo.list_enabled()


async def get_exercise_type(type_id: int) -> dict | None:
    return await exercise_type_repo.get_by_id(type_id)


async def create_exercise_type(
    *, name: str, category: str | None = None, notes: str | None = None,
) -> dict:
    type_id = await exercise_type_repo.create(
        name=name, category=category, notes=notes, is_standard=0, is_enabled=1,
    )
    return await exercise_type_repo.get_by_id(type_id)


async def update_exercise_type(type_id: int, **fields) -> dict | None:
    await exercise_type_repo.update(type_id, **fields)
    return await exercise_type_repo.get_by_id(type_id)


async def toggle_exercise_type(type_id: int, enabled: bool) -> bool:
    return await exercise_type_repo.set_enabled(type_id, enabled)


async def delete_exercise_type(type_id: int) -> bool:
    return await exercise_type_repo.delete(type_id)


# ---------------------------------------------------------------------------
# Exercise identification from photo (LLM)
# ---------------------------------------------------------------------------

def _parse_identification_response(raw_text: str) -> ExerciseIdentification:
    """Parse LLM JSON response into ExerciseIdentification."""
    text = raw_text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines).strip()
    data = json.loads(text)
    return ExerciseIdentification(**data)


import uuid as _uuid


async def create_exercise_from_photo(
    photo_path: str, user_hint: str | None = None,
) -> dict:
    """Create an exercise type immediately from a photo. LLM fills metadata async.

    Returns the new exercise type dict right away (status='pending').
    """
    # Create with a temporary unique name so the user sees it immediately
    placeholder_name = f"New Exercise ({_uuid.uuid4().hex[:6]})"
    logger.debug("create_exercise_from_photo: photo_path=%s, hint=%s", photo_path, user_hint)
    type_id = await exercise_type_repo.create(
        name=placeholder_name,
        category=None,
        photo_path=photo_path,
        notes=user_hint,
        is_standard=0,
        is_enabled=1,
        status="pending",
    )
    result = await exercise_type_repo.get_by_id(type_id)
    logger.debug("create_exercise_from_photo: created id=%d, photo_path in db=%s", type_id, result.get("photo_path"))
    return result


async def run_exercise_identification(type_id: int, photo_path: str, user_hint: str | None = None):
    """Background task: LLM identifies the exercise and updates the record."""
    logger.info("run_exercise_identification: starting for type_id=%d, photo_path=%s", type_id, photo_path)
    backend = get_llm_backend()
    prompt = build_exercise_identification_prompt(user_hint)

    try:
        image_bytes = get_resized_image_bytes(photo_path)
        logger.debug("run_exercise_identification: resized image=%d bytes", len(image_bytes))
    except Exception as e:
        logger.error("Failed to read/resize image for type %d: %s", type_id, e, exc_info=True)
        await exercise_type_repo.update(type_id, status="failed")
        return

    try:
        response = await backend.analyze_image(image_bytes, prompt)
        logger.debug("run_exercise_identification: LLM response text=%s", response.text[:500] if response.text else None)
        identification = _parse_identification_response(response.text)
        logger.info("run_exercise_identification: identified as '%s' (%s)", identification.name, identification.category)
    except (LLMError, json.JSONDecodeError, KeyError) as e:
        logger.error("Exercise identification failed for type %d: %s", type_id, e, exc_info=True)
        await exercise_type_repo.update(type_id, status="failed")
        return
    except Exception as e:
        logger.error("Exercise identification unexpected error for type %d: %s", type_id, e, exc_info=True)
        await exercise_type_repo.update(type_id, status="failed")
        return

    # Check if an exercise with that name already exists
    existing = await exercise_type_repo.get_by_name(identification.name)
    if existing and existing["id"] != type_id:
        # Duplicate — update the photo-created entry to match, but use a unique name variant
        final_name = f"{identification.name} (photo)"
        # Check that variant doesn't also exist
        variant_check = await exercise_type_repo.get_by_name(final_name)
        if variant_check:
            final_name = f"{identification.name} ({_uuid.uuid4().hex[:4]})"
    else:
        final_name = identification.name

    await exercise_type_repo.update(
        type_id,
        name=final_name,
        category=identification.category,
        notes=identification.description,
        status="done",
    )


# ---------------------------------------------------------------------------
# Workouts
# ---------------------------------------------------------------------------

async def list_workouts(
    *,
    target_date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 30,
) -> list[dict]:
    return await workout_repo.list_workouts(
        date=target_date, start_date=start_date, end_date=end_date, limit=limit,
    )


async def get_workout(workout_id: int) -> dict | None:
    return await workout_repo.get_workout(workout_id)


async def create_workout(
    *,
    workout_date: str | None = None,
    notes: str | None = None,
    activity_type: str = "traditionalStrengthTraining",
    duration_minutes: float | None = None,
    calories_burned: float | None = None,
    source: str = "manual",
    exercises: list[dict] | None = None,
) -> dict:
    """Create a workout, optionally with nested exercises and sets."""
    target_date = workout_date or date.today().isoformat()

    if exercises:
        workout_id = await workout_repo.create_workout_with_exercises(
            date=target_date, notes=notes, activity_type=activity_type,
            duration_minutes=duration_minutes, calories_burned=calories_burned,
            source=source, exercises=exercises,
        )
    else:
        workout_id = await workout_repo.create_workout(
            date=target_date, notes=notes, activity_type=activity_type,
            duration_minutes=duration_minutes, calories_burned=calories_burned,
            source=source,
        )

    return await workout_repo.get_workout(workout_id)


async def update_workout(workout_id: int, **fields) -> dict | None:
    await workout_repo.update_workout(workout_id, **fields)
    return await workout_repo.get_workout(workout_id)


async def delete_workout(workout_id: int) -> bool:
    return await workout_repo.delete_workout(workout_id)


# ---------------------------------------------------------------------------
# Workout summary (LLM)
# ---------------------------------------------------------------------------

def _format_workout_for_llm(workout: dict) -> str:
    """Format a workout with exercises/sets into text for LLM prompt."""
    lines = [f"Date: {workout['date']}"]
    if workout.get("notes"):
        lines.append(f"Notes: {workout['notes']}")
    if workout.get("activity_type"):
        lines.append(f"Activity: {workout['activity_type']}")
    if workout.get("duration_minutes"):
        lines.append(f"Duration: {workout['duration_minutes']:.0f} minutes")
    lines.append("")
    for ex in workout.get("exercises", []):
        lines.append(f"### {ex['exercise_name']} ({ex.get('exercise_category', 'unknown')})")
        for s in ex.get("sets", []):
            parts = [f"Set {s['set_number']}:"]
            if s.get("reps") is not None:
                parts.append(f"{s['reps']} reps")
            if s.get("weight_kg") is not None:
                parts.append(f"@ {s['weight_kg']} kg")
            if s.get("duration_seconds") is not None:
                parts.append(f"for {s['duration_seconds']}s")
            lines.append("  " + " ".join(parts))
        lines.append("")
    return "\n".join(lines)


def _parse_summary_response(raw_text: str) -> WorkoutSummary:
    """Parse LLM JSON response into WorkoutSummary."""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines).strip()
    data = json.loads(text)
    return WorkoutSummary(**data)


def _format_history_for_llm(analyses: list[dict]) -> str:
    """Format recent workout analyses into context text for LLM."""
    if not analyses:
        return ""
    lines = []
    for a in analyses:
        parts = [f"- {a.get('workout_date', '?')}:"]
        if a.get("summary"):
            parts.append(a["summary"])
        if a.get("total_volume_kg"):
            parts.append(f"Volume: {a['total_volume_kg']:.0f} kg.")
        if a.get("estimated_calories"):
            parts.append(f"Calories: {a['estimated_calories']:.0f}.")
        if a.get("intensity"):
            parts.append(f"Intensity: {a['intensity']}.")
        if a.get("muscle_groups"):
            parts.append(f"Muscles: {', '.join(a['muscle_groups'])}.")
        lines.append(" ".join(parts))
    return "\n".join(lines)


async def get_workout_analysis(workout_id: int) -> dict | None:
    """Get the active analysis for a workout."""
    return await workout_analysis_repo.get_active(workout_id)


async def summarize_workout(workout_id: int) -> dict:
    """Use LLM to summarize a workout with personal trainer analysis."""
    workout = await workout_repo.get_workout(workout_id)
    if not workout:
        raise ValueError("Workout not found")
    if not workout.get("exercises"):
        raise ValueError("Workout has no exercises to summarize")

    # Get user weight for better calorie estimation
    user_weight_kg = None
    try:
        profile = await profile_service.get_profile()
        user_weight_kg = profile.get("latest_weight_kg")
    except Exception:
        pass

    # Fetch recent workout analyses for context
    recent_analyses = await workout_analysis_repo.get_recent_analyses(limit=10)
    # Exclude the current workout from history
    recent_analyses = [a for a in recent_analyses if a["workout_id"] != workout_id]
    history_text = _format_history_for_llm(recent_analyses) or None

    workout_text = _format_workout_for_llm(workout)
    prompt = build_workout_summary_prompt(workout_text, user_weight_kg, history_text)

    backend = get_llm_backend()
    try:
        response = await backend.complete(prompt)
        summary = _parse_summary_response(response.text)
    except (LLMError, json.JSONDecodeError, KeyError) as e:
        logger.error("Workout summary failed: %s", e)
        raise ValueError(f"Could not summarize workout: {e}") from e

    # Store structured analysis in workout_analyses table
    await workout_analysis_repo.create(
        workout_id=workout_id,
        total_sets=summary.total_sets,
        total_reps=summary.total_reps,
        total_volume_kg=summary.total_volume_kg,
        estimated_calories=summary.estimated_calories,
        intensity=summary.intensity,
        muscle_groups=summary.muscle_groups_worked,
        summary=summary.summary,
        trainer_notes=summary.trainer_notes,
        progress_notes=summary.progress_notes,
        recommendations=summary.recommendations,
        llm_backend=response.backend,
        model=response.model,
        raw_response=response.text,
    )

    # Also update workout row for backwards compat
    await workout_repo.update_workout(
        workout_id,
        calories_burned=summary.estimated_calories,
        summary=summary.summary,
    )

    return {
        "workout_id": workout_id,
        **summary.model_dump(),
    }


# ---------------------------------------------------------------------------
# Workout exercises
# ---------------------------------------------------------------------------

async def add_exercise(
    *, workout_id: int, exercise_type_id: int, order_index: int = 0,
    notes: str | None = None,
) -> int:
    return await workout_repo.add_exercise(
        workout_id=workout_id, exercise_type_id=exercise_type_id,
        order_index=order_index, notes=notes,
    )


async def update_exercise(exercise_id: int, **fields) -> bool:
    return await workout_repo.update_exercise(exercise_id, **fields)


async def delete_exercise(exercise_id: int) -> bool:
    return await workout_repo.delete_exercise(exercise_id)


# ---------------------------------------------------------------------------
# Exercise sets
# ---------------------------------------------------------------------------

async def add_set(
    *, workout_exercise_id: int, set_number: int,
    reps: int | None = None, weight_kg: float | None = None,
    duration_seconds: int | None = None, notes: str | None = None,
) -> int:
    return await workout_repo.add_set(
        workout_exercise_id=workout_exercise_id, set_number=set_number,
        reps=reps, weight_kg=weight_kg, duration_seconds=duration_seconds,
        notes=notes,
    )


async def update_set(set_id: int, **fields) -> bool:
    return await workout_repo.update_set(set_id, **fields)


async def delete_set(set_id: int) -> bool:
    return await workout_repo.delete_set(set_id)


# ---------------------------------------------------------------------------
# Timer presets
# ---------------------------------------------------------------------------

async def list_timer_presets() -> list[dict]:
    return await timer_preset_repo.list_all()


async def get_timer_preset(preset_id: int) -> dict | None:
    return await timer_preset_repo.get_by_id(preset_id)


async def create_timer_preset(
    *, name: str, rest_seconds: int = 60, work_seconds: int = 0,
    sets: int = 3, notes: str | None = None,
) -> dict:
    preset_id = await timer_preset_repo.create(
        name=name, rest_seconds=rest_seconds, work_seconds=work_seconds,
        sets=sets, notes=notes,
    )
    return await timer_preset_repo.get_by_id(preset_id)


async def update_timer_preset(preset_id: int, **fields) -> dict | None:
    await timer_preset_repo.update(preset_id, **fields)
    return await timer_preset_repo.get_by_id(preset_id)


async def delete_timer_preset(preset_id: int) -> bool:
    return await timer_preset_repo.delete(preset_id)
