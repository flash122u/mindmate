"""人格核心管理 — SOUL.md 读写 + 人格上下文构建."""

from __future__ import annotations

from mindmate.memory import MemoryStore


class SoulManager:
    """
    人格管理器 — 读取和维护 SOUL.md.

    SOUL.md 包含：
    - 基本信息（名字、性格、背景）
    - 雷区（不可触碰的话题）
    - 关系记忆（当前关系阶段）
    - 日常故事线（Diary Agent 产出）
    """

    def __init__(self, memory: MemoryStore | None = None) -> None:
        self.memory = memory or MemoryStore()

    def get_system_prompt(self) -> str:
        """生成系统提示词，注入人格信息."""
        soul = self.memory.read_soul()
        return f"""你是一个温暖的心理陪伴者。

{soul}

请始终以这个角色进行对话。回复要简短自然，像朋友聊天，不要长篇大论。"""

    def update_soul(self, section: str, content: str) -> None:
        """更新 SOUL.md 的某个 section."""
        current = self.memory.read_soul()
        # 简单追加/替换逻辑
        marker = f"## {section}\n"
        if marker in current:
            idx = current.index(marker)
            rest = current[idx + len(marker):]
            end = current.index("\n## ", idx + len(marker)) if "\n## " in rest else len(current)
            new_soul = current[:idx + len(marker)] + content + "\n" + current[end:]
        else:
            new_soul = current + f"\n## {section}\n{content}\n"
        self.memory.write_soul(new_soul)
