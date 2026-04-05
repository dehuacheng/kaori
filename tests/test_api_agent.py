"""Integration tests for the agent API endpoints."""

import json


class TestAgentSessionsAPI:
    async def test_create_session(self, api_client):
        resp = await api_client.post("/api/agent/sessions", json={
            "backend": "anthropic", "model": "claude-sonnet-4-6",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"]
        assert data["backend"] == "anthropic"
        assert data["status"] == "active"

    async def test_create_session_minimal(self, api_client):
        resp = await api_client.post("/api/agent/sessions", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"]
        assert data["backend"] is None

    async def test_list_sessions(self, api_client):
        await api_client.post("/api/agent/sessions", json={"backend": "a"})
        await api_client.post("/api/agent/sessions", json={"backend": "b"})

        resp = await api_client.get("/api/agent/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    async def test_list_sessions_status_filter(self, api_client):
        r1 = await api_client.post("/api/agent/sessions", json={})
        s1_id = r1.json()["id"]
        await api_client.post("/api/agent/sessions", json={})

        # Archive one
        await api_client.put(f"/api/agent/sessions/{s1_id}", json={"status": "archived"})

        active = (await api_client.get("/api/agent/sessions?status=active")).json()
        assert len(active) == 1
        archived = (await api_client.get("/api/agent/sessions?status=archived")).json()
        assert len(archived) == 1

    async def test_get_session_detail(self, api_client):
        r = await api_client.post("/api/agent/sessions", json={"backend": "test"})
        sid = r.json()["id"]

        resp = await api_client.get(f"/api/agent/sessions/{sid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session"]["id"] == sid
        assert data["messages"] == []

    async def test_get_session_not_found(self, api_client):
        resp = await api_client.get("/api/agent/sessions/nonexistent")
        assert resp.status_code == 404

    async def test_update_session_title(self, api_client):
        r = await api_client.post("/api/agent/sessions", json={})
        sid = r.json()["id"]

        resp = await api_client.put(f"/api/agent/sessions/{sid}", json={"title": "My Chat"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "My Chat"

    async def test_delete_session(self, api_client):
        r = await api_client.post("/api/agent/sessions", json={})
        sid = r.json()["id"]

        resp = await api_client.delete(f"/api/agent/sessions/{sid}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        # Verify gone
        resp = await api_client.get(f"/api/agent/sessions/{sid}")
        assert resp.status_code == 404

    async def test_delete_session_not_found(self, api_client):
        resp = await api_client.delete("/api/agent/sessions/nonexistent")
        assert resp.status_code == 404


class TestAgentMemoryAPI:
    async def test_upsert_and_list(self, api_client):
        resp = await api_client.put("/api/agent/memory/name", json={
            "value": "Dehua", "category": "preference",
        })
        assert resp.status_code == 200
        assert resp.json()["key"] == "name"
        assert resp.json()["value"] == "Dehua"

        resp = await api_client.get("/api/agent/memory")
        assert resp.status_code == 200
        entries = resp.json()
        assert len(entries) == 1
        assert entries[0]["key"] == "name"

    async def test_upsert_overwrites(self, api_client):
        await api_client.put("/api/agent/memory/lang", json={"value": "en"})
        await api_client.put("/api/agent/memory/lang", json={"value": "zh"})

        resp = await api_client.get("/api/agent/memory")
        entries = resp.json()
        lang = [e for e in entries if e["key"] == "lang"]
        assert len(lang) == 1
        assert lang[0]["value"] == "zh"

    async def test_list_by_category(self, api_client):
        await api_client.put("/api/agent/memory/a", json={"value": "1", "category": "fact"})
        await api_client.put("/api/agent/memory/b", json={"value": "2", "category": "preference"})

        resp = await api_client.get("/api/agent/memory?category=fact")
        assert len(resp.json()) == 1
        assert resp.json()[0]["key"] == "a"

    async def test_delete(self, api_client):
        await api_client.put("/api/agent/memory/temp", json={"value": "x"})
        resp = await api_client.delete("/api/agent/memory/temp")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    async def test_delete_not_found(self, api_client):
        resp = await api_client.delete("/api/agent/memory/nonexistent")
        assert resp.status_code == 404


class TestAgentPromptsAPI:
    async def test_create_and_list(self, api_client):
        resp = await api_client.post("/api/agent/prompts", json={
            "name": "kaori", "prompt_text": "You are Kaori.",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "kaori"
        assert not resp.json()["is_active"]

        resp = await api_client.get("/api/agent/prompts")
        assert len(resp.json()) == 1

    async def test_update_prompt(self, api_client):
        r = await api_client.post("/api/agent/prompts", json={
            "name": "test", "prompt_text": "original",
        })
        pid = r.json()["id"]

        resp = await api_client.put(f"/api/agent/prompts/{pid}", json={
            "prompt_text": "updated",
        })
        assert resp.status_code == 200
        assert resp.json()["prompt_text"] == "updated"

    async def test_activate_prompt(self, api_client):
        r1 = await api_client.post("/api/agent/prompts", json={
            "name": "a", "prompt_text": "prompt a",
        })
        r2 = await api_client.post("/api/agent/prompts", json={
            "name": "b", "prompt_text": "prompt b",
        })

        # Activate a
        resp = await api_client.put(f"/api/agent/prompts/{r1.json()['id']}/activate")
        assert resp.status_code == 200
        assert resp.json()["is_active"]

        # Activate b — a should be deactivated
        resp = await api_client.put(f"/api/agent/prompts/{r2.json()['id']}/activate")
        assert resp.json()["is_active"]

        # List and check only b is active
        prompts = (await api_client.get("/api/agent/prompts")).json()
        active = [p for p in prompts if p["is_active"]]
        assert len(active) == 1
        assert active[0]["name"] == "b"

    async def test_delete_prompt(self, api_client):
        r = await api_client.post("/api/agent/prompts", json={
            "name": "temp", "prompt_text": "temp",
        })
        pid = r.json()["id"]

        resp = await api_client.delete(f"/api/agent/prompts/{pid}")
        assert resp.status_code == 200

    async def test_delete_not_found(self, api_client):
        resp = await api_client.delete("/api/agent/prompts/999")
        assert resp.status_code == 404

    async def test_update_not_found(self, api_client):
        resp = await api_client.put("/api/agent/prompts/999", json={
            "prompt_text": "x",
        })
        assert resp.status_code == 404

    async def test_activate_not_found(self, api_client):
        resp = await api_client.put("/api/agent/prompts/999/activate")
        assert resp.status_code == 404
