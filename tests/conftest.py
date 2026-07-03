"""共享测试 fixtures — 数据库隔离、路径设置等."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_memory_dir(monkeypatch):
    """将 MEMORY_DIR 重定向到临时目录，确保每个测试拥有独立的 SQLite 数据库。

    所有测试共享同一个持久化 memory.db 会导致数据累积：
        - test_add_agent_trace_stores 期望 1 条 trace，实际 2 条
        - test_context_stats_compression_ratio 期望 50 条历史，实际 107 条
        - 等等

    本 fixture 在每个测试函数执行前用 tempfile.TemporaryDirectory
    替换 mindmate.memory.store.MEMORY_DIR，测试结束后自动清理。
    """
    with tempfile.TemporaryDirectory(prefix="mindmate_test_") as tmp:
        monkeypatch.setattr("mindmate.memory.store.MEMORY_DIR", Path(tmp))
        yield
