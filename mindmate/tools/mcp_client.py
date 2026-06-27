"""MCP 接入 —— 把外部 MCP server 的工具接进来.

通过 MCP（Model Context Protocol）stdio 连接外部工具服务，
把它们的工具包装成本项目的 Tool，注册进同一个 ToolRegistry，
这样小暖就能调用任意 MCP server 提供的能力。

配置（settings.mcp_servers）示例：
{
  "weather": {"command": "uvx", "args": ["mcp-server-weather"]},
  "fs": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/p"]}
}

未配置任何 server、或未安装 `mcp` 包时，本模块优雅跳过（不影响主流程）。
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any

from loguru import logger

from mindmate.tools.base import Tool, ToolRegistry


class MCPTool(Tool):
    """把一个 MCP server 工具包装成本项目的 Tool."""

    def __init__(
        self, session: Any, name: str, description: str, parameters: dict[str, Any]
    ) -> None:
        self._session = session
        self.name = name
        self.description = description or f"MCP tool {name}"
        self.parameters = parameters or {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> str:
        result = await self._session.call_tool(self.name, kwargs)
        return self._extract_text(result)

    @staticmethod
    def _extract_text(result: Any) -> str:
        """从 MCP CallToolResult 里抽取纯文本."""
        parts: list[str] = []
        for item in getattr(result, "content", []) or []:
            text = getattr(item, "text", None)
            if text:
                parts.append(text)
        return "\n".join(parts) if parts else str(result)


class MCPManager:
    """连接配置中的 MCP server，并把工具注册进 registry."""

    def __init__(self, servers: dict[str, dict[str, Any]]) -> None:
        self.servers = servers or {}
        self._stack: AsyncExitStack | None = None
        self.tools: list[MCPTool] = []

    async def connect(self, registry: ToolRegistry) -> int:
        """连接所有 server，注册工具，返回注册的工具数（失败优雅跳过）."""
        if not self.servers:
            return 0
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            logger.warning(
                "未安装 mcp 包，跳过 MCP 接入。需要请: pip install mcp"
            )
            return 0

        self._stack = AsyncExitStack()
        count = 0
        for name, cfg in self.servers.items():
            try:
                params = StdioServerParameters(
                    command=cfg["command"], args=cfg.get("args", [])
                )
                read, write = await self._stack.enter_async_context(
                    stdio_client(params)
                )
                session = await self._stack.enter_async_context(
                    ClientSession(read, write)
                )
                await session.initialize()
                resp = await session.list_tools()
                for t in resp.tools:
                    tool = MCPTool(session, t.name, t.description, t.inputSchema)
                    registry.register(tool)
                    self.tools.append(tool)
                    count += 1
                logger.info("MCP server '{}' connected, {} tools", name, len(resp.tools))
            except Exception:
                logger.exception("连接 MCP server '{}' 失败，跳过", name)
        return count

    async def close(self) -> None:
        if self._stack is not None:
            try:
                await self._stack.aclose()
            except Exception:
                logger.debug("MCP cleanup error (ignored)")
            self._stack = None
