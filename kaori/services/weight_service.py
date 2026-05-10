from datetime import date

from kaori.services import profile_service
from kaori.services.vault_sync_service import trigger_sync_body_month
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
    entry_id = await weight_repo.create(date=target_date, weight_kg=weight_kg, notes=notes)
    trigger_sync_body_month(target_date)
    return entry_id


async def update(entry_id: int, *, weight_kg: float, notes: str | None = None):
    entry = await weight_repo.get_by_id(entry_id)
    await weight_repo.update(entry_id, weight_kg=weight_kg, notes=notes)
    if entry:
        trigger_sync_body_month(entry["date"])


async def delete(entry_id: int) -> bool:
    entry = await weight_repo.get_by_id(entry_id)
    deleted = await weight_repo.delete(entry_id)
    if deleted and entry:
        trigger_sync_body_month(entry["date"])
    return deleted


async def bulk_import(entries: list[dict]) -> dict:
    existing = await weight_repo.get_existing_date_weight_pairs()
    imported = 0
    skipped = 0
    affected_months: set[str] = set()
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
            affected_months.add(entry["date"][:7])
    # Fire one sync per affected month so the vault doesn't churn per-row.
    for month in affected_months:
        trigger_sync_body_month(f"{month}-01")
    return {"imported": imported, "skipped": skipped}


async def get_profile() -> dict:
    return await profile_service.get_profile()
