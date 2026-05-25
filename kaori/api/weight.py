import asyncio

from pydantic import BaseModel, model_validator
from fastapi import APIRouter

from kaori.services import weight_service

router = APIRouter(prefix="/weight", tags=["api-weight"])


class WeightCreate(BaseModel):
    weight_date: str | None = None
    weight_kg: float | None = None
    waist_at_navel_cm: float | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _require_one_measurement(self):
        if self.weight_kg is None and self.waist_at_navel_cm is None:
            raise ValueError(
                "At least one of weight_kg or waist_at_navel_cm must be provided"
            )
        return self


class WeightUpdate(BaseModel):
    """Patch-style update. Only fields the client explicitly sets are written;
    omitted fields keep their existing DB value (no destructive overwrite).

    Note: passing an explicit `null` IS treated as "set to null" — the API
    can't tell that apart from "absent" once it lands in Pydantic. iOS should
    use a Codable that omits nil fields rather than emitting them as JSON null."""

    weight_kg: float | None = None
    waist_at_navel_cm: float | None = None
    notes: str | None = None


class BulkImportEntry(BaseModel):
    # Bulk import is intentionally weight-only — historical backfills come from
    # Apple Health weight samples. Waist data is logged via POST /api/weight.
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
        weight_date=body.weight_date,
        weight_kg=body.weight_kg,
        waist_at_navel_cm=body.waist_at_navel_cm,
        notes=body.notes,
    )
    context_parts = []
    if body.weight_kg is not None:
        context_parts.append(f"weight {body.weight_kg} kg")
    if body.waist_at_navel_cm is not None:
        context_parts.append(f"waist {body.waist_at_navel_cm} cm")
    asyncio.create_task(_trigger_heartbeat(
        "weight_logged", "Measurement logged: " + ", ".join(context_parts),
    ))
    return {
        "id": entry_id,
        "date": body.weight_date,
        "weight_kg": body.weight_kg,
        "waist_at_navel_cm": body.waist_at_navel_cm,
    }


async def _trigger_heartbeat(event_type: str, context: str = ""):
    try:
        from kaori.services import heartbeat_service
        await heartbeat_service.on_event(event_type, context)
    except Exception:
        pass


@router.put("/{entry_id}")
async def update_weight(entry_id: int, body: WeightUpdate):
    # exclude_unset → only the keys the client actually sent reach the repo.
    # Omitted fields keep their existing value in the DB.
    fields = body.model_dump(exclude_unset=True)
    await weight_service.update(entry_id, fields)
    # Echo the post-update row so the client doesn't have to re-fetch.
    from kaori.storage import weight_repo
    row = await weight_repo.get_by_id(entry_id)
    if row is None:
        return {"id": entry_id}
    return {
        "id": entry_id,
        "weight_kg": row.get("weight_kg"),
        "waist_at_navel_cm": row.get("waist_at_navel_cm"),
        "notes": row.get("notes"),
    }


@router.delete("/{entry_id}")
async def delete_weight(entry_id: int):
    deleted = await weight_service.delete(entry_id)
    return {"id": entry_id, "deleted": deleted}


@router.post("/bulk-import")
async def bulk_import_weight(body: BulkImportRequest):
    result = await weight_service.bulk_import([e.model_dump() for e in body.entries])
    return result
