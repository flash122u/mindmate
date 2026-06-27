"""被动消息处理循环."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from mindmate.bus.events import MessageBus


class PassiveLoop:
    """
    被动循环 — 消息驱动的响应模式.

    工作流程：
    1. 从 MessageBus 消费 InboundMessage
    2. 交给 AgentLoop 处理
    3. 将 OutboundMessage 推回总线
    """

    def __init__(self, bus: MessageBus, processor: Any) -> None:
        self.bus = bus
        self.processor = processor
        self._running = False

    async def run(self) -> None:
        self._running = True
        logger.info("PassiveLoop started")

        while self._running:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0,
                )
            except asyncio.TimeoutError:
                continue

            try:
                response = await self.processor(msg)
                if response:
                    await self.bus.publish_outbound(response)
            except Exception:
                logger.exception("Error in passive loop")

    def stop(self) -> None:
        self._running = False
