"""Run Trace — Agent 决策可观测性.

每次消息处理生成一条 Trace，记录每个决策步骤的耗时和结果，
在 dashboard 上可视化。面试时可以直接拿出数字：
"防御检查 0.3ms，锚点召回 1ms，LLM 调用 2.3s"。
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass


@dataclass
class TraceStep:
    """单条 trace 中的一个决策步骤."""

    step_number: int
    step_name: str  # "DEFENSE_CHECK" / "CRISIS_CHECK" / "ANCHOR_RECALL" ...
    status: str  # "ok" / "skipped" / "error"
    detail: str  # one-liner 摘要
    elapsed_ms: float  # 本步骤耗时（毫秒）


class TraceBuilder:
    """在消息处理过程中累计步骤，处理完成后落库."""

    def __init__(self, session_key: str, message_id: str) -> None:
        self.trace_id = _make_trace_id(session_key)
        self.session_key = session_key
        self.message_id = message_id
        self.started_at: float = time.time()  # epoch 秒
        self.steps: list[TraceStep] = []
        self._counter: int = 0
        self._current_name: str = ""
        self._current_start: float = 0.0

    def begin(self, name: str) -> None:
        """开始计时一个步骤."""
        self._counter += 1
        self._current_name = name
        self._current_start = time.monotonic()

    def end(self, status: str = "ok", detail: str = "") -> None:
        """结束当前步骤计时并记录."""
        elapsed = (time.monotonic() - self._current_start) * 1000.0
        self.steps.append(
            TraceStep(
                step_number=self._counter,
                step_name=self._current_name,
                status=status,
                detail=detail,
                elapsed_ms=round(elapsed, 2),
            )
        )

    def total_elapsed_ms(self) -> float:
        """从 TraceBuilder 创建到此刻的总耗时（毫秒）."""
        return round((time.time() - self.started_at) * 1000.0, 2)


def _make_trace_id(session_key: str) -> str:
    """生成唯一 trace_id：session_key + 毫秒时间戳 + 随机后缀."""
    ts = int(time.time() * 1000)
    suffix = secrets.token_hex(3)  # 6 hex chars, ~16M 种可能
    return f"{session_key}_{ts}_{suffix}"
