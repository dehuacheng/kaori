"""Agent LLM backend — chat with tool support and streaming.

This is a separate abstraction from kaori.llm.base.LLMBackend, which handles
one-shot tasks (meal analysis, summaries). This module handles multi-turn
chat with tool_use loops, ported from kaori-agent's LLM layer.
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class AgentLLMError(Exception):
    """Raised when an agent LLM backend encounters an error."""


@dataclass
class ToolCall:
    """A tool invocation requested by the model."""
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class TurnResult:
    """Provider-agnostic result from a single LLM API call."""
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"  # "end_turn" | "tool_use" | "max_tokens"
    raw: Any = None


@dataclass
class StreamEvent:
    """A single streaming event from the LLM."""
    type: str  # "thinking" | "text" | "tool_use" | "turn_complete"
    text: str = ""
    tool_call: ToolCall | None = None
    result: TurnResult | None = None


@dataclass
class ToolResult:
    """Result from executing a tool."""
    output: str
    is_error: bool = False


class BaseTool(ABC):
    """Abstract base for agent tools."""
    name: str
    description: str
    input_schema: dict[str, Any]

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        ...


class AgentLLMBackend(ABC):
    """Abstract interface for agent chat with tool support."""

    @abstractmethod
    async def chat(
        self, messages: list, tool_schemas: list[dict],
        system: str, model: str, max_tokens: int,
    ) -> TurnResult:
        ...

    async def chat_stream(
        self, messages: list, tool_schemas: list[dict],
        system: str, model: str, max_tokens: int,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream events. Default falls back to non-streaming."""
        result = await self.chat(messages, tool_schemas, system, model, max_tokens)
        if result.text:
            yield StreamEvent(type="text", text=result.text)
        yield StreamEvent(type="turn_complete", result=result)

    @abstractmethod
    def format_tool_schemas(self, tools: list[BaseTool]) -> list[dict]:
        ...

    @abstractmethod
    def make_assistant_message(self, result: TurnResult) -> Any:
        ...

    @abstractmethod
    def make_tool_results(
        self, tool_calls: list[ToolCall], results: list[ToolResult],
    ) -> list:
        ...


# ---------------------------------------------------------------------------
# Anthropic implementation
# ---------------------------------------------------------------------------

class AnthropicAgentBackend(AgentLLMBackend):
    """Agent backend using the Anthropic Python SDK."""

    def __init__(self, api_key: str | None = None):
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise AgentLLMError("anthropic package not installed")
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise AgentLLMError("ANTHROPIC_API_KEY not set")
        self._client = AsyncAnthropic(api_key=key)

    async def chat(
        self, messages: list, tool_schemas: list[dict],
        system: str, model: str, max_tokens: int,
    ) -> TurnResult:
        kwargs: dict = dict(
            model=model, max_tokens=max_tokens, system=system, messages=messages,
        )
        if tool_schemas:
            kwargs["tools"] = tool_schemas

        try:
            response = await self._client.messages.create(**kwargs)
        except Exception as e:
            raise AgentLLMError(f"Anthropic API error: {e}") from e

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id, name=block.name, input=block.input,
                ))

        if response.stop_reason == "tool_use":
            stop_reason = "tool_use"
        elif response.stop_reason == "max_tokens":
            stop_reason = "max_tokens"
        else:
            stop_reason = "end_turn"

        return TurnResult(
            text="\n".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            raw=response.content,
        )

    async def chat_stream(
        self, messages: list, tool_schemas: list[dict],
        system: str, model: str, max_tokens: int,
    ) -> AsyncGenerator[StreamEvent, None]:
        from anthropic import NOT_GIVEN

        kwargs: dict = dict(
            model=model, max_tokens=max_tokens, system=system, messages=messages,
        )
        if tool_schemas:
            kwargs["tools"] = tool_schemas

        try:
            async with self._client.messages.stream(**kwargs) as stream:
                text_parts: list[str] = []
                tool_calls: list[ToolCall] = []
                # Track tool_use blocks being built
                current_tool: dict | None = None

                async for event in stream:
                    if event.type == "content_block_start":
                        block = event.content_block
                        if block.type == "text":
                            pass  # text deltas come via content_block_delta
                        elif block.type == "tool_use":
                            current_tool = {
                                "id": block.id, "name": block.name, "input_json": [],
                            }
                    elif event.type == "content_block_delta":
                        delta = event.delta
                        if delta.type == "text_delta":
                            text_parts.append(delta.text)
                            yield StreamEvent(type="text", text=delta.text)
                        elif delta.type == "thinking_delta":
                            yield StreamEvent(type="thinking", text=delta.thinking)
                        elif delta.type == "input_json_delta":
                            if current_tool:
                                current_tool["input_json"].append(delta.partial_json)
                    elif event.type == "content_block_stop":
                        if current_tool:
                            raw_json = "".join(current_tool["input_json"])
                            try:
                                args = json.loads(raw_json) if raw_json else {}
                            except json.JSONDecodeError:
                                args = {"_raw": raw_json}
                            tool_calls.append(ToolCall(
                                id=current_tool["id"],
                                name=current_tool["name"],
                                input=args,
                            ))
                            current_tool = None

                # Determine stop reason from the final message
                final = await stream.get_final_message()
                if final.stop_reason == "tool_use":
                    stop_reason = "tool_use"
                elif final.stop_reason == "max_tokens":
                    stop_reason = "max_tokens"
                else:
                    stop_reason = "end_turn"

                yield StreamEvent(
                    type="turn_complete",
                    result=TurnResult(
                        text="".join(text_parts),
                        tool_calls=tool_calls,
                        stop_reason=stop_reason,
                        raw=final.content,
                    ),
                )
        except Exception as e:
            raise AgentLLMError(f"Anthropic streaming error: {e}") from e

    def format_tool_schemas(self, tools: list[BaseTool]) -> list[dict]:
        return [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in tools
        ]

    def make_assistant_message(self, result: TurnResult) -> dict:
        content: list[dict] = []
        if result.text:
            content.append({"type": "text", "text": result.text})
        for tc in result.tool_calls:
            content.append({
                "type": "tool_use", "id": tc.id,
                "name": tc.name, "input": tc.input,
            })
        return {"role": "assistant", "content": content}

    def make_tool_results(
        self, tool_calls: list[ToolCall], results: list[ToolResult],
    ) -> list[dict]:
        blocks = []
        for tc, r in zip(tool_calls, results):
            content = r.output if not r.is_error else f"Error: {r.output}"
            block = {"type": "tool_result", "tool_use_id": tc.id, "content": content}
            if r.is_error:
                block["is_error"] = True
            blocks.append(block)
        return [{"role": "user", "content": blocks}]


# ---------------------------------------------------------------------------
# OpenAI-compatible implementation (DeepSeek, Kimi, OpenAI, etc.)
# ---------------------------------------------------------------------------

class OpenAIAgentBackend(AgentLLMBackend):
    """Agent backend using the OpenAI SDK (any compatible API)."""

    def __init__(self, api_key: str, base_url: str, name: str = "openai"):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise AgentLLMError("openai package not installed")
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.name = name

    async def chat(
        self, messages: list, tool_schemas: list[dict],
        system: str, model: str, max_tokens: int,
    ) -> TurnResult:
        full_messages = [{"role": "system", "content": system}] + messages
        kwargs: dict = dict(model=model, max_tokens=max_tokens, messages=full_messages)
        if tool_schemas:
            kwargs["tools"] = tool_schemas
            kwargs["tool_choice"] = "auto"

        try:
            response = await self._client.chat.completions.create(**kwargs)
        except Exception as e:
            raise AgentLLMError(f"{self.name} API error: {e}") from e

        choice = response.choices[0]
        message = choice.message
        text = message.content or ""

        tool_calls: list[ToolCall] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    args = {"_raw": tc.function.arguments}
                tool_calls.append(ToolCall(
                    id=tc.id, name=tc.function.name, input=args,
                ))

        if choice.finish_reason == "tool_calls" or tool_calls:
            stop_reason = "tool_use"
        elif choice.finish_reason == "length":
            stop_reason = "max_tokens"
        else:
            stop_reason = "end_turn"

        return TurnResult(text=text, tool_calls=tool_calls, stop_reason=stop_reason, raw=message)

    async def chat_stream(
        self, messages: list, tool_schemas: list[dict],
        system: str, model: str, max_tokens: int,
    ) -> AsyncGenerator[StreamEvent, None]:
        full_messages = [{"role": "system", "content": system}] + messages
        kwargs: dict = dict(
            model=model, max_tokens=max_tokens, messages=full_messages, stream=True,
        )
        if tool_schemas:
            kwargs["tools"] = tool_schemas
            kwargs["tool_choice"] = "auto"

        try:
            stream = await self._client.chat.completions.create(**kwargs)
        except Exception as e:
            raise AgentLLMError(f"{self.name} API error: {e}") from e

        text_parts: list[str] = []
        tc_accum: dict[int, dict] = {}
        finish_reason = None

        async for chunk in stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta

            # Thinking / reasoning (DeepSeek-R1)
            reasoning = getattr(delta, "reasoning_content", None)
            if not reasoning and hasattr(delta, "model_extra") and delta.model_extra:
                reasoning = delta.model_extra.get("reasoning_content")
            if reasoning:
                yield StreamEvent(type="thinking", text=reasoning)

            if delta.content:
                text_parts.append(delta.content)
                yield StreamEvent(type="text", text=delta.content)

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tc_accum:
                        tc_accum[idx] = {"id": "", "name": "", "arguments": []}
                    if tc_delta.id:
                        tc_accum[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tc_accum[idx]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tc_accum[idx]["arguments"].append(tc_delta.function.arguments)

            if choice.finish_reason:
                finish_reason = choice.finish_reason

        text = "".join(text_parts)
        tool_calls: list[ToolCall] = []
        for idx in sorted(tc_accum):
            acc = tc_accum[idx]
            raw_args = "".join(acc["arguments"])
            try:
                args = json.loads(raw_args)
            except (json.JSONDecodeError, TypeError):
                args = {"_raw": raw_args}
            tool_calls.append(ToolCall(id=acc["id"], name=acc["name"], input=args))

        if finish_reason == "tool_calls" or tool_calls:
            stop_reason = "tool_use"
        elif finish_reason == "length":
            stop_reason = "max_tokens"
        else:
            stop_reason = "end_turn"

        yield StreamEvent(
            type="turn_complete",
            result=TurnResult(text=text, tool_calls=tool_calls, stop_reason=stop_reason),
        )

    def format_tool_schemas(self, tools: list[BaseTool]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name, "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in tools
        ]

    def make_assistant_message(self, result: TurnResult) -> dict:
        msg: dict = {"role": "assistant"}
        if result.text:
            msg["content"] = result.text
        if result.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id, "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.input)},
                }
                for tc in result.tool_calls
            ]
            if "content" not in msg:
                msg["content"] = None
        return msg

    def make_tool_results(
        self, tool_calls: list[ToolCall], results: list[ToolResult],
    ) -> list[dict]:
        return [
            {
                "role": "tool", "tool_call_id": tc.id,
                "content": r.output if not r.is_error else f"Error: {r.output}",
            }
            for tc, r in zip(tool_calls, results)
        ]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

# Backend configs: name -> (env_key, base_url, BackendClass)
_OPENAI_BACKENDS = {
    "deepseek": ("DEEPSEEK_API_KEY", "https://api.deepseek.com"),
    "kimi": ("KIMI_API_KEY", "https://api.moonshot.cn/v1"),
    "openai": ("OPENAI_API_KEY", "https://api.openai.com/v1"),
}


def get_agent_backend(
    backend_name: str | None = None,
    api_key: str | None = None,
) -> AgentLLMBackend:
    """Create an agent LLM backend from env vars or explicit config.

    backend_name: "anthropic", "deepseek", "kimi", "openai"
    Falls back to KAORI_AGENT_BACKEND env var, then "anthropic".
    """
    name = backend_name or os.environ.get("KAORI_AGENT_BACKEND", "anthropic")

    if name == "anthropic":
        return AnthropicAgentBackend(api_key=api_key)

    if name in _OPENAI_BACKENDS:
        env_key, base_url = _OPENAI_BACKENDS[name]
        key = api_key or os.environ.get(env_key)
        if not key:
            raise AgentLLMError(f"{env_key} not set for backend '{name}'")
        return OpenAIAgentBackend(api_key=key, base_url=base_url, name=name)

    raise AgentLLMError(f"Unknown agent backend: {name}")
