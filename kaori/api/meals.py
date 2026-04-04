import asyncio
import json
from datetime import date
from typing import Optional

from pydantic import BaseModel
from fastapi import APIRouter, UploadFile, File, Form

from kaori.services import meal_service
from kaori.storage import meal_repo
from kaori.storage.file_store import save_photo

router = APIRouter(prefix="/meals", tags=["api-meals"])

class MealUpdate(BaseModel):
    meal_date: str | None = None
    meal_type: str | None = None
    description: str | None = None
    calories: int | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    notes: str | None = None


MEDIA_TYPE_MAP = {
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/png": "image/png",
    "image/webp": "image/webp",
    "image/heic": "image/jpeg",
}


@router.get("")
async def list_meals(date: str | None = None):
    target_date = date or __import__("datetime").date.today().isoformat()
    meals = await meal_service.list_by_date(target_date)
    totals = await meal_service.get_totals(target_date)
    return {"date": target_date, "meals": meals, "totals": totals}


@router.post("/compact-history")
async def compact_history():
    return await meal_service.compact_meal_history()


@router.get("/history-versions")
async def list_history_versions():
    return await meal_service.list_history_versions()


@router.post("/history-versions/{version}/rollback")
async def rollback_history(version: int):
    return await meal_service.rollback_history(version)


@router.post("/{meal_id}/reprocess")
async def reprocess_meal(meal_id: int):
    """Re-run LLM analysis on an existing meal."""
    raw = await meal_repo.get_raw(meal_id)
    if not raw:
        return {"error": "not found"}, 404

    analysis_id = await meal_service.reprocess_meal(meal_id)

    photo_paths_raw = raw.get("photo_paths")
    photo_paths = json.loads(photo_paths_raw) if photo_paths_raw else None
    asyncio.create_task(meal_service.run_analysis(
        meal_id, photo_path=raw.get("photo_path"), photo_paths=photo_paths,
        description=raw.get("description"), notes=raw.get("notes"),
    ))

    return {"meal_id": meal_id, "analysis_id": analysis_id, "analysis_status": "pending"}


@router.get("/{meal_id}/analyses")
async def list_analyses(meal_id: int):
    """List all analysis versions for a meal."""
    analyses = await meal_service.list_analyses(meal_id)
    return {"meal_id": meal_id, "analyses": analyses}


@router.post("/{meal_id}/analyses/{analysis_id}/activate")
async def activate_analysis(meal_id: int, analysis_id: int):
    """Activate a specific analysis version (rollback)."""
    result = await meal_service.rollback_analysis(meal_id, analysis_id)
    return result


@router.get("/{meal_id}")
async def get_meal(meal_id: int):
    meal = await meal_service.get_by_id(meal_id)
    if not meal:
        return {"error": "not found"}, 404
    return meal


@router.post("")
async def create_meal(
    meal_date: str = Form(None),
    meal_type: str = Form("snack"),
    description: str = Form(None),
    notes: str = Form(None),
    photo: UploadFile | None = File(None),
    photos: Optional[list[UploadFile]] = File(None),
):
    today = meal_date or date.today().isoformat()
    photo_path = None
    photo_paths: list[str] = []

    # Handle multiple photos (new multi-photo field)
    if photos:
        for p in photos:
            if p.size and p.size > 0:
                image_bytes = await p.read()
                media_type = MEDIA_TYPE_MAP.get(p.content_type, "image/jpeg")
                ext = ".jpg" if "jpeg" in media_type else f".{media_type.split('/')[-1]}"
                photo_paths.append(save_photo(image_bytes, ext))
        if photo_paths:
            photo_path = photo_paths[0]  # first photo as primary for backward compat

    # Fall back to single photo field
    if not photo_paths and photo and photo.size and photo.size > 0:
        image_bytes = await photo.read()
        media_type = MEDIA_TYPE_MAP.get(photo.content_type, "image/jpeg")
        ext = ".jpg" if "jpeg" in media_type else f".{media_type.split('/')[-1]}"
        photo_path = save_photo(image_bytes, ext)
        photo_paths = [photo_path]

    meal_type = meal_service.auto_detect_meal_type(meal_type)

    meal_id, needs_analysis = await meal_service.create(
        meal_date=today, meal_type=meal_type,
        description=description, photo_path=photo_path,
        photo_paths=photo_paths or None, notes=notes,
    )

    if needs_analysis:
        asyncio.create_task(meal_service.run_analysis(
            meal_id, photo_path=photo_path, photo_paths=photo_paths or None,
            description=description, notes=notes,
        ))

    return {"id": meal_id, "date": today, "analysis_status": "pending" if needs_analysis else "done"}


@router.put("/{meal_id}")
async def update_meal(meal_id: int, body: MealUpdate):
    meal_date = await meal_service.update(
        meal_id, date=body.meal_date, meal_type=body.meal_type,
        description=body.description, calories=body.calories,
        protein_g=body.protein_g, carbs_g=body.carbs_g,
        fat_g=body.fat_g, notes=body.notes,
    )
    return {"id": meal_id, "date": meal_date}


@router.delete("/{meal_id}")
async def delete_meal(meal_id: int):
    meal_date = await meal_service.delete(meal_id)
    return {"id": meal_id, "date": meal_date}
