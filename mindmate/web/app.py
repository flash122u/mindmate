"""FastAPI 应用 — Web 聊天 + 管理后台."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from mindmate.bus.events import InboundMessage


APP_DIR = Path(__file__).parent


def create_app(bus: Any) -> FastAPI:
    """创建 FastAPI 应用."""
    app = FastAPI(title="MindMate", version="0.1.0")

    # 全局 WebSocket 客户端列表
    _clients: list[WebSocket] = []

    # 静态文件
    static_dir = APP_DIR / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # 聊天页面
    @app.get("/", response_class=HTMLResponse)
    async def index():
        return (static_dir / "index.html").read_text(encoding="utf-8")

    @app.get("/chat", response_class=HTMLResponse)
    async def chat_page():
        return (static_dir / "chat.html").read_text(encoding="utf-8")

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard():
        return (static_dir / "dashboard.html").read_text(encoding="utf-8")

    # API: 发送消息
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
        _clients.append(websocket)

        try:
            while True:
                # 1. 接收客户端消息 → 推送到总线
                data = await websocket.receive_text()
                await bus.publish_inbound(
                    InboundMessage(
                        channel="web_ws",
                        sender_id="user",
                        chat_id="default",
                        content=data,
                    )
                )
        except WebSocketDisconnect:
            _clients.remove(websocket)
        except Exception:
            if websocket in _clients:
                _clients.remove(websocket)

    # 供 Agent Loop 调用的推送方法
    async def push_to_clients(content: str, metadata: dict | None = None) -> None:
        """Agent 通过此方法推送消息给所有连接的客户端."""
        import json
        payload = {"type": "message", "content": content, "metadata": metadata or {}}
        disconnected = []
        for client in _clients:
            try:
                await client.send_text(json.dumps(payload, ensure_ascii=False))
            except Exception:
                disconnected.append(client)
        for c in disconnected:
            if c in _clients:
                _clients.remove(c)

    # 挂载到 bus 上，供 Agent 调用
    bus.push_to_clients = push_to_clients

    return app
