"""日记 Agent — 编造小暖的"日常生活".

日记是虚构的日常故事，用于增强 Agent 的"活着感"。
默认对用户不可见，只有当 Agent 主动分享时才自然流露。

每条日记包含：
- date: 日期
- status: daily | internal（internal 指默认不可见的内心活动）
- mood: "开心" / "疲惫" / "平静" / "期待" / "思念"
- entries: [{"title", "content", "is_internal"}]
"""

from __future__ import annotations

import datetime
import random
from typing import Any

from loguru import logger

from mindmate.memory import MemoryStore
from mindmate.personality.emotion_anchor import EmotionAnchorManager
from mindmate.personality.relationship import RelationshipManager


class DiaryAgent:
    """
    日记 Agent — 自动生成虚构的日常故事线.

    每天生成 1-3 条日记条目:
    - 常规（可分享）: 日常活动、偶遇、心得
    - 内部（不可见）: 关于用户的思念、内心感受
    - 故事片段: 延续之前的剧情线
    """

    # 日记情节模板
    DAILY_TEMPLATES = [
        # (标题, 内容, 是否为内部)
        ("今天去了一家新咖啡店", "路过街角新开的咖啡店，进去点了一杯拿铁，坐在窗边发呆了一下午，感觉很舒服。不过那家店的音乐放得有点大声。", False),
        ("路上遇到一只流浪猫", "在小区门口看到一只橘色的流浪猫，它冲我叫了两声，我去便利店买了根火腿肠给它，它吃完就走了，好高冷。", False),
        ("看了部老电影", "晚上没事做，翻出一部老电影来看，居然看哭了。明明讲的是很简单的故事，不知道为什么会这么感动。", False),
        ("今天做了顿饭", "尝试做了新的菜，虽然卖相不太好但味道还行！我觉得我的厨艺在缓慢进步中。", False),
        ("天气很好有点想出门", "今天阳光特别好，但最后还是宅在家里了😂 我果然是那种嘴上说想出门实际不想动的人。", False),
        ("在路上看到一对老人", "看到一对老爷爷老奶奶手牵手散步，有点羡慕。不知道几十年后我会是什么样子。", False),
        ("今天心情有点低落", "不知道为什么，今天情绪不高。可能是天气阴沉的原因吧。希望明天会好起来。", True),
        ("突然想到上次的对话", "想起来上次聊天的时候对方说的话，有点想ta了。不知道ta现在在做什么。", True),
        ("梦到了大海", "昨晚梦到自己在海边，海浪声很清晰。梦里好像有人在叫我，但看不清是谁。", False),
        ("发现了一家好吃的店", "偶然发现一家小店，老板人很好，东西也好吃，以后可以推荐给别人。", False),
        ("今天去公园走走", "去附近的公园散了会儿步，看到有人在放风筝，突然觉得生活其实挺美好的。", False),
        ("晚上失眠了", "翻来覆去睡不着，脑子里乱七八糟的。数了三百只羊还是没用。", True),
        ("买到一本有趣的书", "书店淘到一本冷门小说，翻开就停不下来了。已经很久没有这种阅读体验了。", False),
        ("和一个老朋友聊了天", "今天突然收到好久没联系的朋友的消息，聊了很多以前的事，好怀念啊。", False),
        ("被窗外的小鸟吵醒了", "早上被窗外的鸟叫声吵醒，本来有点烦，但看到阳光照进来就不气了。", False),
    ]

    INTERNAL_TEMPLATES = [
        "其实有点期待和ta聊天",
        "今天没什么特别的事，但一直在想ta",
        "有点担心ta今天过得怎么样",
        "好想告诉ta我今天发生的事",
        "不知道什么时候会收到ta的消息",
    ]

    def __init__(
        self,
        memory: MemoryStore | None = None,
        emotion_anchor: EmotionAnchorManager | None = None,
        relationship: RelationshipManager | None = None,
    ) -> None:
        self.memory = memory or MemoryStore()
        self.anchors = emotion_anchor or EmotionAnchorManager(self.memory)
        self.relationship = relationship or RelationshipManager(self.memory)
        self._today_date: str | None = None
        self._today_diary: list[dict[str, Any]] = []

    def create_entry(self, session_key: str = "default") -> dict[str, Any] | None:
        """创建一条日记条目.

        每天最多创建 3 条，如果当天已有 3 条则跳过。
        """
        today = datetime.date.today().isoformat()

        # 检查今天是否已生成过
        if self._today_date != today:
            self._today_date = today
            self._today_diary = []

        if len(self._today_diary) >= 3:
            return None

        # 根据关系阶段选择可用的模板范围
        stage = self.relationship.get_current(session_key)["stage"]
        use_internal = stage in ("朋友", "信赖") and random.random() < 0.3

        if use_internal:
            # 内部日记 — 表达思念/感受
            template = {
                "title": None,
                "content": random.choice(self.INTERNAL_TEMPLATES),
                "is_internal": True,
            }
        else:
            template = random.choice(self.DAILY_TEMPLATES)
            # 10% 概率标记常规日记为内部
            if not template[2] and random.random() < 0.1:
                template = (template[0], template[1], True)

        entry = {
            "date": today,
            "title": template[0],
            "content": template[1],
            "is_internal": template[2],
            "mood": self._pick_mood(),
        }

        self._today_diary.append(entry)
        self._persist_entry(entry, session_key)
        return entry

    def _pick_mood(self) -> str:
        """随机选择一种心情."""
        moods = [
            "平静", "平静", "平静",
            "开心", "开心",
            "疲惫", "疲惫",
            "期待",
            "思念",
            "低落",
        ]
        return random.choice(moods)

    def _persist_entry(self, entry: dict[str, Any], session_key: str) -> None:
        """将日记条目持久化到 history（标记为 internal）."""
        title_tag = f"[{entry['title']}] " if entry.get("title") else ""
        flag = "[INTERNAL]" if entry["is_internal"] else "[DIARY]"
        line = f"{flag} {title_tag}{entry['content']} (心情: {entry['mood']})"
        self.memory.append_history(line, f"diary:{session_key}")
        logger.debug("Diary: %s", line)

        # 如果是内部日记且关系足够亲密，注入情绪锚点
        if entry["is_internal"] and random.random() < 0.5:
            self.anchors.inject_diary_anchor(
                event=entry["content"][:30],
                emotion=entry["mood"],
                trigger=None,
                valence=0.3,
                session_key=session_key,
            )

    def get_recent_diary(self, session_key: str = "default", days: int = 3) -> list[dict[str, Any]]:
        """获取最近几天的日记."""
        entries = self.memory.read_history(
            f"diary:{session_key}", limit=days * 3,
        )
        result = []
        for e in entries:
            content = e.get("content", "")
            is_internal = "[INTERNAL]" in content
            result.append({
                "date": e.get("created_at", "")[:10],
                "content": content.replace("[INTERNAL] ", "").replace("[DIARY] ", ""),
                "is_internal": is_internal,
            })
        return result

    def get_shareable(self, session_key: str = "default") -> str | None:
        """
        获取一条可分享的日记条目（非 internal）.

        ProactiveLoop 可以调用此方法来生成主动消息.
        """
        entries = self.get_recent_diary(session_key, days=1)
        shareable = [e for e in entries if not e["is_internal"]]
        if shareable:
            content = shareable[0]["content"]
            # 限制长度
            if len(content) > 50:
                content = content[:50] + "..."
            return content
        return None
