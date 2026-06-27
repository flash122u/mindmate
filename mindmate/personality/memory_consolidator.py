"""记忆整合 —— 把超出上下文窗口的旧对话沉淀为长期记忆.

对话历史在 SQLite 里是完整、不可篡改的客观日志层。
但注入 LLM 的上下文只取最近 N 轮。更久远的对话需要"沉淀"成摘要，
写入 MEMORY.md（主观长期记忆层），这样小暖才记得住"很久以前的事"。

触发：当某 session 的历史轮数超过阈值时，把窗口之外的旧对话总结进 MEMORY.md。
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from mindmate.memory import MemoryStore

_SUMMARIZE_PROMPT = """把下面这段较早的对话，浓缩成几条「你（小暖）记住的事」。
用第一人称、口语化，关注对方是个怎样的人、你们聊过什么重要的事、ta 的状态。
每条一行，简短。只返回这些记忆条目，不要额外说明。

对话：
"""


class MemoryConsolidator:
    """长期记忆整合器."""

    def __init__(
        self,
        memory: MemoryStore,
        provider: Any = None,
        keep_recent_turns: int = 20,
        trigger_total_turns: int = 40,
    ) -> None:
        """
        Args:
            keep_recent_turns: 保留在上下文窗口内的最近轮数
            trigger_total_turns: 历史总轮数超过此值才触发整合
        """
        self.memory = memory
        self.provider = provider
        self.keep_recent_turns = keep_recent_turns
        self.trigger_total_turns = trigger_total_turns
        # 已整合到的 cursor 位置（每 session）
        self._consolidated_cursor: dict[str, int] = {}

    async def maybe_consolidate(self, session_key: str = "default") -> bool:
        """必要时把旧对话整合进 MEMORY.md，返回是否执行了整合."""
        if self.provider is None:
            return False

        all_history = self.memory.read_history(session_key, limit=100000)
        if len(all_history) < self.trigger_total_turns:
            return False

        last_cursor = self._consolidated_cursor.get(session_key, 0)
        # 取「窗口之外、且尚未整合过」的旧对话
        cutoff = len(all_history) - self.keep_recent_turns
        to_consolidate = [
            h for h in all_history[:cutoff] if h["cursor"] > last_cursor
        ]
        if len(to_consolidate) < 5:
            return False

        text = "\n".join(
            f"{'我' if h['role'] == 'assistant' else '对方'}: {h['content']}"
            for h in to_consolidate
        )
        try:
            resp = await self.provider.chat(
                messages=[{"role": "user", "content": _SUMMARIZE_PROMPT + text}],
                temperature=0.3,
            )
            summary = (resp["content"] or "").strip()
        except Exception:
            logger.exception("Memory consolidation failed")
            return False

        if not summary:
            return False

        # 追加到 MEMORY.md（长期主观记忆层）
        existing = self.memory.read_memory()
        from datetime import datetime
        stamp = datetime.now().strftime("%Y-%m-%d")
        new_block = f"\n### {stamp}\n{summary}\n"
        self.memory.write_memory(existing + new_block)

        self._consolidated_cursor[session_key] = to_consolidate[-1]["cursor"]
        logger.info(
            "Consolidated {} old turns into MEMORY.md for {}",
            len(to_consolidate), session_key,
        )
        return True
