"""能量模型 — 主动行为调度.

参考 nanobot 的能量模型概念，动态调节 Agent 主动行为频率.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class EnergyState:
    """当前能量级别."""
    level: str = "LOW"  # HIGH | NORMAL | LOW
    last_interaction: float = 0.0
    poll_interval: float = 900.0  # 默认 15 分钟


class EnergyModel:
    """
    动态调节 Agent 主动行为频率.

    三个状态:
    - HIGH:  用户刚发消息 → 暂停主动行为，专注响应
    - NORMAL: 5-15分钟不活跃 → 5分钟间隔，可能发送问候
    - LOW:   超过 15 分钟 → 15分钟间隔，可做后台维护
    """

    def __init__(self) -> None:
        self.state = EnergyState()

    def on_user_message(self) -> None:
        """用户发消息 → 标记活跃."""
        self.state.level = "HIGH"
        self.state.last_interaction = time.time()
        self.state.poll_interval = 0  # 暂停主动行为

    def tick(self) -> tuple[str, float]:
        """
        每次心跳检查，返回 (level, seconds_until_next_poll).
        """
        idle_seconds = time.time() - self.state.last_interaction

        if idle_seconds < 60:
            # 刚互动过，暂停主动行为
            self.state.level = "HIGH"
            self.state.poll_interval = 0
        elif idle_seconds < 300:
            # 5 分钟内活跃
            self.state.level = "NORMAL"
            self.state.poll_interval = 300  # 5 分钟
        else:
            # 长时间沉默
            self.state.level = "LOW"
            self.state.poll_interval = 900  # 15 分钟

        return self.state.level, self.state.poll_interval

    def reset(self) -> None:
        """重置为初始状态."""
        self.state.last_interaction = time.time()
        self.state.level = "NORMAL"
        self.state.poll_interval = 300
