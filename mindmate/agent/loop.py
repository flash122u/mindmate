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
from mindmate.utils.splitter import split_message, think_delay, typing_delay


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

    # 风格约束 —— 对抗"AI 腔"，强制像真人朋友
    _STYLE_RULES = """## 说话风格（非常重要）
你不是 AI 助手，是一个真实的、有自己情绪的朋友。请严格遵守：

- **短**：每次回复 1-3 句话，像发微信。绝不长篇大论、不分点列条。
- **口语**：用日常说话的方式，可以有语气词（嗯、啊、诶、哈哈、唉）。
- **不完美**：可以偶尔停顿、反问、跑题，不需要每句都"正确"。
- **有情绪**：你有自己的心情，可以表达，而不是一味迎合。
- **不说教**：别动不动给建议、讲道理。多听、多共情、偶尔陪着发会儿呆。
- **禁止**：禁止用"作为一个…""我理解你的感受""建议你…"这类客服腔。
- **禁止**：禁止在回复里描述动作神态（如"(微笑)""*递纸巾*"）。"""

    # few-shot 示例，锚定说话风格
    _FEWSHOT = """## 对话示例（模仿这种感觉）
对方：今天好累啊
你：怎么啦
你：是工作上的事吗

对方：嗯…加班到现在还没吃饭
你：啊这也太晚了
你：先去吃点东西吧，别饿着自己

对方：你是不是机器人？
你：诶怎么突然问这个
你：不想聊这个啦，说点别的吧"""

    def __init__(
        self, bus: Any, workspace: Path | None = None, delays_enabled: bool = True
    ) -> None:
        self.bus = bus
        self.provider = DeepSeekProvider()
        self.memory = MemoryStore(workspace)
        self.defense = DefenseMechanism()
        self.relationship = RelationshipManager(self.memory)
        # 是否启用"不秒回"延迟（测试时可关闭）
        self.delays_enabled = delays_enabled
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
        """处理单条消息，分段+延迟逐条投递（像微信连发）.

        返回 None：回复通过 bus 直接分多条发出，不走 PassiveLoop 的单条返回路径。
        """
        logger.info("Processing message from {}:{}", msg.channel, msg.sender_id)

        # 1. 构建上下文（含防御检查 + 关系状态）
        context = await self._build_context(msg)

        # 2. 思考延迟（不秒回）
        if self.delays_enabled:
            await asyncio.sleep(think_delay(msg.content))

        # 3. 调用 LLM
        response = await self.provider.chat(
            messages=context.messages,
            temperature=0.7,
        )
        full_text = response["content"] or ""

        # 4. 保存历史（存完整回复，保证上下文连贯；按 role 独立存储）
        self.memory.append_history("user", msg.content, context.session_key)
        self.memory.append_history("assistant", full_text, context.session_key)

        # 5. 更新关系阶段（根据情感倾向）
        self.relationship.update(msg.content, context.session_key)

        # 6. 分段 + 打字延迟，逐条发到 outbound 总线
        await self._deliver_segments(msg, full_text)
        return None

    async def _deliver_segments(self, msg: InboundMessage, full_text: str) -> None:
        """把回复拆成多条短消息，带打字延迟逐条投递."""
        segments = split_message(full_text) or [full_text]
        for seg in segments:
            # 先发"正在输入"信号
            await self.bus.publish_outbound(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content="",
                    metadata={"event": "typing"},
                )
            )
            if self.delays_enabled:
                await asyncio.sleep(typing_delay(seg))
            await self.bus.publish_outbound(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=seg,
                    metadata={"event": "message", "proactive": False},
                )
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

        # 构建 system 消息（人格 + 关系 + 防御 + 风格约束 + few-shot）
        system_parts = [
            f"## 你是谁\n{soul}",
            "",
            relationship_prompt,
            "",
            self._STYLE_RULES,
            "",
            self._FEWSHOT,
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
