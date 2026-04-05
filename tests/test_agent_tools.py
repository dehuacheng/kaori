"""Tests for agent tools and chat service helpers."""

import json

from kaori.services.agent_chat_service import _estimate_tokens, _build_system_prompt


class TestTokenEstimation:
    def test_ascii(self):
        assert _estimate_tokens("hello world") == 2  # 11 chars / 4

    def test_cjk(self):
        assert _estimate_tokens("你好世界") == 2  # 4 CJK chars / 2

    def test_mixed(self):
        text = "hello你好"
        # 5 ASCII chars + 2 CJK chars
        assert _estimate_tokens(text) == 5 // 4 + 2 // 2  # 1 + 1 = 2

    def test_empty(self):
        assert _estimate_tokens("") == 0


class TestBuildSystemPrompt:
    def test_basic(self):
        prompt = _build_system_prompt(memory_entries=[], active_prompt=None)
        assert "helpful personal assistant" in prompt
        assert "Current date and time" in prompt

    def test_with_memory(self):
        entries = [
            {"key": "name", "value": "Dehua"},
            {"key": "lang", "value": "bilingual"},
        ]
        prompt = _build_system_prompt(memory_entries=entries)
        assert "name: Dehua" in prompt
        assert "lang: bilingual" in prompt
        assert "Things I remember" in prompt

    def test_with_active_prompt(self):
        prompt = _build_system_prompt(
            memory_entries=[],
            active_prompt={"prompt_text": "You are Kaori, a caring assistant."},
        )
        assert "Kaori, a caring assistant" in prompt
        # Base instructions should still be there
        assert "helpful personal assistant" in prompt

    def test_resumed_session(self):
        prompt = _build_system_prompt(memory_entries=[], is_resumed=True)
        assert "continuation of a previous conversation" in prompt


class TestAgentMemoryTools:
    async def test_save_memory(self, test_db):
        from kaori.services.agent_tools import SaveMemoryTool

        tool = SaveMemoryTool(session_id="test-session")
        result = await tool.execute(key="color", value="blue", category="preference")
        assert not result.is_error
        assert "color" in result.output

        # Verify persisted
        from kaori.services import agent_service
        entry = await agent_service.get_memory("color")
        assert entry["value"] == "blue"
        assert entry["source"] == "test-session"

    async def test_get_memory_all(self, test_db):
        from kaori.services import agent_service
        from kaori.services.agent_tools import GetMemoryTool

        await agent_service.upsert_memory("a", "1")
        await agent_service.upsert_memory("b", "2")

        tool = GetMemoryTool()
        result = await tool.execute()
        assert not result.is_error
        assert "a: 1" in result.output
        assert "b: 2" in result.output

    async def test_get_memory_by_key(self, test_db):
        from kaori.services import agent_service
        from kaori.services.agent_tools import GetMemoryTool

        await agent_service.upsert_memory("name", "Dehua")

        tool = GetMemoryTool()
        result = await tool.execute(key="name")
        assert "Dehua" in result.output

    async def test_get_memory_not_found(self, test_db):
        from kaori.services.agent_tools import GetMemoryTool

        tool = GetMemoryTool()
        result = await tool.execute(key="nonexistent")
        assert "No memory found" in result.output

    async def test_get_memory_empty(self, test_db):
        from kaori.services.agent_tools import GetMemoryTool

        tool = GetMemoryTool()
        result = await tool.execute()
        assert "No memories saved" in result.output


class TestDefaultTools:
    def test_tool_count(self):
        from kaori.services.agent_tools import get_default_tools

        tools = get_default_tools()
        assert len(tools) == 9

    def test_tool_names(self):
        from kaori.services.agent_tools import get_default_tools

        tools = get_default_tools()
        names = {t.name for t in tools}
        assert "get_feed" in names
        assert "get_meals" in names
        assert "get_weight" in names
        assert "get_profile" in names
        assert "get_portfolio_summary" in names
        assert "get_workouts" in names
        assert "get_reminders" in names
        assert "save_memory" in names
        assert "get_memory" in names

    def test_tools_have_schemas(self):
        from kaori.services.agent_tools import get_default_tools

        tools = get_default_tools()
        for tool in tools:
            assert tool.name
            assert tool.description
            assert isinstance(tool.input_schema, dict)
