"""能量模型 — 决定"什么时候主动找对方".

借鉴 nanobot 的能量概念，但聚焦一个朴素问题：
真人朋友不会秒回，也不会一直骚扰你。ta 会在你沉默一阵后偶尔冒个泡，
但有分寸——半夜不发、刚聊完不发、一天也不会发太多次。

设计：
- on_user_message(): 用户说话 → 重置沉默计时
- should_reach_out(): 综合判断此刻是否适合主动开口
- mark_proactive(): 主动发过后进入冷却
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EnergyModel:
    """主动行为调度器."""

    # 沉默多久后才考虑主动开口（秒）。默认 30 分钟。
    idle_threshold_s: float = 1800.0
    # 两次主动之间的最小冷却（秒）。默认 2 小时。
    cooldown_s: float = 7200.0
    # 安静时段 [start, end)，这期间不主动打扰。默认 23:00–08:00。
    quiet_start: int = 23
    quiet_end: int = 8
    # 每天最多主动几次。
    max_per_day: int = 4

    last_interaction: float = field(default_factory=time.time)
    last_proactive: float = 0.0
    _proactive_count: int = 0
    _count_day: str = ""

    def on_user_message(self, now: float | None = None) -> None:
        """用户发来消息 → 重置沉默计时."""
        self.last_interaction = now if now is not None else time.time()

    def mark_proactive(self, now: float | None = None) -> None:
        """记录一次主动开口，进入冷却."""
        t = now if now is not None else time.time()
        self.last_proactive = t
        # 主动开口也算一次"互动"，重置沉默计时，避免连环发
        self.last_interaction = t
        day = self._day_of(t)
        if day != self._count_day:
            self._count_day = day
            self._proactive_count = 0
        self._proactive_count += 1

    def is_quiet_hour(self, hour: int) -> bool:
        """判断某个小时是否落在安静时段."""
        if self.quiet_start == self.quiet_end:
            return False
        if self.quiet_start < self.quiet_end:
            return self.quiet_start <= hour < self.quiet_end
        # 跨午夜（如 23–8）
        return hour >= self.quiet_start or hour < self.quiet_end

    def should_reach_out(self, now: float | None = None) -> tuple[bool, str]:
        """综合判断此刻是否适合主动开口.

        Returns:
            (是否开口, 原因/拒绝理由)
        """
        t = now if now is not None else time.time()
        dt = datetime.fromtimestamp(t)

        # 1. 安静时段不打扰
        if self.is_quiet_hour(dt.hour):
            return False, "quiet_hour"

        # 2. 沉默时长未达阈值
        idle = t - self.last_interaction
        if idle < self.idle_threshold_s:
            return False, "not_idle_enough"

        # 3. 冷却中
        if self.last_proactive and (t - self.last_proactive) < self.cooldown_s:
            return False, "cooldown"

        # 4. 今日次数上限
        if self._day_of(t) == self._count_day and self._proactive_count >= self.max_per_day:
            return False, "daily_limit"

        return True, "ok"

    @staticmethod
    def _day_of(t: float) -> str:
        return datetime.fromtimestamp(t).strftime("%Y-%m-%d")
