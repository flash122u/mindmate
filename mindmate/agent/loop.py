"""Agent Loop — 核心处理引擎（被动响应）.

参考 nanobot agent/loop.py 的状态机：
RESTORE → COMPACT → BUILD → RUN → SAVE → RESPOND → DONE
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from mindmate.bus.events import InboundMessage, OutboundMessage
from mindmate.llm import DeepSeekProvider
from mindmate.memory import MemoryStore
from mindmate.personality.defense import DefenseMechanism
from mindmate.personality.relationship import RelationshipManager


@dataclass
class TurnContext:
    """单次对话的上下文."""
    msg: InboundMessage
    session_key: str = "default"
    history: list[dict[str, Any]] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    final_content: str | None = None
    tools_used: list[str] = field(default_factory=list)
    outbound: OutboundMessage | None = None


class AgentLoop:
    """
    Agent 主循环 — 被动响应模式.

    收到消息后：
    1. 恢复会话上下文（SOUL + 防御检查 + 关系状态 + 近期历史）
    2. 构建 LLM 消息列表
    3. 调用 LLM
    4. 保存响应到历史
    5. 更新关系阶段
    6. 推送回复
    """

    def __init__(self, bus: Any, workspace: Path | None = None) -> None:
        self.bus = bus
        self.provider = DeepSeekProvider()
        self.memory = MemoryStore(workspace)
        self.defense = DefenseMechanism()
        self.relationship = RelationshipManager(self.memory)
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

        # 1. 构建上下文（含防御检查 + 关系状态）
        context = await self._build_context(msg)

        # 2. 调用 LLM
        response = await self.provider.chat(
            messages=context.messages,
            temperature=0.7,
        )

        # 3. 保存历史（按 role 独立存储，支持多轮对话重建）
        self.memory.append_history("user", msg.content, context.session_key)
        self.memory.append_history("assistant", response["content"], context.session_key)

        # 4. 更新关系阶段（根据情感倾向）
        self.relationship.update(msg.content, context.session_key)

        # 5. 返回回复（由上层 PassiveLoop 发到 outbound 总线，Web 端消费投递）
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=response["content"],
        )

    async def _build_context(self, msg: InboundMessage) -> TurnContext:
        """构建 LLM 上下文：system(人格/关系/防御) + 真实多轮对话 + 当前消息."""
        ctx = TurnContext(msg=msg)

        # 加载人格
        soul = self.memory.read_soul()

        # 防御检查
        defense_result = self.defense.check(msg.content, ctx.session_key)
        defense_prompt = self.defense.build_defense_prompt(defense_result)

        # 关系状态
        relationship_prompt = self.relationship.build_relationship_prompt(ctx.session_key)

        # 构建 system 消息（人格 + 关系 + 防御，不含历史）
        system_parts = [
            "你是一个温暖的心理陪伴者，叫小暖。",
            "你关心对方的感受，不会急于给建议。",
            "你的回复简短自然，像朋友聊天一样。",
            "",
            "---",
            "",
            f"## 你的身份\n{soul}",
            "",
            relationship_prompt,
        ]
        if defense_prompt:
            system_parts.extend(["", defense_prompt])

        # 真实多轮对话历史（user/assistant 交替）——连贯性的关键
        history_messages = self.memory.read_history_as_messages(
            ctx.session_key, max_turns=20
        )

        ctx.messages = [
            {"role": "system", "content": "\n".join(system_parts)},
            *history_messages,
            {"role": "user", "content": msg.content},
        ]

        return ctx
