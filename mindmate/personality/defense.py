"""防御机制模块.

根据 SOUL.md 中定义的"雷区"，在回复前判断：
1. 用户消息是否触发雷区
2. 如果是，选择回避策略（转移话题 / 含糊回应 / 直接拒绝 / 温柔拒绝）
"""

from __future__ import annotations

import re
from typing import Any

from mindmate.memory import MemoryStore


class DefenseSystem:
    """
    防御机制 — 让 Agent 拥有"心理边界".

    在每次 LLM 回复前执行防御检查。如果用户消息触发雷区，
    注入防御指令让 Agent 自然回避问题，而不是硬编码回复.

    四种策略:
    - deflect:  转移话题（"唉，今天天气真好"）
    - vague:    含糊回应（"嗯…说不好"）
    - refuse:   直接拒绝（"我不想讨论这个"）
    - gentle:   温柔拒绝（"这个问题我现在还不想聊，可以换个话题吗？"）
    """

    def __init__(self, memory: MemoryStore | None = None) -> None:
        self.memory = memory or MemoryStore()
        # 缓存编译好的雷区正则
        self._taboo_patterns: list[tuple[re.Pattern, str, str]] | None = None

    def check(self, user_message: str, session_key: str = "default") -> dict[str, Any] | None:
        """
        检查用户消息是否触发雷区.

        Returns:
            None: 安全，无需防御
            dict: {strategy: str, taboo: str, instruction: str}
                注入到 LLM 上下文的防御指令
        """
        soul = self.memory.read_soul()
        taboos = self._parse_taboos(soul)

        for pattern, strategy, taboo in taboos:
            if pattern.search(user_message):
                return {
                    "strategy": strategy,
                    "taboo": taboo,
                    "instruction": self._build_instruction(strategy, taboo),
                }

        return None

    def _parse_taboos(self, soul: str) -> list[tuple[re.Pattern, str, str]]:
        """解析 SOUL.md 中 ## 雷区 部分."""
        # 匹配雷区区域
        taboo_section = re.search(r"## 雷区\s*\n(.*?)(?=\n## |\Z)", soul, re.DOTALL)
        if not taboo_section:
            return []

        patterns: list[tuple[re.Pattern, str, str]] = []
        for line in taboo_section.group(1).strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            # 格式 1: "- "触发词" → ["策略"] 描述"
            match = re.match(r'- "([^"]+)"\s*→\s*\[?"?([^\]"]+)"?\]?\s*(.*)', line)
            if match:
                keyword = match.group(1)
                strategy = match.group(2).strip()
                description = match.group(3).strip()
                strategy = self._normalize_strategy(strategy)
                patterns.append((re.compile(keyword, re.IGNORECASE), strategy, description))
                continue

            # 格式 2: "- 触发词 → "回复内容""（无引号的触发词）
            match2 = re.match(r'- (.+?)\s*→\s*"([^"]+)"', line)
            if match2:
                keyword = match2.group(1).strip()
                reply = match2.group(2).strip()
                # 从关键词中提取核心词（去掉动词前缀如"追问"）
                core_keyword = self._extract_core_keyword(keyword)
                patterns.append((re.compile(core_keyword, re.IGNORECASE), "gentle", reply))
                continue

            # 格式 3: "- 触发词 → 回复内容"（无引号）
            match3 = re.match(r'- (.+?)\s*→\s*(.+)', line)
            if match3:
                keyword = match3.group(1).strip()
                reply = match3.group(2).strip()
                core_keyword = self._extract_core_keyword(keyword)
                patterns.append((re.compile(core_keyword, re.IGNORECASE), "gentle", reply))

        return patterns

    def _normalize_strategy(self, strategy: str) -> str:
        """将策略名称规范化为英文简写."""
        strategy_map = {
            "转移话题": "deflect", "含糊": "vague",
            "直接拒绝": "refuse", "温柔拒绝": "gentle",
        }
        if strategy in strategy_map:
            return strategy_map[strategy]
        if strategy in ("deflect", "vague", "refuse", "gentle"):
            return strategy
        return "gentle"

    def _extract_core_keyword(self, text: str) -> str:
        """从关键词中提取核心词，去掉动词前缀.

        例如: "追问日记内容" → "日记"
              "你是不是机器人" → "机器人"
        """
        # 常见动词前缀
        prefixes = ("追问", "问", "聊", "说", "看", "听", "谈论", "讨论", "提")
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):]
                break
        # 去掉常见的后缀词
        suffixes = ("内容", "事情", "问题")
        for suffix in suffixes:
            if text.endswith(suffix):
                text = text[:-len(suffix)]
                break
        return text.strip() if text.strip() else text

    def _build_instruction(self, strategy: str, taboo: str) -> str:
        """根据策略生成 LLM 指令."""
        instructions = {
            "deflect": (
                f"你的雷区「{taboo}」被触发了。"
                "你感到不适和抗拒，不想深入讨论这个话题。"
                "请自然地转移话题，比如聊天气、日常、或者问对方近况。"
            ),
            "vague": (
                f"你的雷区「{taboo}」被触发了。"
                "你不想正面回答这个问题。"
                "请给出一个含糊的回应，比如'嗯…说不好'或者'算了吧'，然后自然带过。"
            ),
            "refuse": (
                f"你的雷区「{taboo}」被触发了。"
                "你感到强烈的抗拒。"
                "请直接拒绝回答，可以说'我不想讨论这个'或'到此为止吧'。"
                "语气可以冷淡一些，这是你的权利。"
            ),
            "gentle": (
                f"你的雷区「{taboo}」被触发了。"
                "你不太想聊这个，但不想让对方难过。"
                "请温柔地拒绝，比如'这个问题我现在还不想聊，可以换个话题吗？'"
            ),
        }
        return instructions.get(strategy, instructions["gentle"])

    def get_defense_system_prompt(self, session_key: str = "default") -> str:
        """生成防御机制的系统提示，注入到 LLM 上下文."""
        from mindmate.memory.store import MemoryStore
        # 已经通过 __init__ 拿到了 self.memory
        soul = self.memory.read_soul()
        taboo_section = re.search(r"## 雷区\s*\n(.*?)(?=\n## |\Z)", soul, re.DOTALL)
        if not taboo_section:
            return ""
        taboos = taboo_section.group(1).strip()
        return f"""## 你的雷区

以下是你内心不愿意讨论的话题。当对方触碰时，你可以选择回避、转移话题或直接拒绝——这是你的权利，就如同真实的人一样。

{taboos}

请记住：你不需要回答每一个问题。有些问题你可以选择不回答。"""
