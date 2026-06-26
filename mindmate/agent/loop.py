"""Agent Loop — 核心处理引擎（被动响应）.

参考 nanobot agent/loop.py 的状态机：
RESTORE → COMPACT → BUILD → RUN → SAVE → RESPOND → DONE
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from mindmate.bus.events import InboundMessage, OutboundMessage
from mindmate.llm import DeepSeekProvider
from mindmate.memory import MemoryStore


@dataclass
class TurnContext:
    """单次对话的上下文."""
    msg: InboundMessage
    session_key: str = "default"
    history: list[dict[str, Any]] = field(default_factory=list)
    final_content: str | None = None
    tools_used: list[str] = field(default_factory=list)
    outbound: OutboundMessage | None = None


class AgentLoop:
    """
    Agent 主循环 — 被动响应模式.

    收到消息后：
    1. 恢复会话上下文（SOUL + 近期历史）
    2. 构建 LLM 消息列表
    3. 调用 LLM
    4. 执行工具调用（如有）
    5. 保存响应到历史
    6. 返回 OutboundMessage
    """

    def __init__(self, bus: Any, workspace: Path | None = None) -> None:
        self.bus = bus
        self.provider = DeepSeekProvider()
        self.memory = MemoryStore(workspace)
        self._running = False

    async def run(self) -> None:
        """启动 Agent 主循环，持续监听消息总线."""
        self._running = True
        logger.info("AgentLoop started")

        while self._running:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0,
                )
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.warning("Error consuming message: %s", e)
                continue

            try:
                response = await self._process_message(msg)
                if response:
                    await self.bus.publish_outbound(response)
            except Exception:
                logger.exception("Error processing message")
                await self.bus.publish_outbound(
                    OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content="抱歉，我这边出了点问题，请稍后再试.",
                    )
                )

    def stop(self) -> None:
        self._running = False
        logger.info("AgentLoop stopping")

    async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """处理单条消息，返回回复."""
        logger.info("Processing message from {}:{}", msg.channel, msg.sender_id)

        # 1. 构建上下文
        context = await self._build_context(msg)

        # 2. 调用 LLM
        response = await self.provider.chat(
            messages=context.messages,
            temperature=0.7,
        )

        # 3. 保存历史
        self.memory.append_history(f"[{msg.sender_id}] {msg.content}", context.session_key)
        self.memory.append_history(f"[Assistant] {response['content']}", context.session_key)

        # 4. 推送到所有 WebSocket 客户端
        if hasattr(self.bus, "push_to_clients"):
            await self.bus.push_to_clients(
                response["content"],
                metadata={"channel": msg.channel, "proactive": False},
            )

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=response["content"],
        )

    async def _build_context(self, msg: InboundMessage) -> TurnContext:
        """构建 LLM 上下文：SOUL + 近期历史 + 当前消息."""
        ctx = TurnContext(msg=msg)

        # 加载人格
        soul = self.memory.read_soul()

        # 加载近期历史
        recent = self.memory.read_recent_for_prompt(ctx.session_key, max_entries=20)

        # 构建系统消息
        system_parts = [
            "你是一个温暖的心理陪伴者，叫小暖。",
            "你关心对方的感受，不会急于给建议。",
            "你的回复简短自然，像朋友聊天一样。",
            "",
            "---",
            "",
            f"## 你的身份\n{soul}",
            "",
            "---",
            "",
        ]
        if recent:
            system_parts.extend(["## 最近对话", recent])
            system_parts.append("")
            system_parts.append("---")

        ctx.messages = [
            {"role": "system", "content": "\n".join(system_parts)},
            {"role": "user", "content": msg.content},
        ]

        return ctx
