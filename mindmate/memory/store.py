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

        # 私密日记（小暖的内在生活，默认不进对话上下文）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS diary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_key TEXT NOT NULL DEFAULT 'default',
                content TEXT NOT NULL,
                mood TEXT,
                shared INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)

        # 私密梦境
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dreams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_key TEXT NOT NULL DEFAULT 'default',
                content TEXT NOT NULL,
                tone TEXT,
                shared INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)

        # 风险预警（医生后台）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS crisis_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_key TEXT NOT NULL DEFAULT 'default',
                level TEXT NOT NULL,
                signal TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_alerts_session "
            "ON crisis_alerts(session_key, created_at)"
        )

        # Agent 运行轨迹（可观测性）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS agent_traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL UNIQUE,
                session_key TEXT NOT NULL DEFAULT 'default',
                message_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                steps_json TEXT NOT NULL DEFAULT '[]',
                total_elapsed_ms REAL
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_traces_session "
            "ON agent_traces(session_key, started_at DESC)"
        )

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
        self, session_key: str = "default", max_turns: int = 40
    ) -> list[dict[str, str]]:
        """读取最近历史，重建为标准多轮对话格式（role/content）.

        连贯性的关键。一条回复可能被拆成多条短消息分别存储（每段一行），
        这里把**连续同角色**的行合并回一条，使 LLM 看到的是完整的一轮，
        而前端按行展示则是分段气泡——两边各取所需。
        """
        entries = self.read_history(session_key, max_turns)
        merged: list[dict[str, str]] = []
        for e in entries:
            role = e["role"]
            if role not in ("user", "assistant"):
                continue
            if merged and merged[-1]["role"] == role:
                merged[-1]["content"] += e["content"]
            else:
                merged.append({"role": role, "content": e["content"]})
        return merged

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

    def list_sessions(self) -> list[str]:
        """返回所有有过对话的 session_key（去重），供调度器/后台遍历用户."""
        cur = self._conn.cursor()
        cur.execute("SELECT DISTINCT session_key FROM history ORDER BY session_key")
        return [r["session_key"] for r in cur.fetchall()]

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
    # 私密日记（小暖的内在生活）
    # ------------------------------------------------------------------

    def add_diary(
        self, content: str, mood: str | None = None, session_key: str = "default"
    ) -> int:
        """写一条私密日记."""
        from datetime import datetime

        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO diary (session_key, content, mood, created_at) "
            "VALUES (?, ?, ?, ?)",
            (session_key, content, mood, datetime.now().isoformat()),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_diaries(
        self, session_key: str = "default", limit: int = 30
    ) -> list[dict[str, Any]]:
        """读取私密日记（仅内部使用，不进对话上下文）."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, content, mood, shared, created_at FROM diary "
            "WHERE session_key = ? ORDER BY id DESC LIMIT ?",
            (session_key, limit),
        )
        return [dict(r) for r in cur.fetchall()]

    def mark_diary_shared(self, diary_id: int) -> None:
        cur = self._conn.cursor()
        cur.execute("UPDATE diary SET shared = 1 WHERE id = ?", (diary_id,))
        self._conn.commit()

    # ------------------------------------------------------------------
    # 私密梦境
    # ------------------------------------------------------------------

    def add_dream(
        self, content: str, tone: str | None = None, session_key: str = "default"
    ) -> int:
        """记录一个梦境."""
        from datetime import datetime

        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO dreams (session_key, content, tone, created_at) "
            "VALUES (?, ?, ?, ?)",
            (session_key, content, tone, datetime.now().isoformat()),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_dreams(
        self, session_key: str = "default", limit: int = 30
    ) -> list[dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, content, tone, shared, created_at FROM dreams "
            "WHERE session_key = ? ORDER BY id DESC LIMIT ?",
            (session_key, limit),
        )
        return [dict(r) for r in cur.fetchall()]

    def mark_dream_shared(self, dream_id: int) -> None:
        cur = self._conn.cursor()
        cur.execute("UPDATE dreams SET shared = 1 WHERE id = ?", (dream_id,))
        self._conn.commit()

    # ------------------------------------------------------------------
    # 风险预警（医生后台）
    # ------------------------------------------------------------------

    def add_crisis_alert(
        self, level: str, signal: str, message: str, session_key: str = "default"
    ) -> int:
        """记录一条风险预警."""
        from datetime import datetime

        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO crisis_alerts (session_key, level, signal, message, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_key, level, signal, message, datetime.now().isoformat()),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_crisis_alerts(
        self, session_key: str = "default", limit: int = 50
    ) -> list[dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT level, signal, message, created_at FROM crisis_alerts "
            "WHERE session_key = ? ORDER BY id DESC LIMIT ?",
            (session_key, limit),
        )
        return [dict(r) for r in cur.fetchall()]

    def get_emotion_trend(
        self, session_key: str = "default", limit: int = 100
    ) -> list[dict[str, Any]]:
        """情绪锚点的时间序列（valence over time），用于趋势图."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT event, emotion, valence, created_at FROM emotion_anchors "
            "WHERE session_key = ? ORDER BY id ASC LIMIT ?",
            (session_key, limit),
        )
        return [dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Agent 运行轨迹（可观测性）
    # ------------------------------------------------------------------

    def add_agent_trace(
        self,
        trace_id: str,
        session_key: str,
        message_id: str,
        started_at: str,
        completed_at: str,
        steps: list[dict[str, Any]],
        total_elapsed_ms: float,
    ) -> None:
        """写入一条 Agent 运行轨迹（steps 序列化为 JSON）."""
        import json

        cur = self._conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO agent_traces "
            "(trace_id, session_key, message_id, started_at, completed_at, "
            "steps_json, total_elapsed_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                trace_id,
                session_key,
                message_id,
                started_at,
                completed_at,
                json.dumps(steps, ensure_ascii=False),
                total_elapsed_ms,
            ),
        )
        self._conn.commit()

    def get_agent_traces(
        self, session_key: str = "default", limit: int = 20
    ) -> list[dict[str, Any]]:
        """获取最近 N 条 trace，steps 已从 JSON 解析."""
        import json

        cur = self._conn.cursor()
        cur.execute(
            "SELECT trace_id, session_key, message_id, started_at, completed_at, "
            "steps_json, total_elapsed_ms "
            "FROM agent_traces WHERE session_key = ? ORDER BY id DESC LIMIT ?",
            (session_key, limit),
        )
        results = []
        for row in cur.fetchall():
            d = dict(row)
            try:
                d["steps"] = json.loads(d.pop("steps_json"))
            except (json.JSONDecodeError, TypeError):
                d["steps"] = []
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # 上下文管理指标（面试向：可量化的压缩比/窗口大小/锚点召回）
    # ------------------------------------------------------------------

    def get_context_stats(self, session_key: str = "default") -> dict[str, Any]:
        """计算上下文管理指标（从现有数据，无副作用）."""
        cur = self._conn.cursor()

        # 1. 历史总条数
        cur.execute(
            "SELECT COUNT(*) FROM history WHERE session_key = ?", (session_key,)
        )
        total_history_rows = cur.fetchone()[0]
        # 实际窗口：LLM 最多看到 20 merged turns
        window_size = min(total_history_rows, 20)

        # 2. system prompt 估算（SOUL.md + 静态规则）
        soul = self.read_soul()
        # AgentLoop._STYLE_RULES ≈ 400 chars, _FEWSHOT ≈ 250 chars
        system_prompt_chars = len(soul) + 400 + 250

        # 3. 本轮锚点召回数（从最新 trace 的 ANCHOR_RECALL 步骤提取）
        anchor_recall_count = 0
        traces = self.get_agent_traces(session_key, limit=1)
        if traces:
            for step in traces[0].get("steps", []):
                if step.get("step_name") == "ANCHOR_RECALL":
                    detail = step.get("detail", "")
                    if "hits=" in detail:
                        try:
                            anchor_recall_count = int(
                                detail.split("hits=")[1].split(",")[0]
                            )
                        except (ValueError, IndexError):
                            anchor_recall_count = 0
                    break

        # 4. 锚点存储总数
        cur.execute(
            "SELECT COUNT(*) FROM emotion_anchors WHERE session_key = ?",
            (session_key,),
        )
        anchor_store_count = cur.fetchone()[0]

        # 5. MEMORY.md 大小
        memory_md = self.read_memory()
        memory_md_chars = len(memory_md)

        # 6. 压缩比：存储条数 / 窗口大小（>1 表示有压缩）
        compression_ratio = round(total_history_rows / max(window_size, 1), 2)

        return {
            "window_size": window_size,
            "total_history_rows": total_history_rows,
            "system_prompt_chars_approx": system_prompt_chars,
            "anchor_recall_count": anchor_recall_count,
            "anchor_store_count": anchor_store_count,
            "memory_md_chars": memory_md_chars,
            "compression_ratio": compression_ratio,
        }

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
