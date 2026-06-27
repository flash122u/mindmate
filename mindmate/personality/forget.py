"""遗忘机制 —— 让记忆像人一样会褪色.

核心理念（来自项目想法文档）：
真实的人会遗忘。遗忘不是删除，而是「模糊」——
精确的事实褪色成模糊的感觉。但绝不能凭空捏造客观层不存在的事件。

本模块只作用于「主观体验层」（情绪锚点），不碰客观日志（history）。

策略（轻量、确定性，不依赖 LLM）：
- 情绪锚点随时间衰减 valence 的绝对值（感觉变淡）
- 低强度且陈旧的锚点会被遗忘（删除）
- 强烈的情绪（|valence| 大）记得更久
"""

from __future__ import annotations

from datetime import datetime

from loguru import logger

from mindmate.memory import MemoryStore


class ForgetAgent:
    """情绪锚点的遗忘/褪色处理器."""

    def __init__(
        self,
        memory: MemoryStore,
        forget_after_days: float = 30.0,
        weak_threshold: float = 0.2,
    ) -> None:
        """
        Args:
            forget_after_days: 超过这个天数的弱锚点会被遗忘
            weak_threshold: |valence| 低于此值视为"弱"记忆
        """
        self.memory = memory
        self.forget_after_days = forget_after_days
        self.weak_threshold = weak_threshold

    def forget_stale(self, session_key: str = "default", now: datetime | None = None) -> int:
        """遗忘陈旧且微弱的情绪锚点，返回遗忘条数.

        强烈的情绪（|valence| 高）即使陈旧也保留——刻骨铭心的事忘得慢。
        """
        now = now or datetime.now()
        anchors = self._all_anchors_with_id(session_key)
        forgotten = 0
        for a in anchors:
            try:
                created = datetime.fromisoformat(a["created_at"])
            except (ValueError, TypeError):
                continue
            age_days = (now - created).total_seconds() / 86400
            strength = abs(a.get("valence", 0.0))
            # 陈旧 + 微弱 → 遗忘；强烈的情绪保留更久（阈值随强度放宽）
            effective_limit = self.forget_after_days * (1 + strength * 3)
            if age_days > effective_limit and strength < self.weak_threshold:
                self._delete_anchor(a["id"])
                forgotten += 1
        if forgotten:
            logger.info("Forgot {} stale emotion anchor(s) for {}", forgotten, session_key)
        return forgotten

    def _all_anchors_with_id(self, session_key: str) -> list[dict]:
        cur = self.memory._conn.cursor()
        cur.execute(
            "SELECT id, event, emotion, trigger, valence, created_at "
            "FROM emotion_anchors WHERE session_key = ?",
            (session_key,),
        )
        return [dict(r) for r in cur.fetchall()]

    def _delete_anchor(self, anchor_id: int) -> None:
        cur = self.memory._conn.cursor()
        cur.execute("DELETE FROM emotion_anchors WHERE id = ?", (anchor_id,))
        self.memory._conn.commit()
