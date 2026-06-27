"""测试情绪锚点系统."""

import sys

sys.path.insert(0, '.')

import asyncio

from mindmate.memory import MemoryStore
from mindmate.personality.emotion_anchor import EmotionAnchorManager


def test_parse_anchors_valid_json():
    text = '[{"event":"聊考研","emotion":"焦虑","trigger":"考试","valence":-0.3}]'
    anchors = EmotionAnchorManager._parse_anchors(text)
    assert len(anchors) == 1
    assert anchors[0]["emotion"] == "焦虑"


def test_parse_anchors_with_codeblock():
    text = '```json\n[{"event":"a","emotion":"开心","valence":0.5}]\n```'
    anchors = EmotionAnchorManager._parse_anchors(text)
    assert len(anchors) == 1


def test_parse_anchors_empty():
    assert EmotionAnchorManager._parse_anchors("[]") == []
    assert EmotionAnchorManager._parse_anchors("没有锚点") == []


def test_parse_anchors_skips_incomplete():
    text = '[{"event":"a"},{"event":"b","emotion":"难过"}]'
    anchors = EmotionAnchorManager._parse_anchors(text)
    assert len(anchors) == 1  # 缺 emotion 的被过滤


def test_recall_matches_trigger():
    mem = MemoryStore()
    try:
        mgr = EmotionAnchorManager(mem)
        mem.add_emotion_anchor(
            event="那次晚餐", emotion="安全感", trigger="下雨",
            valence=0.8, session_key="ea1",
        )
        hits = mgr.recall("今天下雨了，好冷", session_key="ea1")
        assert len(hits) == 1
        assert hits[0]["emotion"] == "安全感"
    finally:
        mem.close()


def test_recall_no_match():
    mem = MemoryStore()
    try:
        mgr = EmotionAnchorManager(mem)
        mem.add_emotion_anchor(
            event="那次晚餐", emotion="安全感", trigger="下雨",
            valence=0.8, session_key="ea2",
        )
        hits = mgr.recall("今天天气真好", session_key="ea2")
        assert hits == []
    finally:
        mem.close()


def test_build_anchor_prompt():
    mem = MemoryStore()
    try:
        mgr = EmotionAnchorManager(mem)
        anchors = [{"event": "那次晚餐", "emotion": "安全感", "valence": 0.8}]
        prompt = mgr.build_anchor_prompt(anchors)
        assert "那次晚餐" in prompt
        assert "安全感" in prompt
    finally:
        mem.close()


def test_build_anchor_prompt_empty():
    mem = MemoryStore()
    try:
        mgr = EmotionAnchorManager(mem)
        assert mgr.build_anchor_prompt([]) == ""
    finally:
        mem.close()


def test_extract_stores_anchors():
    mem = MemoryStore()

    class FakeProvider:
        async def chat(self, messages, temperature=0.7):
            return {
                "content": '[{"event":"聊起考研","emotion":"焦虑",'
                '"trigger":"考试","valence":-0.4}]'
            }

    try:
        mgr = EmotionAnchorManager(mem, FakeProvider())
        mem.append_history("user", "我在准备考研，压力好大", session_key="ea3")

        async def run():
            return await mgr.extract(session_key="ea3")

        count = asyncio.run(run())
        assert count == 1
        anchors = mem.get_emotion_anchors(session_key="ea3")
        assert anchors[0]["emotion"] == "焦虑"
    finally:
        mem.close()


def test_extract_no_provider():
    mem = MemoryStore()
    try:
        mgr = EmotionAnchorManager(mem, provider=None)

        async def run():
            return await mgr.extract(session_key="ea4")

        assert asyncio.run(run()) == 0
    finally:
        mem.close()
