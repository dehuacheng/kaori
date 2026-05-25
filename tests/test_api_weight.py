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

    async def test_update_is_patch_not_replace(self, api_client):
        """PUT only writes fields present in the body — omitted fields keep their value."""
        resp = await api_client.post("/api/weight", json={
            "weight_date": "2025-01-15", "weight_kg": 80.0, "waist_at_navel_cm": 82.5,
        })
        entry_id = resp.json()["id"]

        # Update only the waist; weight must survive.
        resp = await api_client.put(f"/api/weight/{entry_id}", json={"waist_at_navel_cm": 81.0})
        assert resp.status_code == 200
        body = resp.json()
        assert body["weight_kg"] == 80.0
        assert body["waist_at_navel_cm"] == 81.0

    async def test_update_notes_only(self, api_client):
        """Notes-only update is allowed; measurements must survive."""
        resp = await api_client.post("/api/weight", json={
            "weight_date": "2025-01-15", "weight_kg": 80.0,
        })
        entry_id = resp.json()["id"]
        resp = await api_client.put(f"/api/weight/{entry_id}", json={"notes": "after fasting"})
        assert resp.status_code == 200
        assert resp.json()["weight_kg"] == 80.0
        assert resp.json()["notes"] == "after fasting"

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

    async def test_create_waist_only(self, api_client):
        resp = await api_client.post("/api/weight", json={
            "weight_date": "2025-01-15", "waist_at_navel_cm": 82.5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["weight_kg"] is None
        assert data["waist_at_navel_cm"] == 82.5

    async def test_create_both_measurements(self, api_client):
        resp = await api_client.post("/api/weight", json={
            "weight_date": "2025-01-15",
            "weight_kg": 80.0,
            "waist_at_navel_cm": 82.5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["weight_kg"] == 80.0
        assert data["waist_at_navel_cm"] == 82.5

    async def test_create_requires_at_least_one_measurement(self, api_client):
        resp = await api_client.post("/api/weight", json={
            "weight_date": "2025-01-15", "notes": "empty",
        })
        assert resp.status_code == 422

    async def test_update_waist_on_weight_only_entry(self, api_client):
        """Adding a waist measurement to an existing weight-only row keeps the weight."""
        resp = await api_client.post("/api/weight", json={
            "weight_date": "2025-01-15", "weight_kg": 80.0,
        })
        entry_id = resp.json()["id"]
        resp = await api_client.put(
            f"/api/weight/{entry_id}",
            json={"waist_at_navel_cm": 81.0},
        )
        assert resp.status_code == 200
        assert resp.json()["waist_at_navel_cm"] == 81.0
        assert resp.json()["weight_kg"] == 80.0

    async def test_auth_required(self, test_db):
        """Requests without auth token should be rejected."""
        from httpx import AsyncClient, ASGITransport
        from kaori.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/weight")
            assert resp.status_code == 422 or resp.status_code == 401
