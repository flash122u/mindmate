"""WebSocket 通道 — 参考 nanobot channels/websocket.py."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from loguru import logger
from websockets.server import serve

from mindmate.bus.events import InboundMessage, MessageBus, OutboundMessage


class WebChannel:
    """
    WebSocket 通道，处理浏览器客户端的连接.

    客户端连接后：
    - 接收 OutboundMessage → 推送给客户端
    - 接收客户端消息 → 转为 InboundMessage 发布到总线
    """

    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus
        self._clients: set[Any] = set()
        self._outbound_handler: asyncio.Task | None = None

    async def handle_connection(self, websocket: Any) -> None:
        """处理单个 WebSocket 连接."""
        self._clients.add(websocket)
        logger.info("Client connected (%d total)", len(self._clients))

        try:
            async for raw in websocket:
                try:
                    data = json.loads(raw)
                    content = data.get("content", "")
                    if content:
                        await self.bus.publish_inbound(
                            InboundMessage(
                                channel="web",
                                sender_id="default",
                                chat_id="default",
                                content=content,
                            )
                        )
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON from client")
        except Exception:
            pass
        finally:
            self._clients.discard(websocket)
            logger.info("Client disconnected (%d remaining)", len(self._clients))

    async def start(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        """启动 WebSocket 服务器."""
        logger.info("WebChannel starting on ws://%s:%d", host, port)

        # 启动 outbound 分发
        self._outbound_handler = asyncio.create_task(self._dispatch_outbound())

        async with serve(self.handle_connection, host, port):
            logger.info("WebSocket server running on ws://%s:%d", host, port)
            await asyncio.Future()  # 永驻

    async def _dispatch_outbound(self) -> None:
        """将 OutboundMessage 推送给所有连接的客户端."""
        while True:
            try:
                msg = await self.bus.consume_outbound()
                payload = {
                    "type": "message",
                    "content": msg.content,
                    "metadata": msg.metadata,
                }
                if self._clients:
                    await asyncio.gather(
                        *(c.send(json.dumps(payload)) for c in self._clients),
                        return_exceptions=True,
                    )
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error dispatching outbound message")

    def stop(self) -> None:
        if self._outbound_handler:
            self._outbound_handler.cancel()
