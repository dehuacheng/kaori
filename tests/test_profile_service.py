"""Tests for profile_service: compute_targets() and format_profile_context()."""

from kaori.services.profile_service import compute_targets, format_profile_context


# ---------------------------------------------------------------------------
# compute_targets — BMR / TDEE / macros
# ---------------------------------------------------------------------------

class TestComputeTargets:
    def test_bmr_male(self):
        profile = {"height_cm": 175, "age": 30, "gender": "male"}
        result = compute_targets(profile, weight_kg=80)
        # Mifflin-St Jeor: 10*80 + 6.25*175 - 5*30 + 5 = 800+1093.75-150+5 = 1748.75
        assert result["bmr"] == round(10 * 80 + 6.25 * 175 - 5 * 30 + 5)

    def test_bmr_female(self):
        profile = {"height_cm": 165, "age": 25, "gender": "female"}
        result = compute_targets(profile, weight_kg=60)
        # 10*60 + 6.25*165 - 5*25 - 161 = 600+1031.25-125-161 = 1345.25
        assert result["bmr"] == round(10 * 60 + 6.25 * 165 - 5 * 25 - 161)

    def test_tdee_is_bmr_times_1_2(self):
        profile = {"height_cm": 175, "age": 30, "gender": "male"}
        result = compute_targets(profile, weight_kg=80)
        # TDEE computed from unrounded BMR: (10*80+6.25*175-5*30+5) * 1.2
        bmr_raw = 10 * 80 + 6.25 * 175 - 5 * 30 + 5
        assert result["estimated_tdee"] == round(bmr_raw * 1.2)

    def test_calorie_adjustment_positive(self):
        profile = {"height_cm": 175, "age": 30, "gender": "male", "calorie_adjustment_pct": 10}
        result = compute_targets(profile, weight_kg=80)
        bmr = 10 * 80 + 6.25 * 175 - 5 * 30 + 5
        expected = round(bmr * 1.2 * 1.10)
        assert result["target_calories"] == expected

    def test_calorie_adjustment_negative(self):
        profile = {"height_cm": 175, "age": 30, "gender": "male", "calorie_adjustment_pct": -20}
        result = compute_targets(profile, weight_kg=80)
        bmr = 10 * 80 + 6.25 * 175 - 5 * 30 + 5
        expected = round(bmr * 1.2 * 0.80)
        assert result["target_calories"] == expected

    def test_protein_target_default(self):
        profile = {}
        result = compute_targets(profile, weight_kg=80)
        # Default protein_per_kg=1.6
        assert result["target_protein_g"] == round(80 * 1.6)

    def test_protein_target_custom_rate(self):
        profile = {"protein_per_kg": 2.0}
        result = compute_targets(profile, weight_kg=80)
        assert result["target_protein_g"] == round(80 * 2.0)

    def test_carbs_target_default(self):
        profile = {}
        result = compute_targets(profile, weight_kg=80)
        # Default carbs_per_kg=3.0
        assert result["target_carbs_g"] == round(80 * 3.0)

    def test_missing_weight_returns_none(self):
        profile = {"height_cm": 175, "age": 30, "gender": "male"}
        result = compute_targets(profile, weight_kg=None)
        assert result["bmr"] is None
        assert result["target_protein_g"] is None
        assert result["target_carbs_g"] is None

    def test_missing_gender_no_bmr(self):
        profile = {"height_cm": 175, "age": 30}
        result = compute_targets(profile, weight_kg=80)
        assert result["bmr"] is None
        assert result["estimated_tdee"] is None
        # Macros still computed (only need weight)
        assert result["target_protein_g"] == round(80 * 1.6)

    def test_missing_age_no_bmr(self):
        profile = {"height_cm": 175, "gender": "male"}
        result = compute_targets(profile, weight_kg=80)
        assert result["bmr"] is None
        assert result["target_protein_g"] == round(80 * 1.6)


# ---------------------------------------------------------------------------
# format_profile_context
# ---------------------------------------------------------------------------

class TestFormatProfileContext:
    def test_full_profile(self):
        profile = {
            "gender": "male", "age": 30, "height_cm": 180,
            "latest_weight_kg": 80, "target_calories": 2100,
            "target_protein_g": 128, "target_carbs_g": 240,
            "notes": "Trying to cut",
        }
        ctx = format_profile_context(profile)
        assert "## User Profile" in ctx
        assert "Gender: male" in ctx
        assert "Age: 30" in ctx
        assert "Height: 180cm" in ctx
        assert "Current weight: 80kg" in ctx
        assert "Daily calorie target: 2100 kcal" in ctx
        assert "Trying to cut" in ctx

    def test_empty_profile(self):
        assert format_profile_context({}) == ""

    def test_unit_preferences_non_default(self):
        profile = {"gender": "male", "unit_body_weight": "lb", "unit_height": "in"}
        ctx = format_profile_context(profile)
        assert "Preferred units:" in ctx
        assert "body weight in lb" in ctx
        assert "height in in" in ctx

    def test_unit_preferences_default_omitted(self):
        profile = {"gender": "male", "unit_body_weight": "kg", "unit_height": "cm"}
        ctx = format_profile_context(profile)
        assert "Preferred units:" not in ctx
