import asyncio

from pydantic import BaseModel
from fastapi import APIRouter

from kaori.services import weight_service

router = APIRouter(prefix="/weight", tags=["api-weight"])


class WeightCreate(BaseModel):
    weight_date: str | None = None
    weight_kg: float
    notes: str | None = None


class WeightUpdate(BaseModel):
    weight_kg: float
    notes: str | None = None


class BulkImportEntry(BaseModel):
    date: str
    weight_kg: float
    notes: str | None = None


class BulkImportRequest(BaseModel):
    entries: list[BulkImportEntry]


@router.get("")
async def get_weight(limit: int = 365):
    return await weight_service.get_trends(limit=limit)


@router.post("")
async def log_weight(body: WeightCreate):
    entry_id = await weight_service.log(
        weight_date=body.weight_date, weight_kg=body.weight_kg, notes=body.notes,
    )
    asyncio.create_task(_trigger_heartbeat(
        "weight_logged", f"Weight logged: {body.weight_kg} kg",
    ))
    return {"id": entry_id, "date": body.weight_date, "weight_kg": body.weight_kg}


async def _trigger_heartbeat(event_type: str, context: str = ""):
    try:
        from kaori.services import heartbeat_service
        await heartbeat_service.on_event(event_type, context)
    except Exception:
        pass


@router.put("/{entry_id}")
async def update_weight(entry_id: int, body: WeightUpdate):
    await weight_service.update(entry_id, weight_kg=body.weight_kg, notes=body.notes)
    return {"id": entry_id, "weight_kg": body.weight_kg}


@router.delete("/{entry_id}")
async def delete_weight(entry_id: int):
    deleted = await weight_service.delete(entry_id)
    return {"id": entry_id, "deleted": deleted}


@router.post("/bulk-import")
async def bulk_import_weight(body: BulkImportRequest):
    result = await weight_service.bulk_import([e.model_dump() for e in body.entries])
    return result
