"""入口 — 启动 Web 服务 + Agent 循环."""

from __future__ import annotations

import asyncio
from pathlib import Path

from loguru import logger

from mindmate.bus.events import MessageBus
from mindmate.config import settings


async def run_agent_loop(bus: MessageBus) -> None:
    """被动循环：持续监听消息并处理."""
    from mindmate.agent.loop import AgentLoop

    loop = AgentLoop(bus=bus)
    await loop.run()


async def run_proactive_loop(bus: MessageBus) -> None:
    """主动循环：定时触发问候/闲聊."""
    from mindmate.proactive.loop import ProactiveLoop

    loop = ProactiveLoop(bus=bus)
    await loop.run()


async def run_outbound_consumer(bus: MessageBus) -> None:
    """消费出站消息，分段推送到 WebSocket 客户端."""
    from mindmate.utils.splitter import MessageSplitter

    while True:
        try:
            msg = await bus.consume_outbound()
            if not hasattr(bus, "push_to_clients"):
                continue

            push_fn = bus.push_to_clients
            content = msg.content
            is_proactive = msg.metadata.get("proactive", False) if msg.metadata else False

            # 分段推送
            segments = list(MessageSplitter.yield_segments(content))

            for seg, delay, is_last in segments:
                if delay > 0:
                    await asyncio.sleep(delay)
                await push_fn(
                    seg,
                    metadata={
                        **msg.metadata,
                        "segment": True,
                        "proactive": is_proactive,
                        "is_last": is_last,
                    },
                )
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Error pushing outbound")


async def run_web_server(bus: MessageBus) -> None:
    """启动 FastAPI Web 服务."""
    import uvicorn
    from mindmate.web.app import create_app

    app = create_app(bus)
    config = uvicorn.Config(app, host=settings.host, port=settings.port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main() -> None:
    """主入口：启动所有组件."""
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(str(log_dir / "mindmate.log"), rotation="10 MB", level="INFO")
    logger.info("=== MindMate starting ===")

    bus = MessageBus()

    # 启动 Web 服务器（阻塞，在后台线程跑 Uvicorn）
    web_task = asyncio.create_task(run_web_server(bus))

    # 启动 outbound 消费者（把消息推给 WebSocket）
    outbound_task = asyncio.create_task(run_outbound_consumer(bus))

    # 启动 Agent 被动循环
    agent_task = asyncio.create_task(run_agent_loop(bus))

    # 启动主动循环
    proactive_task = asyncio.create_task(run_proactive_loop(bus))

    # 保持运行
    try:
        await asyncio.gather(web_task, agent_task, proactive_task, outbound_task)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        for t in [agent_task, proactive_task, web_task, outbound_task]:
            t.cancel()


if __name__ == "__main__":
    asyncio.run(main())
