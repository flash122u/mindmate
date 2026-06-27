"""入口 — 启动 Web 服务 + Agent 循环."""

from __future__ import annotations

import asyncio

from loguru import logger

from mindmate.bus.events import MessageBus
from mindmate.config import settings
from mindmate.proactive.passive import PassiveLoop


async def run_agent_loop(bus: MessageBus) -> None:
    """被动循环：持续监听消息并处理."""
    from mindmate.agent.loop import AgentLoop

    loop = AgentLoop(bus=bus)
    passive = PassiveLoop(bus, loop._process_message)
    await passive.run()


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

    # Web 服务器 + Agent 被动循环并行运行
    web_task = asyncio.create_task(run_web_server(bus))
    agent_task = asyncio.create_task(run_agent_loop(bus))

    # 注：主动循环（ProactiveLoop）尚未完成，Step 4 再启用
    # proactive_task = asyncio.create_task(run_proactive_loop(bus))

    try:
        await asyncio.gather(web_task, agent_task)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Shutting down...")
        agent_task.cancel()
        web_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
