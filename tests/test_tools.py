"""测试工具抽象 + 注册表 + 工具调用循环 + 天气工具."""

import sys

sys.path.insert(0, '.')

import asyncio

from mindmate.agent.loop import AgentLoop
from mindmate.bus.events import MessageBus
from mindmate.tools.base import Tool, ToolRegistry
from mindmate.tools.weather import WeatherTool


class EchoTool(Tool):
    name = "echo"
    description = "回显输入"
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    async def execute(self, text: str = "", **_):
        return f"echo: {text}"


class BoomTool(Tool):
    name = "boom"
    description = "总是出错"
    parameters = {"type": "object", "properties": {}}

    async def execute(self, **_):
        raise RuntimeError("boom")


# ---- 注册表 ----

def test_registry_empty():
    r = ToolRegistry()
    assert r.is_empty()
    assert r.schemas() == []


def test_registry_register_and_schema():
    r = ToolRegistry()
    r.register(EchoTool())
    assert not r.is_empty()
    assert r.names() == ["echo"]
    s = r.schemas()
    assert s[0]["type"] == "function"
    assert s[0]["function"]["name"] == "echo"
    assert "text" in s[0]["function"]["parameters"]["properties"]


def test_registry_execute():
    r = ToolRegistry()
    r.register(EchoTool())
    out = asyncio.run(r.execute("echo", {"text": "hi"}))
    assert out == "echo: hi"


def test_registry_unknown_tool():
    r = ToolRegistry()
    out = asyncio.run(r.execute("nope", {}))
    assert "不存在" in out


def test_registry_tool_error_caught():
    r = ToolRegistry()
    r.register(BoomTool())
    out = asyncio.run(r.execute("boom", {}))
    assert "出错" in out  # 异常被捕获，返回可读文本而非抛出


def test_register_requires_name():
    r = ToolRegistry()

    class NoName(Tool):
        name = ""
        async def execute(self, **_):
            return ""

    try:
        r.register(NoName())
        assert False, "应抛 ValueError"
    except ValueError:
        pass


# ---- 工具调用循环 ----

def test_run_llm_no_tools_single_round():
    """无工具 → 单轮，行为不变."""
    bus = MessageBus()
    loop = AgentLoop(bus=bus, delays_enabled=False, memory_maintenance=False)

    calls = []
    async def fake_chat(messages, temperature=0.7):
        calls.append(messages)
        return {"content": "你好呀"}
    loop.provider.chat = fake_chat

    out = asyncio.run(loop._run_llm([{"role": "user", "content": "hi"}]))
    assert out == "你好呀"
    assert len(calls) == 1


def test_run_llm_with_tool_call_roundtrip():
    """模型要调工具 → 执行 → 喂回 → 再 chat 出最终回复."""
    bus = MessageBus()
    reg = ToolRegistry()
    reg.register(EchoTool())
    loop = AgentLoop(
        bus=bus, delays_enabled=False, memory_maintenance=False, tools=reg
    )

    step = {"n": 0}
    async def fake_chat(messages, tools=None, temperature=0.7):
        step["n"] += 1
        if step["n"] == 1:
            # 第一次：要求调用 echo
            assert tools is not None
            raw = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "echo", "arguments": '{"text":"ok"}'},
                    }
                ],
            }
            return {
                "content": None,
                "tool_calls": [
                    {"id": "c1", "name": "echo", "arguments": {"text": "ok"}}
                ],
                "raw_message": raw,
            }
        # 第二次：拿到工具结果后给最终回复
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        assert tool_msgs and tool_msgs[-1]["content"] == "echo: ok"
        return {"content": "工具说 echo: ok", "tool_calls": None}
    loop.provider.chat = fake_chat

    out = asyncio.run(loop._run_llm([{"role": "user", "content": "调用echo"}]))
    assert out == "工具说 echo: ok"
    assert step["n"] == 2


def test_run_llm_max_rounds():
    """工具一直被调用 → 达到上限后强制收尾，不死循环."""
    bus = MessageBus()
    reg = ToolRegistry()
    reg.register(EchoTool())
    loop = AgentLoop(
        bus=bus, delays_enabled=False, memory_maintenance=False, tools=reg
    )

    n = {"c": 0}
    async def always_tool(messages, tools=None, temperature=0.7):
        n["c"] += 1
        # 不带 tools 的最终调用 → 收尾
        if tools is None:
            return {"content": "收尾", "tool_calls": None}
        return {
            "content": None,
            "tool_calls": [{"id": f"c{n['c']}", "name": "echo", "arguments": {"text": "x"}}],
            "raw_message": {"role": "assistant", "content": None, "tool_calls": []},
        }
    loop.provider.chat = always_tool

    out = asyncio.run(loop._run_llm([{"role": "user", "content": "hi"}]))
    assert out == "收尾"


# ---- 天气工具 ----

def test_weather_empty_location():
    w = WeatherTool()
    out = asyncio.run(w.execute(location=""))
    assert "未提供" in out


def test_weather_schema():
    w = WeatherTool()
    s = w.schema()
    assert s["function"]["name"] == "get_weather"
    assert "location" in s["function"]["parameters"]["properties"]
