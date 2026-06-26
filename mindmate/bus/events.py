"""消息总线 — 参考 nanobot bus/queue.py."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class InboundMessage:
    """从通道到达的消息."""
    channel: str
    sender_id: str
    chat_id: str
    content: str
    media: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OutboundMessage:
    """发送给通道的回复."""
    channel: str
    chat_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class MessageBus:
    """异步消息总线，解耦通道与 Agent 核心."""

    def __init__(self) -> None:
        self._inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self._outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()
        self._handlers: dict[str, list[asyncio.Queue]] = {}

    async def publish_inbound(self, msg: InboundMessage) -> None:
        """发布入站消息."""
        await self._inbound.put(msg)

    async def consume_inbound(self) -> InboundMessage:
        """消费入站消息."""
        return await self._inbound.get()

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        """发布出站消息."""
        await self._outbound.put(msg)

    async def consume_outbound(self) -> OutboundMessage:
        """消费出站消息."""
        return await self._outbound.get()
