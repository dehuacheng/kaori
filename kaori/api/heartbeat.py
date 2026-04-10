"""Heartbeat configuration and manual trigger API."""

from fastapi import APIRouter

from kaori.models.heartbeat import HeartbeatConfigUpdate
from kaori.services import heartbeat_service
from kaori.storage import agent_session_repo

router = APIRouter(prefix="/heartbeat", tags=["api-heartbeat"])


@router.get("/config")
async def get_config():
    return await heartbeat_service.get_config()


@router.put("/config")
async def update_config(body: HeartbeatConfigUpdate):
    fields = body.model_dump(exclude_none=True)
    return await heartbeat_service.update_config(**fields)


@router.post("/trigger")
async def trigger():
    """Manually trigger a heartbeat run (for testing). Bypasses debounce."""
    session_id = await heartbeat_service.trigger_manual()
    if session_id:
        return {"triggered": True, "session_id": session_id}
    return {"triggered": False, "reason": "disabled or already running"}


@router.get("/history")
async def history(limit: int = 20):
    """List recent heartbeat sessions."""
    return await agent_session_repo.list_all(source="heartbeat", status=None, limit=limit)
