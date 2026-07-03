"""入口 — 启动 Web 服务 + 被动循环 + 主动循环."""

from __future__ import annotations

import asyncio

from loguru import logger

from mindmate.agent.energy import EnergyRegistry
from mindmate.agent.loop import AgentLoop
from mindmate.agent.scheduler import DailyScheduler
from mindmate.bus.events import MessageBus
from mindmate.config import settings
from mindmate.proactive.loop import ProactiveLoop
from mindmate.proactive.passive import PassiveLoop
from mindmate.tools import ToolRegistry, WeatherTool
from mindmate.tools.activity_tool import RandomActivityTool
from mindmate.tools.mcp_client import MCPManager
from mindmate.tools.time_tool import TimeTool


async def build_tools() -> tuple[ToolRegistry | None, MCPManager | None]:
    """构建工具注册表：内置工具 + MCP server 工具."""
    if not settings.tools_enabled:
        return None, None
    registry = ToolRegistry()
    registry.register(WeatherTool())
    registry.register(TimeTool())
    registry.register(RandomActivityTool())
    mcp = MCPManager(settings.mcp_servers)
    try:
        await mcp.connect(registry)
    except Exception:
        logger.exception("MCP connect failed, continuing with built-in tools")
    return registry, mcp


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
    # 工具：内置（天气）+ MCP server
    tools, mcp = await build_tools()
    if tools is not None:
        logger.info("Tools enabled: {}", tools.names())
    # 能量注册表：每个用户独立的沉默计时/冷却/每日计数
    energy = EnergyRegistry()
    agent = AgentLoop(bus=bus, energy=energy, tools=tools)

    passive = PassiveLoop(bus, agent._process_message)
    proactive = ProactiveLoop(
        energy, agent.generate_proactive, list_sessions=agent.memory.list_sessions
    )

    tasks = [
        asyncio.create_task(run_web_server(bus)),
        asyncio.create_task(passive.run()),
        asyncio.create_task(proactive.run()),
    ]

    # 每日内在生活调度器（日记/梦自动生成）
    if settings.inner_life_enabled:
        scheduler = DailyScheduler(
            run_cb=agent.run_daily_inner_life,
            list_sessions=agent.memory.list_sessions,
            hour=settings.inner_life_hour,
        )
        tasks.append(asyncio.create_task(scheduler.run()))

    try:
        await asyncio.gather(*tasks)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Shutting down...")
        for t in tasks:
            t.cancel()
    finally:
        if mcp is not None:
            await mcp.close()


if __name__ == "__main__":
    asyncio.run(main())
