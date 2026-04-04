from datetime import date

from kaori.storage import post_repo


async def list_by_date(date_str: str) -> list[dict]:
    return await post_repo.list_by_date(date_str)


async def create(
    *, post_date: str | None = None, title: str | None = None, content: str
) -> int:
    target_date = post_date or date.today().isoformat()
    return await post_repo.create(date=target_date, title=title, content=content)


async def get(post_id: int) -> dict | None:
    return await post_repo.get(post_id)


async def update(post_id: int, **fields) -> None:
    await post_repo.update(post_id, **fields)


async def delete(post_id: int) -> bool:
    return await post_repo.delete(post_id)


async def get_history(limit: int = 50) -> list[dict]:
    return await post_repo.get_history(limit)
