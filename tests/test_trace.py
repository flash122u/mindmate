"""测试 Run Trace 可观测性."""

import sys

sys.path.insert(0, '..')

import asyncio
import time as _time_module

from mindmate.agent.loop import AgentLoop
from mindmate.agent.trace import TraceBuilder
from mindmate.bus.events import InboundMessage, MessageBus
from mindmate.memory import MemoryStore


def _uniq(prefix: str) -> str:
    return f"{prefix}_{int(_time_module.time() * 1000000)}"


def test_trace_builder_creates_steps():
    tb = TraceBuilder(session_key="test", message_id="hello")
    tb.begin("DEFENSE_CHECK")
    tb.end("ok", "triggered=False")
    tb.begin("LLM_CALL")
    tb.end("ok", "response 42 chars")
    assert len(tb.steps) == 2
    assert tb.steps[0].step_number == 1
    assert tb.steps[0].step_name == "DEFENSE_CHECK"
    assert tb.steps[0].status == "ok"
    assert tb.steps[0].detail == "triggered=False"
    assert tb.steps[1].step_number == 2
    assert tb.steps[1].step_name == "LLM_CALL"


def test_trace_builder_elapsed_positive():
    tb = TraceBuilder(session_key="test", message_id="hello")
    tb.begin("TEST_STEP")
    tb.end("ok", "done")
    assert tb.steps[0].elapsed_ms >= 0


def test_trace_builder_total_elapsed():
    import time as _time_module
    tb = TraceBuilder(session_key="test", message_id="hello")
    _time_module.sleep(0.01)
    assert tb.total_elapsed_ms() > 0


def test_trace_builder_unique_ids():
    tb1 = TraceBuilder(session_key="a", message_id="m1")
    tb2 = TraceBuilder(session_key="a", message_id="m2")
    assert tb1.trace_id != tb2.trace_id


def test_add_agent_trace_stores():
    store = MemoryStore()
    try:
        store.add_agent_trace(
            trace_id=_uniq("test_trace"),
            session_key="test_s",
            message_id="hello",
            started_at="2025-01-01T00:00:00+00:00",
            completed_at="2025-01-01T00:00:02+00:00",
            steps=[
                {"step_number": 1, "step_name": "LLM_CALL", "status": "ok",
                 "detail": "response 42 chars", "elapsed_ms": 2000.0},
            ],
            total_elapsed_ms=2100.0,
        )
        traces = store.get_agent_traces(session_key="test_s", limit=10)
        assert len(traces) == 1
        t = traces[0]
        assert t["trace_id"].startswith("test_trace_")
        assert len(t["steps"]) == 1
        assert t["steps"][0]["step_name"] == "LLM_CALL"
    finally:
        store.close()


def test_get_agent_traces_empty():
    store = MemoryStore()
    try:
        traces = store.get_agent_traces(session_key="no_traces_session", limit=10)
        assert len(traces) == 0
    finally:
        store.close()


def test_get_agent_traces_respects_limit():
    store = MemoryStore()
    try:
        for i in range(5):
            store.add_agent_trace(
                trace_id=_uniq(f"limit_test_{i}"),
                session_key="limit_s",
                message_id=f"msg{i}",
                started_at="2025-01-01T00:00:00+00:00",
                completed_at="2025-01-01T00:00:01+00:00",
                steps=[],
                total_elapsed_ms=1000.0,
            )
        traces = store.get_agent_traces(session_key="limit_s", limit=3)
        assert len(traces) == 3
    finally:
        store.close()


def test_get_agent_traces_session_isolation():
    store = MemoryStore()
    try:
        store.add_agent_trace(
            trace_id=_uniq("session_a"),
            session_key="trace_s_a",
            message_id="msg",
            started_at="2025-01-01T00:00:00+00:00",
            completed_at="2025-01-01T00:00:01+00:00",
            steps=[],
            total_elapsed_ms=1000.0,
        )
        traces_b = store.get_agent_traces(session_key="trace_s_b", limit=10)
        assert len(traces_b) == 0
    finally:
        store.close()


def test_trace_integration_in_process_message():
    """Mock LLM，验证 _process_message 写入 trace."""
    bus = MessageBus()
    loop = AgentLoop(bus=bus, delays_enabled=False, memory_maintenance=False)

    # mock LLM
    async def fake_chat(messages, temperature=0.7, tools=None):
        return {"content": "怎么啦？有什么烦心事吗？"}

    loop.provider.chat = fake_chat

    async def run():
        msg = InboundMessage(
            channel="web", sender_id="user", chat_id="trace_integ",
            content="最近有点累", metadata={},
        )
        await loop._process_message(msg)

    asyncio.run(run())

    traces = loop.memory.get_agent_traces(session_key="trace_integ", limit=5)
    assert len(traces) >= 1
    step_names = [s["step_name"] for s in traces[0]["steps"]]
    assert "DEFENSE_CHECK" in step_names
    assert "CRISIS_CHECK" in step_names
    assert "ANCHOR_RECALL" in step_names
    assert "LLM_CALL" in step_names
    assert "RELATIONSHIP_UPDATE" in step_names
    assert "MEMORY_MAINTENANCE" in step_names
    # verify LLM_CALL step has detail
    llm_step = [s for s in traces[0]["steps"] if s["step_name"] == "LLM_CALL"][0]
    assert "chars" in llm_step["detail"]
    loop.memory.close()


def test_trace_skip_anchor_on_empty_session():
    """空 session 时 ANCHOR_RECALL trace 应该是 hits=0."""
    bus = MessageBus()
    loop = AgentLoop(bus=bus, delays_enabled=False, memory_maintenance=False)

    async def fake_chat(messages, temperature=0.7, tools=None):
        return {"content": "你好呀"}

    loop.provider.chat = fake_chat

    async def run():
        msg = InboundMessage(
            channel="web", sender_id="user", chat_id="trace_skip",
            content="你好", metadata={},
        )
        await loop._process_message(msg)

    asyncio.run(run())

    traces = loop.memory.get_agent_traces(session_key="trace_skip", limit=5)
    anchor_step = [s for s in traces[0]["steps"]
                   if s["step_name"] == "ANCHOR_RECALL"][0]
    assert anchor_step["detail"] == "hits=0"
    loop.memory.close()
