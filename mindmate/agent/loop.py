"""Agent Loop — 核心处理引擎（被动响应）.

参考 nanobot agent/loop.py 的状态机：
RESTORE → COMPACT → BUILD → RUN → SAVE → RESPOND → DONE
"""

from __future__ import annotations

import asyncio
import random
import time as _time_module
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from mindmate.agent.router import IntentResult, IntentRouter
from mindmate.agent.trace import TraceBuilder
from mindmate.bus.events import InboundMessage, OutboundMessage
from mindmate.config import settings
from mindmate.llm import DeepSeekProvider
from mindmate.memory import MemoryStore
from mindmate.personality.defense import DefenseMechanism
from mindmate.personality.diary import DiaryAgent
from mindmate.personality.dream import DreamAgent
from mindmate.personality.emotion_anchor import EmotionAnchorManager
from mindmate.personality.forget import ForgetAgent
from mindmate.personality.memory_consolidator import MemoryConsolidator
from mindmate.personality.relationship import RelationshipManager
from mindmate.skills.skill import SkillLibrary
from mindmate.tools.crisis_detect import CrisisDetector
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

    _MAX_TOOL_ROUNDS = 4

    def __init__(
        self,
        bus: Any,
        workspace: Path | None = None,
        delays_enabled: bool = True,
        energy: Any = None,
        memory_maintenance: bool = True,
        tools: Any = None,
        router: IntentRouter | None = None,
        skill_library: SkillLibrary | None = None,
    ) -> None:
        self.bus = bus
        self.provider = DeepSeekProvider()
        self.memory = MemoryStore(workspace)
        # 工具注册表（None 或空 → 退化为单轮对话，行为不变）
        self.tools = tools
        # 意图路由器（可注入，测试友好）
        self.router = router or IntentRouter()
        # 陪伴场景 Skill 库（可注入，测试友好）
        self.skill_library = skill_library or SkillLibrary()
        self.defense = DefenseMechanism()
        self.relationship = RelationshipManager(self.memory)
        # 情绪锚点 + 记忆整合 + 遗忘
        self.anchors = EmotionAnchorManager(self.memory, self.provider)
        self.consolidator = MemoryConsolidator(self.memory, self.provider)
        self.forget = ForgetAgent(self.memory)
        # 私密内在生活：日记 + 梦
        self.diary = DiaryAgent(self.memory, self.provider)
        self.dream = DreamAgent(self.memory, self.provider)
        # 吐露私密的概率（仅在关系深 + 强情绪共鸣时才考虑）
        self.share_prob = 0.3
        # 小暖自己所在的城市 + 主动分享天气的概率（方向 A）
        self.home_city = settings.home_city
        self.weather_share_prob = 0.4
        # 风险检测
        self.crisis = CrisisDetector(self.memory)
        # 能量模型（主动行为调度）；与 ProactiveLoop 共享同一实例
        self.energy = energy
        # 是否在对话后做记忆维护（提取锚点/整合/遗忘），测试时可关闭
        self.memory_maintenance = memory_maintenance
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

        session_key = msg.chat_id or "default"
        trace = TraceBuilder(session_key=session_key, message_id=msg.content[:60])

        # 0. 意图路由（LLM 调用前，规则分类）
        trace.begin("INTENT_ROUTE")
        intent_result = self.router.route(msg.content)
        trace.end(
            "ok",
            f"intent={intent_result.intent} confidence={intent_result.confidence:.2f}",
        )

        # 快速路径：非 chat 意图用预写回复模板，零 LLM 调用
        fast_path = _fast_path_response(intent_result, self.router)
        if fast_path is not None:
            logger.info(
                "Fast-path: intent={} for {}", intent_result.intent, session_key
            )
            # risk 路径仍需记录预警
            if intent_result.intent == "risk":
                self.crisis.check_and_record(msg.content, session_key)
            segments = split_message(fast_path) or [fast_path]
            self.memory.append_history("user", msg.content, session_key)
            for seg in segments:
                self.memory.append_history("assistant", seg, session_key)
            if self.energy is not None:
                self.energy.get(session_key).on_user_message()
            await self._deliver_segments(
                msg.channel, msg.chat_id, segments, proactive=False
            )
            self._flush_trace(trace)
            return None

        # 正常路径：chat → 原有流程
        context = await self._build_context(msg, trace)

        # 2. 思考延迟（不秒回）
        if self.delays_enabled:
            await asyncio.sleep(think_delay(msg.content))

        # 3. 调用 LLM（带工具调用循环）
        trace.begin("LLM_CALL")
        try:
            full_text = await self._run_llm(context.messages, trace)
            trace.end("ok", f"response {len(full_text)} chars")
        except Exception:
            trace.end("error", "LLM call failed")
            self._flush_trace(trace)
            raise

        segments = split_message(full_text) or [full_text]

        # 4. 保存历史：用户一行 + 每个分段各一行（前端按行显示分段气泡，
        #    LLM 上下文会自动把连续 assistant 行合并回一轮）
        self.memory.append_history("user", msg.content, context.session_key)
        for seg in segments:
            self.memory.append_history("assistant", seg, context.session_key)

        # 5. 更新关系阶段（根据情感倾向）+ 重置该用户的能量沉默计时
        trace.begin("RELATIONSHIP_UPDATE")
        try:
            self.relationship.update(msg.content, context.session_key)
            state = self.relationship.get_state(context.session_key)
            trace.end("ok", f"stage={state.stage}")
        except Exception:
            trace.end("error", "relationship update failed")
        if self.energy is not None:
            self.energy.get(context.session_key).on_user_message()

        # 6. 打字延迟，逐条发到 outbound 总线
        await self._deliver_segments(
            msg.channel, msg.chat_id, segments, proactive=False
        )

        # 7. 后台沉淀记忆：提取情绪锚点 + 整合长期记忆（不阻塞回复）
        trace.begin("MEMORY_MAINTENANCE")
        if self.memory_maintenance:
            asyncio.create_task(self._post_turn_memory(context.session_key))
            trace.end("ok", "started background task")
        else:
            trace.end("skipped", "memory_maintenance disabled")

        self._flush_trace(trace)
        return None

    async def _run_llm(
        self,
        messages: list[dict[str, Any]],
        trace: TraceBuilder | None = None,
    ) -> str:
        """调用 LLM；若注册了工具则进入工具调用循环.

        无工具时退化为单轮 chat（与原行为完全一致）。
        有工具时：chat → 模型要调工具 → 执行 → 把结果喂回 → 再 chat，
        直到模型给出最终文本，或达到最大回合数。
        """
        if self.tools is None or self.tools.is_empty():
            resp = await self.provider.chat(messages=messages, temperature=0.7)
            return resp.get("content") or ""

        work = list(messages)
        for _ in range(self._MAX_TOOL_ROUNDS):
            resp = await self.provider.chat(
                messages=work,
                tools=self.tools.schemas(),
                temperature=0.7,
            )
            tool_calls = resp.get("tool_calls")
            if not tool_calls:
                return resp.get("content") or ""
            # 把助手的"调用工具"这一回合追加进对话
            work.append(resp["raw_message"])
            for tc in tool_calls:
                if trace is not None:
                    trace.begin("TOOL_CALL")
                logger.info("Tool call: {}({})", tc["name"], tc["arguments"])
                result = await self.tools.execute(tc["name"], tc["arguments"])
                if trace is not None:
                    trace.end("ok", f"{tc['name']}")
                work.append(
                    {"role": "tool", "tool_call_id": tc["id"], "content": result}
                )
        # 回合用尽，强制要一个不带工具的最终回复
        resp = await self.provider.chat(messages=work, temperature=0.7)
        return resp.get("content") or ""

    async def _post_turn_memory(self, session_key: str) -> None:
        """对话后的记忆维护：提取情绪锚点、整合长期记忆、遗忘陈旧锚点."""
        try:
            await self.anchors.extract(session_key)
            await self.consolidator.maybe_consolidate(session_key)
            self.forget.forget_stale(session_key)
        except Exception:
            logger.exception("Post-turn memory maintenance failed")

    async def generate_proactive(self, session_key: str = "default") -> None:
        """主动开口：不回应具体问题，自然地发起一段对话.

        由 ProactiveLoop 在合适时机调用。生成内容经分段后逐条投递，
        并存入历史，使后续对话保持连贯。
        """
        logger.info("Generating proactive message for {}", session_key)

        soul = self.memory.read_soul()
        relationship_prompt = self.relationship.build_relationship_prompt(session_key)
        history = self.memory.read_history_as_messages(session_key, max_turns=10)
        # 方向 A：小暖感知自己城市的真实天气，借此自然开启对话
        weather_hint = await self._home_weather_hint()
        nudge = self._proactive_nudge(weather_hint)

        system_parts = [
            f"## 你是谁\n{soul}",
            "",
            relationship_prompt,
            "",
            self._STYLE_RULES,
            "",
            self._FEWSHOT,
        ]
        messages = [
            {"role": "system", "content": "\n".join(system_parts)},
            *history,
            {"role": "user", "content": nudge},
        ]

        response = await self.provider.chat(messages=messages, temperature=0.9)
        full_text = (response["content"] or "").strip()
        if not full_text:
            return

        # 主动消息按分段存 assistant 历史（nudge 是内部指令，不持久化）
        segments = split_message(full_text) or [full_text]
        for seg in segments:
            self.memory.append_history("assistant", seg, session_key)

        await self._deliver_segments("web", session_key, segments, proactive=True)

    async def _home_weather_hint(self) -> str:
        """按概率获取小暖所在城市的真实天气，作为主动开口的素材.

        这是"方向 A"：天气服务于小暖自己的生活感知（她有自己的城市），
        而非查询用户位置——更贴合"伙伴有自己的世界"的设定。
        """
        if not self.tools or random.random() > self.weather_share_prob:
            return ""
        wt = self.tools.get("get_weather")
        if wt is None:
            return ""
        try:
            w = await wt.execute(location=self.home_city)
        except Exception:
            return ""
        if not w or w.startswith("["):
            return ""
        return (
            f"\n你此刻在{self.home_city}，那边的天气是：{w}。"
            "可以很自然地提一句你这边的天气，或借天气状态关心一下对方"
            "（比如下雨就提醒带伞、变冷就让ta加衣），别像播报天气。"
        )

    def _proactive_nudge(self, weather_hint: str = "") -> str:
        """根据时间/随机意图，生成主动开口的内部指令（不持久化）."""
        from datetime import datetime

        hour = datetime.now().hour
        if 5 <= hour < 11:
            period = "早上"
        elif 11 <= hour < 14:
            period = "中午"
        elif 14 <= hour < 18:
            period = "下午"
        elif 18 <= hour < 23:
            period = "晚上"
        else:
            period = "深夜"

        intents = [
            "随口问候一下，看看对方最近怎么样",
            "分享你今天遇到的一件无关紧要的小事（编一个就好，像生活碎屑）",
            "因为有一阵没聊了，有点想ta，主动关心一下",
            "突然想起之前聊过的事，顺嘴提一句",
        ]
        intent = random.choice(intents)
        return (
            f"（现在是{period}，对方已经有一阵子没说话了。你想主动发消息找ta。"
            f"这次的意图是：{intent}。"
            f"{weather_hint}"
            "不要回应任何具体问题，自然地开启对话，简短、随意，"
            "像朋友突然发来的消息。）"
        )

    async def _deliver_segments(
        self, channel: str, chat_id: str, segments: list[str], *, proactive: bool
    ) -> None:
        """把已分段的多条短消息，带打字延迟逐条投递."""
        for seg in segments:
            # 先发"正在输入"信号
            await self.bus.publish_outbound(
                OutboundMessage(
                    channel=channel,
                    chat_id=chat_id,
                    content="",
                    metadata={"event": "typing"},
                )
            )
            if self.delays_enabled:
                await asyncio.sleep(typing_delay(seg))
            await self.bus.publish_outbound(
                OutboundMessage(
                    channel=channel,
                    chat_id=chat_id,
                    content=seg,
                    metadata={"event": "message", "proactive": proactive},
                )
            )

    async def _build_context(
        self, msg: InboundMessage, trace: TraceBuilder | None = None
    ) -> TurnContext:
        """构建 LLM 上下文：system(人格/关系/防御) + 真实多轮对话 + 当前消息."""
        # 用 chat_id 作为用户标识，实现多用户记忆/关系隔离
        ctx = TurnContext(msg=msg, session_key=msg.chat_id or "default")

        # 加载人格
        soul = self.memory.read_soul()

        # 防御检查
        if trace is not None:
            trace.begin("DEFENSE_CHECK")
        defense_result = self.defense.check(msg.content, ctx.session_key)
        defense_prompt = self.defense.build_defense_prompt(defense_result)
        if trace is not None:
            trace.end("ok", f"triggered={defense_result.triggered}")

        # 风险检测（命中则记录预警 + 注入关切指引）
        if trace is not None:
            trace.begin("CRISIS_CHECK")
        crisis_result = self.crisis.check_and_record(msg.content, ctx.session_key)
        care_prompt = self.crisis.build_care_prompt(crisis_result)
        if trace is not None:
            trace.end("ok", f"level={crisis_result.level}")

        # 关系状态
        relationship_prompt = self.relationship.build_relationship_prompt(
            ctx.session_key
        )

        # 长期记忆（MEMORY.md，沉淀的旧事）
        long_term = self.memory.read_memory().strip()

        # 召回被当前消息触发的情绪锚点
        if trace is not None:
            trace.begin("ANCHOR_RECALL")
        recalled = self.anchors.recall(msg.content, ctx.session_key)
        anchor_prompt = self.anchors.build_anchor_prompt(recalled)
        if trace is not None:
            trace.end("ok", f"hits={len(recalled)}")

        # 分享冲动：交心时刻才考虑吐露一点私密的日记/梦
        if trace is not None:
            trace.begin("INNER_LIFE_SHARE")
        share_prompt = self._maybe_share_inner_life(ctx.session_key, recalled)
        if trace is not None:
            trace.end(
                "ok" if share_prompt else "skipped",
                "shared" if share_prompt else "no share",
            )

        # 构建 system 消息（人格 + 关系 + 长期记忆 + 情绪锚点 + 防御 + 风格 + few-shot）
        system_parts = [
            f"## 你是谁\n{soul}",
            "",
            relationship_prompt,
        ]
        if long_term:
            system_parts.extend(["", f"## 你记得的一些事\n{long_term}"])
        if anchor_prompt:
            system_parts.extend(["", anchor_prompt])
        if share_prompt:
            system_parts.extend(["", share_prompt])

        # 陪伴场景 Skill：根据用户消息选择匹配的共情指南，注入到系统提示
        if trace is not None:
            trace.begin("SKILL_SELECT")
        skill_context = self.skill_library.build_skill_context(
            msg.content, intent="chat"
        )
        if trace is not None:
            selected = (
                self.skill_library.select_skill_names(msg.content, intent="chat")
            )
            trace.end(
                "ok" if skill_context else "skipped",
                f"selected={','.join(selected)}" if selected else "selected=none",
            )
        if skill_context:
            system_parts.extend(["", skill_context])

        system_parts.extend(["", self._STYLE_RULES, "", self._FEWSHOT])
        if care_prompt:
            system_parts.extend(["", care_prompt])
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

    def _maybe_share_inner_life(
        self, session_key: str, recalled: list[dict[str, Any]]
    ) -> str:
        """交心时刻才考虑吐露一点私密的日记/梦.

        条件（避免过度暴露）：
        - 关系已到「朋友」或「信赖」
        - 且（此刻有强情绪共鸣 或 概率命中）
        命中后取一条未分享的日记/梦，提示 LLM 含蓄吐露一点点，并标记已分享。
        """
        stage = self.relationship.get_state(session_key).stage
        if stage == "初识":
            return ""

        strong_resonance = any(abs(a.get("valence", 0.0)) >= 0.6 for a in recalled)
        deep = stage == "信赖"
        if not (strong_resonance or deep):
            return ""
        if random.random() > self.share_prob:
            return ""

        # 优先吐露梦（更私密），其次日记；取最近一条未分享的
        for kind, getter, marker in (
            ("梦", self.memory.get_dreams, self.memory.mark_dream_shared),
            ("日记", self.memory.get_diaries, self.memory.mark_diary_shared),
        ):
            items = [i for i in getter(session_key, limit=10) if not i.get("shared")]
            if items:
                item = items[0]
                marker(item["id"])
                return (
                    f"## 此刻的一点私心（内部）\n"
                    f"你心里浮起一件没跟人说过的私密的事（你的{kind}）：「{item['content']}」。"
                    "如果此刻你们聊得很交心、气氛合适，你可以**不经意地、含蓄地**"
                    "用'其实…'开头提一点点，只露一句，别和盘托出，也别解释太多。"
                    "如果气氛不对，就不提。"
                )
        return ""

    async def run_daily_inner_life(self, session_key: str = "default") -> None:
        """生成当天的私密日记 + 梦（由调度器每日调用，不投递给用户）."""
        await self.diary.write_today(session_key)
        await self.dream.dream(session_key)

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    def _flush_trace(self, trace: TraceBuilder) -> None:
        """将 trace 写入数据库（非 async，避免阻塞消息处理）."""
        try:
            self.memory.add_agent_trace(
                trace_id=trace.trace_id,
                session_key=trace.session_key,
                message_id=trace.message_id,
                started_at=_format_iso(trace.started_at),
                completed_at=_format_iso(_time_module.time()),
                steps=[
                    {
                        "step_number": s.step_number,
                        "step_name": s.step_name,
                        "status": s.status,
                        "detail": s.detail,
                        "elapsed_ms": s.elapsed_ms,
                    }
                    for s in trace.steps
                ],
                total_elapsed_ms=trace.total_elapsed_ms(),
            )
        except Exception:
            logger.exception("Failed to persist agent trace")


def _format_iso(epoch: float) -> str:
    """epoch 秒 → ISO 8601 字符串（UTC）."""
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _fast_path_response(
    intent_result: IntentResult, router: IntentRouter,
) -> str | None:
    """非 chat 意图 → 返回预写模板；chat → 返回 None（走正常 LLM 流程）."""
    if intent_result.intent == "risk":
        return router.RISK_RESPONSE
    if intent_result.intent == "functional":
        return router.FUNCTIONAL_RESPONSE
    if intent_result.intent == "identity":
        return router.IDENTITY_RESPONSE
    return None
