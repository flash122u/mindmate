"""测试主动行为循环 + Agent 主动开口生成（多用户）."""

import sys

sys.path.insert(0, '.')

import asyncio

from mindmate.agent.energy import EnergyRegistry
from mindmate.agent.loop import AgentLoop
from mindmate.bus.events import MessageBus
from mindmate.proactive.loop import ProactiveLoop


def test_proactive_tick_skips_when_not_ready():
    """用户刚互动过 → 不开口."""
    reg = EnergyRegistry(idle_threshold_s=1800)
    reg.get("u1").on_user_message()
    calls = []

    async def gen(sk):
        calls.append(sk)

    loop = ProactiveLoop(reg, gen, list_sessions=lambda: ["u1"])

    n = asyncio.run(loop.tick())
    assert n == 0
    assert calls == []


def test_proactive_tick_triggers_when_ready():
    """满足条件 → 开口并进入冷却."""
    reg = EnergyRegistry(idle_threshold_s=0, cooldown_s=7200)
    calls = []

    async def gen(sk):
        calls.append(sk)

    loop = ProactiveLoop(reg, gen, list_sessions=lambda: ["u1"])

    n = asyncio.run(loop.tick())
    assert n == 1
    assert calls == ["u1"]
    ok, reason = reg.get("u1").should_reach_out()
    assert ok is False
    assert reason == "cooldown"


def test_proactive_per_user_isolation():
    """多用户：只对满足条件的用户开口."""
    reg = EnergyRegistry(idle_threshold_s=1800, cooldown_s=7200)
    # u1 刚互动过（不开口），u2 沉默够久（开口）
    reg.get("u1").on_user_message()
    u2 = reg.get("u2")
    u2.idle_threshold_s = 0  # 让 u2 立即可开口
    calls = []

    async def gen(sk):
        calls.append(sk)

    loop = ProactiveLoop(reg, gen, list_sessions=lambda: ["u1", "u2"])
    n = asyncio.run(loop.tick())
    assert n == 1
    assert calls == ["u2"]


def test_generate_proactive_delivers_to_session():
    """generate_proactive 用 LLM 生成、分段、投递到对应用户并存历史."""
    bus = MessageBus()
    reg = EnergyRegistry()
    loop = AgentLoop(bus=bus, delays_enabled=False, energy=reg)

    async def fake_chat(messages, temperature=0.7):
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
    # 投递的 chat_id 应是目标用户
    assert all(e.chat_id == "proa" for e in msgs)
    assert all(e.metadata.get("proactive") is True for e in msgs)
    hist = loop.memory.read_history_as_messages(session_key="proa")
    assert any(h["role"] == "assistant" for h in hist)


def test_proactive_nudge_has_time_and_intent():
    bus = MessageBus()
    loop = AgentLoop(bus=bus, delays_enabled=False)
    nudge = loop._proactive_nudge()
    assert "对方" in nudge
    assert any(p in nudge for p in ("早上", "中午", "下午", "晚上", "深夜"))
