"""测试情绪锚点管理."""

import sys
sys.path.insert(0, '..')

from mindmate.memory import MemoryStore
from mindmate.personality.emotion_anchor import EmotionAnchorManager


class TestExtraction:
    def test_detect_happy(self):
        mgr = EmotionAnchorManager()
        result = mgr.extract_from_messages(
            "今天好开心啊，遇到了一件好事", "太好了！什么事让你这么开心？"
        )
        assert result is not None
        assert result["emotion"] in ("高兴", "惊喜")
        assert result["valence"] > 0

    def test_detect_sad(self):
        mgr = EmotionAnchorManager()
        result = mgr.extract_from_messages(
            "最近真的好难过，唉", "怎么了？愿意跟我说说吗"
        )
        assert result is not None
        assert result["valence"] < 0

    def test_no_emotion(self):
        mgr = EmotionAnchorManager()
        result = mgr.extract_from_messages(
            "今天星期二", "嗯，星期二了"
        )
        assert result is None

    def test_trigger_extraction(self):
        mgr = EmotionAnchorManager()
        result = mgr.extract_from_messages(
            "关于工作的事情让我很焦虑", "别着急，慢慢说"
        )
        assert result is not None
        assert result["trigger"] is not None

    def test_inject_diary_anchor(self):
        store = MemoryStore()
        try:
            mgr = EmotionAnchorManager(store)
            aid = mgr.inject_diary_anchor(
                event="在路上看到一只猫",
                emotion="温暖",
                trigger="猫",
                valence=0.5,
            )
            assert aid > 0
            anchors = store.get_emotion_anchors()
            assert any(a["event"] == "在路上看到一只猫" for a in anchors)
        finally:
            store.close()


class TestAnchorContext:
    def test_get_anchor_context_match(self):
        store = MemoryStore()
        try:
            mgr = EmotionAnchorManager(store)
            store.add_emotion_anchor("聊到下雨", "温暖", "下雨", 0.7)
            context = mgr.get_anchor_context("今天下雨了，有点冷", max_anchors=5)
            assert "下雨" in context
            assert "温暖" in context
        finally:
            store.close()

    def test_get_anchor_context_no_match(self):
        store = MemoryStore()
        try:
            mgr = EmotionAnchorManager(store)
            context = mgr.get_anchor_context("今天天气不错", session_key="no_match_test", max_anchors=5)
            assert context == ""
        finally:
            store.close()

    def test_get_anchor_context_fallback(self):
        store = MemoryStore()
        try:
            store.add_emotion_anchor("聊到工作", "焦虑", "工作", -0.6)
            store.add_emotion_anchor("聊到旅行", "开心", "旅行", 0.8)
            mgr = EmotionAnchorManager(store)
            context = mgr.get_anchor_context("周末好无聊")
            # fallback 取最近最强烈的锚点
            assert len(context) > 0
        finally:
            store.close()
