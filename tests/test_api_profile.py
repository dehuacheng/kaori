"""Integration tests for the profile API endpoints."""


class TestProfileAPI:
    async def test_get_default_profile(self, api_client):
        resp = await api_client.get("/api/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["display_name"] == "User"
        assert data["unit_body_weight"] == "kg"

    async def test_update_profile(self, api_client):
        resp = await api_client.put("/api/profile", json={
            "height_cm": 175, "gender": "male", "birth_date": "1994-01-15",
        })
        assert resp.status_code == 200

        resp = await api_client.get("/api/profile")
        data = resp.json()
        assert data["height_cm"] == 175
        assert data["gender"] == "male"

    async def test_computed_age(self, api_client):
        resp = await api_client.put("/api/profile", json={
            "birth_date": "1994-01-15",
        })
        resp = await api_client.get("/api/profile")
        data = resp.json()
        # Age should be computed from birth_date
        assert data["age"] is not None
        assert data["age"] >= 30

    async def test_computed_targets_with_weight(self, api_client):
        # Set up profile
        await api_client.put("/api/profile", json={
            "height_cm": 180, "gender": "male", "birth_date": "1994-01-15",
        })
        # Add weight entry
        await api_client.post("/api/weight", json={
            "weight_date": "2025-01-15", "weight_kg": 80.0,
        })

        resp = await api_client.get("/api/profile")
        data = resp.json()
        assert data["bmr"] is not None
        assert data["estimated_tdee"] is not None
        assert data["target_protein_g"] is not None
        assert data["target_calories"] is not None

    async def test_unit_preferences_round_trip(self, api_client):
        resp = await api_client.put("/api/profile", json={
            "unit_body_weight": "lb", "unit_height": "in", "unit_exercise_weight": "lb",
        })
        assert resp.status_code == 200

        resp = await api_client.get("/api/profile")
        data = resp.json()
        assert data["unit_body_weight"] == "lb"
        assert data["unit_height"] == "in"
        assert data["unit_exercise_weight"] == "lb"
