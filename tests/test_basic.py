"""基础测试 — 验证项目骨架可导入."""

import sys

sys.path.insert(0, '.')

from mindmate import __version__
from mindmate.bus.events import InboundMessage, MessageBus
from mindmate.config import settings
from mindmate.memory import MemoryStore


def test_version():
    assert __version__ == "0.1.0"


def test_settings():
    assert settings.host == "0.0.0.0"
    assert settings.port == 19876


def test_message_bus():
    bus = MessageBus()
    msg = InboundMessage(channel="web", sender_id="user", chat_id="default", content="hello")
    import asyncio
    asyncio.run(bus.publish_inbound(msg))
    received = asyncio.run(bus.consume_inbound())
    assert received.content == "hello"


def test_memory_store_init():
    store = MemoryStore()
    assert store._conn is not None
    soul = store.read_soul()
    assert "小暖" in soul
    store.close()


def test_history_append_and_read():
    store = MemoryStore()
    try:
        c1 = store.append_history("user", "hello", session_key="h1")
        c2 = store.append_history("assistant", "world", session_key="h1")
        assert c1 < c2
        entries = store.read_history(session_key="h1", limit=10)
        assert len(entries) >= 2
        # 时间正序：hello 在前，world 在后
        assert entries[0]["content"] == "hello"
        assert entries[0]["role"] == "user"
        assert entries[-1]["content"] == "world"
        assert entries[-1]["role"] == "assistant"
    finally:
        store.close()


def test_append_history_invalid_role():
    import pytest
    store = MemoryStore()
    try:
        with pytest.raises(ValueError):
            store.append_history("robot", "hi")
    finally:
        store.close()


def test_history_as_messages():
    store = MemoryStore()
    try:
        store.append_history("user", "你好", session_key="h2")
        store.append_history("assistant", "你好呀", session_key="h2")
        store.append_history("user", "今天累吗", session_key="h2")
        msgs = store.read_history_as_messages(session_key="h2")
        assert len(msgs) == 3
        assert msgs[0] == {"role": "user", "content": "你好"}
        assert msgs[1] == {"role": "assistant", "content": "你好呀"}
        assert all(m["role"] in ("user", "assistant") for m in msgs)
    finally:
        store.close()


def test_history_merges_consecutive_assistant_segments():
    """一轮回复存成多条 assistant 行 → LLM 上下文合并回一条."""
    store = MemoryStore()
    try:
        store.append_history("user", "我好累", session_key="hm")
        # 一轮回复的 3 个分段
        store.append_history("assistant", "怎么啦？", session_key="hm")
        store.append_history("assistant", "是工作的事吗？", session_key="hm")
        store.append_history("assistant", "先别急。", session_key="hm")
        store.append_history("user", "嗯", session_key="hm")
        msgs = store.read_history_as_messages(session_key="hm")
        # 合并后应是 user / assistant(合并) / user 三条
        assert len(msgs) == 3
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["content"] == "怎么啦？是工作的事吗？先别急。"
        assert msgs[2]["role"] == "user"
        # 但原始行仍是分开存的（前端按行显示分段气泡）
        rows = store.read_history(session_key="hm")
        assistant_rows = [r for r in rows if r["role"] == "assistant"]
        assert len(assistant_rows) == 3
    finally:
        store.close()


def test_history_recent_for_prompt():
    store = MemoryStore()
    try:
        store.append_history("user", "你好", session_key="h3")
        store.append_history("assistant", "你好呀", session_key="h3")
        prompt = store.read_recent_for_prompt(session_key="h3", max_entries=20)
        assert "你好" in prompt
        assert "你好呀" in prompt
    finally:
        store.close()


def test_emotion_anchor():
    store = MemoryStore()
    try:
        aid = store.add_emotion_anchor(
            event="聊到下雨天",
            emotion="感到温暖",
            trigger="下雨天",
            valence=0.7,
        )
        assert aid > 0
        anchors = store.get_emotion_anchors()
        assert len(anchors) >= 1
        assert anchors[0]["emotion"] == "感到温暖"
    finally:
        store.close()


def test_emotion_anchor_by_trigger():
    store = MemoryStore()
    try:
        store.add_emotion_anchor(
            event="雨天聊天", emotion="安心", trigger="下雨", valence=0.5
        )
        matches = store.get_emotion_anchors_by_trigger("下雨")
        assert len(matches) >= 1
    finally:
        store.close()


def test_relationship_initial():
    store = MemoryStore()
    try:
        rel = store.get_relationship(session_key="rel_initial")
        assert rel["stage"] == "初识"
    finally:
        store.close()


def test_relationship_update():
    store = MemoryStore()
    try:
        store.update_relationship_stage("rel_update", "朋友")
        rel = store.get_relationship("rel_update")
        assert rel["stage"] == "朋友"
    finally:
        store.close()


def test_relationship_invalid_stage():
    store = MemoryStore()
    try:
        store.update_relationship_stage("rel_stage", "信赖")
        rel = store.get_relationship("rel_stage")
        assert rel["stage"] == "信赖"
    finally:
        store.close()
