from datetime import date

from kaori.services import profile_service
from kaori.storage import weight_repo


async def get_history(limit: int = 30) -> list[dict]:
    return await weight_repo.get_history(limit)


async def get_trends(limit: int = 365) -> dict:
    weights = await weight_repo.get_history(limit)
    latest = weights[0]["weight_kg"] if weights else None
    if len(weights) >= 7:
        avg_7d = sum(w["weight_kg"] for w in weights[:7]) / 7
    else:
        avg_7d = latest
    if len(weights) >= 2:
        delta_week = weights[0]["weight_kg"] - weights[min(6, len(weights) - 1)]["weight_kg"]
    else:
        delta_week = 0

    return {
        "weights_asc": list(reversed(weights)),
        "latest": latest,
        "avg_7d": avg_7d,
        "delta_week": delta_week,
    }


async def log(*, weight_date: str | None = None, weight_kg: float, notes: str | None = None) -> int:
    target_date = weight_date or date.today().isoformat()
    return await weight_repo.create(date=target_date, weight_kg=weight_kg, notes=notes)


async def update(entry_id: int, *, weight_kg: float, notes: str | None = None):
    await weight_repo.update(entry_id, weight_kg=weight_kg, notes=notes)


async def delete(entry_id: int) -> bool:
    return await weight_repo.delete(entry_id)


async def bulk_import(entries: list[dict]) -> dict:
    existing = await weight_repo.get_existing_date_weight_pairs()
    imported = 0
    skipped = 0
    for entry in entries:
        key = (entry["date"], round(entry["weight_kg"], 1))
        if key in existing:
            skipped += 1
        else:
            await weight_repo.create(
                date=entry["date"], weight_kg=entry["weight_kg"], notes=entry.get("notes"),
            )
            existing.add(key)
            imported += 1
    return {"imported": imported, "skipped": skipped}


async def get_profile() -> dict:
    return await profile_service.get_profile()
