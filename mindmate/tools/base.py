"""工具抽象 + 注册表 —— 工具调用的地基.

Tool 定义一个可被 LLM 调用的能力；ToolRegistry 收集工具，
对外输出 OpenAI tools 格式（DeepSeek 兼容），并负责按名执行。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from loguru import logger


class Tool(ABC):
    """一个可被 LLM 调用的工具."""

    #: 工具名（LLM 用它来调用，须唯一、英文）
    name: str = ""
    #: 给 LLM 看的描述（决定模型何时调用）
    description: str = ""
    #: 参数的 JSON Schema（OpenAI function parameters 格式）
    parameters: dict[str, Any] = {"type": "object", "properties": {}}

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """执行工具，返回喂回给 LLM 的文本结果."""
        raise NotImplementedError

    def schema(self) -> dict[str, Any]:
        """转成 OpenAI tools 格式的一项."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """工具注册表."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if not tool.name:
            raise ValueError("Tool must have a name")
        self._tools[tool.name] = tool
        logger.info("Registered tool: {}", tool.name)

    def is_empty(self) -> bool:
        return not self._tools

    def get(self, name: str) -> Tool | None:
        """按名取工具（不存在返回 None）."""
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def schemas(self) -> list[dict[str, Any]]:
        """所有工具的 OpenAI tools 格式列表."""
        return [t.schema() for t in self._tools.values()]

    async def execute(self, name: str, arguments: dict[str, Any]) -> str:
        """按名执行工具；未知工具/异常返回可读错误（不抛出，让 LLM 自行处理）."""
        tool = self._tools.get(name)
        if tool is None:
            return f"[工具 {name} 不存在]"
        try:
            return await tool.execute(**(arguments or {}))
        except Exception as e:
            logger.exception("Tool {} failed", name)
            return f"[工具 {name} 执行出错: {e}]"
