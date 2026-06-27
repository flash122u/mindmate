"""能量模型 — 主动行为调度核心.

参考 nanobot 的能量模型概念，动态调节 Agent 主动行为频率.

状态机:
  HIGH   ← 用户刚互动 → 专注响应，不主动触发
  NORMAL ← 5-15min沉默 → 可发问候/关心
  LOW    ← >15min沉默  → 可发日常闲聊
  DEEP   ← >1h沉默     → 可执行 Drift Mode 后台维护
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class EnergyState:
    """当前能量状态."""
    level: str = "DEEP"
    last_interaction: float = 0.0
    poll_interval: float = 900.0
    consecutive_ticks: int = 0  # 同一 level 持续多少次 tick


ENERGY_THRESHOLDS = [
    ("HIGH",   0,      10),     # (<1min, interval=0s → 基本不轮询)
    ("NORMAL", (60, 1),  60),   # (1-5min, interval=60s)
    ("NORMAL", (300, 1), 120),  # (5-15min, interval=2min)
    ("LOW",    900,     300),   # (>15min, interval=5min)
    ("DEEP",   3600,    600),   # (>1h, interval=10min)
]


class EnergyModel:
    """
    能量模型 — 动态调节 Agent 主动行为频率.

    五个状态:
    - HIGH:  用户刚发消息 → 暂停主动，专注响应
    - NORMAL: 5-15分钟不活跃 → 每1-2分钟检查一次
    - LOW:   超过 15 分钟 → 每5分钟，可发问候
    - DEEP:  超过 1 小时 → 每10分钟，可做后台维护+主动推送
    """

    def __init__(self) -> None:
        self.state = EnergyState()

    def on_user_message(self) -> None:
        """用户发消息 → 切回 HIGH."""
        self.state.level = "HIGH"
        self.state.last_interaction = time.time()
        self.state.poll_interval = 0
        self.state.consecutive_ticks = 0

    def tick(self) -> tuple[str, float]:
        """
        每次心跳检查。

        Returns:
            (level, seconds_until_next_poll):
                level="HIGH" 时 seconds=0 表示不执行主动行为，但仍需定期检查
        """
        idle_seconds = time.time() - self.state.last_interaction

        if idle_seconds < 60:
            level = "HIGH"
            interval = 10           # 每10秒检查一次，不算主动
        elif idle_seconds < 300:
            level = "NORMAL"
            interval = 60           # 每1分钟
        elif idle_seconds < 900:
            level = "NORMAL"
            interval = 120          # 每2分钟
        elif idle_seconds < 3600:
            level = "LOW"
            interval = 300          # 每5分钟
        else:
            level = "DEEP"
            interval = 600          # 每10分钟

        if level == self.state.level:
            self.state.consecutive_ticks += 1
        else:
            self.state.consecutive_ticks = 1

        self.state.level = level
        self.state.poll_interval = interval
        return level, interval

    def reset(self) -> None:
        """重置为 NORMAL."""
        self.state.last_interaction = time.time()
        self.state.level = "NORMAL"
        self.state.poll_interval = 60
        self.state.consecutive_ticks = 0

    def is_idle(self) -> bool:
        """是否进入空闲状态（可以执行 Drift Mode 的级别）. """
        return self.state.level in ("LOW", "DEEP")
