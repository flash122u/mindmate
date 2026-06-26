"""入口 — 启动 Web 服务 + Agent 循环."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from loguru import logger

from mindmate.bus.events import MessageBus
from mindmate.channels.web import WebChannel
from mindmate.config import settings
from mindmate.proactive.loop import ProactiveLoop
from mindmate.proactive.passive import PassiveLoop


async def run_agent_loop(bus: MessageBus) -> None:
    """被动循环：持续监听消息并处理."""
    from mindmate.agent.loop import AgentLoop

    loop = AgentLoop(bus=bus)
    passive = PassiveLoop(bus, loop._process_message)
    await passive.run()


async def run_proactive_loop(bus: MessageBus) -> None:
    """主动循环：定时触发问候/闲聊."""
    from mindmate.agent.energy import EnergyModel

    energy = EnergyModel()
    proactive = ProactiveLoop(bus, energy)
    await proactive.run()


async def run_web_server(bus: MessageBus) -> None:
    """启动 FastAPI Web 服务."""
    import uvicorn
    from mindmate.web.app import create_app

    app = create_app(bus)
    uvicorn.run(app, host=settings.host, port=settings.port)


async def main() -> None:
    """主入口：启动所有组件."""
    logger.add("logs/mindmate.log", rotation="10 MB", level="INFO")
    logger.info("=== MindMate starting ===")

    bus = MessageBus()

    # 启动 Web 服务器（后台任务）
    web_task = asyncio.create_task(run_web_server(bus))

    # 启动 Agent 被动循环
    agent_task = asyncio.create_task(run_agent_loop(bus))

    # 启动主动循环
    proactive_task = asyncio.create_task(run_proactive_loop(bus))

    # 保持运行
    try:
        await asyncio.gather(web_task, agent_task, proactive_task)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        agent_task.cancel()
        proactive_task.cancel()
        web_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
