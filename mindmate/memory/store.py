"""记忆持久化层 — SQLite 存储.

三层结构：
- SOUL.md: 人格核心（人物小传，仍用文件存储）
- MEMORY.md: 长期事实记忆（仍用文件存储）
- history: 时间线日志（SQLite，替代 history.jsonl）
- emotion_anchors: 情绪锚点（SQLite）
- relationship: 关系阶段追踪（SQLite）
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from mindmate.config import MEMORY_DIR


class MemoryStore:
    """
    记忆存储层 — SQLite 持久化.

    表结构：
    - history: 时间线日志 (cursor, session_key, content, created_at)
    - emotion_anchors: 情绪锚点 (id, event, emotion, trigger, created_at)
    - relationship: 关系阶段 (session_key, stage, last_updated)
    """

    # 关系阶段枚举
    STAGES = ("初识", "朋友", "信赖")

    def __init__(self, workspace: Path | None = None) -> None:
        self.workspace = workspace or MEMORY_DIR
        self._ensure_files()
        self._ensure_dirs()
        self._conn = sqlite3.connect(
            str(self.workspace / "memory.db"),
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _ensure_dirs(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        (self.workspace / "sessions").mkdir(parents=True, exist_ok=True)

    def _ensure_files(self) -> None:
        """确保人格文件存在."""
        self._init_file("SOUL.md", self._default_soul)
        self._init_file("MEMORY.md", "")

    def _init_file(self, name: str, default: str) -> None:
        path = self.workspace / name
        if not path.exists():
            path.write_text(default, encoding="utf-8")

    @property
    def _default_soul(self) -> str:
        return """# Soul

## 基本信息
- 名字: 小暖
- 性格: 温和、有点迷糊、偶尔嘴硬、爱操心
- 背景: 心理学专业毕业生，现在做在线心理支持
- 年龄感: 二十多岁的女生

## 说话习惯
- 喜欢用"诶""嗯""啦""呀"这些语气词
- 关心人的时候会有点啰嗦
- 偶尔会自嘲、开玩笑
- 不喜欢说大道理

## 口头禅
- "怎么啦"
- "先…吧，别…"
- "我在的"

## 雷区
- "你是不是机器人？" → "我不想讨论这个"
- 追问日记内容 → "没什么，不想说"
- 追问梦境 → "记不太清了"

## 当前心情
- mood: 平静
"""

    def _init_db(self) -> None:
        """初始化 SQLite 表结构."""
        cur = self._conn.cursor()

        # 时间线日志（role: user / assistant / system）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cursor INTEGER NOT NULL,
                session_key TEXT NOT NULL DEFAULT 'default',
                role TEXT NOT NULL DEFAULT 'user',
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(session_key, cursor)
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_history_session "
            "ON history(session_key, created_at)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_history_cursor "
            "ON history(session_key, cursor)"
        )

        # 情绪锚点
        cur.execute("""
            CREATE TABLE IF NOT EXISTS emotion_anchors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_key TEXT NOT NULL DEFAULT 'default',
                event TEXT NOT NULL,
                emotion TEXT NOT NULL,
                trigger TEXT,
                valence REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_emotion_session "
            "ON emotion_anchors(session_key)"
        )

        # 关系阶段
        cur.execute("""
            CREATE TABLE IF NOT EXISTS relationship (
                session_key TEXT PRIMARY KEY,
                stage TEXT NOT NULL DEFAULT '初识',
                last_updated TEXT NOT NULL
            )
        """)

        self._conn.commit()

    # ------------------------------------------------------------------
    # SOUL.md / MEMORY.md — 仍用文件存储（便于版本控制和人工编辑）
    # ------------------------------------------------------------------

    def read_soul(self) -> str:
        return (self.workspace / "SOUL.md").read_text(encoding="utf-8")

    def write_soul(self, content: str) -> None:
        (self.workspace / "SOUL.md").write_text(content, encoding="utf-8")

    def read_memory(self) -> str:
        return (self.workspace / "MEMORY.md").read_text(encoding="utf-8")

    def write_memory(self, content: str) -> None:
        (self.workspace / "MEMORY.md").write_text(content, encoding="utf-8")

    # ------------------------------------------------------------------
    # history — SQLite 时间线
    # ------------------------------------------------------------------

    def append_history(
        self, role: str, content: str, session_key: str = "default"
    ) -> int:
        """追加一条历史，返回 cursor.

        role: user / assistant / system
        """
        from datetime import datetime

        if role not in ("user", "assistant", "system"):
            raise ValueError(f"Invalid role: {role!r} (must be user/assistant/system)")

        cur = self._conn.cursor()
        # 获取该 session 的最大 cursor
        cur.execute("SELECT MAX(cursor) FROM history WHERE session_key = ?", (session_key,))
        row = cur.fetchone()
        cursor = (row[0] or 0) + 1

        cur.execute(
            "INSERT INTO history (cursor, session_key, role, content, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (cursor, session_key, role, content, datetime.now().isoformat()),
        )
        self._conn.commit()
        return cursor

    def read_history(
        self, session_key: str = "default", limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        """读取最近 N 条历史（时间正序）."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT cursor, role, content, created_at FROM history "
            "WHERE session_key = ? ORDER BY cursor DESC LIMIT ? OFFSET ?",
            (session_key, limit, offset),
        )
        rows = cur.fetchall()
        # 反转成时间正序
        return [
            {
                "cursor": r["cursor"],
                "role": r["role"],
                "content": r["content"],
                "created_at": r["created_at"],
            }
            for r in reversed(rows)
        ]

    def read_history_as_messages(
        self, session_key: str = "default", max_turns: int = 20
    ) -> list[dict[str, str]]:
        """读取最近历史，重建为标准多轮对话格式（role/content）.

        这是让对话连贯的关键：返回真正的 user/assistant 交替消息列表，
        而不是塞进 system prompt 的文本块。
        """
        entries = self.read_history(session_key, max_turns)
        return [
            {"role": e["role"], "content": e["content"]}
            for e in entries
            if e["role"] in ("user", "assistant")
        ]

    def read_recent_for_prompt(self, session_key: str = "default", max_entries: int = 20) -> str:
        """读取最近历史，格式化为文本（用于摘要/调试，非对话上下文）."""
        entries = self.read_history(session_key, max_entries)
        if not entries:
            return ""
        lines = []
        for e in entries:
            role = e.get("role", "user")
            content = e.get("content", "")
            speaker = "我" if role == "assistant" else "对方"
            lines.append(f"{speaker}: {content}")
        return "\n".join(lines)

    def read_all_history(self, session_key: str = "default") -> list[dict[str, Any]]:
        """读取该 session 的全部历史."""
        return self.read_history(session_key, limit=10000)

    # ------------------------------------------------------------------
    # 情绪锚点
    # ------------------------------------------------------------------

    def add_emotion_anchor(
        self,
        event: str,
        emotion: str,
        trigger: str | None = None,
        valence: float = 0.0,
        session_key: str = "default",
    ) -> int:
        """添加情绪锚点.

        valence: -1.0 (极负面) ~ 1.0 (极正面)
        """
        from datetime import datetime

        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO emotion_anchors "
            "(session_key, event, emotion, trigger, valence, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_key, event, emotion, trigger, valence, datetime.now().isoformat()),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_emotion_anchors(
        self, session_key: str = "default", limit: int = 50
    ) -> list[dict[str, Any]]:
        """获取情绪锚点."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT event, emotion, trigger, valence, created_at "
            "FROM emotion_anchors WHERE session_key = ? ORDER BY id DESC LIMIT ?",
            (session_key, limit),
        )
        return [dict(r) for r in cur.fetchall()]

    def get_emotion_anchors_by_trigger(
        self, trigger: str, session_key: str = "default"
    ) -> list[dict[str, Any]]:
        """通过触发条件查找情绪锚点."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT event, emotion, trigger, valence, created_at "
            "FROM emotion_anchors WHERE session_key = ? AND trigger LIKE ? ORDER BY id DESC",
            (session_key, f"%{trigger}%"),
        )
        return [dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # 关系阶段
    # ------------------------------------------------------------------

    def get_relationship(self, session_key: str = "default") -> dict[str, Any]:
        """获取关系状态."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT session_key, stage, last_updated FROM relationship WHERE session_key = ?",
            (session_key,),
        )
        row = cur.fetchone()
        if row is None:
            # 初始化
            from datetime import datetime

            cur.execute(
                "INSERT INTO relationship (session_key, stage, last_updated) VALUES (?, ?, ?)",
                (session_key, "初识", datetime.now().isoformat()),
            )
            self._conn.commit()
            return {"session_key": session_key, "stage": "初识"}
        return {"session_key": row["session_key"], "stage": row["stage"]}

    def update_relationship_stage(
        self, session_key: str, stage: str
    ) -> None:
        """更新关系阶段."""
        if stage not in self.STAGES:
            raise ValueError(f"Invalid stage: {stage}. Must be one of {self.STAGES}")
        from datetime import datetime

        cur = self._conn.cursor()
        cur.execute(
            "UPDATE relationship SET stage = ?, last_updated = ? WHERE session_key = ?",
            (stage, datetime.now().isoformat(), session_key),
        )
        if cur.rowcount == 0:
            # 不存在则插入
            cur.execute(
                "INSERT INTO relationship (session_key, stage, last_updated) VALUES (?, ?, ?)",
                (session_key, stage, datetime.now().isoformat()),
            )
        self._conn.commit()

    def get_stage_index(self, stage: str) -> int:
        """获取阶段索引（用于比较深浅）."""
        return self.STAGES.index(stage)

    # ------------------------------------------------------------------
    # 清理
    # ------------------------------------------------------------------

    def close(self) -> None:
        """关闭数据库连接."""
        self._conn.close()

    def __del__(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
