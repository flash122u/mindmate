"""测试主动行为循环 + Agent 主动开口生成."""

import sys

sys.path.insert(0, '.')

import asyncio

from mindmate.agent.energy import EnergyModel
from mindmate.agent.loop import AgentLoop
from mindmate.bus.events import MessageBus
from mindmate.proactive.loop import ProactiveLoop


def test_proactive_loop_skips_when_not_ready():
    """能量模型说不该开口时，不调用生成回调."""
    energy = EnergyModel(idle_threshold_s=1800)
    energy.on_user_message()  # 刚互动过 → not idle
    calls = []

    async def gen():
        calls.append(1)

    loop = ProactiveLoop(energy, gen, check_interval_s=0.01)

    async def run():
        task = asyncio.create_task(loop.run())
        await asyncio.sleep(0.05)
        loop.stop()
        task.cancel()

    asyncio.run(run())
    assert calls == []


def test_proactive_loop_triggers_when_ready():
    """满足条件时调用生成回调并标记冷却."""
    energy = EnergyModel(idle_threshold_s=0, cooldown_s=7200)
    calls = []

    async def gen():
        calls.append(1)

    loop = ProactiveLoop(energy, gen, check_interval_s=0.01)

    async def run():
        task = asyncio.create_task(loop.run())
        await asyncio.sleep(0.05)
        loop.stop()
        task.cancel()

    asyncio.run(run())
    assert len(calls) >= 1
    # 触发后应进入冷却
    ok, reason = energy.should_reach_out()
    assert ok is False
    assert reason == "cooldown"


def test_generate_proactive_delivers_segments():
    """generate_proactive 用 LLM 生成、分段、投递并存历史."""
    bus = MessageBus()
    energy = EnergyModel()
    loop = AgentLoop(bus=bus, delays_enabled=False, energy=energy)

    async def fake_chat(messages, temperature=0.7):
        # 验证最后一条是主动开口的内部指令
        assert messages[-1]["role"] == "user"
        assert "主动" in messages[-1]["content"]
        return {"content": "诶，在忙吗？今天突然有点想你。"}

    loop.provider.chat = fake_chat

    async def run():
        await loop.generate_proactive(session_key="proa")
        events = []
        while not bus._outbound.empty():
            events.append(bus._outbound.get_nowait())
        return events

    events = asyncio.run(run())
    msgs = [e for e in events if e.metadata.get("event") == "message"]
    assert len(msgs) >= 1
    assert all(e.metadata.get("proactive") is True for e in msgs)
    # 应存入历史
    hist = loop.memory.read_history_as_messages(session_key="proa")
    assert any(h["role"] == "assistant" for h in hist)


def test_proactive_nudge_has_time_and_intent():
    bus = MessageBus()
    loop = AgentLoop(bus=bus, delays_enabled=False)
    nudge = loop._proactive_nudge()
    assert "对方" in nudge
    # 含某个时段词
    assert any(p in nudge for p in ("早上", "中午", "下午", "晚上", "深夜"))
