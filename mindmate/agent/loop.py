"""Agent Loop — 核心处理引擎（被动响应）.

参考 nanobot agent/loop.py 的状态机：
RESTORE → COMPACT → BUILD → RUN → SAVE → RESPOND → DONE

增强:
- 集成防御机制（触发雷区时注入回避指令）
- 集成关系演进（根据互动情感调整关系阶段）
- 支持"不秒回"：RESPOND 阶段加入随机延迟
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
from mindmate.personality import DefenseSystem, RelationshipManager, SoulManager


@dataclass
class TurnContext:
    """单次对话的上下文."""
    msg: InboundMessage
    session_key: str = "default"
    history: list[dict[str, Any]] = field(default_factory=list)
    final_content: str | None = None
    tools_used: list[str] = field(default_factory=list)
    outbound: OutboundMessage | None = None
    defense_triggered: bool = False
    relationship_stage: str = "初识"


class AgentLoop:
    """
    Agent 主循环 — 被动响应模式.

    收到消息后：
    1. 防御检查（是否触发雷区）
    2. 恢复会话上下文（SOUL + 关系 + 近期历史）
    3. 调用 LLM
    4. 保存响应到历史
    5. 随机延迟（去即时感）
    6. 推送到 WebSocket 客户端
    """

    def __init__(self, bus: Any, workspace: Path | None = None) -> None:
        self.bus = bus
        self.provider = DeepSeekProvider()
        self.memory = MemoryStore(workspace)
        self.defense = DefenseSystem(self.memory)
        self.relationship = RelationshipManager(self.memory)
        self.soul = SoulManager(self.memory)
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

        # 1. 防御检查
        defense_result = self.defense.check(msg.content, msg.chat_id)

        # 2. 记录互动（用于关系演进）
        self.relationship.on_user_message(msg.chat_id)

        # 3. 构建上下文（含防御指令 + 关系信息）
        context = await self._build_context(msg, defense_result)

        # 4. 调用 LLM
        response = await self.provider.chat(
            messages=context.messages,
            temperature=0.7,
        )

        # 5. 保存历史
        self.memory.append_history(f"[{msg.sender_id}] {msg.content}", msg.chat_id)
        self.memory.append_history(f"[Assistant] {response['content']}", msg.chat_id)

        # 6. 记录互动情感（简化：默认中性 0.0，后续可用 LLM 评估）
        self.relationship.record_interaction(0.0, msg.chat_id)

        # 7. 通过 bus 发布出站消息（由 run_outbound_consumer 统一推送）
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=response["content"],
        )

    async def _build_context(
        self,
        msg: InboundMessage,
        defense_result: dict[str, Any] | None,
    ) -> TurnContext:
        """构建 LLM 上下文：SOUL + 关系 + 防御 + 近期历史."""
        ctx = TurnContext(msg=msg)

        # 加载人格
        soul = self.memory.read_soul()

        # 加载近期历史
        recent = self.memory.read_recent_for_prompt(ctx.session_key, max_entries=20)

        # 加载关系信息
        rel_state = self.relationship.get_current(ctx.session_key)
        ctx.relationship_stage = rel_state["stage"]
        style_instructions = self.relationship.get_style_instructions(ctx.session_key)

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
            style_instructions,
            "",
            "---",
            "",
        ]

        # 防御指令
        if defense_result:
            ctx.defense_triggered = True
            system_parts.extend([
                "## 防御机制",
                defense_result["instruction"],
                "",
                "---",
                "",
            ])

        if recent:
            system_parts.extend(["## 最近对话", recent])
            system_parts.append("")
            system_parts.append("---")

        ctx.messages = [
            {"role": "system", "content": "\n".join(system_parts)},
            {"role": "user", "content": msg.content},
        ]

        return ctx
