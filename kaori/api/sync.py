"""iOS offline-sync API (Phase 1: pull-only read replica).

GET /api/sync/changes — incremental changes + tombstones since a cursor, used by the
iOS local mirror. Writes still go through the existing per-domain endpoints in Phase 1;
a /sync/push endpoint arrives in Phase 2 (offline outbox).
"""

from fastapi import APIRouter

from kaori.storage import sync_repo

router = APIRouter(prefix="/sync", tags=["api-sync"])


@router.get("/changes")
async def get_changes(since: str | None = None, types: str | None = None):
    """Return rows changed (and rows deleted) since `since`.

    Query params:
      - since: server cursor 'YYYY-MM-DD HH:MM:SS' from a prior response's
        `server_time`. Omit for a full initial snapshot.
      - types: optional comma-separated entity types to restrict the pull
        (e.g. 'meals,posts'); unknown names are ignored.

    Response: { server_time, since, changes: {table: [rows]}, deletions: [...] }.
    `server_time` is the cursor to pass as `since` on the next pull.
    """
    type_list = [t.strip() for t in types.split(",") if t.strip()] if types else None
    return await sync_repo.get_changes(since=since, types=type_list)
