"""Integration tests for the weight API endpoints."""

from datetime import date


class TestWeightAPI:
    async def test_create_weight(self, api_client):
        resp = await api_client.post("/api/weight", json={
            "weight_date": "2025-01-15", "weight_kg": 80.5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] is not None
        assert data["weight_kg"] == 80.5

    async def test_list_weights(self, api_client):
        # Create two entries
        await api_client.post("/api/weight", json={"weight_date": "2025-01-15", "weight_kg": 80.0})
        await api_client.post("/api/weight", json={"weight_date": "2025-01-15", "weight_kg": 81.0})

        resp = await api_client.get("/api/weight")
        assert resp.status_code == 200
        data = resp.json()
        assert "weights_asc" in data
        assert len(data["weights_asc"]) == 2

    async def test_update_weight(self, api_client):
        resp = await api_client.post("/api/weight", json={"weight_date": "2025-01-15", "weight_kg": 80.0})
        entry_id = resp.json()["id"]

        resp = await api_client.put(f"/api/weight/{entry_id}", json={"weight_kg": 79.5})
        assert resp.status_code == 200
        assert resp.json()["weight_kg"] == 79.5

    async def test_delete_weight(self, api_client):
        resp = await api_client.post("/api/weight", json={"weight_date": "2025-01-15", "weight_kg": 80.0})
        entry_id = resp.json()["id"]

        resp = await api_client.delete(f"/api/weight/{entry_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    async def test_multiple_entries_per_day(self, api_client):
        """Regression: used to have UNIQUE constraint on date."""
        await api_client.post("/api/weight", json={"weight_date": "2025-01-15", "weight_kg": 80.0})
        resp = await api_client.post("/api/weight", json={"weight_date": "2025-01-15", "weight_kg": 80.5})
        assert resp.status_code == 200  # Should not fail with UNIQUE violation

    async def test_trends_empty(self, api_client):
        resp = await api_client.get("/api/weight")
        assert resp.status_code == 200
        data = resp.json()
        assert data["latest"] is None

    async def test_auth_required(self, test_db):
        """Requests without auth token should be rejected."""
        from httpx import AsyncClient, ASGITransport
        from kaori.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/weight")
            assert resp.status_code == 422 or resp.status_code == 401
