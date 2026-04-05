"""Integration tests for the meals API endpoints."""


class TestMealsAPI:
    async def test_create_text_meal(self, api_client):
        resp = await api_client.post("/api/meals", data={
            "meal_date": "2025-01-15",
            "meal_type": "lunch",
            "description": "Chicken rice bowl",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] is not None
        assert data["date"] == "2025-01-15"
        assert data["analysis_status"] == "pending"

    async def test_list_meals_by_date(self, api_client):
        await api_client.post("/api/meals", data={
            "meal_date": "2025-01-15", "meal_type": "breakfast", "description": "Eggs",
        })
        await api_client.post("/api/meals", data={
            "meal_date": "2025-01-16", "meal_type": "lunch", "description": "Salad",
        })

        resp = await api_client.get("/api/meals", params={"date": "2025-01-15"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["date"] == "2025-01-15"
        assert len(data["meals"]) == 1

    async def test_delete_meal(self, api_client):
        resp = await api_client.post("/api/meals", data={
            "meal_date": "2025-01-15", "meal_type": "lunch", "description": "Burger",
        })
        meal_id = resp.json()["id"]

        resp = await api_client.delete(f"/api/meals/{meal_id}")
        assert resp.status_code == 200

        # Verify it's gone
        resp = await api_client.get("/api/meals", params={"date": "2025-01-15"})
        assert len(resp.json()["meals"]) == 0

    async def test_update_meal_nutrition_override(self, api_client):
        resp = await api_client.post("/api/meals", data={
            "meal_date": "2025-01-15", "meal_type": "lunch", "description": "Pizza",
        })
        meal_id = resp.json()["id"]

        resp = await api_client.put(f"/api/meals/{meal_id}", json={
            "calories": 800, "protein_g": 30, "carbs_g": 90, "fat_g": 35,
        })
        assert resp.status_code == 200

    async def test_get_meal_by_id(self, api_client):
        resp = await api_client.post("/api/meals", data={
            "meal_date": "2025-01-15", "meal_type": "dinner", "description": "Steak",
        })
        meal_id = resp.json()["id"]

        resp = await api_client.get(f"/api/meals/{meal_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "Steak"

    async def test_meal_without_description_no_analysis(self, api_client):
        resp = await api_client.post("/api/meals", data={
            "meal_date": "2025-01-15", "meal_type": "snack",
        })
        assert resp.status_code == 200
        assert resp.json()["analysis_status"] == "done"
