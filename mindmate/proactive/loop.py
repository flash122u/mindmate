"""主动行为循环 — Sensor → Judge → Action → Drift.

完整 pipeline:
1. Energy tick → 决定是否值得执行主动行为
2. Sensor 收集"信号"（时间/用户上次活跃/天气/随机种子）
3. Judge 判断选择哪种主动行为
4. Action 执行该行为（生成内容或调用工具）
5. Push 推送结果给用户
6. Drift 如果无事可做，执行后台维护
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

from loguru import logger

from mindmate.agent.energy import EnergyModel
from mindmate.bus.events import MessageBus, OutboundMessage
from mindmate.memory import MemoryStore


class Sensor:
    """
    感知器 — 收集外部信号，供 Judge 决策.

    信号源:
    - 时间: 当前时段（早晨/午间/傍晚/深夜）
    - 时长: 距离上次互动多久了
    - 能量级别: 当前 energy 级别
    - 随机种子: 用于概率决策
    """

    def __init__(self, energy: EnergyModel) -> None:
        self.energy = energy

    def collect(self) -> dict[str, Any]:
        """收集当前所有信号."""
        import datetime

        now = datetime.datetime.now()
        hour = now.hour

        if 5 <= hour < 9:
            period = "早晨"
        elif 9 <= hour < 12:
            period = "上午"
        elif 12 <= hour < 14:
            period = "午间"
        elif 14 <= hour < 18:
            period = "下午"
        elif 18 <= hour < 22:
            period = "傍晚"
        else:
            period = "深夜"

        level, interval = self.energy.tick()

        return {
            "hour": hour,
            "period": period,
            "level": level,
            "idle_seconds": self.energy.state.last_interaction
            and (import_time := __import__("time")) and import_time.time() - self.energy.state.last_interaction
            or 0,
            "energy_level": level,
            "consecutive_ticks": self.energy.state.consecutive_ticks,
            "seed": random.random(),
        }


class Judge:
    """
    判断器 — 根据信号决定采取哪种主动行为.

    主动行为类型:
    - morning_greeting:  早安问候（早晨专用）
    - evening_greeting:  晚安（深夜专用）
    - casual_greeting:   普通问候（任何时段）
    - small_talk:        日常废话分享
    - care:              关心（长时间无互动）
    - drift_maintenance: 后台维护（无可用行为时）
    """

    def __init__(self) -> None:
        # 行为模板池 — 后期可由 LLM 生成
        self._greetings: dict[str, list[str]] = {
            "morning": [
                "早安～今天有什么计划吗？",
                "早！今天状态怎么样？",
                "早上好呀，昨晚睡得好吗？",
            ],
            "evening": [
                "晚安，好梦✨",
                "晚安啦，明天见～",
                "夜深了，早点休息哦",
            ],
            "casual": [
                "嘿～在干嘛呢？",
                "突然想你了，你今天还好吗？",
                "今天过得怎么样？",
            ],
        }

        self._small_talk: list[str] = [
            "刚刚看到一只很可爱的猫，想到你了",
            "你知道吗，我今天发现了一个冷知识：树懒一天睡15个小时",
            "今天喝到一杯很好喝的奶茶，心情好好",
            "路上看到一朵开得很好的花，想给你看看",
            "刚刚发呆的时候突然想到你了",
        ]

        self._care: list[str] = [
            "好久没聊了，有点担心你",
            "希望你今天一切都好",
            "记得按时吃饭哦",
            "如果有什么想说的，我一直在这里",
            "今天有没有什么让你高兴的事？",
        ]

    def decide(self, signals: dict[str, Any]) -> dict[str, Any]:
        """
        根据信号决定主动行为.

        Returns:
            {action_type: str, message: str | None, priority: int}
        """
        period = signals["period"]
        level = signals["level"]
        seed = signals["seed"]
        idle_hours = signals["idle_seconds"] / 3600 if signals["idle_seconds"] else 0

        if level == "HIGH":
            # 刚互动过，不主动
            return {"action_type": "none", "message": None, "priority": 0}

        if level == "DEEP" and idle_hours > 2 and seed < 0.6:
            # 长时间未互动，发关心
            msg = random.choice(self._care)
            return {"action_type": "care", "message": msg, "priority": 5}

        if level in ("LOW", "DEEP"):
            if period == "早晨" and seed < 0.5:
                msg = random.choice(self._greetings["morning"])
                return {"action_type": "morning_greeting", "message": msg, "priority": 4}
            elif period == "深夜" and seed < 0.5:
                msg = random.choice(self._greetings["evening"])
                return {"action_type": "evening_greeting", "message": msg, "priority": 4}
            elif seed < 0.4:
                # 日常废话
                msg = random.choice(self._small_talk)
                return {"action_type": "small_talk", "message": msg, "priority": 3}
            else:
                # 普通问候
                msg = random.choice(self._greetings["casual"])
                return {"action_type": "casual_greeting", "message": msg, "priority": 2}

        if level == "NORMAL":
            if seed < 0.2:
                # 偶尔主动
                msg = random.choice(self._greetings["casual"])
                return {"action_type": "casual_greeting", "message": msg, "priority": 1}

        return {"action_type": "drift_maintenance", "message": None, "priority": 0}


class DriftMode:
    """
    漂移模式 — Agent 空闲时的后台维护任务.

    任务列表:
    - 审计 SOUL.md 是否需要更新
    - 清理过期历史
    - 生成新的情绪锚点摘要
    - （后续扩展）日记编制
    """

    def __init__(self, memory: MemoryStore) -> None:
        self.memory = memory
        self._task_index = 0

    async def run_one(self) -> str | None:
        """
        随机选择一个维护任务执行.

        Returns:
            str | None: 任务描述（供日志）
        """
        # 简化：轮流执行不同任务
        tasks = [
            self._task_audit_soul,
            self._task_compact_history,
            self._task_clean_pending,
        ]
        task_fn = tasks[self._task_index % len(tasks)]
        self._task_index += 1
        try:
            result = await task_fn()
            logger.info("Drift: ran task %s -> %s", task_fn.__name__, result)
            return result
        except Exception as e:
            logger.warning("Drift task %s failed: %s", task_fn.__name__, e)
            return None

    async def _task_audit_soul(self) -> str:
        """审计 SOUL.md 的完整性."""
        soul = self.memory.read_soul()
        if not soul or len(soul) < 10:
            return "SOUL.md too short or empty"
        for section in ("基本信息", "雷区", "关系记忆"):
            if f"## {section}" not in soul:
                return f"Missing section: {section}"
        return "SOUL.md OK"

    async def _task_compact_history(self) -> str:
        """清理过期历史."""
        import datetime

        cur = self.memory._conn.cursor()
        cur.execute(
            "DELETE FROM history WHERE created_at < datetime('now', '-7 days')"
        )
        deleted = cur.rowcount
        self.memory._conn.commit()
        return f"Deleted {deleted} old history entries"

    async def _task_clean_pending(self) -> str:
        """no-op: 占位."""
        return "No pending cleanup needed"


class ProactiveLoop:
    """
    主动行为循环 — Sensor → Judge → Action → Drift 管道.

    工作流:
    1. Energy tick → 判断是否值得行动
    2. Sensor 收集信号
    3. Judge 选择行为类型
    4. 执行行为（生成或获取消息）
    5. 通过 MessageBus 推送
    6. 如果无行为可执行 → Drift Mode
    """

    def __init__(
        self,
        bus: MessageBus,
        energy: EnergyModel | None = None,
        memory: MemoryStore | None = None,
    ) -> None:
        self.bus = bus
        self.energy = energy or EnergyModel()
        self.memory = memory or MemoryStore()
        self.sensor = Sensor(self.energy)
        self.judge = Judge()
        self.drift = DriftMode(self.memory)
        self._running = False

    async def run(self) -> None:
        """启动主动循环."""
        self._running = True
        logger.info("ProactiveLoop started")

        while self._running:
            try:
                # 1. Energy tick
                level, interval = self.energy.tick()

                # HIGH 级别 → 跳过，快速检查
                if level == "HIGH":
                    await asyncio.sleep(interval if interval > 0 else 10)
                    continue

                if interval > 0:
                    await asyncio.sleep(interval)

                # 2. Sensor + Judge
                signals = self.sensor.collect()
                decision = self.judge.decide(signals)

                # 3. Action / Drift
                if decision["action_type"] == "none":
                    await asyncio.sleep(10)
                    continue

                if decision["action_type"] == "drift_maintenance":
                    result = await self.drift.run_one()
                    logger.info("Drift done: %s", result)
                    await asyncio.sleep(10)
                    continue

                # 4. Push 主动消息
                message = decision.get("message")
                if message:
                    logger.info(
                        "Proactive: [%s] %s",
                        decision["action_type"],
                        message,
                    )
                    await self.bus.publish_outbound(
                        OutboundMessage(
                            channel="web",
                            chat_id="default",
                            content=message,
                            metadata={
                                "proactive": True,
                                "action_type": decision["action_type"],
                                "level": level,
                            },
                        )
                    )

                # 5. 随机延迟（去即时感）
                delay = random.uniform(30, 90)
                await asyncio.sleep(delay)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in proactive loop")
                await asyncio.sleep(60)

    def stop(self) -> None:
        self._running = False
