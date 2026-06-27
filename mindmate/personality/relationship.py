"""关系阶段管理 — 关系随对话自然演进.

关系阶段：初识 → 朋友 → 信赖

演进由对话的情感倾向和互动次数共同驱动，而非用户手动设置。
关系阶段影响 Agent 的亲密程度、自我暴露意愿和回复风格。
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from mindmate.memory import MemoryStore


# 每个阶段晋级所需的"亲密度积分"
STAGE_THRESHOLDS = {
    "初识": 0,
    "朋友": 20,
    "信赖": 60,
}

# 各阶段的回复风格指引
STAGE_STYLES = {
    "初识": "你们刚认识不久，保持礼貌和适度的距离感，不会太热络，也不会主动分享私事。",
    "朋友": "你们已经是朋友了，说话更随意自然，会开玩笑，偶尔分享一些自己的日常。",
    "信赖": "你非常信任对方，愿意分享内心深处的感受，偶尔会不经意吐露日记或梦境的片段。",
}

# 正面/负面情感信号词（简易情感判断）
POSITIVE_WORDS = [
    "谢谢", "喜欢", "开心", "温暖", "陪", "想你", "信任", "懂我",
    "舒服", "安心", "感动", "哈哈", "嘻嘻", "❤", "😊", "抱抱",
]
NEGATIVE_WORDS = [
    "讨厌", "烦", "滚", "闭嘴", "无聊", "敷衍", "假", "骗",
    "失望", "不想理", "别烦我",
]


@dataclass
class RelationshipState:
    """关系状态快照."""
    stage: str
    score: int
    style_hint: str


class RelationshipManager:
    """
    关系阶段管理器.

    每次对话后调用 update()，根据情感倾向调整亲密度积分，
    达到阈值则晋级关系阶段。
    """

    def __init__(self, memory: MemoryStore | None = None) -> None:
        self.memory = memory or MemoryStore()
        # 内存中的亲密度积分缓存（持久化简化版，可后续落库）
        self._scores: dict[str, int] = {}

    def get_state(self, session_key: str = "default") -> RelationshipState:
        """获取当前关系状态."""
        rel = self.memory.get_relationship(session_key)
        stage = rel["stage"]
        score = self._scores.get(session_key, STAGE_THRESHOLDS.get(stage, 0))
        return RelationshipState(
            stage=stage,
            score=score,
            style_hint=STAGE_STYLES.get(stage, ""),
        )

    def score_message(self, message: str) -> int:
        """对单条用户消息评分（情感倾向）.

        返回值：正数表示正面互动，负数表示负面互动。
        """
        text = message.strip()
        score = 0
        for w in POSITIVE_WORDS:
            if w in text:
                score += 2
        for w in NEGATIVE_WORDS:
            if w in text:
                score -= 3
        # 任何正常对话都有微小的熟悉度增长
        if len(text) > 2:
            score += 1
        return score

    def update(self, message: str, session_key: str = "default") -> RelationshipState:
        """根据用户消息更新关系，必要时晋级/降级阶段."""
        current = self.get_state(session_key)
        delta = self.score_message(message)
        new_score = max(0, current.score + delta)
        self._scores[session_key] = new_score

        # 判断是否需要晋级或降级
        new_stage = self._stage_for_score(new_score)
        if new_stage != current.stage:
            logger.info(
                "Relationship {} -> {} (score={})",
                current.stage, new_stage, new_score,
            )
            self.memory.update_relationship_stage(session_key, new_stage)

        return RelationshipState(
            stage=new_stage,
            score=new_score,
            style_hint=STAGE_STYLES.get(new_stage, ""),
        )

    def _stage_for_score(self, score: int) -> str:
        """根据积分确定关系阶段."""
        stage = "初识"
        for name, threshold in sorted(STAGE_THRESHOLDS.items(), key=lambda x: x[1]):
            if score >= threshold:
                stage = name
        return stage

    def build_relationship_prompt(self, session_key: str = "default") -> str:
        """生成注入 system prompt 的关系指引."""
        state = self.get_state(session_key)
        return (
            f"## 你们的关系\n"
            f"当前关系阶段：**{state.stage}**\n"
            f"{state.style_hint}"
        )
