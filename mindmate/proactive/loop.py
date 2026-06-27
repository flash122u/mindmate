"""主动行为循环."""

from __future__ import annotations

import asyncio
import random

from loguru import logger

from mindmate.agent.energy import EnergyModel
from mindmate.bus.events import MessageBus, OutboundMessage


class ProactiveLoop:
    """
    主动循环 — 能量模型驱动的主动触发.

    工作流程：
    1. 每 tick 检查能量级别
    2. HIGH → 暂停
    3. NORMAL → 可能发送问候/关心
    4. LOW → 可能发送日常废话/分享
    5. Drift → 无事可做时执行后台维护
    """

    def __init__(self, bus: MessageBus, energy: EnergyModel) -> None:
        self.bus = bus
        self.energy = energy
        self._running = False

        # 主动消息模板池
        self._greetings = [
            "今天过得怎么样？",
            "嘿，在干嘛呢～",
            "突然想你了，你今天还好吗？",
            "外面天气不错吧？",
        ]
        self._small_talk = [
            "刚刚看到一只很可爱的猫，想到你了",
            "今天喝到一杯很好喝的奶茶",
            "路上遇到一个很奇怪的人，哈哈",
            "你知道吗，我今天发现了一个冷知识：树懒一天睡15个小时",
        ]
        self._care = [
            "好久没聊了，有点担心你",
            "希望你今天一切都好",
            "记得按时吃饭哦",
        ]

    async def run(self) -> None:
        self._running = True
        logger.info("ProactiveLoop started")

        while self._running:
            try:
                level, interval = self.energy.tick()

                if interval > 0:
                    await asyncio.sleep(interval)
                    continue

                # 能量级别 HIGH 时不主动发消息
                if level == "HIGH":
                    await asyncio.sleep(10)
                    continue

                # 随机决定是否主动发消息（降低频率，避免刷屏）
                if random.random() < 0.3:
                    msg = self._pick_message(level)
                    logger.info("Proactive: [%s] %s", level, msg)
                    await self.bus.publish_outbound(
                        OutboundMessage(
                            channel="web",
                            chat_id="default",
                            content=msg,
                            metadata={"proactive": True, "level": level},
                        )
                    )
                    self.energy.reset()
                else:
                    await asyncio.sleep(60)

            except Exception:
                logger.exception("Error in proactive loop")

    def _pick_message(self, level: str) -> str:
        if level == "NORMAL":
            return random.choice(self._greetings)
        elif level == "LOW":
            return random.choice(self._small_talk)
        return random.choice(self._care)

    def stop(self) -> None:
        self._running = False
