"""测试 Agent Loop 核心逻辑."""

import sys
sys.path.insert(0, '..')

from mindmate.bus.events import MessageBus
from mindmate.agent.loop import AgentLoop


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
