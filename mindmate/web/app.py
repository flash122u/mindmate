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
    # 按用户分组的 WebSocket 连接：user_id -> 该用户的连接集合
    clients: dict[str, set[WebSocket]] = {}

    async def _send_to_user(user_id: str, payload_obj: dict) -> None:
        """把一条事件只推送给目标用户的连接（多用户路由）."""
        conns = clients.get(user_id)
        if not conns:
            return
        payload = json.dumps(payload_obj, ensure_ascii=False)
        dead = []
        for client in conns:
            try:
                await client.send_text(payload)
            except Exception:
                dead.append(client)
        for c in dead:
            conns.discard(c)

    async def _outbound_consumer() -> None:
        """后台任务：消费 outbound 总线，按 chat_id 路由给对应用户."""
        while True:
            try:
                msg = await bus.consume_outbound()
                meta = msg.metadata or {}
                event = meta.get("event", "message")
                user_id = msg.chat_id or "default"
                if event == "typing":
                    await _send_to_user(user_id, {"type": "typing", "metadata": meta})
                else:
                    await _send_to_user(
                        user_id,
                        {"type": "message", "content": msg.content, "metadata": meta},
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

    # ------------------------------------------------------------------
    # 医生后台 API（只读，共享同一 SQLite）
    # ------------------------------------------------------------------
    from mindmate.memory import MemoryStore

    store = MemoryStore()

    @app.get("/api/dashboard/overview")
    async def dashboard_overview(session_key: str = "default"):
        rel = store.get_relationship(session_key)
        anchors = store.get_emotion_anchors(session_key, limit=1000)
        alerts = store.get_crisis_alerts(session_key, limit=1000)
        history = store.read_history(session_key, limit=100000)
        avg_valence = (
            sum(a["valence"] for a in anchors) / len(anchors) if anchors else 0.0
        )
        return {
            "stage": rel["stage"],
            "anchor_count": len(anchors),
            "alert_count": len(alerts),
            "high_alert_count": sum(1 for a in alerts if a["level"] == "high"),
            "turn_count": len(history),
            "avg_valence": round(avg_valence, 2),
        }

    @app.get("/api/dashboard/trends")
    async def dashboard_trends(session_key: str = "default"):
        return {"points": store.get_emotion_trend(session_key, limit=200)}

    @app.get("/api/dashboard/alerts")
    async def dashboard_alerts(session_key: str = "default"):
        return {"alerts": store.get_crisis_alerts(session_key, limit=100)}

    @app.get("/api/dashboard/history")
    async def dashboard_history(session_key: str = "default", limit: int = 100):
        return {"history": store.read_history(session_key, limit=limit)}

    # WebSocket: 双向实时通信。?uid=xxx 标识用户，缺省 default
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        uid = websocket.query_params.get("uid") or "default"
        clients.setdefault(uid, set()).add(websocket)
        logger.info("Client connected (uid={}, {} conns)", uid, len(clients[uid]))
        try:
            while True:
                data = await websocket.receive_text()
                await bus.publish_inbound(
                    InboundMessage(
                        channel="web",
                        sender_id=uid,
                        chat_id=uid,
                        content=data,
                    )
                )
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.exception("WebSocket error")
        finally:
            conns = clients.get(uid)
            if conns:
                conns.discard(websocket)
                if not conns:
                    clients.pop(uid, None)
            logger.info("Client disconnected (uid={})", uid)

    # 后台：用户列表（供 dashboard 切换）
    @app.get("/api/dashboard/users")
    async def dashboard_users():
        return {"users": store.list_sessions()}

    return app
