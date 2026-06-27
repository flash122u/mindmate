"""测试 Agent Loop 核心逻辑."""

import sys

sys.path.insert(0, '..')

from mindmate.agent.loop import AgentLoop
from mindmate.bus.events import MessageBus


def test_agent_loop_creation():
    bus = MessageBus()
    loop = AgentLoop(bus=bus)
    assert loop.provider is not None
    assert loop.memory is not None


def test_build_context():
    bus = MessageBus()
    loop = AgentLoop(bus=bus)
    from mindmate.bus.events import InboundMessage
    msg = InboundMessage(channel="web", sender_id="user", chat_id="default", content="你好")
    import asyncio
    ctx = asyncio.run(loop._build_context(msg))
    assert len(ctx.messages) >= 2
    # 第一条是 system（人格）
    assert ctx.messages[0]["role"] == "system"
    assert "小暖" in ctx.messages[0]["content"]
    # 最后一条是当前用户消息
    assert ctx.messages[-1]["role"] == "user"
    assert ctx.messages[-1]["content"] == "你好"


def test_build_context_multiturn():
    """验证多轮对话历史被正确重建为 user/assistant 交替消息."""
    bus = MessageBus()
    loop = AgentLoop(bus=bus)
    sk = "agent_multiturn"
    loop.memory.append_history("user", "我今天很累", session_key=sk)
    loop.memory.append_history("assistant", "辛苦啦，怎么了", session_key=sk)

    msgs = loop.memory.read_history_as_messages(session_key=sk)
    assert msgs == [
        {"role": "user", "content": "我今天很累"},
        {"role": "assistant", "content": "辛苦啦，怎么了"},
    ]


def test_segmented_delivery():
    """验证回复被拆成多条短消息 + typing 信号，逐条发到 outbound."""
    import asyncio

    from mindmate.bus.events import InboundMessage

    bus = MessageBus()
    loop = AgentLoop(bus=bus, delays_enabled=False)  # 关延迟加速测试

    # mock LLM 返回多句话
    async def fake_chat(messages, temperature=0.7):
        return {"content": "怎么啦？是工作上的事吗？先别急。"}

    loop.provider.chat = fake_chat

    async def run():
        msg = InboundMessage(
            channel="web", sender_id="user", chat_id="default",
            content="我好累", metadata={},
        )
        result = await loop._process_message(msg)
        # 分段投递时返回 None
        assert result is None
        # 收集 outbound
        events = []
        while not bus._outbound.empty():
            events.append(bus._outbound.get_nowait())
        return events

    events = asyncio.run(run())
    # 应有 typing + message 交替，且 message 条数 >= 2
    msgs = [e for e in events if e.metadata.get("event") == "message"]
    typings = [e for e in events if e.metadata.get("event") == "typing"]
    assert len(msgs) >= 2, f"应拆成多条，实际 {len(msgs)}"
    assert len(typings) >= len(msgs), "每条消息前应有 typing 信号"
    # 拼回去覆盖原意
    joined = "".join(m.content for m in msgs)
    assert "怎么啦" in joined and "先别急" in joined
