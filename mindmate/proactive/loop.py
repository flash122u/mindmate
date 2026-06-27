"""主动行为循环 — 能量模型驱动，LLM 生成自然的主动消息.

不再用硬编码模板（那会像骚扰）。而是：
1. 定时检查能量模型，判断此刻是否适合主动开口
2. 适合 → 调用 AgentLoop.generate_proactive() 用 LLM 生成自然消息
3. 发过后进入冷却
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from loguru import logger

from mindmate.agent.energy import EnergyModel


class ProactiveLoop:
    """主动循环 — 在合适时机让 Agent 主动找对方."""

    def __init__(
        self,
        energy: EnergyModel,
        generate_cb: Callable[[], Awaitable[None]],
        check_interval_s: float = 60.0,
        session_key: str = "default",
    ) -> None:
        """
        Args:
            energy: 与 AgentLoop 共享的能量模型
            generate_cb: 生成并投递一条主动消息的异步回调
            check_interval_s: 每隔多久检查一次是否该开口
            session_key: 目标会话
        """
        self.energy = energy
        self.generate_cb = generate_cb
        self.check_interval_s = check_interval_s
        self.session_key = session_key
        self._running = False

    async def run(self) -> None:
        self._running = True
        logger.info("ProactiveLoop started (check every {}s)", self.check_interval_s)

        while self._running:
            try:
                await asyncio.sleep(self.check_interval_s)
                ok, reason = self.energy.should_reach_out()
                if not ok:
                    logger.debug("Proactive skip: {}", reason)
                    continue

                logger.info("Proactive: reaching out")
                await self.generate_cb()
                self.energy.mark_proactive()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in proactive loop")

    def stop(self) -> None:
        self._running = False
