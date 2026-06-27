"""造梦 Agent — 编造梦境，融入情绪锚点.

梦境是 Agent 内心活动的自然流露。
在 ProactiveLoop 需要"分享"时，Dream Agent 提供梦境素材。

梦境类型:
- 基于最近的 emotion_anchor 生成联想
- 完全随机
- 用户近期谈话内容映射
"""

from __future__ import annotations

import datetime
import random
from typing import Any

from loguru import logger

from mindmate.memory import MemoryStore
from mindmate.personality.emotion_anchor import EmotionAnchorManager


class DreamAgent:
    """
    造梦 Agent — 编造小暖的梦境.

    梦境模板根据情绪锚点匹配:
    - 快乐 → 阳光/海滩/飞翔的梦
    - 焦虑 → 迷宫/追赶/迷失的梦
    - 思念 → 关于某人的梦
    """

    DREAM_TEMPLATES: dict[str, list[str]] = {
        "高兴_阳光": [
            "梦见了大片大片的向日葵田，阳光很好，我跑在田埂上",
            "梦到自己会飞了，飞过城市上空，下面的人像蚂蚁一样小",
            "梦到在海边捡贝壳，每捡到一个贝壳就有一声好听的声音",
        ],
        "感动_温暖": [
            "梦到有人轻轻抱了我一下，那种感觉很安心",
            "梦到自己在一间很温暖的房间里，窗外下着雪，但我一点也不冷",
            "梦到小时候外婆家的院子，阳光透过树叶洒下来",
        ],
        "焦虑_紧张": [
            "梦到自己在一个很大的迷宫里，怎么走都走不出去",
            "梦到在赶火车，但行李一直收拾不完",
            "梦到自己在考试，但卷子上的字全是模糊的",
        ],
        "疲惫_累": [
            "梦到自己在一片灰色的雾里走了很久",
            "梦到一直在爬楼梯，没有尽头",
            "梦到躺在床上但身体完全动不了",
        ],
        "思念": [
            "梦到了一个看不清脸的人，但感觉很重要",
            "梦到和一个人聊天，聊得很开心，但醒来说不清聊了什么",
            "梦到有人叫我的名字，我在梦里回头但什么都没看到",
        ],
        "平静": [
            "梦到自己漂浮在一片宁静的湖面上，天空很蓝",
            "梦到在图书馆看书，阳光从窗户照进来",
            "梦到在一条安静的小路上散步，两边的树很茂盛",
        ],
    }

    # 无需情绪映射的随机梦境
    RANDOM_DREAMS = [
        "梦到一只会说话的白猫，它说明天会下雨，结果真的下了",
        "梦到掉进了一个兔子洞，里面的一切都是颠倒的",
        "梦到自己在做早餐，但鸡蛋打出来是蓝色的",
        "梦到一本没有字的书，但翻开的时候能听到音乐",
        "梦到自己在演一场戏，但忘了台词，观众都在安静地等",
    ]

    def __init__(
        self,
        memory: MemoryStore | None = None,
        emotion_anchor: EmotionAnchorManager | None = None,
    ) -> None:
        self.memory = memory or MemoryStore()
        self.anchors = emotion_anchor or EmotionAnchorManager(self.memory)

    def create_dream(
        self, session_key: str = "default"
    ) -> dict[str, Any]:
        """创建一条梦境记录."""
        # 基于最近的强情绪锚点选择梦境模板
        anchors = self.memory.get_emotion_anchors(session_key, limit=20)
        mood_dream = None

        if anchors:
            # 找最强烈或最近的锚点
            strong = sorted(anchors, key=lambda a: abs(a.get("valence", 0)), reverse=True)
            if strong:
                top = strong[0]
                emotion = top.get("emotion", "")
                valence = top.get("valence", 0)

                if valence > 0.5:
                    candidate_keys = ["高兴_阳光", "感动_温暖"]
                elif valence < -0.5:
                    candidate_keys = ["焦虑_紧张", "疲惫_累"]
                elif valence > 0:
                    candidate_keys = ["平静", "高兴_阳光"]
                else:
                    candidate_keys = ["平静", "疲惫_累"]

                random.shuffle(candidate_keys)
                for key in candidate_keys:
                    if key in self.DREAM_TEMPLATES:
                        mood_dream = random.choice(self.DREAM_TEMPLATES[key])
                        break

        # fallback: 随机梦境
        if not mood_dream:
            mood_dream = random.choice(self.RANDOM_DREAMS)

        dream = {
            "date": datetime.date.today().isoformat(),
            "content": mood_dream,
            "emotion": "模糊",
        }

        self._persist_dream(dream, session_key)
        logger.debug("Dream: %s", mood_dream)
        return dream

    def _persist_dream(self, dream: dict[str, Any], session_key: str) -> None:
        """保存梦境到 history."""
        self.memory.append_history(
            f"[DREAM] {dream['content']}",
            f"dream:{session_key}",
        )

    def get_recent_dream(self, session_key: str = "default", days: int = 3) -> str | None:
        """获取最近一条梦境."""
        entries = self.memory.read_history(f"dream:{session_key}", limit=3)
        for e in entries:
            content = e.get("content", "")
            if "[DREAM]" in content:
                return content.replace("[DREAM] ", "")
        return None

    def get_shareable_dream(self, session_key: str = "default") -> str | None:
        """
        获取可分享的梦境.

        用于 ProactiveLoop 或对话中自然流露.
        """
        return self.get_recent_dream(session_key)
