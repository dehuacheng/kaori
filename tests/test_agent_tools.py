"""Tests for agent tools and chat service helpers."""

import json

from kaori.services.agent_chat_service import _estimate_tokens, _BASE_INSTRUCTIONS_BACKEND
from kaori_agent.prompt_kit import build_system_prompt


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
    """Now tests the shared kaori_agent.prompt_kit.build_system_prompt that the
    backend chat service delegates to. See docs/FRONTEND-PARITY.md."""

    def test_basic(self):
        prompt = build_system_prompt(
            persona_text="", memory_entries=[],
            base_instructions=_BASE_INSTRUCTIONS_BACKEND,
        )
        assert "tools for querying health" in prompt
        assert "Current date and time" in prompt

    def test_with_memory(self):
        entries = [
            {"key": "name", "value": "Dehua"},
            {"key": "lang", "value": "bilingual"},
        ]
        prompt = build_system_prompt(
            persona_text="", memory_entries=entries,
            base_instructions=_BASE_INSTRUCTIONS_BACKEND,
        )
        assert "name: Dehua" in prompt
        assert "lang: bilingual" in prompt
        assert "What I know about you" in prompt

    def test_with_personality_text(self):
        prompt = build_system_prompt(
            persona_text="You are Kaori, a caring assistant.",
            memory_entries=[],
            base_instructions=_BASE_INSTRUCTIONS_BACKEND,
        )
        assert "Kaori, a caring assistant" in prompt
        # Tool capabilities note should still be present after the persona divider
        assert "tools for querying health" in prompt
        # Persona and base are separated by ---
        assert "---" in prompt

    def test_resumed_session(self):
        prompt = build_system_prompt(
            persona_text="", memory_entries=[], is_resumed=True,
            base_instructions=_BASE_INSTRUCTIONS_BACKEND,
        )
        assert "continuation of a previous conversation" in prompt

    def test_with_session_digests(self):
        digests = {
            "recent": [{"title": "trip planning", "summary": "We talked about hiking.", "updated_at": "2026-04-12 10:00:00"}],
            "older_count": 2,
            "older_titles": ["book club", "dad call"],
        }
        prompt = build_system_prompt(
            persona_text="", memory_entries=[], session_digests=digests,
            base_instructions=_BASE_INSTRUCTIONS_BACKEND,
        )
        assert "Recent conversations" in prompt
        assert "trip planning" in prompt
        assert "book club" in prompt

    def test_with_feed_snapshot(self):
        snap = "**Today**\n- workouts: morning run (34 min)"
        prompt = build_system_prompt(
            persona_text="", memory_entries=[], feed_snapshot=snap,
            base_instructions=_BASE_INSTRUCTIONS_BACKEND,
        )
        assert "What's going on with you lately" in prompt
        assert "morning run" in prompt

    def test_with_vault_routing(self):
        routing = "Vault root: /tmp/vault\n\n### Subtree map\n| topic | subtree |"
        prompt = build_system_prompt(
            persona_text="", memory_entries=[], vault_routing=routing,
            base_instructions=_BASE_INSTRUCTIONS_BACKEND,
        )
        assert "Your Obsidian vault" in prompt
        assert "Subtree map" in prompt


class TestVaultToolAdapters:
    """Smoke test that vault adapters are registered + delegate correctly."""

    def test_no_vault_tools_when_disabled(self):
        from kaori.services.agent_tools import get_default_tools

        tools = get_default_tools(vault_config=None)
        names = {t.name for t in tools}
        # The base set always includes web_search, get_feed, etc.
        assert "web_search" in names
        # Vault tools only appear when enabled
        assert "read_file" not in names
        assert "glob" not in names
        assert "grep" not in names

    def test_vault_tools_appear_when_enabled(self, tmp_path):
        from kaori_agent.config import VaultConfig
        from kaori.services.agent_tools import get_default_tools

        cfg = VaultConfig(enabled=True, root=tmp_path, exclude_paths=[])
        tools = get_default_tools(vault_config=cfg)
        names = {t.name for t in tools}
        assert "read_file" in names
        assert "glob" in names
        assert "grep" in names

    async def test_vault_read_adapter_delegates(self, tmp_path):
        from kaori.services.agent_tools import VaultReadFileTool

        (tmp_path / "INDEX.md").write_text("# Vault\n")
        tool = VaultReadFileTool(vault_root=tmp_path)
        result = await tool.execute(file_path="INDEX.md")
        assert not result.is_error
        assert "Vault" in result.output

    async def test_vault_read_adapter_rejects_escape(self, tmp_path):
        from kaori.services.agent_tools import VaultReadFileTool

        tool = VaultReadFileTool(vault_root=tmp_path)
        result = await tool.execute(file_path="../escape.txt")
        assert result.is_error
        assert "escapes vault root" in result.output.lower()

    async def test_vault_glob_adapter_rejects_escape(self, tmp_path):
        from kaori.services.agent_tools import VaultGlobTool

        tool = VaultGlobTool(vault_root=tmp_path)
        result = await tool.execute(pattern="*", path="../")
        assert result.is_error
        assert "escapes vault root" in result.output.lower()

    async def test_vault_grep_adapter_rejects_escape(self, tmp_path):
        from kaori.services.agent_tools import VaultGrepTool

        tool = VaultGrepTool(vault_root=tmp_path)
        result = await tool.execute(pattern="x", path="../")
        assert result.is_error
        assert "escapes vault root" in result.output.lower()


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
        assert len(tools) == 23

    def test_tool_names(self):
        from kaori.services.agent_tools import get_default_tools

        tools = get_default_tools()
        names = {t.name for t in tools}
        assert "get_feed" in names
        assert "get_meals" in names
        assert "get_meal_detail" in names
        assert "get_weight" in names
        assert "get_profile" in names
        assert "get_portfolio_summary" in names
        assert "get_financial_accounts" in names
        assert "get_account_holdings" in names
        assert "get_workouts" in names
        assert "get_workout_detail" in names
        assert "get_reminders" in names
        assert "get_daily_summary" in names
        assert "get_weekly_summary" in names
        assert "get_meal_streak" in names
        assert "get_exercise_types" in names
        assert "save_memory" in names
        assert "get_memory" in names
        assert "web_search" in names

    def test_tools_have_schemas(self):
        from kaori.services.agent_tools import get_default_tools

        tools = get_default_tools()
        for tool in tools:
            assert tool.name
            assert tool.description
            assert isinstance(tool.input_schema, dict)
