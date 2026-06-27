"""测试记忆整合 + 遗忘."""

import sys

sys.path.insert(0, '.')

import asyncio
from datetime import datetime, timedelta

from mindmate.memory import MemoryStore
from mindmate.personality.forget import ForgetAgent
from mindmate.personality.memory_consolidator import MemoryConsolidator


class FakeProvider:
    async def chat(self, messages, temperature=0.7):
        return {"content": "对方在准备考研，压力比较大，是个努力的人。"}


def test_consolidate_skips_when_short():
    mem = MemoryStore()
    try:
        c = MemoryConsolidator(mem, FakeProvider(), trigger_total_turns=40)
        for i in range(10):
            mem.append_history("user", f"消息{i}", session_key="mc1")

        async def run():
            return await c.maybe_consolidate(session_key="mc1")

        assert asyncio.run(run()) is False
    finally:
        mem.close()


def test_consolidate_writes_memory():
    mem = MemoryStore()
    try:
        c = MemoryConsolidator(
            mem, FakeProvider(), keep_recent_turns=5, trigger_total_turns=20
        )
        for i in range(30):
            role = "user" if i % 2 == 0 else "assistant"
            mem.append_history(role, f"第{i}条对话内容", session_key="mc2")

        before = mem.read_memory()

        async def run():
            return await c.maybe_consolidate(session_key="mc2")

        result = asyncio.run(run())
        assert result is True
        after = mem.read_memory()
        assert len(after) > len(before)
        assert "考研" in after
    finally:
        mem.close()


def test_consolidate_no_provider():
    mem = MemoryStore()
    try:
        c = MemoryConsolidator(mem, provider=None, trigger_total_turns=2)
        for i in range(10):
            mem.append_history("user", f"m{i}", session_key="mc3")

        async def run():
            return await c.maybe_consolidate(session_key="mc3")

        assert asyncio.run(run()) is False
    finally:
        mem.close()


def test_forget_removes_stale_weak():
    mem = MemoryStore()
    try:
        f = ForgetAgent(mem, forget_after_days=30, weak_threshold=0.2)
        # 弱 + 旧 → 应遗忘
        mem.add_emotion_anchor(
            event="无聊小事", emotion="平淡", trigger="x",
            valence=0.05, session_key="fg1",
        )
        # 手动改 created_at 为很久以前
        cur = mem._conn.cursor()
        old = (datetime.now() - timedelta(days=60)).isoformat()
        cur.execute("UPDATE emotion_anchors SET created_at = ? WHERE session_key = 'fg1'", (old,))
        mem._conn.commit()

        forgotten = f.forget_stale(session_key="fg1")
        assert forgotten == 1
        assert mem.get_emotion_anchors(session_key="fg1") == []
    finally:
        mem.close()


def test_forget_keeps_strong_emotions():
    mem = MemoryStore()
    try:
        f = ForgetAgent(mem, forget_after_days=30, weak_threshold=0.2)
        # 强烈情绪 + 旧 → 保留（刻骨铭心忘得慢）
        mem.add_emotion_anchor(
            event="重要的事", emotion="刻骨铭心", trigger="y",
            valence=0.95, session_key="fg2",
        )
        cur = mem._conn.cursor()
        old = (datetime.now() - timedelta(days=60)).isoformat()
        cur.execute("UPDATE emotion_anchors SET created_at = ? WHERE session_key = 'fg2'", (old,))
        mem._conn.commit()

        forgotten = f.forget_stale(session_key="fg2")
        assert forgotten == 0
        assert len(mem.get_emotion_anchors(session_key="fg2")) == 1
    finally:
        mem.close()


def test_forget_keeps_recent():
    mem = MemoryStore()
    try:
        f = ForgetAgent(mem, forget_after_days=30, weak_threshold=0.2)
        # 弱但新 → 保留
        mem.add_emotion_anchor(
            event="刚发生的小事", emotion="平淡", trigger="z",
            valence=0.05, session_key="fg3",
        )
        forgotten = f.forget_stale(session_key="fg3")
        assert forgotten == 0
    finally:
        mem.close()
