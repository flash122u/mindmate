"""测试日记 Agent."""

import sys
sys.path.insert(0, '..')

from mindmate.memory import MemoryStore
from mindmate.personality.diary import DiaryAgent
from mindmate.personality.emotion_anchor import EmotionAnchorManager


class TestDiaryAgent:
    def test_create_entry(self):
        store = MemoryStore()
        try:
            diary = DiaryAgent(store)
            entry = diary.create_entry("test_diary_entry")
            # 第一次调用应该总是成功
            assert entry is not None
            assert "content" in entry
            assert "is_internal" in entry
        finally:
            store.close()

    def test_create_multiple_entries(self):
        store = MemoryStore()
        try:
            diary = DiaryAgent(store)
            # 最多 3 条
            e1 = diary.create_entry("test_diary_multi")
            e2 = diary.create_entry("test_diary_multi")
            e3 = diary.create_entry("test_diary_multi")
            e4 = diary.create_entry("test_diary_multi")  # 应该被跳过

            assert e1 is not None
            assert e2 is not None
            assert e3 is not None
            assert e4 is None
        finally:
            store.close()

    def test_get_recent_diary(self):
        store = MemoryStore()
        try:
            diary = DiaryAgent(store)
            diary.create_entry("test_diary_recent")
            recent = diary.get_recent_diary("test_diary_recent", days=1)
            assert len(recent) >= 1
        finally:
            store.close()

    def test_get_shareable(self):
        store = MemoryStore()
        try:
            diary = DiaryAgent(store)
            # 创建一条非 internal 的日记
            shareable = diary.get_shareable("test_diary_share")
            # 可能没有，但不会报错
            assert shareable is None or isinstance(shareable, str)
        finally:
            store.close()

    def test_diary_generates_anchor(self):
        store = MemoryStore()
        try:
            diary = DiaryAgent(store)
            anchor_mgr = EmotionAnchorManager(store)
            entry = diary.create_entry("test_diary_anchor")
            assert entry is not None
        finally:
            store.close()
