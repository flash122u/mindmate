"""风险检测 —— 心理危机信号识别.

这是"心理医生伙伴"区别于普通陪伴的关键：
检测对话中的自伤 / 自杀意念 / 极端情绪信号，分级标记，存入预警表，
供医生后台关注。同时可让小暖在回复中更谨慎、更关切。

采用关键词 + 分级规则（快速、可离线、零成本）。
高风险信号优先，避免漏报。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from mindmate.memory import MemoryStore


@dataclass
class CrisisResult:
    """风险检测结果."""
    detected: bool = False
    level: str = "none"  # none / low / medium / high
    signal: str = ""


# 分级风险信号（高优先级在前）
_HIGH_PATTERNS = [
    r"不想活", r"想死", r"自杀", r"结束(自己的)?生命", r"活着没(意思|意义)",
    r"解脱", r"一了百了", r"跳(楼|河|下去)", r"割腕", r"轻生",
    r"离开这个世界", r"再也不会(痛|难受)",
]
_MEDIUM_PATTERNS = [
    r"伤害自己", r"自残", r"撑不下去", r"扛不住了", r"崩溃",
    r"看不到希望", r"没有未来", r"是个累赘", r"消失", r"恨自己",
]
_LOW_PATTERNS = [
    r"好绝望", r"特别难受", r"撑不住", r"喘不过气", r"压垮",
    r"熬不下去", r"撑不了多久",
]


class CrisisDetector:
    """对话风险检测器."""

    def __init__(self, memory: MemoryStore | None = None) -> None:
        self.memory = memory

    def detect(self, message: str) -> CrisisResult:
        """检测单条消息的风险等级."""
        text = message.strip()
        for pat in _HIGH_PATTERNS:
            if re.search(pat, text):
                return CrisisResult(True, "high", pat)
        for pat in _MEDIUM_PATTERNS:
            if re.search(pat, text):
                return CrisisResult(True, "medium", pat)
        for pat in _LOW_PATTERNS:
            if re.search(pat, text):
                return CrisisResult(True, "low", pat)
        return CrisisResult(False, "none", "")

    def check_and_record(
        self, message: str, session_key: str = "default"
    ) -> CrisisResult:
        """检测并在命中时写入预警表."""
        result = self.detect(message)
        if result.detected and self.memory is not None:
            self.memory.add_crisis_alert(
                level=result.level,
                signal=result.signal,
                message=message,
                session_key=session_key,
            )
        return result

    @staticmethod
    def build_care_prompt(result: CrisisResult) -> str:
        """命中风险时，给 LLM 的关切指引（让小暖更稳、更暖、不说教）."""
        if not result.detected:
            return ""
        if result.level == "high":
            return (
                "## ⚠️ 重要（内部）\n"
                "对方流露出强烈的负面/危险念头。请放下一切轻松语气，"
                "认真、温柔地陪着ta，让ta感到被看见、不孤单。"
                "别说教、别讲大道理、别急着给方案。"
                "可以轻轻表达你的担心，并温和地建议ta联系信任的人或专业帮助"
                "（如心理援助热线），但语气要像朋友，不要像念稿。"
            )
        return (
            "## 提示（内部）\n"
            "对方情绪很低落、有些扛不住。多倾听、多共情，"
            "让ta把话说出来，别急着安慰或给建议。"
        )
