import json
from datetime import date

from kaori.storage import post_repo


async def list_by_date(date_str: str) -> list[dict]:
    return await post_repo.list_by_date(date_str)


async def create(
    *, post_date: str | None = None, title: str | None = None, content: str,
    photo_path: str | None = None, photo_paths: list[str] | None = None,
    source: str = "user",
) -> int:
    target_date = post_date or date.today().isoformat()
    photo_paths_json = json.dumps(photo_paths) if photo_paths else None
    return await post_repo.create(
        date=target_date, title=title, content=content,
        photo_path=photo_path, photo_paths=photo_paths_json,
        source=source,
    )


async def get(post_id: int) -> dict | None:
    return await post_repo.get(post_id)


async def update(post_id: int, **fields) -> None:
    await post_repo.update(post_id, **fields)


async def delete(post_id: int) -> bool:
    return await post_repo.delete(post_id)


async def list_unread_agent(limit: int = 50) -> list[dict]:
    return await post_repo.list_unread_agent(limit)


async def mark_read(post_id: int) -> None:
    await post_repo.mark_read(post_id)


async def get_history(limit: int = 50) -> list[dict]:
    return await post_repo.get_history(limit)
