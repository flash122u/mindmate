"""关系阶段管理.

跟踪 Agent 与用户的关系深度，影响对话风格和亲密程度.
关系随时间和互动质量自动演进.
"""

from __future__ import annotations

from typing import Any

from mindmate.memory import MemoryStore


class RelationshipManager:
    """
    关系管理器 — 动态演进的关系阶段.

    三个阶段:
    - 初识: 礼貌、保持距离、称呼"你"
    - 朋友: 放松、偶尔开玩笑、可以分享个人故事
    - 信赖: 亲近、主动关心、会用昵称

    演进规则:
    - 初识 → 朋友: 连续 3 次正向互动（valence > 0.3）
    - 朋友 → 信赖: 连续 5 次正向互动 + 互动次数 > 10
    - 退缩: 连续 2 次负向互动（valence < -0.3）→ 降一级
    """

    STAGES = ("初识", "朋友", "信赖")

    # 各阶段的对话风格
    STYLES = {
        "初识": {
            "tone": "礼貌、稍显拘谨",
            "address": "你",
            "nicknames": [],
            "self_disclosure": "低（只分享表面信息）",
            "warmth": 0.3,
        },
        "朋友": {
            "tone": "轻松、自然",
            "address": "你",
            "nicknames": ["亲爱的"],
            "self_disclosure": "中（可以分享个人故事）",
            "warmth": 0.6,
        },
        "信赖": {
            "tone": "亲密、坦诚",
            "address": "你",
            "nicknames": ["宝贝", "亲爱的", "宝"],
            "self_disclosure": "高（分享内心感受）",
            "warmth": 0.9,
        },
    }

    def __init__(self, memory: MemoryStore | None = None) -> None:
        self.memory = memory or MemoryStore()

    def get_current(self, session_key: str = "default") -> dict[str, Any]:
        """获取当前关系状态."""
        rel = self.memory.get_relationship(session_key)
        stage = rel.get("stage", "初识")
        style = self.STYLES.get(stage, self.STYLES["初识"])
        return {
            "stage": stage,
            "style": style,
            "session_key": session_key,
        }

    def on_user_message(self, session_key: str = "default") -> None:
        """用户发来消息时调用（记录互动计数）."""
        # 在 get_current 中自动初始化
        self.get_current(session_key)

    def record_interaction(self, valence: float, session_key: str = "default") -> str:
        """
        记录一次互动的情感倾向.

        Args:
            valence: 情感值 (-1.0 ~ 1.0)

        Returns:
            当前关系阶段
        """
        from datetime import datetime

        cur = self.memory._conn.cursor()
        cur.execute(
            "SELECT stage, last_updated FROM relationship WHERE session_key = ?",
            (session_key,),
        )
        row = cur.fetchone()

        if row is None:
            # 初始化
            cur.execute(
                "INSERT INTO relationship (session_key, stage, last_updated) VALUES (?, ?, ?)",
                (session_key, "初识", datetime.now().isoformat()),
            )
            self.memory._conn.commit()
            return "初识"

        stage = row["stage"]
        current_style = self.STYLES.get(stage, self.STYLES["初识"])
        current_idx = list(self.STAGES).index(stage)

        # 判断互动类型
        if valence > 0.3:
            # 正向互动
            self._advance_if_ready(cur, session_key, stage, current_idx, valence)
        elif valence < -0.3:
            # 负向互动 — 可能退缩
            self._retreat_if_ready(cur, session_key, stage, current_idx, valence)

        self.memory._conn.commit()
        return stage

    def _advance_if_ready(
        self, cur: Any, session_key: str, stage: str, idx: int, valence: float
    ) -> None:
        """检查是否可以推进关系.

        规则: 需要至少 3 次正向互动记录在 history 中（30 分钟内）才能推进.
        """
        if idx >= len(self.STAGES) - 1:
            return

        # 统计最近 30 分钟内该 session 的历史条目数
        cur.execute(
            "SELECT COUNT(*) FROM history WHERE session_key = ? "
            "AND created_at > datetime('now', '-30 minutes')",
            (session_key,),
        )
        recent_count = cur.fetchone()[0]

        # 需要至少 3 次正向互动
        if recent_count >= 3:
            next_stage = self.STAGES[idx + 1]
            from datetime import datetime
            cur.execute(
                "UPDATE relationship SET stage = ?, last_updated = ? WHERE session_key = ?",
                (next_stage, datetime.now().isoformat(), session_key),
            )

    def _retreat_if_ready(
        self, cur: Any, session_key: str, stage: str, idx: int, valence: float
    ) -> None:
        """检查是否可以退步 — 单次强负向即可."""
        if idx <= 0:
            return
        if valence <= -0.5:
            prev_stage = self.STAGES[idx - 1]
            from datetime import datetime
            cur.execute(
                "UPDATE relationship SET stage = ?, last_updated = ? WHERE session_key = ?",
                (prev_stage, datetime.now().isoformat(), session_key),
            )

    def get_style_instructions(self, session_key: str = "default") -> str:
        """获取当前关系的对话风格指令."""
        state = self.get_current(session_key)
        stage = state["stage"]
        style = state["style"]

        return (
            f"## 当前关系阶段: {stage}\n"
            f"- 你的语气: {style['tone']}\n"
            f"- 称呼对方: {style['address']}\n"
            f"- 可用的昵称: {', '.join(style['nicknames']) or '无'}\n"
            f"- 自我披露程度: {style['self_disclosure']}\n"
            f"- 亲密度: {style['warmth']:.0%}"
        )
