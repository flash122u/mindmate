"""遗忘 Agent — 模糊主观记忆层.

真实的人会遗忘和扭曲记忆。遗忘 Agent 定期执行:

1. 模糊精确事实: "2025年6月20日下午3点在星巴克" → "有一次在咖啡馆"
2. 弱化情绪锚点: 降低旧锚点的 valence 绝对值
3. 移除矛盾记忆: 检测并解决冲突的记忆
4. 老化: 陈旧记忆逐渐衰减直至可移除
"""

from __future__ import annotations

import datetime
import random
from typing import Any

from loguru import logger

from mindmate.memory import MemoryStore


class ForgetAgent:
    """
    遗忘 Agent — 记忆模糊与衰减.

    规则:
    - 7天前的锚点: valence 绝对值减少 0.1/天
    - 14天前的锚点: 触发词模糊化（"那天"）
    - 30天前的锚点: 进入"褪色"状态，有概率被清理
    - 冲突记忆: 保留时间较近的，移除较远的
    """

    def __init__(self, memory: MemoryStore | None = None) -> None:
        self.memory = memory or MemoryStore()

    async def run_forget_cycle(self, session_key: str = "default") -> dict[str, Any]:
        """
        执行一次遗忘周期.

        Returns:
            dict: {faded: int, removed: int, aged: int}
        """
        result = {
            "faded": await self._fade_old_anchors(session_key),
            "removed": await self._remove_expired(session_key),
            "aged": await self._fuzzy_memory(session_key),
        }
        logger.debug("Forget: %s", result)
        return result

    async def _fade_old_anchors(self, session_key: str = "default") -> int:
        """
        衰减旧锚点的情感强度.

        SQL: 对 7 天前的锚点，valence 向 0 衰减 0.1.
        """
        cur = self.memory._conn.cursor()
        # 衰减 7-14 天前的锚点
        cur.execute(
            "UPDATE emotion_anchors SET valence = valence * 0.8 "
            "WHERE session_key = ? AND created_at < datetime('now', '-7 days') "
            "AND created_at >= datetime('now', '-14 days')",
            (session_key,),
        )
        faded = cur.rowcount

        # 衰减 14-30 天前的锚点（更大幅度）
        cur.execute(
            "UPDATE emotion_anchors SET valence = valence * 0.5 "
            "WHERE session_key = ? AND created_at < datetime('now', '-14 days') "
            "AND created_at >= datetime('now', '-30 days')",
            (session_key,),
        )
        faded += cur.rowcount

        self.memory._conn.commit()
        return faded

    async def _remove_expired(self, session_key: str = "default") -> int:
        """
        移除 30 天前的旧锚点.

        只保留 valence 绝对值仍然 >= 0.5 的。
        """
        cur = self.memory._conn.cursor()
        cur.execute(
            "DELETE FROM emotion_anchors WHERE session_key = ? "
            "AND created_at < datetime('now', '-30 days') "
            "AND ABS(valence) < 0.5",
            (session_key,),
        )
        removed = cur.rowcount
        self.memory._conn.commit()
        return removed

    async def _fuzzy_memory(self, session_key: str = "default") -> int:
        """
        模糊化陈旧记忆的 event 和 trigger 字段.

        14 天前的锚点，event 和 trigger 替换为模糊描述。
        """
        cur = self.memory._conn.cursor()
        cur.execute(
            "SELECT id, event, trigger FROM emotion_anchors "
            "WHERE session_key = ? AND created_at < datetime('now', '-14 days')",
            (session_key,),
        )
        rows = cur.fetchall()

        aged = 0
        for row in rows:
            new_event = self._fuzzy_text(row["event"])
            new_trigger = self._fuzzy_text(row["trigger"]) if row["trigger"] else None
            cur.execute(
                "UPDATE emotion_anchors SET event = ?, trigger = ? WHERE id = ?",
                (new_event, new_trigger, row["id"]),
            )
            aged += 1

        self.memory._conn.commit()
        return aged

    def _fuzzy_text(self, text: str) -> str:
        """模糊化一段文本."""
        import re

        # 去掉具体日期
        text = re.sub(r"\d{4}年\d{1,2}月\d{1,2}日", "某天", text)
        text = re.sub(r"\d{1,2}月\d{1,2}日", "某天", text)

        # 去掉具体时间
        text = re.sub(r"([上中下]午)?\d{1,2}:\d{2}", "", text)

        # 去掉具体地点（简单规则：包含"在X"的）
        text = re.sub(r"在[^，。,]+", "在某个地方", text)

        # 如果处理后的文本太短，使用通用模糊描述
        if len(text) < 4:
            return "有件小事"

        return text.strip()
