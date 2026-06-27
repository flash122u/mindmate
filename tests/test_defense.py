"""测试防御机制."""

import sys
sys.path.insert(0, '.')

from mindmate.personality.defense import (
    DefenseMechanism,
    DefenseStrategy,
    TabooRule,
)


def test_no_trigger_on_normal_message():
    d = DefenseMechanism()
    result = d.check("今天天气真好")
    assert result.triggered is False
    assert result.strategy == DefenseStrategy.NONE


def test_identity_question_triggers():
    d = DefenseMechanism()
    result = d.check("你是不是机器人？")
    assert result.triggered is True
    assert result.rule_name == "身份质疑"


def test_identity_ai_variant():
    d = DefenseMechanism()
    result = d.check("你是AI吧")
    assert result.triggered is True
    assert result.rule_name == "身份质疑"


def test_diary_privacy_triggers():
    d = DefenseMechanism()
    result = d.check("你日记里写了什么")
    assert result.triggered is True
    assert result.rule_name == "日记隐私"


def test_dream_privacy_triggers():
    d = DefenseMechanism()
    result = d.check("你昨天做了什么梦")
    assert result.triggered is True
    assert result.rule_name == "梦境隐私"


def test_pressure_escalation():
    d = DefenseMechanism()
    # 连续逼问同一雷区（每条都需提及日记才能命中规则）
    d.check("你日记写了什么，老实说", session_key="s1")
    d.check("到底日记里写了什么，别回避", session_key="s1")
    result = d.check("快说你日记内容，必须告诉我", session_key="s1")
    # 升级到更强硬的拒绝
    assert result.extra_pressure >= 2
    assert result.strategy == DefenseStrategy.REFUSE_HARD


def test_build_defense_prompt():
    d = DefenseMechanism()
    result = d.check("你是机器人吗")
    prompt = d.build_defense_prompt(result)
    assert "防御提示" in prompt
    assert "身份质疑" in prompt


def test_build_prompt_empty_when_not_triggered():
    d = DefenseMechanism()
    result = d.check("你好呀")
    prompt = d.build_defense_prompt(result)
    assert prompt == ""


def test_reset_pressure():
    d = DefenseMechanism()
    d.check("你日记写了什么，快说", session_key="s2")
    d.reset_pressure("s2")
    # 重置后重新计数
    result = d.check("你日记写了什么", session_key="s2")
    assert result.extra_pressure == 0


def test_custom_rules():
    rules = [
        TabooRule(
            name="测试雷区",
            patterns=[r"秘密"],
            strategy=DefenseStrategy.VAGUE,
            hint="不说",
        )
    ]
    d = DefenseMechanism(rules=rules)
    result = d.check("告诉我你的秘密")
    assert result.triggered is True
    assert result.rule_name == "测试雷区"
