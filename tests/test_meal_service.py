"""Tests for meal_service: auto_detect_meal_type, _parse_analysis_response, _format_recent_meals."""

import json
from datetime import datetime
from unittest.mock import patch

import pytest

from kaori.services.meal_service import (
    auto_detect_meal_type,
    _parse_analysis_response,
    _format_recent_meals,
)


# ---------------------------------------------------------------------------
# auto_detect_meal_type
# ---------------------------------------------------------------------------

class TestAutoDetectMealType:
    def test_explicit_breakfast_unchanged(self):
        assert auto_detect_meal_type("breakfast") == "breakfast"

    def test_explicit_lunch_unchanged(self):
        assert auto_detect_meal_type("lunch") == "lunch"

    def test_explicit_dinner_unchanged(self):
        assert auto_detect_meal_type("dinner") == "dinner"

    @patch("kaori.services.meal_service.datetime")
    def test_snack_morning_becomes_breakfast(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 1, 1, 8, 0)
        assert auto_detect_meal_type("snack") == "breakfast"

    @patch("kaori.services.meal_service.datetime")
    def test_snack_midday_becomes_lunch(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 1, 1, 12, 0)
        assert auto_detect_meal_type("snack") == "lunch"

    @patch("kaori.services.meal_service.datetime")
    def test_snack_evening_becomes_dinner(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 1, 1, 18, 0)
        assert auto_detect_meal_type("snack") == "dinner"

    @patch("kaori.services.meal_service.datetime")
    def test_snack_late_night_stays_snack(self, mock_dt):
        mock_dt.now.return_value = datetime(2025, 1, 1, 22, 0)
        assert auto_detect_meal_type("snack") == "snack"


# ---------------------------------------------------------------------------
# _parse_analysis_response
# ---------------------------------------------------------------------------

class TestParseAnalysisResponse:
    def test_clean_json(self):
        raw = json.dumps({
            "description": "Rice and chicken",
            "items": ["rice", "chicken"],
            "calories": 500, "protein_g": 30, "carbs_g": 60, "fat_g": 10,
            "confidence": "high",
        })
        result = _parse_analysis_response(raw)
        assert result.description == "Rice and chicken"
        assert result.calories == 500
        assert result.protein_g == 30.0
        assert result.items == ["rice", "chicken"]
        assert result.confidence == "high"

    def test_fenced_json(self):
        raw = '```json\n{"description":"Salad","items":[],"calories":200,"protein_g":5,"carbs_g":20,"fat_g":8,"confidence":"medium"}\n```'
        result = _parse_analysis_response(raw)
        assert result.description == "Salad"
        assert result.calories == 200

    def test_items_as_dicts(self):
        raw = json.dumps({
            "description": "Lunch",
            "items": [{"name": "rice", "portion": "1 cup"}, {"name": "chicken"}],
            "calories": 600, "protein_g": 40, "carbs_g": 70, "fat_g": 15,
        })
        result = _parse_analysis_response(raw)
        assert "rice (1 cup)" in result.items
        assert "chicken" in result.items

    def test_items_mixed(self):
        raw = json.dumps({
            "description": "Mixed",
            "items": ["apple", {"name": "banana", "portion": "1 medium"}],
            "calories": 200, "protein_g": 2, "carbs_g": 50, "fat_g": 1,
        })
        result = _parse_analysis_response(raw)
        assert result.items == ["apple", "banana (1 medium)"]

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_analysis_response("not json at all")

    def test_missing_fields_defaults(self):
        raw = json.dumps({"description": "Unknown"})
        result = _parse_analysis_response(raw)
        assert result.calories == 0
        assert result.protein_g == 0.0
        assert result.items == []
        assert result.confidence == "medium"


# ---------------------------------------------------------------------------
# _format_recent_meals
# ---------------------------------------------------------------------------

class TestFormatRecentMeals:
    def test_empty_list(self):
        assert _format_recent_meals([]) == "No recent meals."

    def test_single_meal_with_nutrition(self):
        meals = [{"date": "2025-01-15", "meal_type": "lunch",
                  "description": "Chicken rice", "calories": 600, "protein_g": 40}]
        result = _format_recent_meals(meals)
        assert "2025-01-15 lunch" in result
        assert "Chicken rice" in result
        assert "600 kcal" in result

    def test_meal_without_nutrition(self):
        meals = [{"date": "2025-01-15", "meal_type": "snack",
                  "description": None, "calories": None, "protein_g": None}]
        result = _format_recent_meals(meals)
        assert "no nutrition data" in result
        assert "(no description)" in result
