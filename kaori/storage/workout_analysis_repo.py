import json

from kaori.database import get_db


async def create(
    *,
    workout_id: int,
    total_sets: int | None = None,
    total_reps: int | None = None,
    total_volume_kg: float | None = None,
    estimated_calories: float | None = None,
    intensity: str | None = None,
    muscle_groups: list[str] | None = None,
    summary: str | None = None,
    trainer_notes: str | None = None,
    progress_notes: str | None = None,
    recommendations: str | None = None,
    llm_backend: str | None = None,
    model: str | None = None,
    raw_response: str | None = None,
    error_message: str | None = None,
) -> int:
    """Create a new workout analysis. Deactivates previous analyses for this workout."""
    muscle_groups_json = json.dumps(muscle_groups) if muscle_groups else None
    db = await get_db()
    try:
        # Deactivate previous analyses for this workout
        await db.execute(
            "UPDATE workout_analyses SET is_active = 0 WHERE workout_id = ? AND is_active = 1",
            (workout_id,),
        )
        cursor = await db.execute(
            "INSERT INTO workout_analyses "
            "(workout_id, total_sets, total_reps, total_volume_kg, estimated_calories, "
            " intensity, muscle_groups_json, summary, trainer_notes, progress_notes, "
            " recommendations, llm_backend, model, raw_response, error_message) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (workout_id, total_sets, total_reps, total_volume_kg, estimated_calories,
             intensity, muscle_groups_json, summary, trainer_notes, progress_notes,
             recommendations, llm_backend, model, raw_response, error_message),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def get_active(workout_id: int) -> dict | None:
    """Get the active (latest) analysis for a workout."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM workout_analyses "
            "WHERE workout_id = ? AND is_active = 1 "
            "ORDER BY id DESC LIMIT 1",
            (workout_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        result = dict(row)
        if result.get("muscle_groups_json"):
            result["muscle_groups"] = json.loads(result["muscle_groups_json"])
        else:
            result["muscle_groups"] = []
        return result
    finally:
        await db.close()


async def get_recent_analyses(limit: int = 10) -> list[dict]:
    """Get recent active workout analyses with workout date, for LLM context."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT wa.*, w.date as workout_date "
            "FROM workout_analyses wa "
            "JOIN workouts w ON w.id = wa.workout_id "
            "WHERE wa.is_active = 1 "
            "ORDER BY w.date DESC, wa.id DESC "
            "LIMIT ?",
            (limit,),
        )
        results = []
        for row in await cursor.fetchall():
            d = dict(row)
            if d.get("muscle_groups_json"):
                d["muscle_groups"] = json.loads(d["muscle_groups_json"])
            else:
                d["muscle_groups"] = []
            results.append(d)
        return results
    finally:
        await db.close()
