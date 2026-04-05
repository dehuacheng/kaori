"""Agent session, memory, prompt REST API + SSE chat endpoint."""

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from kaori.models.agent import (
    ChatRequest, SessionCreate, SessionUpdate,
    MemoryUpsert, PromptCreate, PromptUpdate,
)
from kaori.services import agent_service

router = APIRouter(prefix="/agent", tags=["api-agent"])


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@router.get("/sessions")
async def list_sessions(status: str | None = "active", limit: int = 50):
    return await agent_service.list_sessions(status=status, limit=limit)


@router.post("/sessions")
async def create_session(body: SessionCreate):
    session = await agent_service.create_session(
        backend=body.backend, model=body.model,
    )
    return session


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    session = await agent_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = await agent_service.get_session_messages(session_id)
    return {"session": session, "messages": messages}


@router.put("/sessions/{session_id}")
async def update_session(session_id: str, body: SessionUpdate):
    existing = await agent_service.get_session(session_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Session not found")
    updated = await agent_service.update_session(
        session_id,
        title=body.title,
        status=body.status,
    )
    return updated


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    deleted = await agent_service.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"id": session_id, "deleted": True}


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

@router.get("/memory")
async def list_memory(category: str | None = None):
    return await agent_service.list_memory(category=category)


@router.put("/memory/{key}")
async def upsert_memory(key: str, body: MemoryUpsert):
    return await agent_service.upsert_memory(
        key=key, value=body.value, category=body.category,
    )


@router.delete("/memory/{key}")
async def delete_memory(key: str):
    deleted = await agent_service.delete_memory(key)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory entry not found")
    return {"key": key, "deleted": True}


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

@router.get("/prompts")
async def list_prompts():
    return await agent_service.list_prompts()


@router.post("/prompts")
async def create_prompt(body: PromptCreate):
    return await agent_service.create_prompt(
        name=body.name, prompt_text=body.prompt_text,
    )


@router.put("/prompts/{prompt_id}")
async def update_prompt(prompt_id: int, body: PromptUpdate):
    existing = await agent_service.get_prompt(prompt_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return await agent_service.update_prompt(
        prompt_id, name=body.name, prompt_text=body.prompt_text,
    )


@router.put("/prompts/{prompt_id}/activate")
async def activate_prompt(prompt_id: int):
    existing = await agent_service.get_prompt(prompt_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return await agent_service.set_active_prompt(prompt_id)


@router.delete("/prompts/{prompt_id}")
async def delete_prompt(prompt_id: int):
    deleted = await agent_service.delete_prompt(prompt_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return {"id": prompt_id, "deleted": True}


# ---------------------------------------------------------------------------
# Chat (SSE streaming)
# ---------------------------------------------------------------------------

@router.post("/chat")
async def chat_stream(body: ChatRequest):
    """Send a message and receive a stream of agent events (SSE).

    Event types:
      session     — {session_id, title} (first event)
      thinking    — {text} (reasoning tokens)
      text        — {text} (response text delta)
      tool_use    — {name, input} (tool call)
      done        — {message_count} (turn complete)
      error       — {message} (error)
    """
    from kaori.services import agent_chat_service

    async def event_generator():
        async for event in agent_chat_service.chat(
            message=body.message,
            session_id=body.session_id,
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
