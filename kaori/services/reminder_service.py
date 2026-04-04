from datetime import date, timedelta

from kaori.storage import reminder_repo


async def list_for_feed(date_str: str) -> list[dict]:
    """Get reminders for a feed date.

    Today's feed includes overdue items AND items due tomorrow
    (so upcoming reminders surface a day early).
    """
    today = date.today().isoformat()
    if date_str == today:
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        return await reminder_repo.list_active_for_today(today, tomorrow)
    return await reminder_repo.list_by_date(date_str)


async def create(
    *,
    title: str,
    description: str | None = None,
    due_date: str | None = None,
    item_type: str = "todo",
    priority: int = 1,
) -> int:
    target_date = due_date or date.today().isoformat()
    return await reminder_repo.create(
        title=title,
        description=description,
        due_date=target_date,
        original_date=target_date,
        item_type=item_type,
        priority=priority,
    )


async def get(reminder_id: int) -> dict | None:
    return await reminder_repo.get(reminder_id)


async def update(reminder_id: int, **fields) -> None:
    await reminder_repo.update(reminder_id, **fields)


async def push(reminder_id: int, new_date: str) -> None:
    await reminder_repo.push(reminder_id, new_date)


async def mark_done(reminder_id: int, is_done: bool) -> None:
    await reminder_repo.mark_done(reminder_id, is_done)


async def delete(reminder_id: int) -> bool:
    return await reminder_repo.delete(reminder_id)


async def get_history(limit: int = 50) -> list[dict]:
    return await reminder_repo.get_history(limit)
