from fastapi import APIRouter, HTTPException

from kaori.services import workout_service
from kaori.models.workout import TimerPresetCreate, TimerPresetUpdate

router = APIRouter(prefix="/timer-presets", tags=["api-timer-presets"])


@router.get("")
async def list_timer_presets():
    return await workout_service.list_timer_presets()


@router.post("")
async def create_timer_preset(body: TimerPresetCreate):
    result = await workout_service.create_timer_preset(
        name=body.name, rest_seconds=body.rest_seconds,
        work_seconds=body.work_seconds, sets=body.sets, notes=body.notes,
    )
    return result


@router.get("/{preset_id}")
async def get_timer_preset(preset_id: int):
    result = await workout_service.get_timer_preset(preset_id)
    if not result:
        raise HTTPException(status_code=404, detail="Timer preset not found")
    return result


@router.put("/{preset_id}")
async def update_timer_preset(preset_id: int, body: TimerPresetUpdate):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await workout_service.update_timer_preset(preset_id, **updates)
    if not result:
        raise HTTPException(status_code=404, detail="Timer preset not found")
    return result


@router.delete("/{preset_id}")
async def delete_timer_preset(preset_id: int):
    deleted = await workout_service.delete_timer_preset(preset_id)
    return {"id": preset_id, "deleted": deleted}
