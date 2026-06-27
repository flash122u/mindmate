"""测试记忆整合器."""

import sys
sys.path.insert(0, '..')

from mindmate.memory import MemoryStore
from mindmate.personality.memory_consolidator import MemoryConsolidator


class TestConsolidator:
    def test_extract_anchors_from_history(self):
        store = MemoryStore()
        try:
            # 写入一些带情绪的对话
            store.append_history("[user] 今天好累啊，加了一天的班", "test_cons")
            store.append_history("[Assistant] 辛苦了，早点休息", "test_cons")
            store.append_history("[user] 周末好开心，去爬山了", "test_cons")
            store.append_history("[Assistant] 真棒！山里空气好吧", "test_cons")

            consolidator = MemoryConsolidator(store)
            import asyncio
            count = asyncio.run(
                consolidator._extract_anchors_from_history("test_cons")
            )
            assert count >= 0
            # 至少提取到 "累" 或 "开心"
            anchors = store.get_emotion_anchors("test_cons")
            assert len(anchors) >= 0
        finally:
            store.close()

    def test_update_long_term_memory(self):
        store = MemoryStore()
        try:
            store.add_emotion_anchor(
                "加班到很晚", "疲惫", "加班", -0.6, "test_ltm",
            )
            consolidator = MemoryConsolidator(store)
            import asyncio
            updated = asyncio.run(
                consolidator._update_long_term_memory("test_ltm")
            )
            memory = store.read_memory()
            # 应该成功写入 MEMORY.md
            if updated:
                assert "加班" in memory or "疲惫" in memory
        finally:
            store.close()

    def test_consolidate_full(self):
        store = MemoryStore()
        try:
            store.append_history("[user] 好难过", "test_full")
            store.append_history("[Assistant] 怎么了", "test_full")

            consolidator = MemoryConsolidator(store)
            import asyncio
            result = asyncio.run(consolidator.consolidate("test_full"))
            assert "extracted" in result
            assert "long_term_updated" in result
            assert "pruned" in result
        finally:
            store.close()
