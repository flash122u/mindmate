"""记忆整合器 — 将历史对话整合为结构化记忆.

借鉴 Akashic-Agent 的三层记忆概念，在 Agent 空闲时执行:

1. 从最近对话中提取情绪锚点
2. 更新 MEMORY.md 中的长期事实
3. 清理过期或冲突的记忆
"""

from __future__ import annotations

import re
from typing import Any

from mindmate.memory import MemoryStore
from mindmate.personality.emotion_anchor import EmotionAnchorManager


class MemoryConsolidator:
    """
    记忆整合器 — 空闲时执行记忆整合任务.

    整合任务:
    - extract_anchors: 从最近历史提取情绪锚点
    - update_long_term: 更新 MEMORY.md 中的长期事实
    - prune_memory: 清理过期锚点
    """

    def __init__(
        self,
        memory: MemoryStore | None = None,
        anchor_manager: EmotionAnchorManager | None = None,
    ) -> None:
        self.memory = memory or MemoryStore()
        self.anchors = anchor_manager or EmotionAnchorManager(self.memory)

    async def consolidate(self, session_key: str = "default") -> dict[str, Any]:
        """
        执行一次完整的记忆整合.

        Returns:
            dict: {extracted: int, long_term_updated: bool, pruned: int}
        """
        result = {
            "extracted": await self._extract_anchors_from_history(session_key),
            "long_term_updated": await self._update_long_term_memory(session_key),
            "pruned": await self._prune_old_anchors(session_key),
        }
        return result

    async def _extract_anchors_from_history(
        self, session_key: str = "default"
    ) -> int:
        """从最近 50 条历史中提取情绪锚点."""
        entries = self.memory.read_history(session_key, limit=50)
        if not entries:
            return 0

        count = 0
        for i in range(0, len(entries) - 1, 2):
            user_entry = entries[i]
            asst_entry = entries[i + 1] if i + 1 < len(entries) else None

            # 只处理 user→assistant 对
            if not user_entry.get("content", "").startswith(("[user]", "[User]")):
                continue

            user_text = user_entry["content"]
            asst_text = asst_entry["content"] if asst_entry else ""

            anchor = self.anchors.extract_from_messages(
                user_text, asst_text, session_key,
            )
            if anchor:
                # 检查是否已存在相似的锚点（去重）
                existing = self.memory.get_emotion_anchors(session_key, limit=50)
                is_new = True
                for ex in existing:
                    if ex.get("event") == anchor["event"]:
                        is_new = False
                        break
                if is_new:
                    self.memory.add_emotion_anchor(
                        event=anchor["event"],
                        emotion=anchor["emotion"],
                        trigger=anchor["trigger"],
                        valence=anchor["valence"],
                        session_key=session_key,
                    )
                    count += 1

        return count

    async def _update_long_term_memory(self, session_key: str = "default") -> bool:
        """从锚点中提取重要信息更新 MEMORY.md."""
        anchors = self.memory.get_emotion_anchors(session_key, limit=20)
        if not anchors:
            return False

        # 提取强情绪锚点 (|valence| >= 0.5)
        strong = [a for a in anchors if abs(a.get("valence", 0)) >= 0.5]
        if not strong:
            return False

        # 构建记忆行
        lines = []
        for a in strong[:10]:
            v_text = "正面" if a["valence"] > 0 else "负面"
            lines.append(f"- {a['event']} ({a['emotion']}, {v_text})")

        memory_content = self.memory.read_memory()
        marker = f"## {session_key} 记忆"
        new_section = f"{marker}\n{chr(10).join(lines)}"

        if marker in memory_content:
            # 替换旧内容
            memory_content = re.sub(
                rf"{marker}.*?(?=\n## |\Z)",
                new_section,
                memory_content,
                flags=re.DOTALL,
            )
        else:
            memory_content = f"{memory_content}\n\n{new_section}"

        self.memory.write_memory(memory_content)
        return True

    async def _prune_old_anchors(self, session_key: str = "default") -> int:
        """清理 7 天前的旧锚点."""
        cur = self.memory._conn.cursor()
        cur.execute(
            "DELETE FROM emotion_anchors WHERE session_key = ? "
            "AND created_at < datetime('now', '-7 days')",
            (session_key,),
        )
        deleted = cur.rowcount
        self.memory._conn.commit()
        return deleted
