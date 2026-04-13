"""Agent chat service — orchestrates sessions, LLM, tools, and streaming.

This is the main entry point for iOS chat: receives a user message,
runs the agentic turn loop, persists everything, and yields SSE events.

Prompt + context assembly lives in `kaori_agent.prompt_kit` and is shared with
the kaori-agent CLI. See docs/FRONTEND-PARITY.md (in the kaori-agent repo) for
why; do not write a parallel `_build_system_prompt` here.
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from kaori.llm.agent_backend import (
    AgentLLMBackend, StreamEvent, get_agent_backend, get_agent_default_model,
)
from kaori.services import agent_service
from kaori.services.agent_engine import run_turn_stream
from kaori.services.agent_tools import get_default_tools
from kaori.storage import agent_session_repo

# Shared prompt/context layer — see docs/FRONTEND-PARITY.md
from kaori_agent.prompt_kit import (
    build_system_prompt,
    shape_session_digests,
    generate_session_summary,
    render_feed_payload,
    resolve_persona,
)

logger = logging.getLogger(__name__)
_PERSONALITY_FILE_FALLBACK = "~/.kaori-agent/personality-friend.md"

# Token estimation (matches kaori-agent's heuristic)
_CONTEXT_WINDOWS = {
    "deepseek-chat": 64_000,
    "deepseek-reasoner": 64_000,
    "moonshot-v1-128k": 128_000,
    "claude-sonnet-4-6": 200_000,
    "claude-opus-4-6": 200_000,
    "claude-haiku-4-5-20251001": 200_000,
    "gpt-4o": 128_000,
}
_DEFAULT_CONTEXT_WINDOW = 64_000
_DEFAULT_MODEL = "claude-sonnet-4-6"
_DEFAULT_MAX_TOKENS = 4096
_AUTO_COMPACT_THRESHOLD = 80  # percent


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: chars/4 for ASCII, chars/2 for CJK."""
    if not text:
        return 0
    ascii_count = sum(1 for c in text if ord(c) < 128)
    non_ascii = len(text) - ascii_count
    return ascii_count // 4 + non_ascii // 2


_BASE_INSTRUCTIONS_BACKEND = (
    "You have access to tools for querying health, nutrition, fitness, "
    "finance, and personal data, plus tools for cross-session memory."
)


# Per-session feed snapshot cache. Within a chat session we reuse the snapshot
# so we don't pay an in-process fetch on every turn. Invalidation: the feed
# router calls `invalidate_feed_cache()` on every GET /api/feed (iOS
# pull-to-refresh / app open), so the cache stays in sync with whatever the user
# is looking at on screen. Mid-session writes that don't go through a feed view
# refresh won't show up until the next refresh — that's the trade-off.
_feed_cache: dict[str, str | None] = {}


def invalidate_feed_cache(session_id: str | None = None) -> None:
    """Drop cached agent feed snapshots so the next chat turn fetches fresh data.

    Called by the feed router on every GET /api/feed (i.e. whenever the user's
    iOS app fetches the feed — initial load or pull-to-refresh). With no
    argument, clears the entire cache; pass a session_id to invalidate just
    that session's snapshot.
    """
    if session_id is None:
        _feed_cache.clear()
    else:
        _feed_cache.pop(session_id, None)


async def _fetch_feed_snapshot(session_id: str) -> str | None:
    """Fetch today+yesterday from the in-process feed service and render to bullets.

    Cached per session_id; the feed router invalidates the cache on every
    GET /api/feed. Best-effort — any failure returns None so chat still works.
    """
    if session_id in _feed_cache:
        return _feed_cache[session_id]
    try:
        from datetime import date, timedelta
        from kaori.services import feed_service
        today = date.today()
        yesterday = today - timedelta(days=1)
        resp = await feed_service.get_feed(yesterday.isoformat(), today.isoformat())
        payload = resp.model_dump() if hasattr(resp, "model_dump") else resp
        snap = render_feed_payload(payload)
    except Exception as e:
        logger.warning("feed snapshot unavailable: %s", e)
        snap = None
    _feed_cache[session_id] = snap
    return snap


async def _fetch_session_digests(current_session_id: str | None) -> dict | None:
    """Pull recent sessions from the repo and shape into the digest dict."""
    try:
        sessions = await agent_session_repo.list_all(
            status="active", source="user", limit=20,
        )
        return shape_session_digests(sessions, current_session_id=current_session_id)
    except Exception as e:
        logger.warning("session digest unavailable: %s", e)
        return None


async def _resolved_persona() -> str:
    """DB-active prompt > personality file > kit default."""
    db_text = await agent_service.get_personality_text()
    return resolve_persona(db_text, _PERSONALITY_FILE_FALLBACK)


async def _maybe_summarize_inactive(
    backend: AgentLLMBackend,
    model: str,
    current_session_id: str,
) -> None:
    """Background helper: summarize the most recent inactive user session if missing.

    Fired fire-and-forget so it never blocks the user's first response. Picks the
    most recent session that isn't the current one, has >= 2 user messages, and
    has no summary yet.
    """
    try:
        sessions = await agent_session_repo.list_all(
            status="active", source="user", limit=10,
        )
        target = None
        for s in sessions:
            if s.get("id") == current_session_id:
                continue
            if (s.get("message_count") or 0) < 2:
                continue
            if s.get("summary"):
                continue
            target = s
            break
        if target is None:
            return

        # Load the messages and ask prompt_kit for a summary
        raw = await agent_service.get_session_messages(target["id"])
        messages = [json.loads(m["content"]) for m in raw]
        text = await generate_session_summary(
            backend=backend, model=model, messages=messages,
            max_tokens=_DEFAULT_MAX_TOKENS,
        )
        if text:
            await agent_session_repo.update_summary(target["id"], text)
    except Exception as e:
        logger.warning("lazy summary failed for prior session: %s", e)


async def _get_effective_messages(
    session_id: str, all_messages: list[dict],
) -> list[dict]:
    """Reconstruct messages list, applying compaction if present."""
    compaction = await agent_service.get_active_compaction(session_id)
    if not compaction:
        # No compaction — return all messages as-is
        return [json.loads(m["content"]) for m in all_messages]

    up_to_seq = compaction["up_to_seq"]
    summary = compaction["summary_text"]

    # Summary as a user message + messages after the compaction cut point
    result = [{"role": "user", "content": f"[Earlier conversation summary: {summary}]"}]
    for m in all_messages:
        if m["seq"] > up_to_seq:
            result.append(json.loads(m["content"]))
    return result


async def chat(
    message: str,
    session_id: str | None = None,
    backend: AgentLLMBackend | None = None,
    system_prompt_override: str | None = None,
    source: str = "user",
    post_source: str = "user",
) -> AsyncGenerator[dict, None]:
    """Full chat turn — yields SSE event dicts.

    1. Load or create session
    2. Build system prompt (with memory, active prompt)
    3. Append user message
    4. Run agent turn loop (streaming)
    5. Persist assistant response + tool results
    6. Auto-title if first exchange
    7. Yield events throughout

    Args:
        system_prompt_override: If set, replaces the auto-built system prompt.
        source: Session source tag ('user' or 'heartbeat').
        post_source: Source tag for posts created by the agent ('user' or 'agent').
    """
    # --- Resolve backend ---
    if backend is None:
        backend = get_agent_backend()

    # --- Load or create session ---
    session = None
    is_resumed = False

    if session_id:
        session = await agent_service.get_session(session_id)
        if session:
            is_resumed = session["message_count"] > 0

    if not session:
        session = await agent_service.create_session(
            backend=getattr(backend, "name", "anthropic"),
            source=source,
        )

    sid = session["id"]
    model = session.get("model") or get_agent_default_model() or _DEFAULT_MODEL

    yield {"type": "session", "session_id": sid, "title": session.get("title")}

    # --- Build context (shared assembly via prompt_kit) ---
    if system_prompt_override:
        system_prompt = system_prompt_override
    else:
        memory_entries = await agent_service.list_memory()
        persona = await _resolved_persona()
        digests = await _fetch_session_digests(sid)
        feed_snapshot = await _fetch_feed_snapshot(sid)
        system_prompt = build_system_prompt(
            persona_text=persona,
            memory_entries=memory_entries,
            is_resumed=is_resumed,
            session_digests=digests,
            feed_snapshot=feed_snapshot,
            base_instructions=_BASE_INSTRUCTIONS_BACKEND,
        )

    # --- Lazy: summarize the prior inactive session in the background ---
    if not is_resumed:
        asyncio.create_task(_maybe_summarize_inactive(backend, model, sid))

    # --- Load existing messages ---
    db_messages = await agent_service.get_session_messages(sid)
    messages = await _get_effective_messages(sid, db_messages)

    # --- Append user message ---
    user_msg = {"role": "user", "content": message}
    messages.append(user_msg)

    next_seq = await agent_service.get_latest_seq(sid) + 1
    tokens = _estimate_tokens(message)
    await agent_service.append_message(
        sid, next_seq, "user", json.dumps(user_msg), tokens,
    )
    next_seq += 1

    # --- Tools (with memory_saved hook for SSE) ---
    pending_events: list[dict] = []

    def _on_memory_save(key: str, value: str, category: str) -> None:
        pending_events.append({
            "type": "memory_saved",
            "key": key,
            "value": value,
            "category": category,
        })

    tools = get_default_tools(
        session_id=sid, post_source=post_source, on_memory_save=_on_memory_save,
    )

    # --- Run turn loop with streaming ---
    msg_count_before = len(messages)
    thinking_parts: list[str] = []  # accumulate thinking across tool loops
    tool_outputs: dict[str, str] = {}  # tool_call_id -> output

    try:
        async for event in run_turn_stream(
            backend, messages, tools, system_prompt, model, _DEFAULT_MAX_TOKENS,
        ):
            if event.type == "thinking":
                thinking_parts.append(event.text)
                yield {"type": "thinking", "text": event.text}
            elif event.type == "text":
                yield {"type": "text", "text": event.text}
            elif event.type == "tool_use":
                tc = event.tool_call
                yield {
                    "type": "tool_use",
                    "name": tc.name if tc else event.text,
                    "input": tc.input if tc else {},
                }
            elif event.type == "tool_result":
                tc = event.tool_call
                if tc:
                    tool_outputs[tc.id] = event.text or ""
                yield {
                    "type": "tool_result",
                    "name": tc.name if tc else "",
                    "output": event.text or "",
                }
            # Flush any side-channel events (e.g. memory_saved from on_save callback)
            while pending_events:
                yield pending_events.pop(0)
    except Exception as e:
        logger.error("Agent chat error: %s", e)
        yield {"type": "error", "message": str(e)}
        return

    # Final drain in case the last tool emitted after the last stream event
    while pending_events:
        yield pending_events.pop(0)

    # --- Persist new messages with metadata ---
    thinking_text = "".join(thinking_parts)
    new_messages = messages[msg_count_before:]
    total_tokens = 0
    first_assistant = True
    for msg in new_messages:
        role = msg.get("role", "assistant")
        if role == "tool":
            role = "tool_result"
        elif isinstance(msg.get("content"), list):
            first = msg["content"][0] if msg["content"] else {}
            if isinstance(first, dict) and first.get("type") == "tool_result":
                role = "tool_result"

        # Inject thinking text into the first assistant message
        if role == "assistant" and first_assistant and thinking_text:
            msg["_thinking"] = thinking_text
            first_assistant = False

        # Inject tool outputs into tool_result messages
        if role == "tool_result":
            if isinstance(msg.get("content"), list):
                # Anthropic format: [{type: "tool_result", tool_use_id, content}]
                for block in msg["content"]:
                    tc_id = block.get("tool_use_id", "")
                    if tc_id in tool_outputs:
                        block["_output"] = tool_outputs[tc_id]
            elif "tool_call_id" in msg:
                # OpenAI format: {role: "tool", tool_call_id, content}
                tc_id = msg["tool_call_id"]
                if tc_id in tool_outputs:
                    msg["_output"] = tool_outputs[tc_id]

        content_json = json.dumps(msg, ensure_ascii=False)
        tokens = _estimate_tokens(content_json)
        total_tokens += tokens
        await agent_service.append_message(
            sid, next_seq, role, content_json, tokens,
        )
        next_seq += 1

    # --- Update session metadata ---
    msg_count = await agent_service.get_latest_seq(sid)
    await agent_service.update_session(sid, message_count=msg_count)

    # --- Auto-title (first exchange) ---
    if not session.get("title") and msg_count >= 2:
        # Use first 50 chars of user message as title
        title = message[:50].strip()
        if len(message) > 50:
            title += "..."
        await agent_service.update_session(sid, title=title)

    yield {"type": "done", "message_count": msg_count}
