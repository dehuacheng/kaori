"""Tests for workout_service LLM backend selection."""

import json

import pytest

from kaori.models.llm import LLMResponse
from kaori.services import workout_service


class CapturingBackend:
    def __init__(self, response_text: str):
        self.response_text = response_text

    async def complete(self, prompt: str, *, model: str = "sonnet") -> LLMResponse:
        return LLMResponse(text=self.response_text, model="mock", backend="mock")

    async def analyze_image(
        self,
        image_data: bytes,
        prompt: str,
        *,
        media_type: str = "image/jpeg",
        model: str = "sonnet",
        thinking: bool = True,
    ) -> LLMResponse:
        return LLMResponse(text=self.response_text, model="mock", backend="mock")


@pytest.mark.asyncio
async def test_summarize_workout_uses_profile_llm_mode(monkeypatch):
    """Workout summaries should honor the same profile LLM picker as meals."""
    seen: dict[str, object] = {}
    response_text = json.dumps({
        "total_sets": 1,
        "total_reps": 10,
        "total_volume_kg": 600,
        "estimated_calories": 120,
        "muscle_groups_worked": ["chest"],
        "summary": "Solid bench session.",
        "intensity": "moderate",
        "trainer_notes": "Controlled reps.",
        "progress_notes": "First workout.",
        "recommendations": "Add one back movement next time.",
    })

    async def fake_get_profile():
        return {"latest_weight_kg": 80, "llm_mode": "codex_cli"}

    async def fake_get_workout(workout_id: int):
        return {
            "id": workout_id,
            "date": "2026-05-23",
            "activity_type": "traditionalStrengthTraining",
            "duration_minutes": 45,
            "exercises": [
                {
                    "exercise_name": "Bench Press",
                    "exercise_category": "strength",
                    "sets": [{"set_number": 1, "reps": 10, "weight_kg": 60}],
                }
            ],
        }

    def fake_get_llm_backend(mode=None):
        seen["mode"] = mode
        return CapturingBackend(response_text)

    async def fake_create(**kwargs):
        seen["analysis"] = kwargs

    async def fake_update_workout(workout_id: int, **fields):
        seen["workout_update"] = fields

    async def fake_get_recent_analyses(limit: int = 10):
        return []

    monkeypatch.setattr(workout_service.profile_service, "get_profile", fake_get_profile)
    monkeypatch.setattr(workout_service.workout_repo, "get_workout", fake_get_workout)
    monkeypatch.setattr(workout_service.workout_analysis_repo, "get_recent_analyses", fake_get_recent_analyses)
    monkeypatch.setattr(workout_service.workout_analysis_repo, "create", fake_create)
    monkeypatch.setattr(workout_service.workout_repo, "update_workout", fake_update_workout)
    monkeypatch.setattr(workout_service, "get_llm_backend", fake_get_llm_backend)
    monkeypatch.setattr(workout_service, "trigger_sync_workout", lambda *args: None)

    result = await workout_service.summarize_workout(123)

    assert seen["mode"] == "codex_cli"
    assert result["workout_id"] == 123
    assert seen["analysis"]["llm_backend"] == "mock"
    assert seen["workout_update"]["summary"] == "Solid bench session."


@pytest.mark.asyncio
async def test_exercise_identification_uses_profile_llm_mode(monkeypatch):
    """Exercise photo identification should honor the profile LLM picker."""
    seen: dict[str, object] = {"updates": []}
    response_text = json.dumps({
        "name": "Lat Pulldown",
        "category": "back",
        "description": "Cable pulldown movement.",
        "confidence": "high",
    })

    async def fake_get_profile():
        return {"llm_mode": "claude_api"}

    def fake_get_llm_backend(mode=None):
        seen["mode"] = mode
        return CapturingBackend(response_text)

    async def fake_get_by_name(name: str):
        return None

    async def fake_update(type_id: int, **fields):
        seen["updates"].append((type_id, fields))

    monkeypatch.setattr(workout_service.profile_service, "get_profile", fake_get_profile)
    monkeypatch.setattr(workout_service, "get_llm_backend", fake_get_llm_backend)
    monkeypatch.setattr(workout_service, "get_resized_image_bytes", lambda path: b"image")
    monkeypatch.setattr(workout_service.exercise_type_repo, "get_by_name", fake_get_by_name)
    monkeypatch.setattr(workout_service.exercise_type_repo, "update", fake_update)

    await workout_service.run_exercise_identification(7, "photo.jpg")

    assert seen["mode"] == "claude_api"
    assert seen["updates"] == [
        (
            7,
            {
                "name": "Lat Pulldown",
                "category": "back",
                "notes": "Cable pulldown movement.",
                "status": "done",
            },
        )
    ]
