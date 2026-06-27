"""主动行为循环 — 能量模型驱动，LLM 生成自然的主动消息.

不再用硬编码模板（那会像骚扰）。多用户：遍历每个活跃用户，
各自用独立的能量模型判断开口时机。

1. 定时遍历活跃用户
2. 该用户能量模型说适合 → 调 generate_cb(session_key) 生成自然消息
3. 标记该用户进入冷却
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from loguru import logger

from mindmate.agent.energy import EnergyRegistry


class ProactiveLoop:
    """主动循环 — 在合适时机让 Agent 主动找各个用户."""

    def __init__(
        self,
        energy: EnergyRegistry,
        generate_cb: Callable[[str], Awaitable[None]],
        list_sessions: Callable[[], list[str]],
        check_interval_s: float = 60.0,
    ) -> None:
        """
        Args:
            energy: 能量注册表（per-user）
            generate_cb: async (session_key) -> None，生成并投递主动消息
            list_sessions: 返回活跃用户 session_key 列表
            check_interval_s: 检查间隔
        """
        self.energy = energy
        self.generate_cb = generate_cb
        self.list_sessions = list_sessions
        self.check_interval_s = check_interval_s
        self._running = False

    async def run(self) -> None:
        self._running = True
        logger.info("ProactiveLoop started (check every {}s)", self.check_interval_s)
        while self._running:
            try:
                await asyncio.sleep(self.check_interval_s)
                await self.tick()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in proactive loop")

    async def tick(self) -> int:
        """检查一轮所有活跃用户，返回实际主动开口的用户数."""
        fired = 0
        # 已有能量状态的用户 ∪ 有历史的用户
        sessions = set(self.list_sessions()) | set(self.energy.sessions())
        for sk in sessions:
            model = self.energy.get(sk)
            ok, reason = model.should_reach_out()
            if not ok:
                logger.debug("Proactive skip {}: {}", sk, reason)
                continue
            try:
                await self.generate_cb(sk)
                model.mark_proactive()
                fired += 1
                logger.info("Proactive: reached out to {}", sk)
            except Exception:
                logger.exception("Proactive generation failed for {}", sk)
        return fired

    def stop(self) -> None:
        self._running = False
