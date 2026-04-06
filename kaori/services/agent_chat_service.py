"""Agent chat service — orchestrates sessions, LLM, tools, and streaming.

This is the main entry point for iOS chat: receives a user message,
runs the agentic turn loop, persists everything, and yields SSE events.
"""

import json
import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from kaori.llm.agent_backend import (
    AgentLLMBackend, StreamEvent, get_agent_backend, get_agent_default_model,
)
from kaori.services import agent_service
from kaori.services.agent_engine import run_turn_stream
from kaori.services.agent_tools import get_default_tools

logger = logging.getLogger(__name__)

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


def _build_system_prompt(
    memory_entries: list[dict],
    active_prompt: dict | None = None,
    is_resumed: bool = False,
) -> str:
    """Build system prompt from active prompt + memory + context."""
    parts = []

    if active_prompt:
        parts.append(active_prompt["prompt_text"])
        parts.append("---")

    parts.append(
        "You are a helpful personal assistant. "
        "You have access to tools for querying health, nutrition, fitness, "
        "finance, and personal data. Be concise and direct."
    )

    now = datetime.now()
    utc_now = datetime.now(timezone.utc)
    parts.append(
        f"Current date and time: {now.strftime('%Y-%m-%d %H:%M %A')} (local), "
        f"{utc_now.strftime('%Y-%m-%d %H:%M')} UTC"
    )

    if memory_entries:
        lines = [f"- {e['key']}: {e['value']}" for e in memory_entries]
        parts.append("## Things I remember about you\n" + "\n".join(lines))

    if is_resumed:
        parts.append(
            "## Session context\n"
            "This is a continuation of a previous conversation. "
            "The earlier messages are loaded from history."
        )

    return "\n\n".join(parts)


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
) -> AsyncGenerator[dict, None]:
    """Full chat turn — yields SSE event dicts.

    1. Load or create session
    2. Build system prompt (with memory, active prompt)
    3. Append user message
    4. Run agent turn loop (streaming)
    5. Persist assistant response + tool results
    6. Auto-title if first exchange
    7. Yield events throughout
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
        )

    sid = session["id"]
    model = session.get("model") or get_agent_default_model() or _DEFAULT_MODEL

    yield {"type": "session", "session_id": sid, "title": session.get("title")}

    # --- Build context ---
    memory_entries = await agent_service.list_memory()
    active_prompt = await agent_service.get_active_prompt()
    system_prompt = _build_system_prompt(
        memory_entries, active_prompt=active_prompt, is_resumed=is_resumed,
    )

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

    # --- Tools ---
    tools = get_default_tools(session_id=sid)

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
    except Exception as e:
        logger.error("Agent chat error: %s", e)
        yield {"type": "error", "message": str(e)}
        return

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
