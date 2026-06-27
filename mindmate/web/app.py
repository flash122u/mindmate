"""FastAPI 应用 — Web 聊天 + 管理后台."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from mindmate.bus.events import InboundMessage

APP_DIR = Path(__file__).parent


def create_app(bus: Any) -> FastAPI:
    """创建 FastAPI 应用."""
    # 全局 WebSocket 客户端列表
    clients: set[WebSocket] = set()

    async def _broadcast(payload_obj: dict) -> None:
        """把一条事件推送给所有连接的客户端."""
        payload = json.dumps(payload_obj, ensure_ascii=False)
        dead = []
        for client in clients:
            try:
                await client.send_text(payload)
            except Exception:
                dead.append(client)
        for c in dead:
            clients.discard(c)

    async def _outbound_consumer() -> None:
        """后台任务：消费 outbound 总线，把回复/输入信号投递给 Web 客户端."""
        while True:
            try:
                msg = await bus.consume_outbound()
                meta = msg.metadata or {}
                event = meta.get("event", "message")
                if event == "typing":
                    # "正在输入"信号，无正文
                    await _broadcast({"type": "typing", "metadata": meta})
                else:
                    await _broadcast(
                        {"type": "message", "content": msg.content, "metadata": meta}
                    )
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in outbound consumer")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(_outbound_consumer())
        logger.info("Web outbound consumer started")
        yield
        task.cancel()

    app = FastAPI(title="MindMate", version="0.1.0", lifespan=lifespan)

    # 静态文件
    static_dir = APP_DIR / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    def _serve(name: str) -> str:
        return (static_dir / name).read_text(encoding="utf-8")

    # 聊天页面（首页即聊天）
    @app.get("/", response_class=HTMLResponse)
    async def index():
        return _serve("index.html")

    @app.get("/chat", response_class=HTMLResponse)
    async def chat_page():
        return _serve("index.html")

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard():
        return _serve("dashboard.html")

    # API: 发送消息（REST 备用入口）
    @app.post("/api/chat")
    async def send_message(content: str):
        await bus.publish_inbound(
            InboundMessage(
                channel="web",
                sender_id="user",
                chat_id="default",
                content=content,
            )
        )
        return {"status": "sent"}

    # WebSocket: 双向实时通信
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        clients.add(websocket)
        logger.info("Client connected ({} total)", len(clients))
        try:
            while True:
                data = await websocket.receive_text()
                await bus.publish_inbound(
                    InboundMessage(
                        channel="web",
                        sender_id="user",
                        chat_id="default",
                        content=data,
                    )
                )
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.exception("WebSocket error")
        finally:
            clients.discard(websocket)
            logger.info("Client disconnected ({} remaining)", len(clients))

    return app
