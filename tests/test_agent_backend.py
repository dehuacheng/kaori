"""Tests for kaori.llm.agent_backend.OpenAIAgentBackend translation logic.

Mirrors kaori-agent/tests/test_openai_backend.py — these two implementations
satisfy different ABCs (kaori's AgentLLMBackend vs kaori-agent's LLMBackend)
but the deepseek-v4-pro `reasoning_content` echo-back behavior must stay in
sync. See the cross-reference notes in `make_assistant_message` of each.
"""

from dataclasses import dataclass, field

import pytest

from kaori.llm.agent_backend import (
    OpenAIAgentBackend,
    ToolCall,
    TurnResult,
)


class TestMakeAssistantMessage:
    def test_with_reasoning_content(self):
        """reasoning_content from deepseek thinking-mode must be echoed back so
        the next request doesn't 400 with 'reasoning_content must be passed back'."""
        backend = OpenAIAgentBackend.__new__(OpenAIAgentBackend)
        result = TurnResult(
            text="I'll search.",
            tool_calls=[ToolCall(id="tc1", name="search", input={"q": "x"})],
            stop_reason="tool_use",
            reasoning_content="Let me think through this carefully...",
        )
        msg = backend.make_assistant_message(result)
        assert msg["reasoning_content"] == "Let me think through this carefully..."
        assert msg["content"] == "I'll search."
        assert len(msg["tool_calls"]) == 1

    def test_text_only_no_reasoning(self):
        backend = OpenAIAgentBackend.__new__(OpenAIAgentBackend)
        result = TurnResult(text="Hello", stop_reason="end_turn")
        msg = backend.make_assistant_message(result)
        assert msg["content"] == "Hello"
        assert "reasoning_content" not in msg


# --- Mocks for streaming tests ---

@dataclass
class MockFunction:
    name: str | None = None
    arguments: str | None = None


@dataclass
class MockToolCallDelta:
    index: int
    id: str | None = None
    function: MockFunction | None = None


@dataclass
class MockDelta:
    content: str | None = None
    tool_calls: list[MockToolCallDelta] | None = None
    reasoning_content: str | None = None
    model_extra: dict | None = None


@dataclass
class MockChoice:
    delta: MockDelta
    finish_reason: str | None = None


@dataclass
class MockChunk:
    choices: list[MockChoice] = field(default_factory=list)


async def mock_stream_from_chunks(chunks):
    for chunk in chunks:
        yield chunk


def _wire_mock_client(backend, chunks):
    async def mock_create(**kwargs):
        return mock_stream_from_chunks(chunks)

    class MockCompletions:
        create = staticmethod(mock_create)
    class MockChat:
        completions = MockCompletions()
    class MockClient:
        chat = MockChat()

    backend._client = MockClient()


class TestChatStream:
    @pytest.mark.asyncio
    async def test_reasoning_content_stream(self):
        """reasoning_content deltas yield thinking events and accumulate into TurnResult."""
        chunks = [
            MockChunk(choices=[MockChoice(delta=MockDelta(reasoning_content="Thinking..."))]),
            MockChunk(choices=[MockChoice(delta=MockDelta(reasoning_content=" deeper."))]),
            MockChunk(choices=[MockChoice(delta=MockDelta(content="Answer."))]),
            MockChunk(choices=[MockChoice(delta=MockDelta(), finish_reason="stop")]),
        ]

        backend = OpenAIAgentBackend.__new__(OpenAIAgentBackend)
        backend.name = "test"
        _wire_mock_client(backend, chunks)

        events = []
        async for event in backend.chat_stream([], [], "sys", "model", 1000):
            events.append(event)

        assert events[0].type == "thinking"
        assert events[0].text == "Thinking..."
        assert events[1].type == "thinking"
        assert events[1].text == " deeper."
        assert events[2].type == "text"
        assert events[2].text == "Answer."
        assert events[3].type == "turn_complete"
        assert events[3].result.text == "Answer."
        # Must accumulate so the next assistant message can echo it back to
        # deepseek thinking-mode (or it 400s).
        assert events[3].result.reasoning_content == "Thinking... deeper."
