"""入口 — 启动 Web 服务 + 被动循环 + 主动循环."""

from __future__ import annotations

import asyncio

from loguru import logger

from mindmate.agent.energy import EnergyModel
from mindmate.agent.loop import AgentLoop
from mindmate.bus.events import MessageBus
from mindmate.config import settings
from mindmate.proactive.loop import ProactiveLoop
from mindmate.proactive.passive import PassiveLoop


async def run_web_server(bus: MessageBus) -> None:
    """启动 FastAPI Web 服务（异步，不阻塞事件循环）."""
    import uvicorn

    from mindmate.web.app import create_app

    app = create_app(bus)
    config = uvicorn.Config(
        app,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main() -> None:
    """主入口：启动所有组件."""
    logger.add("logs/mindmate.log", rotation="10 MB", level="INFO")
    logger.info("=== MindMate starting ===")

    bus = MessageBus()
    # 能量模型由被动循环（重置沉默计时）和主动循环（判断开口时机）共享
    energy = EnergyModel()
    agent = AgentLoop(bus=bus, energy=energy)

    passive = PassiveLoop(bus, agent._process_message)
    proactive = ProactiveLoop(energy, agent.generate_proactive)

    web_task = asyncio.create_task(run_web_server(bus))
    agent_task = asyncio.create_task(passive.run())
    proactive_task = asyncio.create_task(proactive.run())

    try:
        await asyncio.gather(web_task, agent_task, proactive_task)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Shutting down...")
        agent_task.cancel()
        proactive_task.cancel()
        web_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
