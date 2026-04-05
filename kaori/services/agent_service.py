"""Agent session/memory/prompt management — thin orchestration over repos."""

from kaori.storage import (
    agent_session_repo,
    agent_message_repo,
    agent_memory_repo,
    agent_compaction_repo,
    agent_prompt_repo,
)


# --- Sessions ---

async def create_session(
    backend: str | None = None, model: str | None = None,
) -> dict:
    return await agent_session_repo.create(backend=backend, model=model)


async def get_session(session_id: str) -> dict | None:
    return await agent_session_repo.get(session_id)


async def list_sessions(
    status: str | None = "active", limit: int = 50,
) -> list[dict]:
    return await agent_session_repo.list_all(status=status, limit=limit)


async def update_session(session_id: str, **fields) -> dict | None:
    return await agent_session_repo.update(session_id, **fields)


async def delete_session(session_id: str) -> bool:
    return await agent_session_repo.delete(session_id)


# --- Messages ---

async def get_session_messages(session_id: str) -> list[dict]:
    return await agent_message_repo.list_by_session(session_id)


async def append_message(
    session_id: str, seq: int, role: str, content: str,
    token_count_approx: int = 0,
) -> dict:
    return await agent_message_repo.append(
        session_id, seq, role, content, token_count_approx,
    )


async def get_latest_seq(session_id: str) -> int:
    return await agent_message_repo.get_latest_seq(session_id)


async def get_messages_after_seq(session_id: str, after_seq: int) -> list[dict]:
    return await agent_message_repo.list_after_seq(session_id, after_seq)


# --- Memory ---

async def list_memory(category: str | None = None) -> list[dict]:
    return await agent_memory_repo.list_all(category=category)


async def get_memory(key: str) -> dict | None:
    return await agent_memory_repo.get(key)


async def upsert_memory(
    key: str, value: str, category: str = "general",
    source: str | None = None,
) -> dict:
    return await agent_memory_repo.upsert(key, value, category, source)


async def delete_memory(key: str) -> bool:
    return await agent_memory_repo.delete(key)


# --- Compactions ---

async def get_active_compaction(session_id: str) -> dict | None:
    return await agent_compaction_repo.get_active(session_id)


async def create_compaction(
    session_id: str, version: int, summary_text: str,
    messages_summarized: int, up_to_seq: int,
    llm_backend: str | None = None, model: str | None = None,
    raw_response: str | None = None,
) -> dict:
    return await agent_compaction_repo.create(
        session_id, version, summary_text, messages_summarized,
        up_to_seq, llm_backend, model, raw_response,
    )


# --- Prompts ---

async def list_prompts() -> list[dict]:
    return await agent_prompt_repo.list_all()


async def get_prompt(prompt_id: int) -> dict | None:
    return await agent_prompt_repo.get(prompt_id)


async def get_active_prompt() -> dict | None:
    return await agent_prompt_repo.get_active()


async def create_prompt(name: str, prompt_text: str) -> dict:
    return await agent_prompt_repo.create(name, prompt_text)


async def update_prompt(prompt_id: int, **fields) -> dict | None:
    return await agent_prompt_repo.update(prompt_id, **fields)


async def set_active_prompt(prompt_id: int) -> dict | None:
    return await agent_prompt_repo.set_active(prompt_id)


async def delete_prompt(prompt_id: int) -> bool:
    return await agent_prompt_repo.delete(prompt_id)
