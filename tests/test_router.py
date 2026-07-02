"""测试意图路由器."""

import sys

sys.path.insert(0, '..')

import asyncio

from mindmate.agent.loop import AgentLoop
from mindmate.agent.router import IntentRouter
from mindmate.bus.events import InboundMessage, MessageBus

# ---------------------------------------------------------------------------
# 单测：路由规则
# ---------------------------------------------------------------------------

def test_router_risk_suicide():
    router = IntentRouter()
    r = router.route("我想死")
    assert r.intent == "risk"
    assert r.confidence >= 0.9


def test_router_risk_self_harm():
    router = IntentRouter()
    r = router.route("我真的撑不下去了，每天都想消失")
    assert r.intent == "risk"


def test_router_risk_collapse():
    router = IntentRouter()
    r = router.route("我快崩溃了")
    assert r.intent == "risk"


def test_router_functional_what_can_do():
    router = IntentRouter()
    r = router.route("你能做什么")
    assert r.intent == "functional"


def test_router_functional_help():
    router = IntentRouter()
    r = router.route("帮助")
    assert r.intent == "functional"


def test_router_functional_features():
    router = IntentRouter()
    r = router.route("你有什么功能")
    assert r.intent == "functional"


def test_router_identity_name():
    router = IntentRouter()
    r = router.route("你叫什么名字")
    assert r.intent == "identity"


def test_router_identity_who():
    router = IntentRouter()
    r = router.route("你是谁")
    assert r.intent == "identity"


def test_router_chat_fallback():
    router = IntentRouter()
    r = router.route("今天天气真好")
    assert r.intent == "chat"
    assert r.confidence == 0.5


def test_router_priority_risk_over_functional():
    """优先级：风险信号优先于功能询问."""
    router = IntentRouter()
    r = router.route("我想死，你能做什么")
    assert r.intent == "risk"


def test_router_confidence_range():
    router = IntentRouter()
    for msg in ["我想自杀", "你能做什么", "你是谁", "你好"]:
        r = router.route(msg)
        assert 0.0 <= r.confidence <= 1.0


# ---------------------------------------------------------------------------
# 集成测试：快速路径跳过了 LLM / 正常路径仍用 LLM
# ---------------------------------------------------------------------------

def test_router_integration_risk_skip_llm():
    """risk 意图走预写模板，不调用 LLM."""
    bus = MessageBus()
    loop = AgentLoop(bus=bus, delays_enabled=False, memory_maintenance=False)

    call_count = 0

    async def fake_chat(messages, temperature=0.7, tools=None):
        nonlocal call_count
        call_count += 1
        return {"content": "should not be called"}

    loop.provider.chat = fake_chat

    async def run():
        msg = InboundMessage(
            channel="web", sender_id="user", chat_id="r_risk",
            content="我不想活了", metadata={},
        )
        await loop._process_message(msg)

    asyncio.run(run())
    assert call_count == 0  # LLM 未被调用
    loop.memory.close()


def test_router_integration_functional_skip_llm():
    """functional 意图跳 LLM."""
    bus = MessageBus()
    loop = AgentLoop(bus=bus, delays_enabled=False, memory_maintenance=False)

    call_count = 0

    async def fake_chat(messages, temperature=0.7, tools=None):
        nonlocal call_count
        call_count += 1
        return {"content": "should not be called"}

    loop.provider.chat = fake_chat

    async def run():
        msg = InboundMessage(
            channel="web", sender_id="user", chat_id="r_func",
            content="你能做什么", metadata={},
        )
        await loop._process_message(msg)

    asyncio.run(run())
    assert call_count == 0
    loop.memory.close()


def test_router_integration_identity_skip_llm():
    """identity 意图跳 LLM."""
    bus = MessageBus()
    loop = AgentLoop(bus=bus, delays_enabled=False, memory_maintenance=False)

    call_count = 0

    async def fake_chat(messages, temperature=0.7, tools=None):
        nonlocal call_count
        call_count += 1
        return {"content": "should not be called"}

    loop.provider.chat = fake_chat

    async def run():
        msg = InboundMessage(
            channel="web", sender_id="user", chat_id="r_id",
            content="你是谁", metadata={},
        )
        await loop._process_message(msg)

    asyncio.run(run())
    assert call_count == 0
    loop.memory.close()


def test_router_integration_chat_uses_llm():
    """chat 意图仍然走 LLM."""
    bus = MessageBus()
    loop = AgentLoop(bus=bus, delays_enabled=False, memory_maintenance=False)

    call_count = 0

    async def fake_chat(messages, temperature=0.7, tools=None):
        nonlocal call_count
        call_count += 1
        return {"content": "今天天气确实不错呢"}

    loop.provider.chat = fake_chat

    async def run():
        msg = InboundMessage(
            channel="web", sender_id="user", chat_id="r_chat",
            content="今天天气真好", metadata={},
        )
        await loop._process_message(msg)

    asyncio.run(run())
    assert call_count == 1  # LLM 被调用了
    loop.memory.close()


# ---------------------------------------------------------------------------
# 构造函数：默认 router / 自定义 router
# ---------------------------------------------------------------------------

def test_agent_loop_has_default_router():
    bus = MessageBus()
    loop = AgentLoop(bus=bus)
    assert loop.router is not None
    assert isinstance(loop.router, IntentRouter)


def test_agent_loop_accepts_custom_router():
    bus = MessageBus()
    custom = IntentRouter()
    loop = AgentLoop(bus=bus, router=custom)
    assert loop.router is custom


# ---------------------------------------------------------------------------
# router trace 被正确记录
# ---------------------------------------------------------------------------

def test_router_trace_records_intent_route_step():
    """验证 INTENT_ROUTE 步骤被写入 trace."""
    bus = MessageBus()
    loop = AgentLoop(bus=bus, delays_enabled=False, memory_maintenance=False)

    async def fake_chat(messages, temperature=0.7, tools=None):
        return {"content": "是挺好的"}

    loop.provider.chat = fake_chat

    async def run():
        msg = InboundMessage(
            channel="web", sender_id="user", chat_id="r_trace",
            content="你好啊", metadata={},
        )
        await loop._process_message(msg)

    asyncio.run(run())

    traces = loop.memory.get_agent_traces(session_key="r_trace", limit=5)
    assert len(traces) >= 1
    step_names = [s["step_name"] for s in traces[0]["steps"]]
    assert "INTENT_ROUTE" in step_names
    route_step = [s for s in traces[0]["steps"]
                  if s["step_name"] == "INTENT_ROUTE"][0]
    assert "intent=chat" in route_step["detail"]
    loop.memory.close()
