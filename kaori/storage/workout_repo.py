from kaori.database import get_db


# ---------------------------------------------------------------------------
# Workouts
# ---------------------------------------------------------------------------

async def list_workouts(
    *,
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 30,
) -> list[dict]:
    """List workouts with exercise count. Supports single date or date range."""
    db = await get_db()
    try:
        conditions: list[str] = []
        params: list = []
        if date:
            conditions.append("w.date = ?")
            params.append(date)
        else:
            if start_date:
                conditions.append("w.date >= ?")
                params.append(start_date)
            if end_date:
                conditions.append("w.date <= ?")
                params.append(end_date)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        cursor = await db.execute(
            f"SELECT w.*, COUNT(we.id) as exercise_count "
            f"FROM workouts w "
            f"LEFT JOIN workout_exercises we ON we.workout_id = w.id "
            f"{where} "
            f"GROUP BY w.id "
            f"ORDER BY w.date DESC, w.created_at DESC "
            f"LIMIT ?",
            params + [limit],
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def get_workout(workout_id: int) -> dict | None:
    """Get a workout with its full exercise + set tree."""
    db = await get_db()
    try:
        # Get workout
        cursor = await db.execute(
            "SELECT * FROM workouts WHERE id = ?", (workout_id,)
        )
        workout_row = await cursor.fetchone()
        if not workout_row:
            return None
        workout = dict(workout_row)

        # Get exercises with type info
        cursor = await db.execute(
            "SELECT we.*, et.name as exercise_name, et.category as exercise_category "
            "FROM workout_exercises we "
            "JOIN exercise_types et ON et.id = we.exercise_type_id "
            "WHERE we.workout_id = ? "
            "ORDER BY we.order_index",
            (workout_id,),
        )
        exercises = []
        exercise_ids = []
        for row in await cursor.fetchall():
            ex = dict(row)
            ex["sets"] = []
            exercises.append(ex)
            exercise_ids.append(ex["id"])

        # Get all sets for these exercises in one query
        if exercise_ids:
            placeholders = ",".join("?" * len(exercise_ids))
            cursor = await db.execute(
                f"SELECT * FROM exercise_sets "
                f"WHERE workout_exercise_id IN ({placeholders}) "
                f"ORDER BY workout_exercise_id, set_number",
                exercise_ids,
            )
            sets_by_exercise: dict[int, list[dict]] = {}
            for row in await cursor.fetchall():
                s = dict(row)
                sets_by_exercise.setdefault(s["workout_exercise_id"], []).append(s)
            for ex in exercises:
                ex["sets"] = sets_by_exercise.get(ex["id"], [])

        workout["exercises"] = exercises
        return workout
    finally:
        await db.close()


async def create_workout(
    *, date: str, notes: str | None = None,
    activity_type: str = "traditionalStrengthTraining",
    duration_minutes: float | None = None,
) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO workouts (date, notes, activity_type, duration_minutes) "
            "VALUES (?, ?, ?, ?)",
            (date, notes, activity_type, duration_minutes),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def update_workout(workout_id: int, **fields) -> bool:
    allowed = {"date", "notes", "activity_type", "duration_minutes", "calories_burned", "summary"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return False
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [workout_id]
    db = await get_db()
    try:
        cursor = await db.execute(
            f"UPDATE workouts SET {set_clause} WHERE id = ?", values
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def delete_workout(workout_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM workouts WHERE id = ?", (workout_id,)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# Workout Exercises
# ---------------------------------------------------------------------------

async def add_exercise(
    *,
    workout_id: int,
    exercise_type_id: int,
    order_index: int = 0,
    notes: str | None = None,
) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO workout_exercises (workout_id, exercise_type_id, order_index, notes) "
            "VALUES (?, ?, ?, ?)",
            (workout_id, exercise_type_id, order_index, notes),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def update_exercise(exercise_id: int, **fields) -> bool:
    allowed = {"exercise_type_id", "order_index", "notes"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return False
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [exercise_id]
    db = await get_db()
    try:
        cursor = await db.execute(
            f"UPDATE workout_exercises SET {set_clause} WHERE id = ?", values
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def delete_exercise(exercise_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM workout_exercises WHERE id = ?", (exercise_id,)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# Exercise Sets
# ---------------------------------------------------------------------------

async def add_set(
    *,
    workout_exercise_id: int,
    set_number: int,
    reps: int | None = None,
    weight_kg: float | None = None,
    duration_seconds: int | None = None,
    notes: str | None = None,
) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO exercise_sets "
            "(workout_exercise_id, set_number, reps, weight_kg, duration_seconds, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (workout_exercise_id, set_number, reps, weight_kg, duration_seconds, notes),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def update_set(set_id: int, **fields) -> bool:
    allowed = {"set_number", "reps", "weight_kg", "duration_seconds", "notes"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    # Allow setting fields to None (e.g., clearing reps for a timed exercise)
    updates = {k: v for k, v in updates.items() if k in fields}
    if not updates:
        return False
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [set_id]
    db = await get_db()
    try:
        cursor = await db.execute(
            f"UPDATE exercise_sets SET {set_clause} WHERE id = ?", values
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def delete_set(set_id: int) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM exercise_sets WHERE id = ?", (set_id,)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# Bulk creation (single transaction)
# ---------------------------------------------------------------------------

async def create_workout_with_exercises(
    *,
    date: str,
    notes: str | None = None,
    activity_type: str = "traditionalStrengthTraining",
    duration_minutes: float | None = None,
    exercises: list[dict] | None = None,
) -> int:
    """Create a workout with nested exercises and sets in a single transaction."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO workouts (date, notes, activity_type, duration_minutes) "
            "VALUES (?, ?, ?, ?)",
            (date, notes, activity_type, duration_minutes),
        )
        workout_id = cursor.lastrowid

        for ex in (exercises or []):
            cursor = await db.execute(
                "INSERT INTO workout_exercises (workout_id, exercise_type_id, order_index, notes) "
                "VALUES (?, ?, ?, ?)",
                (workout_id, ex["exercise_type_id"], ex.get("order_index", 0), ex.get("notes")),
            )
            exercise_id = cursor.lastrowid
            for s in (ex.get("sets") or []):
                await db.execute(
                    "INSERT INTO exercise_sets "
                    "(workout_exercise_id, set_number, reps, weight_kg, duration_seconds, notes) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        exercise_id,
                        s["set_number"],
                        s.get("reps"),
                        s.get("weight_kg"),
                        s.get("duration_seconds"),
                        s.get("notes"),
                    ),
                )

        await db.commit()
        return workout_id
    finally:
        await db.close()
