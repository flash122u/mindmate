"""每日调度器 —— 驱动小暖的"内在生活"自动运转.

每天在指定时段（默认凌晨 3 点，安静时段），为每个活跃用户
自动生成当天的私密日记 + 梦，无需手动触发。

采用轻量 asyncio 循环，不引入 APScheduler（保持零额外依赖）。
通过可注入的时钟使逻辑可确定性测试。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime

from loguru import logger


class DailyScheduler:
    """每天定时为活跃用户触发每日任务."""

    def __init__(
        self,
        run_cb: Callable[[str], Awaitable[None]],
        list_sessions: Callable[[], list[str]],
        hour: int = 3,
        check_interval_s: float = 600.0,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """
        Args:
            run_cb: async (session_key) -> None，对单个用户执行每日任务
            list_sessions: 返回当前活跃用户 session_key 列表
            hour: 每天几点触发（0-23）
            check_interval_s: 轮询间隔
            clock: 返回当前时间的可注入时钟（测试用）
        """
        self.run_cb = run_cb
        self.list_sessions = list_sessions
        self.hour = hour
        self.check_interval_s = check_interval_s
        self._clock = clock or datetime.now
        # 每个 session 上次执行的日期，防同一天重复
        self._last_run_date: dict[str, str] = {}
        self._running = False

    async def run(self) -> None:
        self._running = True
        logger.info("DailyScheduler started (fires at {:02d}:00)", self.hour)
        while self._running:
            try:
                await asyncio.sleep(self.check_interval_s)
                await self.tick()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in daily scheduler")

    async def tick(self) -> int:
        """检查一次：到点则为每个未执行过的活跃用户触发任务.

        返回本次实际触发的用户数（便于测试）。
        """
        now = self._clock()
        if now.hour != self.hour:
            return 0

        today = now.strftime("%Y-%m-%d")
        fired = 0
        for sk in self.list_sessions():
            if self._last_run_date.get(sk) == today:
                continue
            try:
                await self.run_cb(sk)
                self._last_run_date[sk] = today
                fired += 1
                logger.info("Daily inner-life generated for {}", sk)
            except Exception:
                logger.exception("Daily task failed for {}", sk)
        return fired

    def stop(self) -> None:
        self._running = False
