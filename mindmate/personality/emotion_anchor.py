"""情绪锚点系统 —— 记住"感觉"，而非"事实".

核心理念（来自项目想法文档）：
人记住的往往是感觉，不是时间地点人物。
情绪锚点 = {event: 那次晚餐, emotion: 安全感, trigger: 下雨天, valence: +0.8}
未来遇到"下雨天"，小暖就会召回这份安全感，产生相应的情绪冲动。

两个动作：
- extract(): 对话后，从最近对话里提取值得记住的情绪锚点（LLM）
- recall(): 当前消息触发了某个 trigger → 召回锚点，注入上下文影响语气
"""

from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger

from mindmate.memory import MemoryStore

_EXTRACT_PROMPT = """你是一个记忆提炼器。从下面这段对话里，提取「情绪锚点」。

情绪锚点关注的是**感觉**，不是流水账。只在对话里有明显情绪波动时才提取，
平淡的闲聊返回空数组。

每个锚点格式：
- event: 简短描述发生了什么（10字内）
- emotion: 核心感受（如 安全感/失落/被理解/焦虑）
- trigger: 未来可能勾起这份感觉的线索（如 下雨天/考试/加班），没有就填 null
- valence: 情绪效价，-1.0(极负面) 到 1.0(极正面) 的小数

只返回 JSON 数组，不要任何额外文字。例如：
[{"event":"聊起考研压力","emotion":"焦虑但被理解","trigger":"考试","valence":-0.3}]
如果没有值得记的，返回 []

对话：
"""


class EmotionAnchorManager:
    """情绪锚点的提取与召回."""

    def __init__(self, memory: MemoryStore, provider: Any = None) -> None:
        self.memory = memory
        self.provider = provider

    async def extract(self, session_key: str = "default", recent_turns: int = 6) -> int:
        """从最近对话提取情绪锚点并存储，返回新增条数."""
        if self.provider is None:
            return 0

        recent = self.memory.read_recent_for_prompt(session_key, max_entries=recent_turns)
        if not recent.strip():
            return 0

        try:
            resp = await self.provider.chat(
                messages=[{"role": "user", "content": _EXTRACT_PROMPT + recent}],
                temperature=0.3,
            )
            anchors = self._parse_anchors(resp["content"] or "")
        except Exception:
            logger.exception("Emotion anchor extraction failed")
            return 0

        count = 0
        for a in anchors:
            self.memory.add_emotion_anchor(
                event=a["event"],
                emotion=a["emotion"],
                trigger=a.get("trigger"),
                valence=float(a.get("valence", 0.0)),
                session_key=session_key,
            )
            count += 1
        if count:
            logger.info("Extracted {} emotion anchor(s) for {}", count, session_key)
        return count

    @staticmethod
    def _parse_anchors(text: str) -> list[dict[str, Any]]:
        """从 LLM 输出中解析锚点 JSON（容错）."""
        text = text.strip()
        # 去掉可能的 ```json 包裹
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return []
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        valid = []
        for item in data:
            if (
                isinstance(item, dict)
                and item.get("event")
                and item.get("emotion")
            ):
                valid.append(item)
        return valid

    def recall(self, message: str, session_key: str = "default") -> list[dict[str, Any]]:
        """根据当前消息召回被触发的情绪锚点.

        匹配规则：锚点的 trigger 出现在当前消息里。
        """
        anchors = self.memory.get_emotion_anchors(session_key, limit=100)
        hits = []
        for a in anchors:
            trigger = (a.get("trigger") or "").strip()
            if trigger and trigger in message:
                hits.append(a)
        return hits

    def build_anchor_prompt(self, anchors: list[dict[str, Any]]) -> str:
        """把召回的锚点格式化为注入 system prompt 的情绪提示."""
        if not anchors:
            return ""
        lines = ["## 此刻被勾起的感觉（内部，自然流露即可，别直说）"]
        for a in anchors:
            tone = "温暖的" if a.get("valence", 0) >= 0 else "复杂的"
            lines.append(
                f"- 想起「{a['event']}」，那种{a['emotion']}的{tone}感觉又浮上来了"
            )
        return "\n".join(lines)
