"""情绪锚点管理.

从对话中提取情绪锚点，用于增强 Agent 的记忆真实感.

情绪锚点 = {event, emotion, trigger, valence}

例如:
- {event: "聊到下雨天", emotion: "感到温暖", trigger: "下雨", valence: 0.7}
- {event: "用户提到加班", emotion: "有点心疼", trigger: "加班", valence: -0.3}

这些锚点会在 Agent 构建上下文时注入，让 LLM 产生"我记得那件事"的感觉.
"""

from __future__ import annotations

import re
from typing import Any

from mindmate.memory import MemoryStore


class EmotionAnchorManager:
    """
    情绪锚点管理器.

    职责:
    - 从对话中提取结构化锚点
    - 判断当前消息是否触发已有锚点
    - 生成可注入 LLM 上下文的锚点文本
    """

    def __init__(self, memory: MemoryStore | None = None) -> None:
        self.memory = memory or MemoryStore()

    def extract_from_messages(
        self,
        user_msg: str,
        assistant_reply: str,
        session_key: str = "default",
    ) -> dict[str, Any] | None:
        """
        从一次对话中提取情绪锚点.

        使用规则引擎（而非 LLM）做轻量级提取:
        - 检测情感关键词（高兴/难过/烦/开心/累/焦虑等）
        - 提取 trigger（助词后的名词）
        - 估算 valence (正面/负面强度)

        Returns:
            None: 无明显情绪锚点
            dict: {event, emotion, trigger, valence}
        """
        text = f"{user_msg} {assistant_reply}"

        # 情感词典
        emotions = {
            "高兴": {"keywords": ["高兴", "开心", "快乐", "哈哈", "好开心", "太棒了"], "valence": 0.6},
            "感动": {"keywords": ["感动", "温暖", "贴心", "哭了", "谢谢你"], "valence": 0.8},
            "难过": {"keywords": ["难过", "伤心", "哭", "不开心", "好难受"], "valence": -0.6},
            "焦虑": {"keywords": ["焦虑", "担心", "紧张", "怕", "烦"], "valence": -0.5},
            "疲惫": {"keywords": ["累", "疲惫", "不想动", "没精力", "困"], "valence": -0.4},
            "惊喜": {"keywords": ["惊喜", "没想到", "太意外了", "惊了"], "valence": 0.5},
            "无聊": {"keywords": ["无聊", "没意思", "想找点事"], "valence": -0.2},
            "安心": {"keywords": ["安心", "放心", "踏实", "安稳"], "valence": 0.4},
        }

        detected_emotion = None
        detected_valence = 0.0
        highest_confidence = 0

        for emotion, info in emotions.items():
            for kw in info["keywords"]:
                if kw in text:
                    score = len(kw)  # 关键词越长越可信
                    if score > highest_confidence:
                        highest_confidence = score
                        detected_emotion = emotion
                        detected_valence = info["valence"]
                    break  # 一个情感匹配了就不再检后面的关键词

        if detected_emotion is None:
            return None

        # 提取 trigger — 用户消息中的名词短语
        trigger = self._extract_trigger(user_msg, detected_emotion)

        # 构造事件描述
        event = self._build_event_description(user_msg, detected_emotion)

        return {
            "event": event,
            "emotion": detected_emotion,
            "trigger": trigger,
            "valence": detected_valence,
        }

    def _extract_trigger(self, user_msg: str, emotion: str) -> str | None:
        """从用户消息中提取触发词."""
        # 尝试 "关于X" / "X让我" / "提到X" 等模式
        for pattern in [
            r"关于(.{2,10})[的，,。；;]",
            r"提到(.{2,10})[的，,。；;]",
            r"(.{2,8})让我",
            r"(.{2,8})真是",
            r"(.{2,8})好",
        ]:
            m = re.search(pattern, user_msg)
            if m:
                return m.group(1).strip()
        # fallback: 取用户消息前 6 个字
        return user_msg[:8] if len(user_msg) > 4 else None

    def _build_event_description(self, user_msg: str, emotion: str) -> str:
        """构造事件描述."""
        if len(user_msg) > 20:
            return user_msg[:20] + "..."
        return user_msg

    # ------------------------------------------------------------------
    # 上下文注入
    # ------------------------------------------------------------------

    def get_anchor_context(
        self,
        user_message: str,
        session_key: str = "default",
        max_anchors: int = 5,
    ) -> str:
        """
        基于当前消息内容，查找匹配的情绪锚点，返回注入文本.

        匹配规则:
        - 用户消息中包含 anchor.trigger → 激活该锚点
        - 取最近 N 个匹配的锚点
        """
        anchors = self.memory.get_emotion_anchors(session_key, limit=100)
        if not anchors:
            return ""

        matched: list[dict[str, Any]] = []
        for anchor in anchors:
            trigger = anchor.get("trigger") or ""
            if trigger and trigger in user_message:
                matched.append(anchor)
                if len(matched) >= max_anchors:
                    break

        if not matched:
            # 没有精确匹配，取最近 2 个最强烈的情绪锚点
            sorted_anchors = sorted(
                anchors, key=lambda a: abs(a.get("valence", 0)), reverse=True
            )
            matched = sorted_anchors[:2]

        if not matched:
            return ""

        lines = []
        for a in matched:
            trigger_str = f" (触发: {a['trigger']})" if a.get("trigger") else ""
            lines.append(f"- {a['event']} → {a['emotion']}{trigger_str}")

        return f"## 我记得的\n{chr(10).join(lines)}"

    def inject_diary_anchor(
        self,
        event: str,
        emotion: str = "平静",
        trigger: str | None = None,
        valence: float = 0.0,
        session_key: str = "default",
    ) -> int:
        """
        注入一条 Diary/Diary Agent 生成的虚构记忆作为情绪锚点.

        这些锚点会让小暖在对话中提到"昨天在路上看到一只猫"之类的话.
        """
        return self.memory.add_emotion_anchor(
            event=event,
            emotion=emotion,
            trigger=trigger,
            valence=valence,
            session_key=session_key,
        )
