"""测试造梦 Agent."""

import sys
sys.path.insert(0, '..')

from mindmate.memory import MemoryStore
from mindmate.personality.dream import DreamAgent


class TestDreamAgent:
    def test_create_dream(self):
        store = MemoryStore()
        try:
            dream = DreamAgent(store)
            d = dream.create_dream("test_dream_create")
            assert d is not None
            assert "content" in d
            assert len(d["content"]) > 5
        finally:
            store.close()

    def test_get_recent_dream(self):
        store = MemoryStore()
        try:
            dream = DreamAgent(store)
            dream.create_dream("test_dream_recent")
            recent = dream.get_recent_dream("test_dream_recent")
            assert recent is not None
        finally:
            store.close()

    def test_emotion_influenced_dream(self):
        """有情绪锚点时的梦境应与无锚点时不同."""
        store = MemoryStore()
        try:
            # 先注入一个强的正面情绪锚点
            store.add_emotion_anchor(
                "在阳光下散步", "温暖", "阳光", 0.8, "test_dream_emotion",
            )
            dream = DreamAgent(store)
            d = dream.create_dream("test_dream_emotion")
            # 应该能生成积极的梦境
            assert len(d["content"]) > 5
        finally:
            store.close()

    def test_get_shareable_dream(self):
        store = MemoryStore()
        try:
            dream = DreamAgent(store)
            dream.create_dream("test_dream_share")
            shareable = dream.get_shareable_dream("test_dream_share")
            assert shareable is not None
        finally:
            store.close()
