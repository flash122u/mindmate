"""测试遗忘 Agent."""

import sys
sys.path.insert(0, '..')

from mindmate.memory import MemoryStore
from mindmate.personality.forget import ForgetAgent


class TestForgetAgent:
    def test_fuzzy_text(self):
        forget = ForgetAgent()
        fuzzy = forget._fuzzy_text("2025年6月20日下午3点在星巴克")
        assert "某天" in fuzzy or "某个地方" in fuzzy
        assert fuzzy != "2025年6月20日下午3点在星巴克"

    def test_fuzzy_short_text(self):
        forget = ForgetAgent()
        fuzzy = forget._fuzzy_text("hi")
        assert len(fuzzy) >= 2  # 兜底

    def test_forget_cycle(self):
        store = MemoryStore()
        try:
            # 添加一些旧锚点（设置 created_at 为过去）
            import datetime
            cur = store._conn.cursor()
            cur.execute(
                "INSERT INTO emotion_anchors (session_key, event, emotion, trigger, valence, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("test_forget", "旧事件", "模糊", None, 0.3, "2025-01-01 00:00:00"),
            )
            store._conn.commit()

            forget = ForgetAgent(store)
            import asyncio
            result = asyncio.run(forget.run_forget_cycle("test_forget"))
            assert "faded" in result
            assert "removed" in result
            assert "aged" in result
        finally:
            store.close()
