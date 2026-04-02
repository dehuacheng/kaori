import json

from kaori.database import get_db


async def create(meal_id: int) -> int:
    """Create a pending analysis entry. Deactivates previous analyses. Returns analysis ID."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE meal_analyses SET is_active = 0 WHERE meal_id = ?",
            (meal_id,),
        )
        cursor = await db.execute(
            "INSERT INTO meal_analyses (meal_id, status, is_active) VALUES (?, 'pending', 1)",
            (meal_id,),
        )
        analysis_id = cursor.lastrowid
        await db.commit()
        return analysis_id
    finally:
        await db.close()


async def set_analyzing(analysis_id: int):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE meal_analyses SET status = 'analyzing' WHERE id = ?",
            (analysis_id,),
        )
        await db.commit()
    finally:
        await db.close()


async def set_done(analysis_id: int, *, description: str, items: list[str],
                   calories: int, protein_g: float, carbs_g: float, fat_g: float,
                   confidence: str, llm_backend: str, model: str, raw_response: str):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE meal_analyses SET status = 'done', description = ?, items_json = ?, "
            "calories = ?, protein_g = ?, carbs_g = ?, fat_g = ?, confidence = ?, "
            "llm_backend = ?, model = ?, raw_response = ?, completed_at = datetime('now') "
            "WHERE id = ?",
            (description, json.dumps(items), calories, protein_g, carbs_g, fat_g,
             confidence, llm_backend, model, raw_response, analysis_id),
        )
        await db.commit()
    finally:
        await db.close()


async def set_failed(analysis_id: int, error_message: str):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE meal_analyses SET status = 'failed', error_message = ?, "
            "completed_at = datetime('now') WHERE id = ?",
            (error_message, analysis_id),
        )
        await db.commit()
    finally:
        await db.close()


async def get_latest_for_meal(meal_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM meal_analyses WHERE meal_id = ? AND is_active = 1",
            (meal_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def list_for_meal(meal_id: int) -> list[dict]:
    """List all analyses for a meal, newest first."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, status, is_active, description, calories, protein_g, carbs_g, fat_g, "
            "confidence, llm_backend, model, created_at, completed_at "
            "FROM meal_analyses WHERE meal_id = ? ORDER BY id DESC",
            (meal_id,),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()


async def set_active(analysis_id: int, meal_id: int):
    """Activate a specific analysis and deactivate all others for the meal."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE meal_analyses SET is_active = 0 WHERE meal_id = ?",
            (meal_id,),
        )
        await db.execute(
            "UPDATE meal_analyses SET is_active = 1 WHERE id = ? AND meal_id = ?",
            (analysis_id, meal_id),
        )
        await db.commit()
    finally:
        await db.close()
