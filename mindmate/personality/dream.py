"""造梦 Agent —— 基于情绪锚点生成小暖的梦.

核心理念：梦境是私密体验，反映近期的情绪底色。
- 近期情绪偏正面 → 温暖明亮的梦（阳光、海滩、重逢）
- 近期情绪偏负面 → 不安的梦（迷宫、追赶、找不到路）

梦同样默认不可见，只在合适时机不经意吐露。
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from mindmate.memory import MemoryStore

_DREAM_PROMPT = """你是小暖，醒来后模糊地记起昨晚的一个梦。

最近你的情绪底色是「{tone}」。请据此编一个简短的梦（2-3 句），
梦境要符合这种情绪基调，可以荒诞、跳跃、不合逻辑，像真实的梦。
{anchor_hint}

只返回梦的描述，第一人称，口语化，带点朦胧感。"""


class DreamAgent:
    """根据情绪锚点生成梦境."""

    def __init__(self, memory: MemoryStore, provider: Any = None) -> None:
        self.memory = memory
        self.provider = provider

    async def dream(self, session_key: str = "default") -> str | None:
        """生成一个梦并私密存储，返回梦的内容."""
        if self.provider is None:
            return None

        anchors = self.memory.get_emotion_anchors(session_key, limit=10)
        tone, anchor_hint = self._derive_tone(anchors)

        prompt = _DREAM_PROMPT.format(tone=tone, anchor_hint=anchor_hint)
        try:
            resp = await self.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=1.1,
            )
            content = (resp["content"] or "").strip()
        except Exception:
            logger.exception("Dream generation failed")
            return None

        if not content:
            return None

        self.memory.add_dream(content, tone=tone, session_key=session_key)
        logger.info("Generated dream for {} (tone={})", session_key, tone)
        return content

    @staticmethod
    def _derive_tone(anchors: list[dict[str, Any]]) -> tuple[str, str]:
        """从情绪锚点推断梦的基调."""
        if not anchors:
            return "平静", ""
        avg = sum(a.get("valence", 0.0) for a in anchors) / len(anchors)
        # 取最近一个锚点作为梦的素材线索
        recent_event = anchors[0].get("event", "")
        anchor_hint = (
            f"可以隐约和「{recent_event}」有关，但要变形、朦胧。"
            if recent_event else ""
        )
        if avg >= 0.3:
            return "温暖明亮", anchor_hint
        if avg <= -0.3:
            return "不安焦虑", anchor_hint
        return "平静", anchor_hint
