"""人格系统 — 人格核心 + 防御机制 + 关系演进 + 情绪锚点 + 记忆整合."""

from .defense import DefenseSystem
from .emotion_anchor import EmotionAnchorManager
from .memory_consolidator import MemoryConsolidator
from .relationship import RelationshipManager
from .soul import SoulManager

__all__ = [
    "SoulManager",
    "DefenseSystem",
    "RelationshipManager",
    "EmotionAnchorManager",
    "MemoryConsolidator",
]
