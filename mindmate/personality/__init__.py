"""人格系统 — 人格核心 + 防御机制 + 关系演进 + 情绪锚点 + 子Agent."""

from .defense import DefenseSystem
from .diary import DiaryAgent
from .dream import DreamAgent
from .emotion_anchor import EmotionAnchorManager
from .forget import ForgetAgent
from .memory_consolidator import MemoryConsolidator
from .relationship import RelationshipManager
from .soul import SoulManager

__all__ = [
    "SoulManager",
    "DefenseSystem",
    "RelationshipManager",
    "EmotionAnchorManager",
    "MemoryConsolidator",
    "DiaryAgent",
    "DreamAgent",
    "ForgetAgent",
]
