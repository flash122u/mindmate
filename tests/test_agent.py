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
    ctx = asyncio.run(loop._build_context(msg, defense_result=None))
    assert len(ctx.messages) >= 2
    assert ctx.messages[0]["role"] == "system"
    assert ctx.messages[1]["role"] == "user"
    assert "小暖" in ctx.messages[0]["content"]
