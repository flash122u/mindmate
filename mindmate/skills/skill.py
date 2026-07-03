"""陪伴场景 Skill 系统 — 声明式提示注入机制.

借鉴 MindBridge skills.py 的架构模式，但定位为"陪伴场景包"而非临床诊疗流程：
- 每个 SKILL.md 是小暖面对特定情绪场景的共情指南
- 基于关键词子串匹配动态选中
- 注入到 LLM 系统提示中，引导小暖的陪伴风格
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

# ---------------------------------------------------------------------------
# 数据类型
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CompanionSkill:
    """一个陪伴场景 Skill."""

    name: str              # "loneliness"
    description: str       # "用户表达孤独/寂寞/没人陪时激活"
    body: str              # SKILL.md frontmatter 后的 Markdown 正文
    path: Path             # 源文件路径
    keywords: list[str]    # 触发关键词列表
    metadata: dict[str, str] = field(default_factory=dict)

    def prompt_context(self) -> str:
        """格式化为注入系统提示的文本块."""
        return f"## 陪伴指引：{self.name}\n{self.body.strip()}"

    def validation_issues(self) -> list[dict[str, str]]:
        """验证 Skill 完整性，返回问题列表."""
        issues: list[dict[str, str]] = []
        if self.path.parent.name != self.name:
            issues.append({
                "level": "WARN",
                "message": f"目录名 '{self.path.parent.name}' 与 name '{self.name}' 不一致",
            })
        if "小暖该怎么做" not in self.body:
            issues.append({
                "level": "WARN",
                "message": "缺少「## 小暖该怎么做」节",
            })
        if "避免" not in self.body:
            issues.append({
                "level": "WARN",
                "message": "缺少「## 避免」节",
            })
        if len(self.description) < 10:
            issues.append({
                "level": "WARN",
                "message": f"description 过短 ({len(self.description)} 字)",
            })
        if not self.keywords:
            issues.append({
                "level": "WARN",
                "message": "keywords 为空，Skill 永远不会被选中",
            })
        return issues


class SkillLoadError(RuntimeError):
    """Skill 加载失败."""
    pass


# ---------------------------------------------------------------------------
# Frontmatter 解析
# ---------------------------------------------------------------------------

def _split_frontmatter(text: str, path: Path) -> tuple[dict[str, str], str, list[str]]:
    """解析 SKILL.md 的 YAML-style frontmatter.

    Returns:
        (metadata, body, keywords) — metadata 键值对，body 正文，keywords 触发词列表
    """
    if not text.startswith("---\n"):
        raise SkillLoadError(f"{path} 缺少 YAML frontmatter")
    end = text.find("\n---", 4)
    if end == -1:
        raise SkillLoadError(f"{path} frontmatter 未闭合")
    # 解析 metadata
    metadata: dict[str, str] = {}
    keywords: list[str] = []
    in_keywords = False
    for line in text[4:end].splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "keywords:":
            in_keywords = True
            continue
        if in_keywords and stripped.startswith("- "):
            kw = stripped[2:].strip().strip("\"'")
            if kw:
                keywords.append(kw)
            continue
        in_keywords = False
        if ":" not in stripped:
            raise SkillLoadError(f"{path} 无效 frontmatter 行: {line}")
        key, value = stripped.split(":", 1)
        metadata[key.strip()] = value.strip().strip("\"'")
    body = text[end + len("\n---"):].strip()
    return metadata, body, keywords


# ---------------------------------------------------------------------------
# SkillRegistry — 文件系统发现 + 加载
# ---------------------------------------------------------------------------

def _default_skills_root() -> Path:
    """默认 skills/ 目录：项目根下的 skills/."""
    return Path(__file__).resolve().parents[2] / "skills"


class SkillRegistry:
    """从文件系统加载 SKILL.md 文件."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or _default_skills_root()

    def list_skills(self) -> list[CompanionSkill]:
        """加载所有 Skill（按文件名排序）."""
        if not self.root.exists():
            logger.info("SkillRegistry: skills dir not found ({})", self.root)
            return []
        skills: list[CompanionSkill] = []
        for skill_file in sorted(self.root.glob("*/SKILL.md")):
            try:
                skills.append(self._load_skill_file(skill_file))
            except SkillLoadError as e:
                logger.warning("SkillRegistry: skip {} — {}", skill_file, e)
        return skills

    def status_items(self) -> list[dict]:
        """Dashboard 用的状态列表."""
        items: list[dict] = []
        if not self.root.exists():
            return items
        for skill_file in sorted(self.root.glob("*/SKILL.md")):
            try:
                skill = self._load_skill_file(skill_file)
                issues = skill.validation_issues()
                has_error = any(i["level"] == "ERROR" for i in issues)
                status = "FAILED" if has_error else ("WARN" if issues else "READY")
                items.append({
                    "name": skill.name,
                    "status": status,
                    "description": skill.description,
                    "keywords": skill.keywords,
                    "issues": issues,
                })
            except SkillLoadError as e:
                items.append({
                    "name": skill_file.parent.name,
                    "status": "FAILED",
                    "description": "",
                    "keywords": [],
                    "issues": [{"level": "ERROR", "message": str(e)}],
                })
        return items

    def get_required(self, name: str) -> CompanionSkill:
        """按名称查找 Skill，找不到则抛 SkillLoadError."""
        # 先尝试精确路径
        direct = self.root / name / "SKILL.md"
        if direct.exists():
            return self._load_skill_file(direct)
        # 扫描所有 Skill
        for skill in self.list_skills():
            if skill.name == name:
                return skill
        raise SkillLoadError(f"Skill '{name}' 未找到")

    def _load_skill_file(self, path: Path) -> CompanionSkill:
        """从 SKILL.md 文件加载单个 Skill."""
        text = path.read_text(encoding="utf-8")
        metadata, body, keywords = _split_frontmatter(text, path)
        name = metadata.get("name") or path.parent.name
        description = metadata.get("description", "")
        if not name.strip():
            raise SkillLoadError(f"{path} 缺少 name")
        if not description.strip():
            raise SkillLoadError(f"{path} 缺少 description")
        if not body.strip():
            raise SkillLoadError(f"{path} 缺少正文")
        return CompanionSkill(
            name=name.strip(),
            description=description.strip(),
            body=body.strip(),
            path=path,
            keywords=keywords,
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# SkillLibrary — 选择 + 格式化
# ---------------------------------------------------------------------------

def _contains_any(text: str, terms: list[str]) -> bool:
    """子串匹配，任一 term 命中即返回 True."""
    return any(term in text for term in terms)


class SkillLibrary:
    """Skill 选择与格式化 — 面向 AgentLoop 的主要 API."""

    _registry: SkillRegistry | None = None

    @classmethod
    def registry(cls) -> SkillRegistry:
        """获取共享的 SkillRegistry（懒加载）."""
        if cls._registry is None:
            cls._registry = SkillRegistry()
        return cls._registry

    @classmethod
    def reset_registry(cls) -> None:
        """重置 registry（测试用）."""
        cls._registry = None

    @staticmethod
    def select_skill_names(text: str, intent: str = "chat") -> list[str]:
        """根据用户消息选择匹配的 Skill 名称列表.

        chat 意图 → 关键词匹配
        其他意图 → 空列表（走快速路径，不注入 Skill）
        """
        if intent != "chat":
            return []

        registry = SkillLibrary.registry()
        skills = registry.list_skills()
        if not skills:
            return []

        selected: list[str] = []
        for skill in skills:
            if not skill.keywords:
                continue
            if _contains_any(text, skill.keywords):
                selected.append(skill.name)
        return selected

    @staticmethod
    def build_skill_context(text: str, intent: str = "chat") -> str:
        """构建注入到系统提示的 Skill 上下文字符串.

        chat 意图 → 选中 Skill → 格式化为提示块
        其他意图 / 无匹配 → 空字符串
        """
        names = SkillLibrary.select_skill_names(text, intent)
        if not names:
            return ""
        registry = SkillLibrary.registry()
        blocks: list[str] = []
        for name in names:
            try:
                skill = registry.get_required(name)
                blocks.append(skill.prompt_context())
            except SkillLoadError:
                logger.warning("SkillLibrary: selected skill '{}' 加载失败", name)
        return "\n\n".join(blocks)
