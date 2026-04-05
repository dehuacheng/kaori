"""Integration tests for the feed API endpoint."""


class TestFeedAPI:
    async def test_feed_returns_date_groups(self, api_client):
        # Create data on two dates
        await api_client.post("/api/weight", json={"weight_date": "2025-01-15", "weight_kg": 80})
        await api_client.post("/api/weight", json={"weight_date": "2025-01-16", "weight_kg": 81})

        resp = await api_client.get("/api/feed", params={
            "start_date": "2025-01-15", "end_date": "2025-01-16",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "dates" in data
        dates = [d["date"] for d in data["dates"]]
        assert "2025-01-15" in dates
        assert "2025-01-16" in dates

    async def test_feed_empty_range(self, api_client):
        resp = await api_client.get("/api/feed", params={
            "start_date": "2020-01-01", "end_date": "2020-01-01",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "dates" in data

    async def test_health_check_unauthenticated(self, test_db):
        """Health endpoint should work without auth."""
        from httpx import AsyncClient, ASGITransport
        from kaori.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/health")
            assert resp.status_code == 200
