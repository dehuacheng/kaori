from fastapi import APIRouter, HTTPException

from kaori.models.reminder import ReminderCreate, ReminderUpdate, ReminderPush, ReminderDone
from kaori.services import reminder_service

router = APIRouter(prefix="/reminders", tags=["api-reminders"])


@router.get("")
async def list_reminders(date: str | None = None, limit: int = 50):
    if date:
        return await reminder_service.list_for_feed(date)
    return await reminder_service.get_history(limit=limit)


@router.post("")
async def create_reminder(body: ReminderCreate):
    reminder_id = await reminder_service.create(
        title=body.title,
        description=body.description,
        due_date=body.due_date,
        item_type=body.item_type,
        priority=body.priority,
    )
    return {"id": reminder_id}


@router.get("/{reminder_id}")
async def get_reminder(reminder_id: int):
    reminder = await reminder_service.get(reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return reminder


@router.put("/{reminder_id}")
async def update_reminder(reminder_id: int, body: ReminderUpdate):
    await reminder_service.update(
        reminder_id,
        title=body.title,
        description=body.description,
        due_date=body.due_date,
        item_type=body.item_type,
        priority=body.priority,
    )
    return {"id": reminder_id}


@router.delete("/{reminder_id}")
async def delete_reminder(reminder_id: int):
    deleted = await reminder_service.delete(reminder_id)
    return {"id": reminder_id, "deleted": deleted}


@router.post("/{reminder_id}/push")
async def push_reminder(reminder_id: int, body: ReminderPush):
    reminder = await reminder_service.get(reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    await reminder_service.push(reminder_id, body.new_date)
    return {"id": reminder_id, "new_date": body.new_date}


@router.post("/{reminder_id}/done")
async def mark_done(reminder_id: int, body: ReminderDone):
    reminder = await reminder_service.get(reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    await reminder_service.mark_done(reminder_id, body.is_done)
    return {"id": reminder_id, "is_done": body.is_done}
