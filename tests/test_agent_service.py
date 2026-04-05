"""Unit tests for agent service layer (sessions, messages, memory, compactions, prompts)."""

import json


class TestAgentSessions:
    async def test_create_session(self, test_db):
        from kaori.services import agent_service

        s = await agent_service.create_session(backend="anthropic", model="claude-sonnet-4-6")
        assert s["id"]
        assert s["backend"] == "anthropic"
        assert s["model"] == "claude-sonnet-4-6"
        assert s["status"] == "active"
        assert s["message_count"] == 0

    async def test_get_session(self, test_db):
        from kaori.services import agent_service

        s = await agent_service.create_session(backend="deepseek")
        loaded = await agent_service.get_session(s["id"])
        assert loaded is not None
        assert loaded["id"] == s["id"]
        assert loaded["backend"] == "deepseek"

    async def test_get_nonexistent_session(self, test_db):
        from kaori.services import agent_service

        result = await agent_service.get_session("nonexistent-id")
        assert result is None

    async def test_list_sessions(self, test_db):
        from kaori.services import agent_service

        await agent_service.create_session(backend="a")
        await agent_service.create_session(backend="b")
        sessions = await agent_service.list_sessions()
        assert len(sessions) == 2

    async def test_list_sessions_status_filter(self, test_db):
        from kaori.services import agent_service

        s1 = await agent_service.create_session(backend="a")
        await agent_service.create_session(backend="b")
        await agent_service.update_session(s1["id"], status="archived")

        active = await agent_service.list_sessions(status="active")
        assert len(active) == 1
        archived = await agent_service.list_sessions(status="archived")
        assert len(archived) == 1
        all_sessions = await agent_service.list_sessions(status=None)
        assert len(all_sessions) == 2

    async def test_update_session_title(self, test_db):
        from kaori.services import agent_service

        s = await agent_service.create_session()
        updated = await agent_service.update_session(s["id"], title="My Chat")
        assert updated["title"] == "My Chat"

    async def test_delete_session(self, test_db):
        from kaori.services import agent_service

        s = await agent_service.create_session()
        deleted = await agent_service.delete_session(s["id"])
        assert deleted is True
        assert await agent_service.get_session(s["id"]) is None

    async def test_delete_nonexistent_session(self, test_db):
        from kaori.services import agent_service

        deleted = await agent_service.delete_session("no-such-id")
        assert deleted is False

    async def test_delete_cascades_messages(self, test_db):
        from kaori.services import agent_service

        s = await agent_service.create_session()
        await agent_service.append_message(s["id"], 1, "user", '{"role":"user","content":"hi"}')
        await agent_service.append_message(s["id"], 2, "assistant", '{"role":"assistant","content":"hello"}')
        await agent_service.delete_session(s["id"])
        msgs = await agent_service.get_session_messages(s["id"])
        assert len(msgs) == 0


class TestAgentMessages:
    async def test_append_and_list(self, test_db):
        from kaori.services import agent_service

        s = await agent_service.create_session()
        msg_content = json.dumps({"role": "user", "content": "hello"})
        await agent_service.append_message(s["id"], 1, "user", msg_content, 5)

        msgs = await agent_service.get_session_messages(s["id"])
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        assert msgs[0]["seq"] == 1
        assert json.loads(msgs[0]["content"])["content"] == "hello"

    async def test_message_ordering(self, test_db):
        from kaori.services import agent_service

        s = await agent_service.create_session()
        await agent_service.append_message(s["id"], 1, "user", '{"role":"user","content":"1"}')
        await agent_service.append_message(s["id"], 2, "assistant", '{"role":"assistant","content":"2"}')
        await agent_service.append_message(s["id"], 3, "user", '{"role":"user","content":"3"}')

        msgs = await agent_service.get_session_messages(s["id"])
        assert len(msgs) == 3
        assert [m["seq"] for m in msgs] == [1, 2, 3]
        assert [m["role"] for m in msgs] == ["user", "assistant", "user"]

    async def test_get_latest_seq(self, test_db):
        from kaori.services import agent_service

        s = await agent_service.create_session()
        assert await agent_service.get_latest_seq(s["id"]) == 0

        await agent_service.append_message(s["id"], 1, "user", '{}')
        assert await agent_service.get_latest_seq(s["id"]) == 1

        await agent_service.append_message(s["id"], 2, "assistant", '{}')
        assert await agent_service.get_latest_seq(s["id"]) == 2

    async def test_get_messages_after_seq(self, test_db):
        from kaori.services import agent_service

        s = await agent_service.create_session()
        for i in range(1, 6):
            await agent_service.append_message(s["id"], i, "user", f'{{"seq":{i}}}')

        after = await agent_service.get_messages_after_seq(s["id"], 3)
        assert len(after) == 2
        assert after[0]["seq"] == 4
        assert after[1]["seq"] == 5


class TestAgentMemory:
    async def test_upsert_and_get(self, test_db):
        from kaori.services import agent_service

        entry = await agent_service.upsert_memory("name", "Dehua", "preference")
        assert entry["key"] == "name"
        assert entry["value"] == "Dehua"
        assert entry["category"] == "preference"

        got = await agent_service.get_memory("name")
        assert got["value"] == "Dehua"

    async def test_upsert_overwrites(self, test_db):
        from kaori.services import agent_service

        await agent_service.upsert_memory("lang", "en")
        await agent_service.upsert_memory("lang", "zh")
        got = await agent_service.get_memory("lang")
        assert got["value"] == "zh"

    async def test_list_all(self, test_db):
        from kaori.services import agent_service

        await agent_service.upsert_memory("a", "1")
        await agent_service.upsert_memory("b", "2")
        entries = await agent_service.list_memory()
        assert len(entries) == 2

    async def test_list_by_category(self, test_db):
        from kaori.services import agent_service

        await agent_service.upsert_memory("a", "1", "preference")
        await agent_service.upsert_memory("b", "2", "fact")
        await agent_service.upsert_memory("c", "3", "preference")

        prefs = await agent_service.list_memory(category="preference")
        assert len(prefs) == 2
        facts = await agent_service.list_memory(category="fact")
        assert len(facts) == 1

    async def test_delete(self, test_db):
        from kaori.services import agent_service

        await agent_service.upsert_memory("temp", "value")
        deleted = await agent_service.delete_memory("temp")
        assert deleted is True
        assert await agent_service.get_memory("temp") is None

    async def test_delete_nonexistent(self, test_db):
        from kaori.services import agent_service

        deleted = await agent_service.delete_memory("nope")
        assert deleted is False


class TestAgentCompactions:
    async def test_create_and_get_active(self, test_db):
        from kaori.services import agent_service

        s = await agent_service.create_session()
        comp = await agent_service.create_compaction(
            session_id=s["id"], version=1,
            summary_text="Summary of first 10 messages",
            messages_summarized=10, up_to_seq=10,
            llm_backend="anthropic", model="claude-sonnet-4-6",
        )
        assert comp["version"] == 1
        assert comp["is_active"] == 1

        active = await agent_service.get_active_compaction(s["id"])
        assert active is not None
        assert active["summary_text"] == "Summary of first 10 messages"

    async def test_new_compaction_deactivates_old(self, test_db):
        from kaori.services import agent_service

        s = await agent_service.create_session()
        await agent_service.create_compaction(
            s["id"], version=1, summary_text="v1", messages_summarized=5, up_to_seq=5,
        )
        await agent_service.create_compaction(
            s["id"], version=2, summary_text="v2", messages_summarized=10, up_to_seq=10,
        )

        active = await agent_service.get_active_compaction(s["id"])
        assert active["version"] == 2
        assert active["summary_text"] == "v2"

    async def test_no_active_compaction(self, test_db):
        from kaori.services import agent_service

        s = await agent_service.create_session()
        assert await agent_service.get_active_compaction(s["id"]) is None


class TestAgentPrompts:
    async def test_create_and_list(self, test_db):
        from kaori.services import agent_service

        p = await agent_service.create_prompt("kaori", "You are Kaori, a helpful assistant.")
        assert p["name"] == "kaori"
        assert p["is_active"] == 0

        prompts = await agent_service.list_prompts()
        assert len(prompts) == 1

    async def test_update_prompt(self, test_db):
        from kaori.services import agent_service

        p = await agent_service.create_prompt("test", "original")
        updated = await agent_service.update_prompt(p["id"], prompt_text="updated")
        assert updated["prompt_text"] == "updated"
        assert updated["name"] == "test"

    async def test_set_active(self, test_db):
        from kaori.services import agent_service

        p1 = await agent_service.create_prompt("a", "prompt a")
        p2 = await agent_service.create_prompt("b", "prompt b")

        await agent_service.set_active_prompt(p1["id"])
        active = await agent_service.get_active_prompt()
        assert active["name"] == "a"

        # Activating p2 should deactivate p1
        await agent_service.set_active_prompt(p2["id"])
        active = await agent_service.get_active_prompt()
        assert active["name"] == "b"

    async def test_delete_prompt(self, test_db):
        from kaori.services import agent_service

        p = await agent_service.create_prompt("temp", "temporary")
        deleted = await agent_service.delete_prompt(p["id"])
        assert deleted is True
        assert await agent_service.get_prompt(p["id"]) is None

    async def test_no_active_prompt(self, test_db):
        from kaori.services import agent_service

        assert await agent_service.get_active_prompt() is None
