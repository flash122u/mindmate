"""测试日记 + 造梦子 Agent."""

import sys

sys.path.insert(0, '.')

import asyncio

from mindmate.memory import MemoryStore
from mindmate.personality.diary import DiaryAgent
from mindmate.personality.dream import DreamAgent


class FakeProvider:
    def __init__(self, content):
        self.content = content

    async def chat(self, messages, temperature=0.7):
        return {"content": self.content}


def test_diary_writes_and_stores():
    mem = MemoryStore()
    try:
        agent = DiaryAgent(mem, FakeProvider("今天去咖啡馆，遇到一只橘猫，心情不错。"))

        async def run():
            return await agent.write_today(session_key="d1")

        content = asyncio.run(run())
        assert content is not None
        diaries = mem.get_diaries(session_key="d1")
        assert len(diaries) == 1
        assert "橘猫" in diaries[0]["content"]
    finally:
        mem.close()


def test_diary_no_provider():
    mem = MemoryStore()
    try:
        agent = DiaryAgent(mem, provider=None)

        async def run():
            return await agent.write_today(session_key="d2")

        assert asyncio.run(run()) is None
    finally:
        mem.close()


def test_diary_mood_inference():
    assert DiaryAgent._infer_mood("今天好开心，笑了一整天") == "开心"
    assert DiaryAgent._infer_mood("好累，有点孤独") == "低落"
    assert DiaryAgent._infer_mood("有点焦虑紧张") == "焦虑"
    assert DiaryAgent._infer_mood("普通的一天") == "平静"


def test_diary_not_in_conversation_context():
    """日记不能进入对话历史（私密性）."""
    mem = MemoryStore()
    try:
        agent = DiaryAgent(mem, FakeProvider("私密日记内容"))

        async def run():
            await agent.write_today(session_key="d3")

        asyncio.run(run())
        # 对话历史里不应有日记
        msgs = mem.read_history_as_messages(session_key="d3")
        assert msgs == []
    finally:
        mem.close()


def test_dream_generates_and_stores():
    mem = MemoryStore()
    try:
        agent = DreamAgent(mem, FakeProvider("梦见自己在海边飞，很轻盈。"))

        async def run():
            return await agent.dream(session_key="dr1")

        content = asyncio.run(run())
        assert content is not None
        dreams = mem.get_dreams(session_key="dr1")
        assert len(dreams) == 1
    finally:
        mem.close()


def test_dream_tone_from_anchors():
    mem = MemoryStore()
    try:
        agent = DreamAgent(mem, FakeProvider("梦"))
        # 正面锚点 → 温暖基调
        mem.add_emotion_anchor("好事", "开心", "x", 0.8, session_key="dr2")
        tone, hint = agent._derive_tone(mem.get_emotion_anchors(session_key="dr2"))
        assert tone == "温暖明亮"
    finally:
        mem.close()


def test_dream_tone_negative():
    mem = MemoryStore()
    try:
        agent = DreamAgent(mem, FakeProvider("梦"))
        mem.add_emotion_anchor("坏事", "焦虑", "y", -0.7, session_key="dr3")
        tone, hint = agent._derive_tone(mem.get_emotion_anchors(session_key="dr3"))
        assert tone == "不安焦虑"
    finally:
        mem.close()


def test_dream_tone_no_anchors():
    mem = MemoryStore()
    try:
        agent = DreamAgent(mem, FakeProvider("梦"))
        tone, hint = agent._derive_tone([])
        assert tone == "平静"
    finally:
        mem.close()
