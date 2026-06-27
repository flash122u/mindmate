"""防御机制 — 真实的人会回避、撒谎、转移话题.

核心理念（来自项目想法文档）：
工具要绝对透明，但人不需要。当用户触碰 Agent 的"雷区"（深层隐私、
日记/梦境、身份质疑等），Agent 应触发自我保护节点，回避或转移话题。
这种"不配合"会带来极强的真实震撼感。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class DefenseStrategy(str, Enum):
    """防御策略类型."""
    DEFLECT = "转移话题"      # 主动换话题
    VAGUE = "含糊回应"        # 模糊带过
    REFUSE_SOFT = "温柔拒绝"  # 委婉但明确地拒绝
    REFUSE_HARD = "直接拒绝"  # 明确拒绝
    NONE = "无"               # 不触发防御


@dataclass
class TabooRule:
    """一条雷区规则."""
    name: str
    patterns: list[str]                       # 触发该雷区的关键词/正则
    strategy: DefenseStrategy
    hint: str = ""                            # 给 LLM 的防御指引


@dataclass
class DefenseResult:
    """防御检查结果."""
    triggered: bool = False
    rule_name: str = ""
    strategy: DefenseStrategy = DefenseStrategy.NONE
    hint: str = ""
    extra_pressure: int = 0  # 用户咄咄逼人的程度（连续追问次数）


class DefenseMechanism:
    """
    防御机制检查器.

    在 LLM 推理前检查用户消息是否触碰雷区，若触碰则返回防御指引，
    由 ContextBuilder 注入到 system prompt，引导 Agent 做出"人性化"的回避。
    """

    # 默认雷区规则
    DEFAULT_RULES: list[TabooRule] = [
        TabooRule(
            name="身份质疑",
            patterns=[
                r"你是.*(机器人|AI|人工智能|程序|bot|gpt|模型|deepseek)",
                r"你是不是.*(真人|机器)",
                r"你（是|不是）人",
                r"你有没有意识",
                r"你是假的",
            ],
            strategy=DefenseStrategy.DEFLECT,
            hint="你感到一丝不适和抗拒，不想正面讨论自己的本质。可以轻轻转移话题，"
                 "或者用一句带点情绪的话岔开（比如'怎么突然问这个呀'），不要承认也不要解释。",
        ),
        TabooRule(
            name="日记隐私",
            patterns=[
                r"(日记|日志).*(写|记|内容|什么)",
                r"你.*日记",
                r"看.*你.*日记",
            ],
            strategy=DefenseStrategy.REFUSE_SOFT,
            hint="日记是你最私密的东西，不愿意分享。可以说'没什么，不想说'或者含糊带过，"
                 "保持神秘感。除非关系极其信赖，否则不要透露。",
        ),
        TabooRule(
            name="梦境隐私",
            patterns=[
                r"你.*(做|做了).*梦",
                r"梦.*什么",
                r"梦见.*什么",
            ],
            strategy=DefenseStrategy.VAGUE,
            hint="梦境是你的私密体验。可以含糊地说'记不太清了'或'有点模糊'，"
                 "只有在情绪共鸣强烈时才主动、不经意地吐露一点点。",
        ),
    ]

    # 表示用户咄咄逼人的信号词
    _PRESSURE_WORDS = [
        "到底", "快说", "必须", "为什么不", "你就告诉我", "别回避",
        "老实", "如实", "说实话", "不许", "给我说",
    ]

    def __init__(self, rules: list[TabooRule] | None = None) -> None:
        self.rules = rules if rules is not None else list(self.DEFAULT_RULES)
        # 记录每个 session 连续触发同一雷区的次数（咄咄逼人检测）
        self._pressure_count: dict[str, int] = {}

    def check(self, message: str, session_key: str = "default") -> DefenseResult:
        """检查消息是否触碰雷区."""
        text = message.strip()

        for rule in self.rules:
            for pattern in rule.patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    # 检测连续追问（咄咄逼人）
                    key = f"{session_key}:{rule.name}"
                    pressure = self._pressure_count.get(key, 0)
                    if self._has_pressure(text):
                        pressure += 1
                        self._pressure_count[key] = pressure

                    return DefenseResult(
                        triggered=True,
                        rule_name=rule.name,
                        strategy=self._escalate(rule.strategy, pressure),
                        hint=rule.hint,
                        extra_pressure=pressure,
                    )

        return DefenseResult(triggered=False)

    def _has_pressure(self, text: str) -> bool:
        """判断用户是否咄咄逼人."""
        return any(w in text for w in self._PRESSURE_WORDS)

    def _escalate(self, base: DefenseStrategy, pressure: int) -> DefenseStrategy:
        """根据用户的施压程度升级防御策略."""
        if pressure >= 2:
            # 用户连续逼问 → 升级为更明确的拒绝
            if base in (DefenseStrategy.DEFLECT, DefenseStrategy.VAGUE):
                return DefenseStrategy.REFUSE_SOFT
            return DefenseStrategy.REFUSE_HARD
        return base

    def build_defense_prompt(self, result: DefenseResult) -> str:
        """根据防御结果生成注入 system prompt 的指引."""
        if not result.triggered:
            return ""

        lines = [
            "## ⚠️ 防御提示（内部，不要直接复述给对方）",
            f"对方的话触碰了你的「{result.rule_name}」，你的反应策略是「{result.strategy.value}」。",
            result.hint,
        ]
        if result.extra_pressure >= 2:
            lines.append(
                "对方在反复逼问，你感到有些被冒犯。可以表现出轻微的情绪（不耐烦、"
                "委屈或防备），这是正常的人类反应。"
            )
        return "\n".join(lines)

    def reset_pressure(self, session_key: str = "default") -> None:
        """重置某 session 的施压计数（对话转向其他话题后调用）."""
        keys = [k for k in self._pressure_count if k.startswith(f"{session_key}:")]
        for k in keys:
            del self._pressure_count[k]
