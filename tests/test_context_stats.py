"""测试上下文管理指标."""

import sys

sys.path.insert(0, '..')

from mindmate.memory import MemoryStore


def test_get_context_stats_empty_session():
    store = MemoryStore()
    try:
        stats = store.get_context_stats(session_key="cs_empty")
        assert stats["window_size"] == 0
        assert stats["total_history_rows"] == 0
        assert stats["anchor_store_count"] == 0
        assert stats["compression_ratio"] == 0.0
        assert stats["memory_md_chars"] >= 0
        assert stats["system_prompt_chars_approx"] > 400
    finally:
        store.close()


def test_get_context_stats_with_history():
    store = MemoryStore()
    try:
        for i in range(5):
            store.append_history("user", f"消息{i}", session_key="cs_hist")
            store.append_history("assistant", f"回复{i}", session_key="cs_hist")
        stats = store.get_context_stats(session_key="cs_hist")
        assert stats["total_history_rows"] == 10
        # 10 rows, window capped at 20 → window_size = 10
        assert stats["window_size"] == 10
        assert stats["compression_ratio"] == 1.0  # 10/10
    finally:
        store.close()


def test_context_stats_anchor_store_count():
    store = MemoryStore()
    try:
        store.add_emotion_anchor(
            event="聊起考试", emotion="焦虑", trigger="考试", valence=-0.5,
            session_key="cs_anchors",
        )
        store.add_emotion_anchor(
            event="一起看日落", emotion="温暖", trigger="傍晚", valence=0.8,
            session_key="cs_anchors",
        )
        stats = store.get_context_stats(session_key="cs_anchors")
        assert stats["anchor_store_count"] == 2
    finally:
        store.close()


def test_context_stats_memory_md_chars():
    store = MemoryStore()
    try:
        store.write_memory("有人喜欢在雨天发呆。")
        stats = store.get_context_stats(session_key="cs_md")
        assert stats["memory_md_chars"] > 0
    finally:
        store.close()


def test_context_stats_compression_ratio():
    """写 50 条历史 → total=50, window=20 → 压缩比 = 2.5."""
    store = MemoryStore()
    try:
        for i in range(50):
            store.append_history("user", f"消息{i}", session_key="cs_comp")
        stats = store.get_context_stats(session_key="cs_comp")
        assert stats["total_history_rows"] == 50
        assert stats["window_size"] == 20
        assert stats["compression_ratio"] == 2.5
    finally:
        store.close()


def test_context_stats_anchor_recall_from_trace():
    """验证 anchor_recall_count 从最新 trace 的 ANCHOR_RECALL 步骤提取."""
    store = MemoryStore()
    try:
        # 写入一条 trace，其中 ANCHOR_RECALL hits=3
        store.add_agent_trace(
            trace_id=f"cs_anchor_trace_{__import__('time').time()}",
            session_key="cs_recall",
            message_id="下雨了",
            started_at="2025-01-01T00:00:00+00:00",
            completed_at="2025-01-01T00:00:01+00:00",
            steps=[
                {"step_number": 1, "step_name": "DEFENSE_CHECK", "status": "ok",
                 "detail": "triggered=False", "elapsed_ms": 0.5},
                {"step_number": 2, "step_name": "ANCHOR_RECALL", "status": "ok",
                 "detail": "hits=3", "elapsed_ms": 1.2},
            ],
            total_elapsed_ms=2000.0,
        )
        stats = store.get_context_stats(session_key="cs_recall")
        assert stats["anchor_recall_count"] == 3
    finally:
        store.close()
