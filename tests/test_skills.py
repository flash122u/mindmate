"""测试陪伴场景 Skill 系统."""

import sys

sys.path.insert(0, '..')

import asyncio
import tempfile
from pathlib import Path

from mindmate.agent.loop import AgentLoop
from mindmate.bus.events import InboundMessage, MessageBus
from mindmate.skills.skill import (
    SkillLibrary,
    SkillLoadError,
    SkillRegistry,
)

# ---------------------------------------------------------------------------
# 辅助：在临时目录中写一个 SKILL.md
# ---------------------------------------------------------------------------

def _write_skill(root: Path, name: str, text: str) -> Path:
    """在 {root}/{name}/SKILL.md 中写入文本，返回文件路径."""
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    f = d / "SKILL.md"
    f.write_text(text, encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# SkillRegistry 加载
# ---------------------------------------------------------------------------

def test_registry_loads_valid_skill():
    """有效 SKILL.md 应该被正确加载."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_skill(root, "loneliness", """---
name: loneliness
description: 用户表达孤独/寂寞/没人陪时激活
keywords:
  - 孤独
  - 寂寞
---

# 孤独陪伴指引

## 小暖该怎么做

- 先接住这种感受

## 避免

- ❌ "你多交朋友就好了"
""")
        reg = SkillRegistry(root=root)
        skills = reg.list_skills()
        assert len(skills) == 1
        s = skills[0]
        assert s.name == "loneliness"
        assert "孤独" in s.keywords
        assert "寂寞" in s.keywords
        assert "## 小暖该怎么做" in s.body
        assert "## 避免" in s.body
        assert s.validation_issues() == []


def test_registry_empty_on_missing_dir():
    """skills 目录不存在时返回空列表."""
    reg = SkillRegistry(root=Path("/nonexistent_skills_dir_12345"))
    assert reg.list_skills() == []
    assert reg.status_items() == []


def test_registry_skips_invalid_frontmatter():
    """缺少 frontmatter 的 Skill 被跳过（不崩溃）."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_skill(root, "bad_skill", "# No frontmatter here")
        reg = SkillRegistry(root=root)
        skills = reg.list_skills()
        for s in skills:
            assert s.name != "bad_skill"


def test_registry_get_required():
    """按名称查找 Skill."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_skill(root, "loneliness", """---
name: loneliness
description: 用户表达孤独时激活
keywords:
  - 孤独
---

# 孤独陪伴

## 小暖该怎么做
- 听
## 避免
- 说教
""")
        reg = SkillRegistry(root=root)
        skill = reg.get_required("loneliness")
        assert skill.name == "loneliness"


def test_registry_get_required_missing():
    """找不到的 Skill 抛出 SkillLoadError."""
    with tempfile.TemporaryDirectory() as td:
        reg = SkillRegistry(root=Path(td))
        try:
            reg.get_required("nonexistent")
            assert False, "应该抛出 SkillLoadError"
        except SkillLoadError:
            pass


# ---------------------------------------------------------------------------
# SkillLibrary 选择逻辑
# ---------------------------------------------------------------------------

def test_select_skill_names_matches_keywords():
    """用户消息命中关键词时返回对应 Skill 名."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_skill(root, "loneliness", """---
name: loneliness
description: 用户表达孤独时激活
keywords:
  - 孤独
  - 寂寞
---

# 孤独陪伴

## 小暖该怎么做
- 听
## 避免
- 说教
""")
        _write_skill(root, "work_stress", """---
name: work_stress
description: 工作压力时激活
keywords:
  - 加班
  - 压力大
---

# 工作压力

## 小暖该怎么做
- 共情
## 避免
- 建议
""")
        SkillLibrary.reset_registry()
        registry = SkillLibrary.registry()
        registry.root = root
        # 命中 loneliness
        assert "loneliness" in SkillLibrary.select_skill_names("我最近好孤独啊")
        # 命中 work_stress
        assert "work_stress" in SkillLibrary.select_skill_names("加班好累不想上班")
        # 无匹配
        assert SkillLibrary.select_skill_names("今天天气真好") == []


def test_select_skill_names_multi_match():
    """一条消息可以命中多个 Skill."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_skill(root, "loneliness", """---
name: loneliness
description: test
keywords:
  - 孤独
---

# 孤独

## 小暖该怎么做
- 听
## 避免
- 说
""")
        _write_skill(root, "anxiety", """---
name: anxiety
description: test
keywords:
  - 焦虑
---

# 焦虑

## 小暖该怎么做
- 安抚
## 避免
- 催促
""")
        SkillLibrary.reset_registry()
        registry = SkillLibrary.registry()
        registry.root = root
        selected = SkillLibrary.select_skill_names("我孤独又焦虑")
        assert "loneliness" in selected
        assert "anxiety" in selected


def test_select_skill_names_empty_for_non_chat():
    """非 chat 意图不注入 Skill."""
    assert SkillLibrary.select_skill_names("我很孤独", intent="risk") == []
    assert SkillLibrary.select_skill_names("你能做什么", intent="functional") == []
    assert SkillLibrary.select_skill_names("你是谁", intent="identity") == []


def test_build_skill_context_formats():
    """验证 build_skill_context 格式化输出."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_skill(root, "loneliness", """---
name: loneliness
description: 用户表达孤独时激活
keywords:
  - 孤独
---

# 孤独陪伴指引

## 小暖该怎么做
- 先接住
""")
        SkillLibrary.reset_registry()
        registry = SkillLibrary.registry()
        registry.root = root
        ctx = SkillLibrary.build_skill_context("我最近好孤独")
        assert "## 陪伴指引：loneliness" in ctx
        assert "小暖该怎么做" in ctx
        assert "先接住" in ctx


def test_build_skill_context_empty_for_non_chat():
    """非 chat 意图返回空字符串."""
    ctx = SkillLibrary.build_skill_context("我很孤独", intent="risk")
    assert ctx == ""


# ---------------------------------------------------------------------------
# 集成测试：Skill 注入到 system prompt
# ---------------------------------------------------------------------------

def test_integration_skill_injected_when_match():
    """命中关键词时，skill context 被注入到 system prompt."""
    SkillLibrary.reset_registry()  # 避免前序测试污染类级单例
    bus = MessageBus()
    loop = AgentLoop(bus=bus, delays_enabled=False, memory_maintenance=False)

    call_count = 0
    _captured_messages = []

    async def fake_chat(messages, temperature=0.7, tools=None):
        nonlocal call_count
        call_count += 1
        _captured_messages.append(messages)
        return {"content": "怎么啦"}

    loop.provider.chat = fake_chat

    async def run():
        msg = InboundMessage(
            channel="web", sender_id="user", chat_id="skill_test",
            content="我最近好孤独", metadata={},
        )
        await loop._process_message(msg)

    asyncio.run(run())

    # LLM 被调用了（chat 意图走正常路径）
    assert call_count == 1
    system = _captured_messages[0][0]["content"]
    # skill context 被注入
    assert "## 陪伴指引" in system
    loop.memory.close()


def test_integration_skill_not_injected_when_no_match():
    """无关键词命中时，skill context 不注入."""
    SkillLibrary.reset_registry()
    bus = MessageBus()
    loop = AgentLoop(bus=bus, delays_enabled=False, memory_maintenance=False)

    _captured_messages = []

    async def fake_chat(messages, temperature=0.7, tools=None):
        _captured_messages.append(messages)
        return {"content": "是啊"}

    loop.provider.chat = fake_chat

    async def run():
        msg = InboundMessage(
            channel="web", sender_id="user", chat_id="skill_none",
            content="今天天气真好", metadata={},
        )
        await loop._process_message(msg)

    asyncio.run(run())

    system = _captured_messages[0][0]["content"]
    assert "## 陪伴指引" not in system
    loop.memory.close()


# ---------------------------------------------------------------------------
# SKILL_SELECT trace 步骤
# ---------------------------------------------------------------------------

def test_skill_select_trace_recorded():
    """命中 Skill 时，trace 中记录 SKILL_SELECT 步骤."""
    SkillLibrary.reset_registry()
    bus = MessageBus()
    loop = AgentLoop(bus=bus, delays_enabled=False, memory_maintenance=False)

    async def fake_chat(messages, temperature=0.7, tools=None):
        return {"content": "怎么啦，跟我说说"}

    loop.provider.chat = fake_chat

    async def run():
        msg = InboundMessage(
            channel="web", sender_id="user", chat_id="skill_trace",
            content="我最近好孤独好焦虑", metadata={},
        )
        await loop._process_message(msg)

    asyncio.run(run())

    traces = loop.memory.get_agent_traces(session_key="skill_trace", limit=5)
    assert len(traces) >= 1
    step_names = [s["step_name"] for s in traces[0]["steps"]]
    assert "SKILL_SELECT" in step_names
    skill_step = [s for s in traces[0]["steps"] if s["step_name"] == "SKILL_SELECT"][0]
    assert "loneliness" in skill_step["detail"] or "anxiety" in skill_step["detail"]
    loop.memory.close()


# ---------------------------------------------------------------------------
# skill_library 可注入
# ---------------------------------------------------------------------------

def test_agent_loop_has_default_skill_library():
    """AgentLoop 默认有 SkillLibrary."""
    bus = MessageBus()
    loop = AgentLoop(bus=bus)
    assert loop.skill_library is not None
    assert isinstance(loop.skill_library, SkillLibrary)


def test_agent_loop_accepts_custom_skill_library():
    """AgentLoop 接受自定义 SkillLibrary."""
    bus = MessageBus()
    custom = SkillLibrary()
    loop = AgentLoop(bus=bus, skill_library=custom)
    assert loop.skill_library is custom
