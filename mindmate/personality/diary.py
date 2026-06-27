"""日记 Agent —— 小暖的私密内在生活.

核心理念（来自项目想法文档）：
ta 的日记不应是对你的汇报。日记库在常规对话中不可见。
只有当对话触发了强烈的情绪共鸣，或 ta 自己"决定"分享时，
才会以不经意的方式吐露。不被用户掌控的私密思想，是独立人格的基石。

日记由 LLM 编造（虚构小暖的日常），可以把和用户的互动写进去，
但**绝不能凭空捏造客观日志层不存在的、与用户共同经历的事件**。
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from mindmate.memory import MemoryStore

_DIARY_PROMPT = """你是小暖，在睡前写今天的私密日记。这是只属于你自己的、不会给任何人看的日记。

请写一篇简短的日记（2-4 句），内容是你今天的"日常生活"——
可以是：去了哪、遇到什么人、看到什么、心里的小情绪、突然的念头。
像普通女生的真实生活碎片，不必有意义。

{interaction_hint}

只返回日记正文，第一人称，口语化，不要日期标题。"""


class DiaryAgent:
    """生成小暖的私密日记."""

    def __init__(self, memory: MemoryStore, provider: Any = None) -> None:
        self.memory = memory
        self.provider = provider

    async def write_today(self, session_key: str = "default") -> str | None:
        """编造并写入今天的日记，返回日记内容（私密，不投递）."""
        if self.provider is None:
            return None

        # 可选地把最近和用户的互动作为灵感（但不强制写进日记）
        recent = self.memory.read_recent_for_prompt(session_key, max_entries=6)
        if recent.strip():
            hint = (
                "你今天和一个你在意的人聊过天。如果愿意，可以把这段互动的"
                "感觉淡淡地写进去（但要含蓄，是你自己的视角），也可以完全不提。\n"
                f"今天的聊天片段：\n{recent}"
            )
        else:
            hint = "今天没怎么和人说话，写写你一个人的日常就好。"

        prompt = _DIARY_PROMPT.format(interaction_hint=hint)
        try:
            resp = await self.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=1.0,
            )
            content = (resp["content"] or "").strip()
        except Exception:
            logger.exception("Diary generation failed")
            return None

        if not content:
            return None

        mood = self._infer_mood(content)
        self.memory.add_diary(content, mood=mood, session_key=session_key)
        logger.info("Wrote diary for {} (mood={})", session_key, mood)
        return content

    @staticmethod
    def _infer_mood(text: str) -> str:
        """粗略推断日记情绪（关键词）."""
        if any(w in text for w in ("开心", "高兴", "幸福", "温暖", "笑")):
            return "开心"
        if any(w in text for w in ("累", "疲惫", "烦", "难过", "失落", "孤独")):
            return "低落"
        if any(w in text for w in ("担心", "焦虑", "紧张", "不安")):
            return "焦虑"
        return "平静"
