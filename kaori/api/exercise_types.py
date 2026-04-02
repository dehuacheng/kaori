from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from kaori.services import workout_service
from kaori.storage.file_store import save_photo
from kaori.models.workout import ExerciseTypeCreate, ExerciseTypeUpdate

MEDIA_TYPE_MAP = {
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/png": "image/png",
    "image/webp": "image/webp",
    "image/heic": "image/jpeg",
}

router = APIRouter(prefix="/exercise-types", tags=["api-exercise-types"])


@router.get("")
async def list_exercise_types(category: str | None = None, enabled_only: bool = False):
    if enabled_only:
        return await workout_service.list_enabled_exercise_types()
    return await workout_service.list_exercise_types(category)


@router.post("")
async def create_exercise_type(body: ExerciseTypeCreate):
    result = await workout_service.create_exercise_type(
        name=body.name, category=body.category, notes=body.notes,
    )
    return result


@router.post("/identify")
async def identify_exercise(
    photo: UploadFile = File(...),
    hint: str = Form(None),
):
    """Create exercise from photo immediately, then LLM fills metadata async."""
    import asyncio
    image_bytes = await photo.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty photo")
    media_type = MEDIA_TYPE_MAP.get(photo.content_type, "image/jpeg")
    ext = ".jpg" if "jpeg" in media_type else f".{media_type.split('/')[-1]}"
    photo_path = save_photo(image_bytes, ext)

    result = await workout_service.create_exercise_from_photo(photo_path, user_hint=hint)
    asyncio.create_task(
        workout_service.run_exercise_identification(result["id"], photo_path, user_hint=hint)
    )
    return result


@router.get("/{type_id}")
async def get_exercise_type(type_id: int):
    result = await workout_service.get_exercise_type(type_id)
    if not result:
        raise HTTPException(status_code=404, detail="Exercise type not found")
    return result


@router.put("/{type_id}")
async def update_exercise_type(type_id: int, body: ExerciseTypeUpdate):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await workout_service.update_exercise_type(type_id, **updates)
    if not result:
        raise HTTPException(status_code=404, detail="Exercise type not found")
    return result


@router.post("/{type_id}/enable")
async def enable_exercise_type(type_id: int):
    await workout_service.toggle_exercise_type(type_id, enabled=True)
    return {"id": type_id, "is_enabled": True}


@router.post("/{type_id}/disable")
async def disable_exercise_type(type_id: int):
    await workout_service.toggle_exercise_type(type_id, enabled=False)
    return {"id": type_id, "is_enabled": False}


@router.delete("/{type_id}")
async def delete_exercise_type(type_id: int):
    try:
        deleted = await workout_service.delete_exercise_type(type_id)
        return {"id": type_id, "deleted": deleted}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
