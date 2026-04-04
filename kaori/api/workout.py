from fastapi import APIRouter, HTTPException

from kaori.services import workout_service
from kaori.models.workout import (
    WorkoutCreate, WorkoutUpdate,
    WorkoutExerciseCreate, WorkoutExerciseUpdate,
    SetCreate, SetUpdate,
)

router = APIRouter(prefix="/workouts", tags=["api-workouts"])


# ---------------------------------------------------------------------------
# Workouts
# ---------------------------------------------------------------------------

@router.get("")
async def list_workouts(
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 30,
):
    return await workout_service.list_workouts(
        target_date=date, start_date=start_date, end_date=end_date, limit=limit,
    )


@router.post("")
async def create_workout(body: WorkoutCreate):
    exercises = None
    if body.exercises:
        exercises = [ex.model_dump() for ex in body.exercises]
    result = await workout_service.create_workout(
        workout_date=body.date, notes=body.notes,
        activity_type=body.activity_type, duration_minutes=body.duration_minutes,
        calories_burned=body.calories_burned, source=body.source,
        exercises=exercises,
    )
    return result


@router.get("/{workout_id}")
async def get_workout(workout_id: int):
    result = await workout_service.get_workout(workout_id)
    if not result:
        raise HTTPException(status_code=404, detail="Workout not found")
    return result


@router.put("/{workout_id}")
async def update_workout(workout_id: int, body: WorkoutUpdate):
    updates = body.model_dump(exclude_none=True)
    result = await workout_service.update_workout(workout_id, **updates)
    if not result:
        raise HTTPException(status_code=404, detail="Workout not found")
    return result


@router.delete("/{workout_id}")
async def delete_workout(workout_id: int):
    deleted = await workout_service.delete_workout(workout_id)
    return {"id": workout_id, "deleted": deleted}


@router.post("/{workout_id}/summarize")
async def summarize_workout(workout_id: int):
    """Use LLM to analyze the workout with personal trainer feedback."""
    try:
        result = await workout_service.summarize_workout(workout_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{workout_id}/analysis")
async def get_workout_analysis(workout_id: int):
    """Get the active analysis for a workout."""
    result = await workout_service.get_workout_analysis(workout_id)
    if not result:
        raise HTTPException(status_code=404, detail="No analysis found")
    return result


# ---------------------------------------------------------------------------
# Workout exercises
# ---------------------------------------------------------------------------

@router.post("/{workout_id}/exercises")
async def add_exercise(workout_id: int, body: WorkoutExerciseCreate):
    exercise_id = await workout_service.add_exercise(
        workout_id=workout_id,
        exercise_type_id=body.exercise_type_id,
        order_index=body.order_index,
        notes=body.notes,
    )
    return {"id": exercise_id, "workout_id": workout_id}


@router.put("/{workout_id}/exercises/{exercise_id}")
async def update_exercise(workout_id: int, exercise_id: int, body: WorkoutExerciseUpdate):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = await workout_service.update_exercise(exercise_id, **updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return {"id": exercise_id, "updated": True}


@router.delete("/{workout_id}/exercises/{exercise_id}")
async def delete_exercise(workout_id: int, exercise_id: int):
    deleted = await workout_service.delete_exercise(exercise_id)
    return {"id": exercise_id, "deleted": deleted}


# ---------------------------------------------------------------------------
# Exercise sets
# ---------------------------------------------------------------------------

@router.post("/{workout_id}/exercises/{exercise_id}/sets")
async def add_set(workout_id: int, exercise_id: int, body: SetCreate):
    set_id = await workout_service.add_set(
        workout_exercise_id=exercise_id,
        set_number=body.set_number,
        reps=body.reps,
        weight_kg=body.weight_kg,
        duration_seconds=body.duration_seconds,
        notes=body.notes,
    )
    return {"id": set_id, "workout_exercise_id": exercise_id}


@router.put("/{workout_id}/exercises/{exercise_id}/sets/{set_id}")
async def update_set(workout_id: int, exercise_id: int, set_id: int, body: SetUpdate):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = await workout_service.update_set(set_id, **updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Set not found")
    return {"id": set_id, "updated": True}


@router.delete("/{workout_id}/exercises/{exercise_id}/sets/{set_id}")
async def delete_set(workout_id: int, exercise_id: int, set_id: int):
    deleted = await workout_service.delete_set(set_id)
    return {"id": set_id, "deleted": deleted}
