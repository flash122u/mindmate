"""测试多用户隔离：不同 chat_id 的记忆/关系互不污染."""

import sys

sys.path.insert(0, '.')

import asyncio

from mindmate.agent.energy import EnergyRegistry
from mindmate.agent.loop import AgentLoop
from mindmate.bus.events import InboundMessage, MessageBus


def _make_loop():
    bus = MessageBus()
    reg = EnergyRegistry()
    loop = AgentLoop(
        bus=bus, delays_enabled=False, memory_maintenance=False, energy=reg
    )

    async def fake_chat(messages, temperature=0.7):
        return {"content": "好的呀。"}

    loop.provider.chat = fake_chat
    return bus, loop


def test_session_key_from_chat_id():
    """_build_context 用 chat_id 作 session_key."""
    bus, loop = _make_loop()
    msg = InboundMessage(channel="web", sender_id="alice", chat_id="alice", content="hi")
    ctx = asyncio.run(loop._build_context(msg))
    assert ctx.session_key == "alice"


def test_history_isolated_between_users():
    """两个用户的对话历史互不可见."""
    bus, loop = _make_loop()

    async def run():
        await loop._process_message(
            InboundMessage(channel="web", sender_id="alice", chat_id="alice", content="我叫爱丽丝")
        )
        await loop._process_message(
            InboundMessage(channel="web", sender_id="bob", chat_id="bob", content="我叫鲍勃")
        )

    asyncio.run(run())
    alice_hist = loop.memory.read_history_as_messages(session_key="alice")
    bob_hist = loop.memory.read_history_as_messages(session_key="bob")
    alice_text = " ".join(h["content"] for h in alice_hist)
    bob_text = " ".join(h["content"] for h in bob_hist)
    assert "爱丽丝" in alice_text and "鲍勃" not in alice_text
    assert "鲍勃" in bob_text and "爱丽丝" not in bob_text


def test_relationship_isolated_between_users():
    """关系阶段按用户隔离."""
    bus, loop = _make_loop()

    async def run():
        # alice 大量正面互动推进关系
        for _ in range(20):
            await loop._process_message(
                InboundMessage(
                    channel="web", sender_id="alice", chat_id="alice",
                    content="谢谢你，好喜欢和你聊天，好开心",
                )
            )
        # bob 只聊一句
        await loop._process_message(
            InboundMessage(channel="web", sender_id="bob", chat_id="bob", content="嗯")
        )

    asyncio.run(run())
    alice_stage = loop.relationship.get_state("alice").stage
    bob_stage = loop.relationship.get_state("bob").stage
    assert alice_stage in ("朋友", "信赖")
    assert bob_stage == "初识"


def test_energy_isolated_between_users():
    """能量沉默计时按用户隔离."""
    bus, loop = _make_loop()

    async def run():
        await loop._process_message(
            InboundMessage(channel="web", sender_id="alice", chat_id="alice", content="hi")
        )

    asyncio.run(run())
    # alice 刚互动过 → 有能量模型且不该开口
    a_ok, _ = loop.energy.get("alice").should_reach_out()
    assert a_ok is False
    # bob 从未互动 → 是一个独立的新模型
    assert "alice" in loop.energy.sessions()


def test_delivery_routed_to_correct_user():
    """回复的 chat_id 是发消息的用户."""
    bus, loop = _make_loop()

    async def run():
        await loop._process_message(
            InboundMessage(channel="web", sender_id="bob", chat_id="bob", content="hi")
        )
        outs = []
        while not bus._outbound.empty():
            outs.append(bus._outbound.get_nowait())
        return outs

    outs = asyncio.run(run())
    msgs = [o for o in outs if o.metadata.get("event") == "message"]
    assert msgs
    assert all(o.chat_id == "bob" for o in outs)
