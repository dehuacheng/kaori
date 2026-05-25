from datetime import date

from kaori.services import profile_service
from kaori.services.vault_sync_service import trigger_sync_body_month
from kaori.storage import weight_repo


async def get_history(limit: int = 30) -> list[dict]:
    return await weight_repo.get_history(limit)


async def get_trends(limit: int = 365) -> dict:
    rows = await weight_repo.get_history(limit)

    # Weight trend stats are derived only from entries that have a weight value;
    # waist-only entries are still returned in the list so the iOS card can show them.
    weight_rows = [r for r in rows if r.get("weight_kg") is not None]
    latest = weight_rows[0]["weight_kg"] if weight_rows else None
    if len(weight_rows) >= 7:
        avg_7d = sum(w["weight_kg"] for w in weight_rows[:7]) / 7
    else:
        avg_7d = latest
    if len(weight_rows) >= 2:
        delta_week = (
            weight_rows[0]["weight_kg"]
            - weight_rows[min(6, len(weight_rows) - 1)]["weight_kg"]
        )
    else:
        delta_week = 0

    return {
        "weights_asc": list(reversed(rows)),
        "latest": latest,
        "avg_7d": avg_7d,
        "delta_week": delta_week,
    }


async def log(
    *,
    weight_date: str | None = None,
    weight_kg: float | None = None,
    waist_at_navel_cm: float | None = None,
    notes: str | None = None,
) -> int:
    target_date = weight_date or date.today().isoformat()
    entry_id = await weight_repo.create(
        date=target_date,
        weight_kg=weight_kg,
        waist_at_navel_cm=waist_at_navel_cm,
        notes=notes,
    )
    trigger_sync_body_month(target_date)
    return entry_id


async def update(entry_id: int, fields: dict):
    """Patch-style update: only the keys present in `fields` are written.

    `fields` should be a dict whose keys are a subset of
    {"weight_kg", "waist_at_navel_cm", "notes"} — typically built from
    `WeightUpdate.model_dump(exclude_unset=True)` so the request payload
    determines which columns get touched.
    """
    entry = await weight_repo.get_by_id(entry_id)
    await weight_repo.update(entry_id, fields)
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
