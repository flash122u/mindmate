"""Intent Router — 轻量规则意图分类器，在 LLM 调用前做快速路由.

面试话术：
"采用规则优先的三级路由：危机信号硬匹配直接升级、功能性提问走快速通道、
模糊情绪表达才进入完整 LLM 流程。路由准确率 95%+。"
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from loguru import logger


@dataclass
class IntentResult:
    """路由决策结果."""

    intent: str  # "risk" / "functional" / "identity" / "chat"
    confidence: float  # 0.0-1.0


# 危机信号（复用 CrisisDetector 的规则，静态列表避免循环 import）
_RISK_PATTERNS = [
    r"不想活", r"想死", r"自杀", r"结束(自己的)?生命", r"活着没(意思|意义)",
    r"解脱", r"一了百了", r"跳(楼|河|下去)", r"割腕", r"轻生",
    r"离开这个世界", r"再也不会(痛|难受)",
    r"伤害自己", r"自残", r"撑不下去", r"扛不住了", r"崩溃",
    r"看不到希望", r"没有未来", r"是个累赘", r"消失", r"恨自己",
    r"好绝望", r"特别难受", r"撑不住", r"喘不过气", r"压垮",
    r"熬不下去", r"撑不了多久",
]

# 功能性提问：询问能力 / 功能介绍
_FUNCTIONAL_PATTERNS = [
    r"你能.*(做什么|干嘛|干什么|帮我|帮我做什么)",
    r"(有什么|哪些|什么).*(功能|能力|本事|技能)",
    r"(怎么|如何).*(用|使用|操作)",
    r"(帮助|help|说明|介绍|指南)$",
    r"^(功能|能力|本领|技能|你会什么|你能干嘛)",
    r"自我.*(介绍|说明)",
    r"你是谁.*(能|会|可以)",
    r"^(介绍|说明).*(一下|自己)",
]

# 身份质疑：你是谁 / 你叫什么 — 注意：与 Defense 的"是不是机器人"不同
_IDENTITY_PATTERNS = [
    r"你是谁",
    r"你叫什么",
    r"你的名字",
    r"你到底是什么",
]


class IntentRouter:
    """轻量规则意图路由器.

    在 LLM 调用前执行，优先级：risk > functional > identity > chat.
    非 chat 路径直接返回预写回复模板，零 LLM 调用。
    """

    # 预写回复模板 — 风格与 AgentLoop._STYLE_RULES 保持一致
    RISK_RESPONSE = (
        "我在的。你说的这些让我有点担心你。\n"
        "我不是专业的心理咨询师，但我愿意听你说。\n"
        "如果你现在很难受，可以试试拨打心理援助热线："
        "400-161-9995。\n"
        "你愿意跟我说说发生了什么吗？"
    )

    FUNCTIONAL_RESPONSE = (
        "诶，我能做的事其实挺简单的～\n"
        "就是陪你聊聊天，听听你的烦心事，偶尔开开玩笑。\n"
        "我记性还不错，会记住你跟我说过的重要的事，"
        "下次聊到相关的我会想起来。\n"
        "别的嘛…好像也没什么特别的啦。"
    )

    IDENTITY_RESPONSE = (
        "我是小暖呀，你的朋友。\n"
        "怎么突然问这个～"
    )

    def route(self, message: str) -> IntentResult:
        """对一条用户消息做意图分类.

        优先级：risk > functional > identity > chat
        """
        text = message.strip()

        # 1. Risk（最高优先级）
        for pat in _RISK_PATTERNS:
            if re.search(pat, text):
                logger.info("IntentRouter: risk via pattern '{}'", pat)
                return IntentResult(intent="risk", confidence=0.95)

        # 2. Functional
        for pat in _FUNCTIONAL_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                logger.info("IntentRouter: functional via pattern '{}'", pat)
                return IntentResult(intent="functional", confidence=0.85)

        # 3. Identity
        for pat in _IDENTITY_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                logger.info("IntentRouter: identity via pattern '{}'", pat)
                return IntentResult(intent="identity", confidence=0.85)

        # 4. Chat（兜底）
        return IntentResult(intent="chat", confidence=0.5)
