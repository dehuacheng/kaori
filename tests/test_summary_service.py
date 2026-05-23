"""Tests for summary_service agent-backed generation."""

import pytest

from kaori.services import summary_service


@pytest.mark.asyncio
async def test_daily_summary_uses_agent_summary(monkeypatch):
    """Short daily notification summaries should use the agent chat backend path."""
    seen: dict[str, object] = {}

    async def fake_build_daily_context(target_date: str | None = None):
        seen["target_date"] = target_date
        return (
            "Meals logged today: breakfast, lunch\n"
            "Today's totals: 1800 kcal, 120g protein\n"
            "Meal logging streak: 5 days",
            {
                "streak": 5,
                "meals_logged": 2,
                "workouts_logged": 0,
                "totals": {
                    "calories": 1800,
                    "protein_g": 120,
                    "carbs_g": 180,
                    "fat_g": 55,
                },
            },
        )

    async def fake_run_agent_summary(message: str):
        seen["message"] = message
        return ("Nice day: 1800 kcal, 120g protein, 5-day streak.", "deepseek", "deepseek-chat")

    monkeypatch.setattr(summary_service, "_build_daily_context", fake_build_daily_context)
    monkeypatch.setattr(summary_service, "_run_agent_summary", fake_run_agent_summary)

    result = await summary_service.get_daily_summary(language="en")

    assert result["summary"] == "Nice day: 1800 kcal, 120g protein, 5-day streak."
    assert result["streak"] == 5
    assert "Respond in English" in seen["message"]
    assert "Do not create a post" in seen["message"]
    assert "Today's totals: 1800 kcal" in seen["message"]


@pytest.mark.asyncio
async def test_run_agent_summary_uses_agent_backend(monkeypatch):
    """The shared summary helper should pass an AgentLLMBackend into chat()."""
    from kaori.llm import agent_backend
    from kaori.services import agent_chat_service

    seen: dict[str, object] = {}

    class FakeAgentBackend:
        name = "openai-compatible"

    backend = FakeAgentBackend()

    def fake_get_agent_backend():
        return backend

    def fake_get_agent_default_model():
        return "deepseek-chat"

    async def fake_chat(**kwargs):
        seen.update(kwargs)
        yield {"type": "text", "text": "hello "}
        yield {"type": "text", "text": "world"}

    monkeypatch.setattr(agent_backend, "get_agent_backend", fake_get_agent_backend)
    monkeypatch.setattr(agent_backend, "get_agent_default_model", fake_get_agent_default_model)
    monkeypatch.setattr(agent_chat_service, "chat", fake_chat)

    text, backend_name, model_name = await summary_service._run_agent_summary("summarize today")

    assert text == "hello world"
    assert backend_name == "openai-compatible"
    assert model_name == "deepseek-chat"
    assert seen["message"] == "summarize today"
    assert seen["backend"] is backend
    assert seen["source"] == "summary"


@pytest.mark.asyncio
async def test_detail_summary_prompts_use_agent_language(monkeypatch):
    """Daily and weekly detail prompts should keep the agent's Chinese language."""
    seen: dict[str, str] = {}

    async def fake_run_agent_summary(message: str):
        if "weekly review" in message:
            seen["weekly"] = message
        else:
            seen["daily"] = message
        return ("summary text", "anthropic", "claude-sonnet-4-6")

    async def fake_create_summary_with_sync(**kwargs):
        return kwargs

    monkeypatch.setattr(summary_service, "_run_agent_summary", fake_run_agent_summary)
    monkeypatch.setattr(summary_service, "_create_summary_with_sync", fake_create_summary_with_sync)

    await summary_service.generate_daily_detail(language="en", target_date="2026-05-23")
    await summary_service.generate_weekly_detail(language="zh")

    assert "Respond in Chinese (中文)" in seen["daily"]
    assert "Respond in Chinese (中文)" in seen["weekly"]
