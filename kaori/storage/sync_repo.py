"""Read-only access for the iOS sync pull (Phase 1).

Returns changed rows per syncable table plus delete-tombstones since a cursor.
See CLAUDE.md "Offline-First Sync" and docs/plans/ios-offline-sync-plan.html.
"""

from kaori.database import get_db, SYNC_TABLES


async def get_changes(since: str | None = None, types: list[str] | None = None) -> dict:
    """Incremental changes since `since` (a server 'YYYY-MM-DD HH:MM:SS' cursor).

    - `since=None` → full snapshot (initial replica load): every row, no tombstones
      (a fresh client has nothing to delete).
    - `since` set → rows with ``updated_at >= since`` per table, plus tombstones with
      ``deleted_at >= since``.

    The lower bound is **inclusive** on purpose: SQLite's ``datetime('now')`` has
    1-second granularity, so a strict ``>`` could drop a row written in the same second
    as the cursor. Re-sending a boundary row is harmless because the client applies
    upserts/deletes idempotently by ``sync_uuid``.

    ``server_time`` is captured up front and returned as the next cursor — any write
    landing during this call has ``updated_at >= server_time`` and is picked up next pull.
    """
    type_filter = set(types) if types else None
    tables = [t for t in SYNC_TABLES if not type_filter or t in type_filter]

    db = await get_db()
    try:
        server_time = (await (await db.execute("SELECT datetime('now')")).fetchone())[0]

        changes: dict[str, list[dict]] = {}
        for table in tables:
            if since:
                cursor = await db.execute(
                    f"SELECT * FROM {table} WHERE updated_at >= ?", (since,)
                )
            else:
                cursor = await db.execute(f"SELECT * FROM {table}")
            rows = [dict(r) for r in await cursor.fetchall()]
            if rows:
                changes[table] = rows

        deletions: list[dict] = []
        if since:
            tcur = await db.execute(
                "SELECT entity_type, sync_uuid, deleted_at FROM sync_deletions "
                "WHERE deleted_at >= ? ORDER BY deleted_at",
                (since,),
            )
            deletions = [dict(r) for r in await tcur.fetchall()]
            if type_filter:
                deletions = [d for d in deletions if d["entity_type"] in type_filter]

        return {
            "server_time": server_time,
            "since": since,
            "changes": changes,
            "deletions": deletions,
        }
    finally:
        await db.close()
